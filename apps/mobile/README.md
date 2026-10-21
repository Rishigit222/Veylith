# Veylith Mobile

Expo + React Native + TypeScript mobile MVP for the Veylith FastAPI API.
The existing backend and web app remain the source of truth; this package only
adds a mobile client under `apps/mobile`.

## Configure the API

Copy `.env.example` to `.env` and set `EXPO_PUBLIC_API_BASE_URL` to the API
origin. The client appends the documented `/api/...` paths itself.

- iOS simulator: `http://127.0.0.1:8000` normally works.
- Android emulator: use `http://10.0.2.2:8000` for a backend on the host machine.
- Physical device: use the host machine's LAN IP and ensure the API is reachable.

No credentials are stored in the repository. Login values are entered at runtime
and the returned session token is persisted locally with AsyncStorage.

## Install and run

From this directory:

```bash
npm install
npx expo start
npx expo start --android
npx expo start --ios
```

Type-check with:

```bash
npm run typecheck
```

The MVP uses an in-app notification center and explicitly displays push as
disabled until push credentials are configured. This avoids pretending that
remote push delivery is available.

## API contract used

The client calls:

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/chronicle/overview`
- `GET /api/chronicle/agent-runs`
- `GET /api/chronicle/notifications`
- `GET /api/chronicle/repairs`
- `POST /api/chronicle/repairs/{finding_id}/decision`
- `GET /api/chronicle/scenarios`
- `POST /api/chronicle/scenarios/{id}/run`

Scenario run responses are used for incident details, event timelines,
counterexamples, and verification results. The UI tolerates common list wrapper
shapes (`items`, `runs`, `findings`, `notifications`, or `scenarios`) so the
backend can evolve without duplicating domain logic in the app.
