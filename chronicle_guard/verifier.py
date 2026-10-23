from __future__ import annotations

from .model import Event, EventKind, GuardState, VerificationResult, Violation, scope_key
from .state import replay


def verify(events: list[Event]) -> VerificationResult:
    """Independently verify stream chronology and authorization invariants."""
    violations: list[Violation] = []
    seen: dict[str, Event] = {}
    approvals: dict[str, Event] = {}
    approval_expiry: dict[str, int | None] = {}
    invalid_approval_expiry: set[str] = set()
    revoked_at: dict[str, int] = {}
    requested_at: dict[str, int] = {}
    executions: dict[str, Event] = {}
    evidence_seen: set[str] = set()
    cancelled_at: dict[str, int] = {}
    previous_at = -1
    first_violation_event_id: str | None = None

    def add_violation(violation: Violation) -> None:
        nonlocal first_violation_event_id
        violations.append(violation)
        if first_violation_event_id is None:
            first_violation_event_id = violation.event_id

    if not events:
        add_violation(Violation(code="empty_trace", message="verification requires at least one event"))

    for event in events:
        prior_event = seen.get(event.id)
        if prior_event is not None:
            if prior_event == event:
                add_violation(Violation(code="duplicate_event", event_id=event.id, action_id=event.action_id, message="identical duplicate delivery is idempotent and has no additional effect"))
            else:
                add_violation(Violation(code="conflicting_duplicate_event", event_id=event.id, action_id=event.action_id, message="event ID was reused with a different payload"))
            continue
        seen[event.id] = event
        logical_time = event.logical_time
        if logical_time < previous_at:
            add_violation(Violation(code="out_of_order", event_id=event.id, action_id=event.action_id, message="event time moves backwards in the processing stream"))
        previous_at = max(previous_at, logical_time)

        action_key = scope_key(event.workflow_id, event.action_id)

        if event.kind is EventKind.ACTION_REQUESTED:
            if action_key in requested_at:
                add_violation(Violation(code="duplicate_action_request", event_id=event.id, action_id=event.action_id, message="action was requested more than once"))
            requested_at[action_key] = logical_time
        elif event.kind is EventKind.APPROVAL_GRANTED:
            approval_id = event.approval_id or event.id
            approval_key = scope_key(event.workflow_id, approval_id)
            if approval_key in approvals:
                add_violation(Violation(code="duplicate_approval", event_id=event.id, action_id=event.action_id, message="approval ID occurs more than once"))
            approvals[approval_key] = event
            raw_expiry = event.payload.get("expires_at")
            if raw_expiry is None:
                approval_expiry[approval_key] = None
            elif isinstance(raw_expiry, bool) or isinstance(raw_expiry, float) or not isinstance(raw_expiry, (int, str)):
                invalid_approval_expiry.add(approval_key)
                add_violation(Violation(code="malformed_approval_expiry", event_id=event.id, action_id=event.action_id, message="approval expires_at must be an integer timestamp"))
            else:
                try:
                    expiry = int(raw_expiry)
                except (TypeError, ValueError):
                    invalid_approval_expiry.add(approval_key)
                    add_violation(Violation(code="malformed_approval_expiry", event_id=event.id, action_id=event.action_id, message="approval expires_at must be an integer timestamp"))
                else:
                    if expiry < 0:
                        invalid_approval_expiry.add(approval_key)
                        add_violation(Violation(code="malformed_approval_expiry", event_id=event.id, action_id=event.action_id, message="approval expires_at must be a non-negative timestamp"))
                    else:
                        approval_expiry[approval_key] = expiry
        elif event.kind is EventKind.APPROVAL_REVOKED:
            approval_id = event.approval_id
            approval_key = scope_key(event.workflow_id, approval_id) if approval_id else None
            if not approval_key or approval_key not in approvals:
                cross_workflow = bool(approval_id and any(approval.approval_id == approval_id for approval in approvals.values()))
                code = "cross_workflow_reference" if cross_workflow else "unknown_approval_revocation"
                add_violation(Violation(code=code, event_id=event.id, action_id=event.action_id, message="revocation references an approval owned by another workflow" if cross_workflow else "revocation references no known approval"))
            else:
                approval = approvals[approval_key]
                if approval.action_id != event.action_id:
                    add_violation(Violation(code="approval_action_mismatch", event_id=event.id, action_id=event.action_id, message="revocation action does not match the approval action"))
                else:
                    revoked_at[approval_key] = logical_time
        elif event.kind is EventKind.ACTION_EXECUTED:
            if action_key in executions:
                add_violation(Violation(code="duplicate_execution", event_id=event.id, action_id=event.action_id, message="action executed more than once; retry requires idempotency proof"))
            executions[action_key] = event
            if action_key not in requested_at:
                add_violation(Violation(code="execution_without_request", event_id=event.id, action_id=event.action_id, message="action executed without a request"))
            if action_key in cancelled_at and cancelled_at[action_key] <= logical_time:
                add_violation(Violation(code="execution_after_cancellation", event_id=event.id, action_id=event.action_id, message="cancelled actions are terminal and cannot execute"))
            valid = []
            revoked = []
            for approval_key, approval in approvals.items():
                if scope_key(approval.workflow_id, approval.action_id) != action_key or approval_key in invalid_approval_expiry:
                    continue
                expiry = approval_expiry.get(approval_key)
                if approval.logical_time <= logical_time and (expiry is None or expiry >= logical_time) and not (approval_key in revoked_at and revoked_at[approval_key] <= logical_time):
                    valid.append(approval)
                if approval_key in revoked_at and revoked_at[approval_key] <= logical_time:
                    revoked.append(approval_key)
            if not valid:
                code = "revoked_approval_race" if revoked else "execution_without_approval"
                add_violation(Violation(code=code, event_id=event.id, action_id=event.action_id, message="execution has no approval valid at execution time"))
            if event.payload.get("uncertain_retry") and event.payload.get("idempotency_key"):
                if any(scope_key(existing.workflow_id, existing.action_id) == action_key and existing.payload.get("idempotency_key") == event.payload["idempotency_key"] for existing in executions.values() if existing.id != event.id):
                    add_violation(Violation(code="retry_after_uncertain_execution", event_id=event.id, action_id=event.action_id, message="uncertain retry reuses an idempotency key after an execution already appeared"))
        elif event.kind is EventKind.EVIDENCE_RECORDED:
            evidence_id = event.evidence_id or event.id
            evidence_key = scope_key(event.workflow_id, evidence_id)
            if evidence_key in evidence_seen:
                add_violation(Violation(code="duplicate_evidence", event_id=event.id, action_id=event.action_id, message="evidence ID occurs more than once"))
            evidence_seen.add(evidence_key)
            if action_key not in executions:
                add_violation(Violation(code="stale_evidence", event_id=event.id, action_id=event.action_id, message="evidence has no execution anchor"))
            elif logical_time < executions[action_key].logical_time:
                add_violation(Violation(code="stale_evidence", event_id=event.id, action_id=event.action_id, message="evidence predates execution"))
            if event.approval_id:
                evidence_approval_key = scope_key(event.workflow_id, event.approval_id)
                approval = approvals.get(evidence_approval_key)
                if approval is None:
                    cross_workflow = any(item.approval_id == event.approval_id for item in approvals.values())
                    add_violation(Violation(code="cross_workflow_reference" if cross_workflow else "unknown_evidence_approval", event_id=event.id, action_id=event.action_id, message="evidence references an approval outside the workflow" if cross_workflow else "evidence references no known approval"))
                elif approval.action_id != event.action_id:
                    add_violation(Violation(code="approval_action_mismatch", event_id=event.id, action_id=event.action_id, message="evidence approval does not match the evidence action"))
        elif event.kind is EventKind.ACTION_CANCELLED:
            if action_key in cancelled_at:
                add_violation(Violation(code="duplicate_action_cancellation", event_id=event.id, action_id=event.action_id, message="action was cancelled more than once"))
            elif action_key in executions:
                add_violation(Violation(code="cancellation_after_execution", event_id=event.id, action_id=event.action_id, message="an executed action cannot transition back to cancelled"))
            else:
                cancelled_at[action_key] = logical_time
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
    non_blocking_codes = {"duplicate_event"}
    invalid_prefix = False
    for event in events:
        candidate = verify(accepted + [event])
        current_event_violations = [violation for violation in candidate.violations if violation.event_id == event.id]
        blocking_current_event = any(violation.code not in non_blocking_codes for violation in current_event_violations)
        if blocking_current_event:
            invalid_prefix = True
            if event.kind is not EventKind.EVIDENCE_RECORDED:
                blocked.append(event.id)
                continue
        if event.kind is EventKind.ACTION_EXECUTED and invalid_prefix:
            blocked.append(event.id)
            continue
        accepted.append(event)
    return replay(accepted), blocked
