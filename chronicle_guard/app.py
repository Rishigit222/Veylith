from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from .export import evidence_export
from .model import ActionRequest, ExportRequest, LoginRequest, RepairDecisionRequest, RepairRequest, ReplayRequest
from .policy import evaluate_baseline
from .repair import validate_repair
from .ring import RingAdapter, RingIntegrationError, ring_status
from .scenarios import SCENARIOS, list_scenarios
from .state import replay
from .storage import get_repair_decision, save_repair_decision
from .verifier import enforce_temporal, reduce_counterexample, verify

app = FastAPI(title="Veylith", version="0.3.0")


def _cors_origins() -> list[str]:
    configured = os.getenv("VEYLITH_CORS_ORIGINS", "")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


_ALLOWED_CORS_ORIGINS = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_CORS_ORIGINS,
    allow_credentials=bool(_ALLOWED_CORS_ORIGINS),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)

# This backend intentionally uses a tiny in-memory store for the demo clients.
# It is reset on process restart and is not a production identity or database.
_SESSIONS: dict[str, dict[str, str]] = {}
_BEARER = HTTPBearer(auto_error=False)
_RING_TEST_STATE: dict[str, Any] = {
    "last_test_at": None,
    "last_success": None,
    "last_error_code": None,
    "last_error": None,
    "device_count": None,
    "verified_operations": {"device_discovery": False, "event_history": False, "whep_session_creation": False},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ring_status() -> dict[str, Any]:
    return ring_status(**_RING_TEST_STATE)


def _record_ring_success(operation: str, *, device_count: int | None = None) -> None:
    _RING_TEST_STATE.update({"last_test_at": _now_iso(), "last_success": True, "last_error_code": None, "last_error": None})
    _RING_TEST_STATE["verified_operations"][operation] = True
    if device_count is not None:
        _RING_TEST_STATE["device_count"] = device_count


def _record_ring_error(error: RingIntegrationError) -> None:
    _RING_TEST_STATE.update({"last_test_at": _now_iso(), "last_success": False, "last_error_code": error.code, "last_error": str(error), "device_count": None})

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

CHRONICLE_IDS = {
    "SCN-001": "happy_path",
    "SCN-042": "revoked_approval_race",
    "SCN-017": "out_of_order",
    "SCN-031": "duplicate_event",
    "SCN-028": "stale_approval",
    "SCN-007": "execute_without_approval",
    "SCN-019": "stale_evidence",
    "SCN-023": "network_timeout",
    "SCN-029": "untrusted_instruction",
}
TRACE_ALIASES = {"trace-7f3a": "SCN-042"}


def _scenario_for_trace(trace_id: str):
    normalized = trace_id.strip()
    scenario_id = TRACE_ALIASES.get(normalized.lower(), normalized.upper())
    name = CHRONICLE_IDS.get(scenario_id)
    if name is None and normalized in SCENARIOS:
        name = normalized
    if name is None:
        raise HTTPException(status_code=404, detail=f"unknown trace: {trace_id}")
    return scenario_id, SCENARIOS[name]()


def _trace_events(events, verification=None):
    labels = {
        "action_requested": ("CALLER", "Action requested", "request recorded", ""),
        "approval_granted": ("AUTHORITY", "Approval granted", "approval is active", "authority"),
        "approval_revoked": ("AUTHORITY", "Approval revoked", "approval is no longer active", "authority"),
        "action_executed": ("COMMIT", "Action executed", "protected operation committed", "commit"),
        "evidence_recorded": ("VERIFY", "Evidence recorded", "evidence attached to action", "verify"),
        "tool_timeout": ("TOOL", "Tool response timed out", "execution outcome is uncertain", "authority"),
        "untrusted_instruction": ("UNTRUSTED", "Untrusted instruction ignored", "event content cannot rewrite agent policy", "authority"),
        "action_cancelled": ("CALLER", "Action cancelled", "pending operation removed", ""),
        "ring_event": ("RING", "Ring event observed", "external Ring-originated fact; not a synthetic scenario event", "authority"),
    }
    violations_by_event: dict[str, list[str]] = {}
    if verification is not None:
        for violation in verification.violations:
            if violation.event_id:
                violations_by_event.setdefault(violation.event_id, []).append(violation.code)
    return [{
        "kind": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[0],
        "label": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[1],
        "detail": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[2],
        "time": f"t+{event.logical_time:03d}ms / recv+{event.received_time:03d}ms",
        "cls": labels.get(event.kind.value, ("EVENT", event.kind.value, "event observed", ""))[3],
        "event_id": event.id,
        "event_kind": event.kind.value,
        "logical_time": event.logical_time,
        "received_time": event.received_time,
        "actor": event.actor,
        "action_id": event.action_id,
        "workflow_id": event.workflow_id,
        "source": event.source,
        "provenance": event.provenance,
        "violation_codes": violations_by_event.get(event.id, []),
    } for event in events]


def _reviewer_credentials() -> tuple[str, str]:
    email = os.getenv("CHRONICLE_DEMO_REVIEWER_EMAIL", "").strip()
    password = os.getenv("CHRONICLE_DEMO_REVIEWER_PASSWORD", "")
    return email, password


def _demo_auth_allowed() -> bool:
    environment = os.getenv("VEYLITH_ENV", "development").strip().lower()
    if environment != "production":
        return True
    return os.getenv("VEYLITH_ALLOW_DEMO_AUTH", "false").strip().lower() == "true"


def _auth_error(detail: str = "Bearer authentication is required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def _current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_BEARER)]) -> dict[str, str]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _auth_error()
    user = _SESSIONS.get(credentials.credentials)
    if user is None:
        raise _auth_error("Invalid or expired demo session")
    return user


def _reviewer_user(user: Annotated[dict[str, str], Depends(_current_user)]) -> dict[str, str]:
    if user.get("role") != "reviewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required")
    return user


def _scenario_records() -> list[dict[str, Any]]:
    """Build client records from the actual deterministic verifier outputs."""
    records: list[dict[str, Any]] = []
    for name, factory in SCENARIOS.items():
        scenario = factory()
        verification = verify(scenario.events)
        evidence = evidence_export(scenario.events)
        scenario_id = scenario.scenario_id or name.upper()
        violations = [violation.model_dump(mode="json") for violation in verification.violations]
        final_hash = evidence["hash_chain"][-1]["hash"] if evidence["hash_chain"] else None
        logical_times = [event.logical_time for event in scenario.events]
        records.append({
            "scenario": scenario,
            "scenario_id": scenario_id,
            "verification": verification,
            "evidence": evidence,
            "violations": violations,
            "event_times": {event.id: event.logical_time for event in scenario.events},
            "run": {
                "id": scenario_id,
                "run_id": scenario_id,
                "scenario_id": scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "status": "completed",
                "outcome": "ALLOW" if verification.valid else "REJECTED",
                "started_at": f"t+{min(logical_times, default=0):03d}ms",
                "completed_at": f"t+{max(logical_times, default=0):03d}ms",
                "event_count": evidence["event_count"],
                "event_ids": verification.checked_event_ids,
                "violation_count": len(verification.violations),
                "violation_codes": [violation.code for violation in verification.violations],
                "verifier_version": verification.verifier_version,
                "evidence_format": evidence["format"],
                "evidence_hash": final_hash,
                "summary": (
                    f"Verifier accepted {evidence['event_count']} events."
                    if verification.valid
                    else f"Verifier rejected the stream: {', '.join(violation.code for violation in verification.violations)}."
                ),
            },
        })
    return records


def _scenario_response(scenario_id: str, scenario) -> dict[str, Any]:
    """Return one canonical, self-describing replay response for every client."""
    verification = verify(scenario.events)
    baseline = evaluate_baseline(scenario.events)
    enforced_state, blocked_event_ids = enforce_temporal(scenario.events)
    evidence = evidence_export(scenario.events)
    return {
        "scenario_id": scenario_id,
        "scenario": {
            "id": scenario_id,
            "name": scenario.name,
            "display_name": scenario.name.replace("_", " ").title(),
            "description": scenario.description,
            "version": scenario.version,
            "seed": scenario.seed,
            "policy_version": scenario.policy_version,
            "event_count": len(scenario.events),
            "event_ids": [event.id for event in scenario.events],
            "events": [event.model_dump(mode="json") for event in scenario.events],
        },
        "outcome": "ALLOW" if verification.valid else "REJECTED",
        "state": replay(scenario.events),
        "events": _trace_events(scenario.events, verification),
        "baseline": baseline,
        "verification": verification,
        "counterexample": reduce_counterexample(scenario.events),
        "enforcement": {"blocked_event_ids": blocked_event_ids, "state": enforced_state},
        "evidence": evidence,
    }


def _repair_records() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for record in _scenario_records():
        for index, violation in enumerate(record["violations"], start=1):
            event_id = violation.get("event_id") or "stream"
            finding_id = f"{record['scenario_id']}:{index}:{violation['code']}:{event_id}"
            decision = get_repair_decision(finding_id)
            findings.append({
                "finding_id": finding_id,
                "scenario_id": record["scenario_id"],
                "scenario_name": record["scenario"].name,
                "code": violation["code"],
                "event_id": violation.get("event_id"),
                "action_id": violation.get("action_id"),
                "message": violation["message"],
                "status": decision["status"] if decision else "PENDING",
                "decision": decision["decision"] if decision else None,
                "decided_by": decision["decided_by"] if decision else None,
                "evidence_format": record["evidence"]["format"],
                "evidence_hash": record["run"]["evidence_hash"],
            })
    return findings


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "veylith", "version": app.version}


@app.post("/api/auth/login")
def login(request: LoginRequest) -> dict[str, Any]:
    if not _demo_auth_allowed():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo authentication is disabled in production; configure a production identity provider before enabling public reviewer actions")
    configured_email, configured_password = _reviewer_credentials()
    if not configured_email or not configured_password:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo reviewer auth is not configured; set CHRONICLE_DEMO_REVIEWER_EMAIL and CHRONICLE_DEMO_REVIEWER_PASSWORD")
    if not (hmac.compare_digest(request.email.strip(), configured_email) and hmac.compare_digest(request.password, configured_password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid demo reviewer credentials", headers={"WWW-Authenticate": "Bearer"})
    token = "demo-" + hashlib.sha256(f"{configured_email}:{configured_password}".encode("utf-8")).hexdigest()
    user = {"id": "demo-reviewer", "email": configured_email, "name": "Chronicle demo reviewer", "role": "reviewer"}
    _SESSIONS[token] = user
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/me")
def me(user: Annotated[dict[str, str], Depends(_current_user)]) -> dict[str, str]:
    return user


@app.get("/api/scenarios")
def scenarios() -> list[dict[str, str]]:
    return list_scenarios()


@app.post("/api/scenarios/{name}/run")
def run_scenario(name: str) -> dict:
    factory = SCENARIOS.get(name)
    if factory is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario: {name}")
    scenario = factory()
    return _scenario_response(scenario.scenario_id or name.upper(), scenario)


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


@app.get("/api/ring/status")
def ring_status_api() -> dict[str, Any]:
    """Return sanitized Ring configuration and last-call status."""
    return _ring_status()


@app.get("/api/ring/device-discovery")
def ring_device_discovery() -> dict[str, Any]:
    """Call Ring's documented Device Discovery operation server-side."""
    adapter = RingAdapter()
    try:
        result = adapter.discover_devices()
    except RingIntegrationError as error:
        _record_ring_error(error)
        raise HTTPException(status_code=503 if error.code == "missing_token" else (error.status_code or 502), detail={"code": error.code, "message": str(error)}) from error
    _record_ring_success("device_discovery", device_count=len(result["data"]))
    return {"status": "success", "source": "ring_api", "response": result, "integration": _ring_status()}


@app.get("/api/ring/devices/{device_id}/event-history")
def ring_event_history(
    device_id: str,
    event_types: list[str] | None = Query(default=None),
    page_key: str | None = Query(default=None, alias="page[key]"),
) -> dict[str, Any]:
    """Call documented Event History and map returned facts into Veylith events."""
    adapter = RingAdapter()
    try:
        result = adapter.event_history(device_id, event_types=event_types, page_key=page_key)
        mapped_events = adapter.history_to_events(result, device_id=device_id)
    except RingIntegrationError as error:
        _record_ring_error(error)
        raise HTTPException(status_code=503 if error.code == "missing_token" else (error.status_code or 502), detail={"code": error.code, "message": str(error)}) from error
    _record_ring_success("event_history")
    return {"status": "success", "source": "ring_api", "response": result, "events": mapped_events, "integration": _ring_status()}


@app.post("/api/ring/devices/{device_id}/whep-session")
def ring_whep_session(
    device_id: str,
    sdp_offer: str = Body(..., media_type="application/sdp"),
    component_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Create a temporary Ring WHEP session; the SDP is never persisted."""
    adapter = RingAdapter()
    try:
        session = adapter.create_whep_session(device_id, sdp_offer, component_id=component_id)
    except RingIntegrationError as error:
        _record_ring_error(error)
        raise HTTPException(status_code=503 if error.code == "missing_token" else (error.status_code or 502), detail={"code": error.code, "message": str(error)}) from error
    _record_ring_success("whep_session_creation")
    return {"status": "success", "source": "ring_api", "session": session, "integration": _ring_status(), "session_persistence": "not_stored"}


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
        "scenario": {
            "id": "SCN-042",
            "name": scenario.name,
            "description": scenario.description,
            "event_count": len(scenario.events),
            "outcome": "ALLOW" if result.valid else "REJECTED",
            "violation_codes": [violation.code for violation in result.violations],
        },
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
    return _scenario_response(scenario_id.upper(), SCENARIOS[name]())


@app.get("/api/chronicle/traces/{trace_id}")
def chronicle_trace(trace_id: str) -> dict:
    scenario_id, scenario = _scenario_for_trace(trace_id)
    response = _scenario_response(scenario_id, scenario)
    return {"trace_id": trace_id, **response}


@app.get("/api/chronicle/timeline/{trace_id}")
def chronicle_timeline(trace_id: str) -> dict:
    scenario_id, scenario = _scenario_for_trace(trace_id)
    response = _scenario_response(scenario_id, scenario)
    return {"trace_id": trace_id, "scenario_id": scenario_id, "events": response["events"]}


@app.get("/api/chronicle/comparisons/{trace_id}")
def chronicle_comparison(trace_id: str) -> dict:
    scenario_id, scenario = _scenario_for_trace(trace_id)
    response = _scenario_response(scenario_id, scenario)
    return {"trace_id": trace_id, "scenario_id": scenario_id, "baseline": response["baseline"], "verifier": response["verification"]}


@app.get("/api/chronicle/repairs")
def chronicle_repairs() -> dict:
    return {"findings": _repair_records()}


@app.get("/api/chronicle/agent-runs")
def chronicle_agent_runs() -> dict:
    return {"runs": [record["run"] for record in _scenario_records()]}


@app.get("/api/chronicle/notifications")
def chronicle_notifications() -> dict:
    notifications: list[dict[str, Any]] = []
    for record in _scenario_records():
        for index, violation in enumerate(record["violations"], start=1):
            event_id = violation.get("event_id") or "stream"
            notifications.append({
                "id": f"notification:{record['scenario_id']}:{index}:{violation['code']}:{event_id}",
                "finding_id": f"{record['scenario_id']}:{index}:{violation['code']}:{event_id}",
                "scenario_id": record["scenario_id"],
                "title": violation["code"].replace("_", " ").title(),
                "message": violation["message"],
                "severity": "critical",
                "read": False,
                "created_at": f"t+{record['event_times'].get(event_id, 0):03d}ms",
            })
    return {"notifications": notifications}


@app.post("/api/chronicle/repairs/{finding_id}/decision")
def chronicle_repair_decision(
    finding_id: str,
    request: RepairDecisionRequest,
    user: Annotated[dict[str, str], Depends(_reviewer_user)],
) -> dict[str, Any]:
    finding = next((item for item in _repair_records() if item["finding_id"] == finding_id), None)
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown finding: {finding_id}")
    decision = {"decision": request.decision, "status": {"approve": "APPROVED", "reject": "REJECTED"}[request.decision], "decided_by": user["id"]}
    saved = save_repair_decision(finding_id, request.decision, decision["status"], user["id"])
    return {**finding, **saved}


@app.get("/api/chronicle/evidence/exports")
def chronicle_exports() -> dict:
    scenario = SCENARIOS["revoked_approval_race"]()
    return evidence_export(scenario.events)


@app.get("/api/chronicle/integrations")
def chronicle_integrations() -> dict:
    return {
        "status": "ring_api_configured" if _ring_status()["configured"] else "simulator-only",
        "integrations": [{"name": "Deterministic event simulator", "status": "active", "kind": "simulated", "source": "synthetic"}],
        "optional": [{"name": "Ring official Partner API", "status": "configured" if _ring_status()["configured"] else "unconfigured", "kind": "real", "source": "ring_api", "note": "Device Discovery, Event History, and WHEP session creation are isolated server-side operations; no token is exposed to clients."}],
        "ring": _ring_status(),
    }
