# Veylith

**Temporal Safety Assurance for Autonomous Agents**

Every action may be permitted. Is the entire sequence safe?

Veylith is a deterministic engineering laboratory for comparing a
transparent per-action authorization baseline with an independent temporal
verifier. It models approval lifecycles, event-time versus processing-time,
replay, stale evidence, duplicate delivery, uncertain retries, and untrusted
 event content. The flagship demonstration is the revoked-approval race. The
 Python package remains `chronicle_guard` for compatibility with the working
 verifier imports.

## Run

```bash
python -m pip install -e ".[test]"
python -m uvicorn chronicle_guard.app:app --reload
```

The application is available at `http://127.0.0.1:8000`, with OpenAPI at
`/docs` and a health endpoint at `/health`.

The web app is served by the same FastAPI process. Repair-review decisions use
SQLite at `VEYLITH_DATA_PATH` (default `data/veylith.sqlite3`); demo sessions
remain in memory and expire on process restart.

## API overview

- `GET /health`
- `GET /api/scenarios`
- `POST /api/scenarios/{name}/run`
- `POST /api/replay`
- `POST /api/verify`
- `POST /api/baseline/evaluate`
- `POST /api/counterexample/reduce`
- `POST /api/repair/validate`
- `POST /api/export`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/chronicle/agent-runs`
- `GET /api/chronicle/notifications`
- `GET /api/chronicle/repairs`
- `POST /api/chronicle/repairs/{finding_id}/decision`

Compatibility console routes are under `/api/chronicle/*` and power the static
browser UI. The UI explicitly reports **simulator-only** integration status.

## Demo flow

1. Open the Scenario Lab and run `SCN-042` / revoked approval race.
2. Compare the baseline's `allowed=true` result with the verifier's
   `revoked_approval_race` violation.
3. Inspect the reduced counterexample and repair validation.
4. Export the JSON evidence bundle and replay its event list with
   `POST /api/replay` or `POST /api/verify`.

The experiment is bounded and deterministic, not exhaustive verification. No
paid model API, live Ring device, physical action, visitor identity, or camera
feed is required.

All scenarios are pure deterministic generators with a seed, version, policy
version, and typed event metadata. The current workspace has no verified Ring
credentials or adapter, so it does not claim a Ring integration. See:

- `docs/prior-art-review.md`
- `docs/temporal-safety-model.md`
- `docs/final-audit.md`

## Mobile

The Expo client lives in `apps/mobile` and uses the same API. Configure
`EXPO_PUBLIC_API_BASE_URL`, then run:

```bash
cd apps/mobile
npm install
npm run typecheck
npx expo start
```

Android emulators reach a host-local API at `http://10.0.2.2:8000`; iOS
simulators normally use `http://127.0.0.1:8000`.
