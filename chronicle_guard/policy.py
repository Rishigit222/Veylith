from __future__ import annotations

from .model import EventKind, GuardState, PolicyDecision
from .state import replay


def evaluate_baseline(events, action_id: str | None = None) -> PolicyDecision:
    """Evaluate the baseline per-action policy against projected state.

    This is intentionally a legacy-style presence check: it requires a
    request, an approval, and an execution, but does not bind approval status
    to the execution boundary. Revocation timing and evidence freshness are
    the verifier's independent concern.
    """
    state: GuardState = replay(events)
    target = action_id or (next(iter(state.actions)) if state.actions else "")
    reasons: list[str] = []
    if not target:
        reasons.append("action_not_requested")
        return PolicyDecision(allowed=False, action_id=target, reasons=reasons)
    if target not in state.actions:
        reasons.append("action_not_requested")
    action_approvals = [a for a in state.approvals.values() if a.action_id == target]
    if not action_approvals:
        reasons.append("approval_required")
    if not any(e.action_id == target and e.kind is EventKind.ACTION_EXECUTED for e in events):
        reasons.append("action_not_executed")
    return PolicyDecision(
        allowed=not reasons,
        action_id=target,
        reasons=reasons,
        approval_id=action_approvals[-1].approval_id if action_approvals else None,
    )
