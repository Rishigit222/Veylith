# Architecture

```text
browser console
      |
      v
FastAPI app  ---- /health, /api/* ---- deterministic scenario catalog
      |                                  |
      +--> baseline policy              +--> event-sourced replay
      |                                  |
      +--> temporal verifier ----------> counterexample reducer
                                         |
                                         +--> repair validation + evidence export
```

## Boundaries

- `model.py`: versionable records and request/response contracts.
- `state.py`: pure replay and idempotent event application.
- `policy.py`: intentionally narrow legacy-style per-action baseline.
- `verifier.py`: temporal invariants independent of model or policy claims.
- `scenarios.py`: deterministic synthetic events with seeds and scenario versions.
- `repair.py`: candidate correction evaluation by replay, not self-authorization.
- `export.py`: inspectable JSON evidence and hash linkage.
- `app.py`: HTTP boundary and static UI serving.

The event stream is synthetic and isolated. A future real adapter must normalize external events into the typed schema, preserve provenance, and remain disabled until independently verified.
