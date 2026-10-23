# Test report

## Checks run

Run from `E:\RISHI\Veylith` on 2026-10-23:

- `python -m pytest -q` — **37 passed**, existing Starlette/httpx deprecation warnings.
- `python -m compileall -q chronicle_guard tests` — passed.
- `node --check static/app.js` — passed after the trusted replay console rewrite.
- `python -m chronicle_guard.cli run revoked_approval_race` — verifier rejected `e4`, enforcement blocked `e4`, protected state remained unexecuted.
- `python -m chronicle_guard.cli replay evidence/sample-revoked-approval-race.json` — replay reproduced the same violation and blocked event.
- Uvicorn smoke server on `127.0.0.1:8765` — `/health`, `/`, `/api/chronicle/overview`, `/api/chronicle/integrations`, all 9 scenario routes, and flagship run returned HTTP 200.
- `docker build -t chronicle-guard:local .` — **blocked** because Docker Desktop's Linux engine was not running (`npipe ... dockerDesktopLinuxEngine` unavailable).
- `npm run typecheck` from `apps/mobile` — **blocked** because `tsc` is not installed locally (`node_modules` is absent).
- `npx expo config --type public` — resolved only through a temporary Expo install; it is not counted as a project dependency check.
- `npx expo-doctor` — **blocked** because the project's Expo package is not installed locally.
- FastAPI integration smoke test — login, `/api/auth/me`, all 9 scenario routes, flagship enforcement, legitimate workflow, reviewer repair decision, conflicting duplicate quarantine, and invalid-prefix fail-closed behavior passed.
- Ring adapter tests — Device Discovery, Event History provenance mapping, WHEP request/response validation, missing/expired token, HTTP error, malformed payload, and sanitized connection status passed with mocked external HTTP only.
- Ring live-call status — not run in this workspace because `RING_ACCESS_TOKEN` was not supplied. The real endpoint returns a sanitized `503 missing_token` response rather than claiming success.

## Coverage focus

The test suite covers deterministic replay, approval revocation, stale evidence, duplicate event delivery, baseline-versus-verifier divergence, counterexample reduction, repair validation, JSON APIs, and static serving. Additional regression tests for timeout retries, untrusted instructions, metadata, and hash-linked evidence are part of the final verification step.

## Honest gaps

No browser automation runner, public deployment, physical device/emulator run, or real Ring credentials were available in this workspace. Those are reported as gaps rather than simulated successes. Mobile dependency checks must be rerun after installing the committed `apps/mobile` dependencies; config now rejects localhost and non-HTTPS origins for EAS builds.
