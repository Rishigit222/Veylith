# Final audit checklist

Status is intentionally evidence-based and was refreshed on 2026-10-21 after the backend and mobile changes.

- [x] Deterministic flagship scenario exists.
- [x] Baseline and independent verifier are separately callable.
- [x] Revoked approval race diverges: baseline allows, verifier rejects.
- [x] Counterexample reduction and repair replay exist.
- [x] Evidence JSON and replay endpoint exist.
- [x] UI distinguishes simulator-only from optional/unconfigured Ring integration.
- [x] No credentials or live device actions are required.
- [x] Web API endpoints support demo sessions, agent-run history, notifications, and reviewer-gated repair decisions.
- [x] Repair-review decisions persist in SQLite at `VEYLITH_DATA_PATH`.
- [x] Expo mobile MVP exists under `apps/mobile` and type-checks.
- [x] Web and mobile UI branding uses Veylith while the Python package remains `chronicle_guard` for compatibility.
- [x] Isolated Ring adapter implements documented Device Discovery, Event History, and WHEP request shapes without exposing the token.
- [x] Ring-originated history facts preserve `source="ring_api"` and `provenance="ring_api"`; synthetic scenarios remain separate.
- [ ] Public HTTPS deployment verified.
- [ ] Veylith server-side Ring Device Discovery independently verified with the user's access token.
- [ ] Veylith server-side Ring Event History independently verified; no device ID was available from the Playground response `{ "data": [] }`.
- [ ] Veylith server-side WHEP session independently verified; Playground session creation is not treated as reusable or externally authenticated.
- [ ] Public sub-three-minute demonstration video recorded.
- [x] Final post-change backend, Ring adapter, and mobile check results attached (29 backend tests; Expo typecheck; Expo Doctor 18/18).

## Submission claim

The defensible claim is: Veylith demonstrates a measurable temporal-verification advantage against its transparent baseline on deterministic synthetic traces. It does not claim universal safety, formal proof of arbitrary workflows, production identity management, or Ring compliance without a verified Ring adapter and approved access.

## Current check evidence

- Backend: 16 pytest tests passed after adding mobile-facing API endpoints.
- Backend compilation: passed.
- Web JavaScript syntax: passed before the final UI wiring changes; rerun after the current change set.
- Mobile: `npm run typecheck` passed; `npx expo-doctor` reported 18/18 checks passed after the current mobile change set.
- Docker: Dockerfile includes a health check, but the local Docker Desktop Linux engine was unavailable during the last build attempt.
- Deployment: no public URL is claimed because no hosting credentials or deployment target were available.
- Ring: official Playground activity was user-confirmed for Device Discovery (`{"data":[]}`) and a simulated WHEP live-view flow, but the Veylith backend has not yet called Ring because no server-side token was available in this workspace. Those are documented observations, not claimed Veylith successes.
