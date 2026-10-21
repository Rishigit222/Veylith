# Test report

## Checks run

Run from `chronicle-guard/` on 2026-10-21:

- `python -m pytest -q` — **18 passed**, one Starlette/httpx deprecation warning.
- `python -m compileall -q chronicle_guard tests` — passed.
- `node --check static/app.js` — passed after Veylith branding and API wiring changes.
- `python -m chronicle_guard.cli run revoked_approval_race` — verifier rejected `e4`, enforcement blocked `e4`, protected state remained unexecuted.
- `python -m chronicle_guard.cli replay evidence/sample-revoked-approval-race.json` — replay reproduced the same violation and blocked event.
- Uvicorn smoke server on `127.0.0.1:8011` — `/health`, `/`, `/api/chronicle/overview`, `/api/chronicle/integrations`, and flagship run returned HTTP 200.
- `docker build -t chronicle-guard:local .` — **blocked** because Docker Desktop's Linux engine was not running (`npipe ... dockerDesktopLinuxEngine` unavailable).
- `npm run typecheck` from `apps/mobile` — passed.
- `npx expo config --type public` — passed; Expo SDK 54 config resolved with Veylith branding and configurable API URL.
- `npx expo-doctor` — **18/18 checks passed** after the current mobile change set.
- FastAPI integration smoke test — login, `/api/auth/me`, all 9 scenario routes, flagship enforcement, legitimate workflow, and reviewer repair decision passed.

## Coverage focus

The test suite covers deterministic replay, approval revocation, stale evidence, duplicate event delivery, baseline-versus-verifier divergence, counterexample reduction, repair validation, JSON APIs, and static serving. Additional regression tests for timeout retries, untrusted instructions, metadata, and hash-linked evidence are part of the final verification step.

## Honest gaps

No browser automation runner, public deployment, physical device/emulator run, or real Ring credentials were available in this workspace. Those are reported as gaps rather than simulated successes. Expo type-checking and Expo Doctor are not a substitute for launching the app on an emulator.
