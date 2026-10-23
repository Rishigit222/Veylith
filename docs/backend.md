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

Verifier state is workflow-scoped: action, approval, and evidence records use a
stable length-prefixed workflow/local keys, so identical local IDs in different workflows
cannot overwrite one another or reuse authorization. `ACTION_CANCELLED` is a
terminal lifecycle transition and execution after cancellation is reported as a
structured `execution_after_cancellation` violation and blocked from protected
state. Invalid approval expiry payloads and empty traces also return verifier
findings instead of raising runtime conversion errors.

`enforce_temporal` is fail-closed at the protected commit boundary. Once an
ordering, reference, malformed-payload, or conflicting-duplicate finding enters
the prefix, later execution events are quarantined instead of being applied to
protected state. Identical duplicate delivery is retained as an idempotent
forensic no-op; conflicting reuse of an event ID is quarantined.

Scenario replay routes share one response contract containing the catalog metadata,
raw event stream, trace projection, baseline result, verifier result, counterexample,
enforcement outcome, and evidence export. This keeps the web and mobile clients
from reconstructing product truth from local fixtures.

The scenario module is a simulator only. It creates synthetic streams and has
no effect on the Ring adapter. Ring calls are isolated in `chronicle_guard.ring`
and use a server-side `RING_ACCESS_TOKEN` only. The documented operations are:

- `GET https://api.amazonvision.com/v1/devices` for Device Discovery.
- `GET https://api.amazonvision.com/v1/history/devices/{device_id}/events` for
  Event History, with optional `event_types` and `page[key]` query parameters.
- `POST https://api.amazonvision.com/v1/devices/{device_id}/media/streaming/whep/sessions`
  with a raw `application/sdp` offer and optional `component_id` query parameter
  for WHEP session creation. The adapter requires HTTP 201, a Location header,
  and an SDP answer, and does not persist the temporary session.

The Ring adapter never logs or returns the bearer token. Device Discovery and
Event History responses are sanitized; history records map to `EventKind.RING_EVENT`
with `source="ring_api"` and `provenance="ring_api"`. These external facts are
separate from deterministic synthetic scenarios. A Playground response or
Playground WHEP video is not counted as a Veylith API success until the backend
itself completes the corresponding documented request.

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
