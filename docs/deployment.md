# Veylith deployment guide

This guide describes the deployable boundary that exists in this repository. It
does not claim that a public deployment has been created or verified.

## Service architecture

The repository uses one FastAPI process for both the web application and API:

- `GET /` serves `static/index.html`.
- `/static/*` serves the CSS and JavaScript assets.
- `/health` serves the process health response.
- `/api/*` serves the JSON APIs.

The production-safe launcher is:

```bash
python -m chronicle_guard.serve
```

`chronicle_guard.serve` reads `HOST` and `PORT`, defaults to `0.0.0.0` and
`8000`, and enables proxy headers for a reverse proxy. An equivalent direct
command is:

```bash
python -m uvicorn chronicle_guard.app:app --host 0.0.0.0 --port ${PORT:-8000}
```

For a platform that provides `$PORT`, use the launcher module rather than
hard-coding a port in the hosting dashboard:

```text
Build:  python -m pip install .
Start:  python -m chronicle_guard.serve
```

The launcher was verified locally by starting Uvicorn and requesting `/`,
`/health`, and `/api/chronicle/overview`.

## Environment variables

Set these through the hosting provider's secret/configuration interface. Do not
commit a real `.env` file.

| Variable | Required | Description |
| --- | --- | --- |
| `VEYLITH_ENV` | Recommended | `development` or `production`. |
| `VEYLITH_ALLOW_DEMO_AUTH` | Required for public demo reviewer actions | Must be explicitly `true` to enable the intentionally limited demo login in production. Leave `false` until a real identity provider exists. |
| `VEYLITH_CORS_ORIGINS` | Only for cross-origin browser clients | Comma-separated exact origins, for example `https://console.example.com`. Same-origin web and native mobile requests do not require CORS. |
| `CHRONICLE_DEMO_REVIEWER_EMAIL` | If demo auth enabled | Demo reviewer email. |
| `CHRONICLE_DEMO_REVIEWER_PASSWORD` | If demo auth enabled | Demo reviewer password. |
| `VEYLITH_DATA_PATH` | Recommended | SQLite path, normally a mounted durable volume such as `/var/lib/veylith/veylith.sqlite3`. |
| `RING_ACCESS_TOKEN` | Optional | Server-side Ring bearer token. Never expose to web/mobile clients. |
| `RING_API_BASE_URL` | Optional | Defaults to `https://api.amazonvision.com`. |
| `HOST` | Optional | Defaults to `0.0.0.0`. |
| `PORT` | Platform-provided | Defaults to `8000` locally; hosting platforms should provide it. |
| `FORWARDED_ALLOW_IPS` | Optional | Defaults to `*` for a trusted hosting proxy. Restrict this for a stricter network model. |

`.env.example` contains placeholders only. `.env` is ignored by Git. Ring tokens,
reviewer passwords, and session material must be managed by the host secret
store.

### Authentication boundary

The current reviewer flow is demo authentication, not production identity:

- Sessions are stored in memory and disappear on restart.
- Repair decisions are protected by reviewer role checks.
- Repair decisions are persisted in SQLite.
- Read-only scenario/overview APIs are currently public.
- In `VEYLITH_ENV=production`, demo login is disabled unless
  `VEYLITH_ALLOW_DEMO_AUTH=true` is explicitly set.

Before a real public deployment, integrate a production identity provider and
protect the appropriate read and write routes. Do not treat the demo credentials
as an acceptable production authentication system.

## CORS and frontend configuration

The FastAPI app applies restrictive CORS configuration. By default,
`VEYLITH_CORS_ORIGINS` is empty, so cross-origin browser requests are not
enabled. Set exact trusted origins only when the web console is hosted on a
different origin from the API.

The existing architecture serves web and API from the same process and origin,
so a same-origin deployment does not need CORS.

The Expo native client uses `EXPO_PUBLIC_API_BASE_URL`; native requests do not
need browser CORS. An Expo web build hosted on another origin does need that
origin listed in `VEYLITH_CORS_ORIGINS`.

## Persistence and restart behavior

### Repair decisions

`chronicle_guard.storage` stores reviewer decisions in SQLite. The default local
path is `data/veylith.sqlite3`; for hosting, set `VEYLITH_DATA_PATH` to a path
on a durable mounted volume.

If the platform uses an ephemeral filesystem, repair decisions can be lost on
restart or redeploy. Do not claim durable review history unless the volume or
managed database has been verified.

### Evidence and event history

The current application does not maintain a durable event database or durable
evidence archive. Event runs and evidence are deterministic and recomputed from
the scenario catalog or supplied request body. Hash-linked evidence is returned
in JSON; it is not automatically written to durable storage.

### Sessions

Demo bearer sessions are intentionally in memory and do not survive process
restarts. This is another reason the demo auth flow is not production identity.

## Non-Docker deployment

Docker is optional. A generic Python hosting service can use:

```bash
python -m pip install .
python -m chronicle_guard.serve
```

The service must:

1. Provide Python 3.10+.
2. Provide a dynamic `PORT` environment variable or allow port 8000.
3. Bind the service to `0.0.0.0`.
4. Mount durable storage if SQLite review decisions must survive restarts.
5. Configure secrets outside Git.
6. Expose HTTPS before connecting a mobile build.

After deployment, verify from outside the host:

```text
GET  https://<public-host>/health
GET  https://<public-host>/
GET  https://<public-host>/api/chronicle/overview
POST https://<public-host>/api/chronicle/scenarios/SCN-042/run
POST https://<public-host>/api/chronicle/scenarios/SCN-001/run
```

Also verify login and reviewer decisions only if demo auth has been explicitly
enabled for a private demonstration.

## Docker

The repository includes a Dockerfile with:

- Python 3.12 slim.
- `python -m chronicle_guard.serve` as the container command.
- Dynamic `$PORT` support.
- A health check against `/health`.

The Docker image was not claimed as locally built in the previous environment
because Docker Desktop's Linux engine was unavailable. A future operator should
run:

```bash
docker build -t veylith:local .
docker run --rm -p 8000:8000 --env-file .env veylith:local
```

Do not report a successful container deployment until the build and health check
have actually completed.

## Mobile local development

Local development configuration remains separate:

```bash
cd apps/mobile
npm install
npx expo start
```

For the Python service, export backend variables in the shell or configure them
through the process manager; the FastAPI app does not automatically load a
`.env` file. For PowerShell, for example:

```powershell
$env:VEYLITH_ENV = "development"
$env:VEYLITH_DATA_PATH = "data/veylith.sqlite3"
python -m chronicle_guard.serve
```

Use:

- iOS simulator: `http://127.0.0.1:8000`
- Android emulator: `http://10.0.2.2:8000`
- Physical device: a reachable LAN API address

These addresses are for local development only.

## Mobile public API configuration

Production and preview builds must use a public HTTPS API origin. The Expo
config rejects a production build when `EXPO_PUBLIC_API_BASE_URL` is missing.

Create `apps/mobile/.env.production` locally or configure the value through EAS
environment secrets. Do not commit the file:

```text
EXPO_PUBLIC_API_BASE_URL=https://<verified-public-api-host>
EXPO_PUBLIC_PUSH_ENABLED=false
```

The repository includes `apps/mobile/.env.production.example` as a placeholder
template only.

## Android preview APK with Expo EAS

Manual prerequisites:

1. Create or sign in to an Expo account.
2. Install or invoke the EAS CLI: `npm install --global eas-cli` or use `npx eas`.
3. Run `eas login`.
4. Configure an EAS project with `eas init` if the app has not been linked.
5. Deploy the FastAPI service first and verify its HTTPS URL.
6. Set the EAS environment variable for the preview environment:

```bash
cd apps/mobile
npx eas env:create --environment preview --name EXPO_PUBLIC_API_BASE_URL --value https://<verified-public-api-host> --visibility plaintext
```

For a sensitive internal API URL, use the provider's secret visibility option
where appropriate. The API URL is not itself a credential, but it should still
be controlled as deployment configuration.

Build an installable Android preview APK using the committed `preview` profile:

```bash
cd apps/mobile
npx eas build --platform android --profile preview
```

The profile in `apps/mobile/eas.json` requests an internal Android APK. EAS
builds require Expo account access and may require Android signing setup. The
resulting download URL is produced by EAS; it is not known until the build runs.

For a production Android build after the public API and identity boundary are
verified:

```bash
npx eas build --platform android --profile production
```

No EAS build or public API connection was run in this workspace, so no APK URL
or mobile production verification is claimed.

## Deployment verification checklist

- [ ] Public HTTPS API host selected.
- [ ] `python -m chronicle_guard.serve` starts on the platform's dynamic port.
- [ ] `/health` verified externally.
- [ ] `/` and `/static/*` verified externally.
- [ ] `/api/chronicle/overview` verified externally.
- [ ] `SCN-042` rejects and blocks `e4`.
- [ ] `SCN-001` remains valid and executes in protected simulator state.
- [ ] Durable SQLite volume verified across restart, if review history is needed.
- [ ] Production identity provider configured, or demo auth explicitly limited to a private demo.
- [ ] Exact CORS origins configured only if cross-origin browser access is needed.
- [ ] `EXPO_PUBLIC_API_BASE_URL` set to the verified HTTPS origin.
- [ ] EAS preview APK built and tested on an emulator or device.

The current repository has no public URL, no verified host account, no verified
Docker build, and no EAS build result. Those are manual deployment steps, not
implemented claims.
