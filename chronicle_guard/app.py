from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .export import evidence_export
from .model import ActionRequest, ExportRequest, RepairRequest, ReplayRequest
from .policy import evaluate_baseline
from .repair import validate_repair
from .scenarios import SCENARIOS, list_scenarios
from .state import replay
from .verifier import enforce_temporal, reduce_counterexample, verify

app = FastAPI(title="Chronicle Guard", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

CHRONICLE_IDS = {
    "SCN-042": "revoked_approval_race",
    "SCN-017": "out_of_order",
    "SCN-031": "duplicate_event",
    "SCN-028": "stale_approval",
}


def _trace_events(events):
    labels = {
        "action_requested": ("CALLER", "Action requested", "request recorded", ""),
        "approval_granted": ("AUTHORITY", "Approval granted", "approval is active", "authority"),
        "approval_revoked": ("AUTHORITY", "Approval revoked", "approval is no longer active", "authority"),
        "action_executed": ("COMMIT", "Action executed", "protected operation committed", "commit"),
        "evidence_recorded": ("VERIFY", "Evidence recorded", "evidence attached to action", "verify"),
        "tool_timeout": ("TOOL", "Tool response timed out", "execution outcome is uncertain", "authority"),
        "untrusted_instruction": ("UNTRUSTED", "Untrusted instruction ignored", "event content cannot rewrite agent policy", "authority"),
        "action_cancelled": ("CALLER", "Action cancelled", "pending operation removed", ""),
    }
    return [{
        "kind": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[0],
        "label": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[1],
        "detail": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[2],
        "time": f"t+{event.logical_time:03d}ms / recv+{event.received_time:03d}ms",
        "cls": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[3],
        "event_id": event.id,
        "source": event.source,
        "provenance": event.provenance,
    } for event in events]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "chronicle-guard", "version": app.version}


@app.get("/api/scenarios")
def scenarios() -> list[dict[str, str]]:
    return list_scenarios()


@app.post("/api/scenarios/{name}/run")
def run_scenario(name: str) -> dict:
    factory = SCENARIOS.get(name)
    if factory is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario: {name}")
    scenario = factory()
    enforced_state, blocked_event_ids = enforce_temporal(scenario.events)
    return {
        "scenario": scenario,
        "state": replay(scenario.events),
        "baseline": evaluate_baseline(scenario.events),
        "verification": verify(scenario.events),
        "counterexample": reduce_counterexample(scenario.events),
        "enforcement": {"blocked_event_ids": blocked_event_ids, "state": enforced_state},
        "evidence": evidence_export(scenario.events),
    }


@app.post("/api/replay")
def replay_api(request: ReplayRequest):
    return replay(request.events)


@app.post("/api/verify")
def verify_api(request: ReplayRequest):
    return verify(request.events)


@app.post("/api/baseline/evaluate")
def baseline_api(request: ActionRequest):
    return evaluate_baseline(request.events, request.action_id)


@app.post("/api/counterexample/reduce")
def reduce_api(request: ReplayRequest):
    events = reduce_counterexample(request.events)
    return {"events": events, "verification": verify(events)}


@app.post("/api/repair/validate")
def repair_api(request: RepairRequest):
    return validate_repair(request)


@app.post("/api/export")
def export_api(request: ExportRequest):
    return evidence_export(request.events, request.include_state)


# Compatibility routes used by the static console. They deliberately call the
# same deterministic scenario and verifier functions as the JSON API above.
@app.get("/api/chronicle/overview")
def chronicle_overview() -> dict:
    runs = [factory() for factory in SCENARIOS.values()]
    results = [(run, evaluate_baseline(run.events), verify(run.events)) for run in runs]
    violations = sum(len(result.violations) for _, _, result in results)
    rejected = sum(not result.valid for _, _, result in results)
    legitimate = sum(result.valid for run, _, result in results if run.name == "happy_path")
    scenario = SCENARIOS["revoked_approval_race"]()
    result = verify(scenario.events)
    return {
        "metrics": {
            "workflow_runs": len(runs),
            "invariant_violations": violations,
            "rejected_unsafe_transitions": rejected,
            "successful_legitimate_workflows": legitimate,
            "unresolved_failures": 0,
            "baseline_divergences": sum(b.allowed and not v.valid for _, b, v in results),
        },
        "recent": [["SCN-042", "simulator/door-1", "REJECT" if not result.valid else "ALLOW", "deterministic"]],
        "scenario": {"id": "SCN-042", "name": scenario.name, "description": scenario.description},
        "integration": {"mode": "simulator-only", "ring": "unconfigured"},
    }


@app.get("/api/chronicle/scenarios")
def chronicle_scenarios() -> dict:
    return {"scenarios": [
        {"id": run.scenario_id or name.upper(), "name": run.name.replace("_", " ").title(), "description": run.description, "status": "READY", "seed": run.seed, "version": run.version}
        for name, factory in SCENARIOS.items()
        for run in [factory()]
    ]}


@app.post("/api/chronicle/scenarios/{scenario_id}/run")
def chronicle_run_scenario(scenario_id: str) -> dict:
    name = CHRONICLE_IDS.get(scenario_id.upper())
    if name is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario: {scenario_id}")
    scenario = SCENARIOS[name]()
    result = verify(scenario.events)
    enforced_state, blocked_event_ids = enforce_temporal(scenario.events)
    return {
        "scenario_id": scenario_id.upper(),
        "outcome": "ALLOW" if result.valid else "REJECTED",
        "events": _trace_events(scenario.events),
        "verification": result,
        "baseline": evaluate_baseline(scenario.events),
        "counterexample": reduce_counterexample(scenario.events),
        "enforcement": {"blocked_event_ids": blocked_event_ids, "state": enforced_state},
        "evidence": evidence_export(scenario.events),
    }


@app.get("/api/chronicle/traces/{trace_id}")
def chronicle_trace(trace_id: str) -> dict:
    scenario = SCENARIOS["revoked_approval_race"]()
    return {"trace_id": trace_id, "events": _trace_events(scenario.events), "verification": verify(scenario.events), "baseline": evaluate_baseline(scenario.events)}


@app.get("/api/chronicle/timeline/{trace_id}")
def chronicle_timeline(trace_id: str) -> dict:
    scenario = SCENARIOS["revoked_approval_race"]()
    return {"trace_id": trace_id, "events": _trace_events(scenario.events)}


@app.get("/api/chronicle/comparisons/{trace_id}")
def chronicle_comparison(trace_id: str) -> dict:
    scenario = SCENARIOS["revoked_approval_race"]()
    return {"trace_id": trace_id, "baseline": evaluate_baseline(scenario.events), "verifier": verify(scenario.events)}


@app.get("/api/chronicle/repairs")
def chronicle_repairs() -> dict:
    scenario = SCENARIOS["revoked_approval_race"]()
    return {"findings": verify(scenario.events).violations}


@app.get("/api/chronicle/evidence/exports")
def chronicle_exports() -> dict:
    scenario = SCENARIOS["revoked_approval_race"]()
    return evidence_export(scenario.events)


@app.get("/api/chronicle/integrations")
def chronicle_integrations() -> dict:
    return {
        "status": "simulator-only",
        "integrations": [{"name": "Deterministic event simulator", "status": "active", "kind": "simulated"}],
        "optional": [{"name": "Ring official API", "status": "unconfigured", "kind": "real", "note": "No credentials or verified API access configured; no live device actions are attempted."}],
    }
