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

## Mobile and web-console API

The client-facing routes are:

- `POST /api/auth/login` with `{ "email": "...", "password": "..." }`.
- `GET /api/auth/me` with `Authorization: Bearer <access_token>`.
- `GET /api/chronicle/agent-runs`.
- `GET /api/chronicle/notifications`.
- `GET /api/chronicle/repairs`.
- `POST /api/chronicle/repairs/{finding_id}/decision` with
  `{ "decision": "approve" }` or `{ "decision": "reject" }`.

Demo authentication is safe and deliberately limited: set
`CHRONICLE_DEMO_REVIEWER_EMAIL` and `CHRONICLE_DEMO_REVIEWER_PASSWORD` in the
environment (the exact example values are in `.env.example`). Login creates a
deterministic in-memory bearer session for the reviewer. Missing or invalid
bearer credentials return `401`; a valid session without the `reviewer` role
returns `403` for repair decisions. Sessions are lost on process restart, while
repair-review decisions are persisted in SQLite at `VEYLITH_DATA_PATH` so the
review queue survives a web restart. This is still demo auth, not production
identity, password storage, or a complete audit system.

Agent runs, notifications, and findings are generated from the deterministic
scenario factories, temporal verifier results, and evidence exports on each
request. No synthetic counters or live device data are added. Repair decisions
only annotate the in-memory demo finding records and do not change verifier
results.
