from __future__ import annotations

from .model import Approval, ActionRecord, Event, EventKind, EvidenceRecord, GuardState, scope_key


def apply_event(state: GuardState, event: Event) -> GuardState:
    """Apply one event without mutating the input state.

    Event IDs are idempotency keys. A repeated event is recorded as ignored,
    which lets replay remain deterministic while the verifier can still flag
    the duplicate in the original stream.
    """
    next_state = state.model_copy(deep=True)
    if event.id in next_state.applied_event_ids:
        if event.id not in next_state.ignored_duplicate_ids:
            next_state.ignored_duplicate_ids.append(event.id)
        return next_state
    logical_time = event.logical_time
    next_state.clock = max(next_state.clock, logical_time)
    action_key = scope_key(event.workflow_id, event.action_id)

    if event.kind is EventKind.ACTION_REQUESTED:
        next_state.actions[action_key] = ActionRecord(
            workflow_id=event.workflow_id,
            action_id=event.action_id,
            requested_at=logical_time,
            requested_by=event.actor,
        )
    elif event.kind is EventKind.APPROVAL_GRANTED:
        approval_id = event.approval_id or event.id
        next_state.approvals[scope_key(event.workflow_id, approval_id)] = Approval(
            workflow_id=event.workflow_id,
            approval_id=approval_id,
            action_id=event.action_id,
            actor=event.actor,
            granted_at=logical_time,
        )
    elif event.kind is EventKind.APPROVAL_REVOKED:
        approval_id = event.approval_id
        approval = next_state.approvals.get(scope_key(event.workflow_id, approval_id)) if approval_id else None
        if approval and approval.action_id == event.action_id:
            approval.revoked_at = logical_time
    elif event.kind is EventKind.ACTION_EXECUTED:
        action = next_state.actions.get(action_key)
        if action and action.cancelled_at is None:
            action.executed_at = logical_time
            action.executed_by = event.actor
            action.execution_event_id = event.id
    elif event.kind is EventKind.ACTION_CANCELLED:
        action = next_state.actions.get(action_key)
        if action and action.cancelled_at is None and action.executed_at is None:
            action.cancelled_at = logical_time
            action.cancelled_by = event.actor
            action.cancellation_event_id = event.id
    elif event.kind is EventKind.EVIDENCE_RECORDED:
        evidence_id = event.evidence_id or event.id
        next_state.evidence[scope_key(event.workflow_id, evidence_id)] = EvidenceRecord(
            workflow_id=event.workflow_id,
            evidence_id=evidence_id,
            action_id=event.action_id,
            recorded_at=logical_time,
            source=event.actor,
            approval_id=event.approval_id,
        )

    next_state.applied_event_ids.append(event.id)
    return next_state


def replay(events: list[Event]) -> GuardState:
    state = GuardState()
    for event in events:
        state = apply_event(state, event)
    return state
