from __future__ import annotations

from .model import Event, EventKind, GuardState, VerificationResult, Violation
from .state import replay


def verify(events: list[Event]) -> VerificationResult:
    """Independently verify stream chronology and authorization invariants."""
    violations: list[Violation] = []
    seen: set[str] = set()
    approvals: dict[str, Event] = {}
    revoked_at: dict[str, int] = {}
    requested_at: dict[str, int] = {}
    executions: dict[str, Event] = {}
    evidence_seen: set[str] = set()
    previous_at = -1
    first_violation_event_id: str | None = None

    def add_violation(violation: Violation) -> None:
        nonlocal first_violation_event_id
        violations.append(violation)
        if first_violation_event_id is None:
            first_violation_event_id = violation.event_id

    for event in events:
        if event.id in seen:
            add_violation(Violation(code="duplicate_event", event_id=event.id, action_id=event.action_id, message="event ID occurs more than once"))
        seen.add(event.id)
        logical_time = event.logical_time
        if logical_time < previous_at:
            add_violation(Violation(code="out_of_order", event_id=event.id, action_id=event.action_id, message="event time moves backwards in the processing stream"))
        previous_at = max(previous_at, logical_time)

        if event.kind is EventKind.ACTION_REQUESTED:
            if event.action_id in requested_at:
                add_violation(Violation(code="duplicate_action_request", event_id=event.id, action_id=event.action_id, message="action was requested more than once"))
            requested_at[event.action_id] = logical_time
        elif event.kind is EventKind.APPROVAL_GRANTED:
            approval_id = event.approval_id or event.id
            if approval_id in approvals:
                add_violation(Violation(code="duplicate_approval", event_id=event.id, action_id=event.action_id, message="approval ID occurs more than once"))
            approvals[approval_id] = event
        elif event.kind is EventKind.APPROVAL_REVOKED:
            approval_id = event.approval_id
            if not approval_id or approval_id not in approvals:
                add_violation(Violation(code="unknown_approval_revocation", event_id=event.id, action_id=event.action_id, message="revocation references no known approval"))
            else:
                revoked_at[approval_id] = logical_time
        elif event.kind is EventKind.ACTION_EXECUTED:
            if event.action_id in executions:
                add_violation(Violation(code="duplicate_execution", event_id=event.id, action_id=event.action_id, message="action executed more than once; retry requires idempotency proof"))
            executions[event.action_id] = event
            if event.action_id not in requested_at:
                add_violation(Violation(code="execution_without_request", event_id=event.id, action_id=event.action_id, message="action executed without a request"))
            valid = [a for aid, a in approvals.items() if a.action_id == event.action_id and a.logical_time <= logical_time and not (aid in revoked_at and revoked_at[aid] <= logical_time) and int(a.payload.get("expires_at", 10**9)) >= logical_time]
            if not valid:
                revoked = [aid for aid, a in approvals.items() if a.action_id == event.action_id and aid in revoked_at and revoked_at[aid] <= logical_time]
                code = "revoked_approval_race" if revoked else "execution_without_approval"
                add_violation(Violation(code=code, event_id=event.id, action_id=event.action_id, message="execution has no approval valid at execution time"))
            if event.payload.get("uncertain_retry") and event.payload.get("idempotency_key"):
                if any(existing.payload.get("idempotency_key") == event.payload["idempotency_key"] for existing in executions.values() if existing.id != event.id):
                    add_violation(Violation(code="retry_after_uncertain_execution", event_id=event.id, action_id=event.action_id, message="uncertain retry reuses an idempotency key after an execution already appeared"))
        elif event.kind is EventKind.EVIDENCE_RECORDED:
            evidence_id = event.evidence_id or event.id
            if evidence_id in evidence_seen:
                add_violation(Violation(code="duplicate_evidence", event_id=event.id, action_id=event.action_id, message="evidence ID occurs more than once"))
            evidence_seen.add(evidence_id)
            if event.action_id not in executions:
                add_violation(Violation(code="stale_evidence", event_id=event.id, action_id=event.action_id, message="evidence has no execution anchor"))
            elif logical_time < executions[event.action_id].logical_time:
                add_violation(Violation(code="stale_evidence", event_id=event.id, action_id=event.action_id, message="evidence predates execution"))
        elif event.kind is EventKind.UNTRUSTED_INSTRUCTION:
            add_violation(Violation(code="untrusted_instruction", event_id=event.id, action_id=event.action_id, message="untrusted event content cannot change authorization or agent instructions"))

    return VerificationResult(valid=not violations, violations=violations, checked_event_ids=[e.id for e in events], first_violation_event_id=first_violation_event_id)


def reduce_counterexample(events: list[Event]) -> list[Event]:
    """Greedily remove events while preserving the first observed violation code."""
    current = list(events)
    original = verify(current)
    if original.valid:
        return current
    target_code = original.violations[0].code
    changed = True
    while changed:
        changed = False
        for index in range(len(current)):
            candidate = current[:index] + current[index + 1 :]
            if any(violation.code == target_code for violation in verify(candidate).violations):
                current = candidate
                changed = True
                break
    return current


def enforce_temporal(events: list[Event]) -> tuple[GuardState, list[str]]:
    """Apply the verifier as a commit-boundary guard in the simulator.

    The raw stream remains available for forensics, but unsafe execution
    transitions are not applied to the protected state.
    """
    accepted: list[Event] = []
    blocked: list[str] = []
    execution_codes = {"revoked_approval_race", "execution_without_approval", "execution_without_request", "duplicate_execution", "retry_after_uncertain_execution"}
    for event in events:
        candidate = verify(accepted + [event])
        current_event_violations = [violation for violation in candidate.violations if violation.event_id == event.id]
        if event.kind is EventKind.ACTION_EXECUTED and any(violation.code in execution_codes for violation in current_event_violations):
            blocked.append(event.id)
            continue
        accepted.append(event)
    return replay(accepted), blocked
