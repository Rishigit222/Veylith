from fastapi.testclient import TestClient

import chronicle_guard.app as app_module
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


def test_demo_login_and_me(monkeypatch):
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_EMAIL", "reviewer@example.com")
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_PASSWORD", "demo-password")
    login = client.post("/api/auth/login", json={"email": "reviewer@example.com", "password": "demo-password"})
    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "reviewer"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == body["user"]


def test_auth_failure_returns_401(monkeypatch):
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_EMAIL", "reviewer@example.com")
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_PASSWORD", "demo-password")
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    finding_id = client.get("/api/chronicle/repairs").json()["findings"][0]["finding_id"]
    response = client.post(f"/api/chronicle/repairs/{finding_id}/decision", json={"decision": "approve"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_client_records_come_from_scenarios_verifier_and_evidence():
    runs = client.get("/api/chronicle/agent-runs")
    notifications = client.get("/api/chronicle/notifications")
    repairs = client.get("/api/chronicle/repairs")
    assert runs.status_code == notifications.status_code == repairs.status_code == 200
    run = next(item for item in runs.json()["runs"] if item["scenario_id"] == "SCN-042")
    assert run["outcome"] == "REJECTED"
    assert "revoked_approval_race" in run["violation_codes"]
    assert run["evidence_format"] == "chronicle-guard-evidence-v1"
    assert any(item["finding_id"].startswith("SCN-042:") and item["code"] == "revoked_approval_race" for item in repairs.json()["findings"])
    assert any(item["scenario_id"] == "SCN-042" and item["severity"] == "critical" for item in notifications.json()["notifications"])


def test_reviewer_can_approve_or_reject_findings(monkeypatch):
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_EMAIL", "reviewer@example.com")
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_PASSWORD", "demo-password")
    token = client.post("/api/auth/login", json={"email": "reviewer@example.com", "password": "demo-password"}).json()["access_token"]
    findings = client.get("/api/chronicle/repairs").json()["findings"]
    approved_id = findings[0]["finding_id"]
    rejected_id = findings[1]["finding_id"]
    headers = {"Authorization": f"Bearer {token}"}
    approved = client.post(f"/api/chronicle/repairs/{approved_id}/decision", headers=headers, json={"decision": "approve"})
    rejected = client.post(f"/api/chronicle/repairs/{rejected_id}/decision", headers=headers, json={"decision": "reject"})
    assert approved.status_code == rejected.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert rejected.json()["status"] == "REJECTED"
    assert client.get("/api/chronicle/repairs").json()["findings"][0]["status"] == "APPROVED"


def test_valid_non_reviewer_session_returns_403_for_decision(monkeypatch):
    finding_id = client.get("/api/chronicle/repairs").json()["findings"][0]["finding_id"]
    app_module._SESSIONS["viewer-session"] = {"id": "demo-viewer", "email": "viewer@example.com", "name": "Viewer", "role": "viewer"}
    response = client.post(
        f"/api/chronicle/repairs/{finding_id}/decision",
        headers={"Authorization": "Bearer viewer-session"},
        json={"decision": "approve"},
    )
    assert response.status_code == 403


def test_mobile_scenario_ids_are_all_runnable():
    catalog = client.get("/api/chronicle/scenarios").json()["scenarios"]
    assert len(catalog) == 9
    for scenario in catalog:
        response = client.post(f"/api/chronicle/scenarios/{scenario['id']}/run")
        assert response.status_code == 200


def test_health_identifies_veylith_service():
    health = client.get("/health").json()
    assert health["service"] == "veylith"
    assert health["status"] == "ok"
