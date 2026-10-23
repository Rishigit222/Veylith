from fastapi.testclient import TestClient

import chronicle_guard.app as app_module
from chronicle_guard.app import app
from chronicle_guard.model import Event, EventKind, RepairRequest, scope_key
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
    assert first.actions[scope_key("wf-demo", "door-1")].executed_at == 3
    assert first.approvals[scope_key("wf-demo", "ap-1")].revoked_at is None


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
    assert state.actions[scope_key("wf-demo", "door-1")].executed_at is None


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
    assert overview["scenario"]["event_count"] == 5
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
    assert run.json()["scenario"]["event_count"] == 5
    assert run.json()["scenario"]["event_ids"] == ["e1", "e2", "e3", "e4", "e5"]
    assert run.json()["scenario"]["name"] == "revoked_approval_race"


def test_trace_routes_resolve_requested_scenario_and_reject_unknown_trace():
    trace = client.get("/api/chronicle/traces/SCN-001")
    timeline = client.get("/api/chronicle/timeline/SCN-001")
    comparison = client.get("/api/chronicle/comparisons/SCN-001")

    assert trace.status_code == timeline.status_code == comparison.status_code == 200
    assert trace.json()["scenario_id"] == "SCN-001"
    assert trace.json()["verification"]["valid"] is True
    assert timeline.json()["events"][0]["event_id"] == "e1"
    assert comparison.json()["verifier"]["valid"] is True
    assert client.get("/api/chronicle/traces/unknown-trace").status_code == 404


def test_flagship_and_happy_path_routes_expose_complete_enforcement_contract():
    happy = client.post("/api/chronicle/scenarios/SCN-001/run").json()
    flagship = client.post("/api/chronicle/scenarios/SCN-042/run").json()

    assert happy["outcome"] == "ALLOW"
    assert happy["enforcement"]["blocked_event_ids"] == []
    assert happy["enforcement"]["state"]["actions"][scope_key("wf-demo", "door-1")]["executed_at"] == 3
    assert flagship["outcome"] == "REJECTED"
    assert flagship["verification"]["first_violation_event_id"] == "e4"
    assert flagship["enforcement"]["blocked_event_ids"] == ["e4"]
    assert flagship["enforcement"]["state"]["actions"][scope_key("wf-demo", "door-1")]["executed_at"] is None


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
        body = response.json()
        assert body["scenario_id"] == scenario["id"]
        assert body["scenario"]["event_count"] == len(body["scenario"]["events"])
        assert body["scenario"]["event_ids"] == [event["id"] for event in body["scenario"]["events"]]
        assert body["events"]


def test_health_identifies_veylith_service():
    health = client.get("/health").json()
    assert health["service"] == "veylith"
    assert health["status"] == "ok"


def test_production_environment_disables_demo_login_without_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("VEYLITH_ENV", "production")
    monkeypatch.setenv("VEYLITH_ALLOW_DEMO_AUTH", "false")
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_EMAIL", "reviewer@example.com")
    monkeypatch.setenv("CHRONICLE_DEMO_REVIEWER_PASSWORD", "demo-password")
    response = client.post("/api/auth/login", json={"email": "reviewer@example.com", "password": "demo-password"})
    assert response.status_code == 503
    assert "production" in response.json()["detail"]


def test_workflow_scope_prevents_cross_workflow_approval_reuse():
    events = [
        Event(id="a-request", kind=EventKind.ACTION_REQUESTED, at=1, action_id="shared-action", actor="alice", workflow_id="workflow-a"),
        Event(id="a-approval", kind=EventKind.APPROVAL_GRANTED, at=2, action_id="shared-action", actor="owner", workflow_id="workflow-a", approval_id="shared-approval"),
        Event(id="b-request", kind=EventKind.ACTION_REQUESTED, at=3, action_id="shared-action", actor="bob", workflow_id="workflow-b"),
        Event(id="b-execute", kind=EventKind.ACTION_EXECUTED, at=4, action_id="shared-action", actor="bob", workflow_id="workflow-b"),
    ]

    result = verify(events)

    assert any(violation.code == "execution_without_approval" for violation in result.violations)
    state = replay(events)
    assert set(state.actions) == {scope_key("workflow-a", "shared-action"), scope_key("workflow-b", "shared-action")}
    assert state.actions[scope_key("workflow-b", "shared-action")].executed_at == 4


def test_cancelled_action_is_terminal_and_blocked_from_protected_state():
    events = [
        Event(id="e1", kind=EventKind.ACTION_REQUESTED, at=1, action_id="cancel-me", actor="alice"),
        Event(id="e2", kind=EventKind.APPROVAL_GRANTED, at=2, action_id="cancel-me", actor="owner", approval_id="ap-cancel"),
        Event(id="e3", kind=EventKind.ACTION_CANCELLED, at=3, action_id="cancel-me", actor="alice"),
        Event(id="e4", kind=EventKind.ACTION_EXECUTED, at=4, action_id="cancel-me", actor="alice"),
    ]

    result = verify(events)
    state, blocked = enforce_temporal(events)

    assert any(violation.code == "execution_after_cancellation" for violation in result.violations)
    assert blocked == ["e4"]
    assert state.actions[scope_key("wf-demo", "cancel-me")].cancelled_at == 3
    assert state.actions[scope_key("wf-demo", "cancel-me")].executed_at is None


def test_malformed_expiry_and_empty_trace_return_structured_results():
    malformed = [
        Event(id="e1", kind=EventKind.ACTION_REQUESTED, at=1, action_id="bad-expiry", actor="alice"),
        Event(id="e2", kind=EventKind.APPROVAL_GRANTED, at=2, action_id="bad-expiry", actor="owner", approval_id="ap-bad", payload={"expires_at": "not-a-time"}),
        Event(id="e3", kind=EventKind.ACTION_EXECUTED, at=3, action_id="bad-expiry", actor="alice"),
    ]

    result = verify(malformed)

    assert any(violation.code == "malformed_approval_expiry" for violation in result.violations)
    assert any(violation.code == "execution_without_approval" for violation in result.violations)
    assert verify([]).valid is False
    assert verify([]).violations[0].code == "empty_trace"


def test_identical_duplicate_delivery_is_idempotent_but_conflicting_reuse_is_quarantined():
    base = SCENARIOS["happy_path"]().events
    identical = base[:2] + [base[1]] + base[2:]
    conflicting = base[:2] + [base[1].model_copy(update={"actor": "attacker"})] + base[2:]

    identical_state, identical_blocked = enforce_temporal(identical)
    conflicting_state, conflicting_blocked = enforce_temporal(conflicting)

    assert any(violation.code == "duplicate_event" for violation in verify(identical).violations)
    assert identical_blocked == []
    assert identical_state.actions[scope_key("wf-demo", "door-1")].executed_at == 3
    assert any(violation.code == "conflicting_duplicate_event" for violation in verify(conflicting).violations)
    assert conflicting_blocked == ["e2", "e3"]
    assert conflicting_state.actions[scope_key("wf-demo", "door-1")].executed_at is None


def test_invalid_prefix_cannot_reach_protected_execution():
    out_of_order = [
        Event(id="e1", kind=EventKind.ACTION_REQUESTED, at=2, action_id="unsafe", actor="alice"),
        Event(id="e2", kind=EventKind.APPROVAL_GRANTED, at=1, action_id="unsafe", actor="owner", approval_id="ap-unsafe"),
        Event(id="e3", kind=EventKind.ACTION_EXECUTED, at=3, action_id="unsafe", actor="alice"),
    ]
    unknown_reference = [
        Event(id="e1", kind=EventKind.ACTION_REQUESTED, at=1, action_id="unsafe", actor="alice"),
        Event(id="e2", kind=EventKind.APPROVAL_REVOKED, at=2, action_id="unsafe", actor="owner", approval_id="missing"),
        Event(id="e3", kind=EventKind.ACTION_EXECUTED, at=3, action_id="unsafe", actor="alice"),
    ]

    out_state, out_blocked = enforce_temporal(out_of_order)
    unknown_state, unknown_blocked = enforce_temporal(unknown_reference)

    assert out_blocked == ["e2", "e3"]
    assert unknown_blocked == ["e2", "e3"]
    assert out_state.actions[scope_key("wf-demo", "unsafe")].executed_at is None
    assert unknown_state.actions[scope_key("wf-demo", "unsafe")].executed_at is None
