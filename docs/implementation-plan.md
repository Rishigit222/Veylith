# Implementation plan

## Delivered slice

1. Typed event model with event time, processing time, provenance, sequence, workflow, and correlation fields.
2. Deterministic replay state machine with idempotent event application.
3. Transparent per-action baseline policy and independent temporal verifier.
4. Deterministic scenario catalog, including the revoked approval race, stale evidence, duplicate delivery, out-of-order events, timeout retries, and untrusted instructions.
5. Greedy counterexample reduction and repair validation by replaying a candidate stream.
6. Evidence export with a hash-linked event chain and explicit authenticity limitation.
7. FastAPI JSON surface and static responsive console.
8. Automated unit/API tests and local health/build smoke checks.

## Verification gates

- `python -m pytest -q`
- `python -m compileall -q chronicle_guard tests`
- `node --check static/app.js`
- Start `uvicorn chronicle_guard.app:app` and check `/health`, `/`, `/api/chronicle/overview`, and the flagship run.

## Explicit non-goals

- No arbitrary shell/code execution by the agent.
- No paid model API dependency.
- No physical Ring actions or live visitor data.
- No claim of exhaustive temporal model checking.
- No claim that hash linkage proves event authenticity.
