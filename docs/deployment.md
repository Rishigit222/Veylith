# Veylith deployment notes

## Production command

```bash
python -m pip install .
python -m uvicorn chronicle_guard.app:app --host 0.0.0.0 --port ${PORT:-8000}
```

The process exposes `/health` and serves the web application at `/`. Configure
these environment variables outside Git:

- `CHRONICLE_DEMO_REVIEWER_EMAIL`
- `CHRONICLE_DEMO_REVIEWER_PASSWORD`
- `VEYLITH_DATA_PATH`

Use a durable volume for `VEYLITH_DATA_PATH`. The current SQLite store persists
review decisions; event runs and evidence are deterministic and can be
recomputed from the scenario catalog. Demo bearer sessions remain in memory and
are intentionally not production identity management.

## Container

`Dockerfile` installs the package, serves on `$PORT`, and includes a container
health check against `/health`. A local `docker build` was attempted on
2026-10-21 but could not run because Docker Desktop's Linux engine was not
available. The image and health check are therefore not claimed as locally
verified.

## Deployment status

No public HTTPS deployment is claimed. No hosting credentials or target were
available in this workspace. Before connecting the mobile app to production:

1. Deploy the API behind HTTPS.
2. Mount a durable volume for the SQLite file or move decisions to a managed DB.
3. Set demo credentials through the host secret manager, not source files.
4. Verify `/health`, `/api/chronicle/overview`, login, scenario execution,
   evidence export, and reviewer-gated repair decisions at the public URL.
5. Set `EXPO_PUBLIC_API_BASE_URL` in `apps/mobile/.env` to the verified HTTPS
   API origin.
