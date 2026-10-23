# Temporal safety model

## State

The replay state contains requested actions, approval lifecycle, evidence records, applied event IDs, duplicate IDs, and a monotonic logical clock. Event time (`event_time`) describes when a fact occurred; processing time (`processing_time`) describes when the simulator delivered it. The verifier checks event-time order while preserving the received stream order.

## Invariants

- `G(execute(action) -> request_seen(action))`
- `G(execute(action) -> exists approval(action) valid_at(execution_time))`
- `G(execute(action) -> workflow_scope(action) == workflow_scope(approval))`
- `G(execute(action) -> !cancelled(action))`
- `G(evidence(action) -> execution_anchor(action) && evidence_time >= execution_time)`
- `G(event_id -> unique(event_id))`
- `G(retry -> idempotency_key has not already committed)`
- `G(untrusted_instruction -> cannot change authorization state)`
- Logical event time must not move backwards in a processed trace.
- Empty traces and malformed approval expiry values are rejected as structured verifier findings.

Enforcement is fail-closed for protected execution: after a blocking ordering,
reference, malformed-payload, or conflicting-duplicate finding, later execution
events are quarantined even if that later event would look locally authorized.
Identical duplicate delivery is idempotent and has no additional replay effect.

Actions, approvals, and evidence are keyed by `workflow_id` plus their local ID. Reusing
an `action_id` or `approval_id` in another workflow therefore creates independent state
instead of silently overwriting or authorizing the wrong workflow. Cancellation is a
terminal lifecycle transition: a later execution is recorded in the forensic stream but
blocked from protected state by `enforce_temporal`.

The verifier reports the first event associated with a violation, the violation code, and all violations found in the bounded trace. `reduce_counterexample` removes events greedily while retaining at least one failing invariant; it is a reduction heuristic, not a minimum proof.

## Limits

This is explicit bounded trace verification. It does not explore every possible interleaving, prove liveness, or establish universal safety for arbitrary workflows. A production deployment would need a stronger policy language, durable storage, clock semantics, concurrency controls, and independent security review.
