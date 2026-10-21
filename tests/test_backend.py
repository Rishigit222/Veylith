from fastapi.testclient import TestClient

from chronicle_guard.app import app
from chronicle_guard.model import Event, EventKind, RepairRequest
from chronicle_guard.policy import evaluate_baseline
from chronicle_guard.scenarios import SCENARIOS
from chronicle_guard.state import replay
from chronicle_guard.verifier import enforce_temporal, reduce_counterexample, verify


client = TestClient(app)


def test_state_transitions_and_replay_are_deterministic():
    events = SCENARIOS["happy_path"]().events
    first = replay(events)
    second = replay(events)
    assert first == second
    assert first.actions["door-1"].executed_at == 3
    assert first.approvals["ap-1"].revoked_at is None


def test_revocation_race_is_rejected_independently_of_baseline():
    events = SCENARIOS["revoked_approval_race"]().events
    assert evaluate_baseline(events).allowed is True
    result = verify(events)
    assert result.valid is False
    assert any(v.code == "revoked_approval_race" for v in result.violations)


def test_stale_evidence_and_duplicates_are_detected():
    assert any(v.code == "stale_evidence" for v in verify(SCENARIOS["stale_evidence"]().events).violations)
    duplicate_events = SCENARIOS["duplicate_event"]().events
    assert any(v.code == "duplicate_event" for v in verify(duplicate_events).violations)
    assert replay(duplicate_events).ignored_duplicate_ids == ["e2"]


def test_baseline_and_temporal_verifier_are_independent():
    events = SCENARIOS["duplicate_event"]().events
    assert evaluate_baseline(events).allowed is True
    assert verify(events).valid is False


def test_counterexample_reduction_preserves_failure():
    reduced = reduce_counterexample(SCENARIOS["revoked_approval_race"]().events)
    assert not verify(reduced).valid
    assert any(v.code == "revoked_approval_race" for v in verify(reduced).violations)
    assert len(reduced) < len(SCENARIOS["revoked_approval_race"]().events)


def test_temporal_enforcement_blocks_sensitive_commit_and_preserves_protected_state():
    state, blocked = enforce_temporal(SCENARIOS["revoked_approval_race"]().events)
    assert blocked == ["e4"]
    assert state.actions["door-1"].executed_at is None


def test_repair_validation_drops_bad_execution():
    events = SCENARIOS["execute_without_approval"]().events
    response = client.post("/api/repair/validate", json={"events": [e.model_dump(mode="json") for e in events], "drop_event_ids": ["e2"]})
    assert response.status_code == 200
    body = response.json()
    assert body["valid_repair"] is True


def test_export_and_json_apis():
    events = SCENARIOS["happy_path"]().events
    payload = {"events": [e.model_dump(mode="json") for e in events]}
    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/api/scenarios").json()) >= 6
    assert client.post("/api/replay", json=payload).json()["clock"] == 4
    assert client.post("/api/verify", json=payload).json()["valid"] is True
    exported = client.post("/api/export", json=payload).json()
    assert exported["format"] == "chronicle-guard-evidence-v1"
    assert exported["event_count"] == 4
    assert len(exported["hash_chain"]) == 4
    assert exported["enforcement"]["blocked_event_ids"] == []


def test_extended_adversarial_catalog_is_deterministic_and_typed():
    assert {"network_timeout", "untrusted_instruction"}.issubset(SCENARIOS)
    timeout = SCENARIOS["network_timeout"]()
    assert timeout.seed == 7
    assert timeout.events[0].workflow_id == "wf-demo"
    assert timeout.events[0].logical_time == timeout.events[0].at
    timeout_result = verify(timeout.events)
    assert any(v.code == "duplicate_execution" for v in timeout_result.violations)
    untrusted_result = verify(SCENARIOS["untrusted_instruction"]().events)
    assert any(v.code == "untrusted_instruction" for v in untrusted_result.violations)


def test_overview_reports_actual_catalog_metrics_and_simulator_boundary():
    overview = client.get("/api/chronicle/overview").json()
    assert overview["metrics"]["workflow_runs"] >= 8
    assert overview["metrics"]["baseline_divergences"] >= 1
    integrations = client.get("/api/chronicle/integrations").json()
    assert integrations["status"] == "simulator-only"
    assert integrations["optional"][0]["status"] == "unconfigured"


def test_static_console_compatibility_routes_are_json_backed():
    assert client.get("/").status_code == 200
    catalog = client.get("/api/chronicle/scenarios")
    assert catalog.status_code == 200
    assert any(item["id"] == "SCN-042" for item in catalog.json()["scenarios"])
    run = client.post("/api/chronicle/scenarios/SCN-042/run")
    assert run.status_code == 200
    assert run.json()["outcome"] == "REJECTED"
    assert run.json()["events"][0]["event_id"] == "e1"
