from __future__ import annotations

from .model import Approval, ActionRecord, Event, EventKind, EvidenceRecord, GuardState


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

    if event.kind is EventKind.ACTION_REQUESTED:
        next_state.actions[event.action_id] = ActionRecord(
            action_id=event.action_id,
            requested_at=logical_time,
            requested_by=event.actor,
        )
    elif event.kind is EventKind.APPROVAL_GRANTED:
        approval_id = event.approval_id or event.id
        next_state.approvals[approval_id] = Approval(
            approval_id=approval_id,
            action_id=event.action_id,
            actor=event.actor,
            granted_at=logical_time,
        )
    elif event.kind is EventKind.APPROVAL_REVOKED:
        approval_id = event.approval_id
        if approval_id and approval_id in next_state.approvals:
            next_state.approvals[approval_id].revoked_at = logical_time
    elif event.kind is EventKind.ACTION_EXECUTED:
        action = next_state.actions.get(event.action_id)
        if action:
            action.executed_at = logical_time
            action.executed_by = event.actor
            action.execution_event_id = event.id
    elif event.kind is EventKind.EVIDENCE_RECORDED:
        evidence_id = event.evidence_id or event.id
        next_state.evidence[evidence_id] = EvidenceRecord(
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
