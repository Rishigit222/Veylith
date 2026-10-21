# Threat model

## Assets

- Protected simulated action state.
- Approval validity and revocation state.
- Evidence integrity and replayability.
- Separation between untrusted events and agent instructions.

## Threats modeled

- Approval revocation after planning and before execution.
- Delayed/out-of-order event delivery.
- Duplicate event delivery and retries after uncertain execution.
- Expired/stale approval or evidence.
- Untrusted event content attempting to alter instructions.
- Partial workflow failure represented by a tool timeout.

## Controls

- Server-side Pydantic validation and extra-field rejection.
- Event IDs as replay/idempotency keys in the replay engine.
- Approval and evidence checks at the temporal transition.
- Provenance classification and explicit simulator-only integration boundary.
- Correlation and workflow identifiers in the event schema.
- No arbitrary tool execution or unrestricted network calls.

## Out of scope

Compromise of the host, key management, authenticating external Ring events, camera privacy, availability under malicious load, and the truthfulness of an upstream event. Hash linkage detects later mutation but does not prove origin.
