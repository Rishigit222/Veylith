# Backend notes

`chronicle_guard.model` contains the typed event and state schemas. Replay is
implemented by `chronicle_guard.state.apply_event` and is deterministic for a
given ordered stream.

The baseline policy engine is a legacy-style per-action presence check for a
request, approval, and execution. The temporal verifier independently scans
the complete event stream and checks ordering, revocation races, duplicate
event IDs, stale approvals/evidence, and execution authorization. Keeping
these implementations separate makes disagreement a useful diagnostic rather
than a circular result.

The scenario module is a simulator only. It creates synthetic streams and has
no Ring SDK, credentials, network calls, or device access.
