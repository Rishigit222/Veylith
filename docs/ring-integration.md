# Ring integration boundary

## Verified API shapes implemented

The adapter in `chronicle_guard/ring.py` is server-side only and uses the
documented Ring Partner API base URL `https://api.amazonvision.com` with a
Bearer access token from `RING_ACCESS_TOKEN`.

### Device Discovery

```text
GET https://api.amazonvision.com/v1/devices
Accept: application/json
Authorization: Bearer <server-side-token>
```

The adapter validates a JSON:API response with `data`, optional `meta`, and
optional `links`, then returns only sanitized resources.

### Event History

```text
GET https://api.amazonvision.com/v1/history/devices/{device_id}/events
```

Optional query parameters:

- `event_types`
- `page[key]`

History resources must use the documented `history-events` type. Their
`attributes.event_type`, `attributes.is_third_party_reviewed`, `attributes.start`,
`attributes.end`, and `relationships.source` values are preserved in a typed
Veylith event with `source="ring_api"` and `provenance="ring_api"`.

### WHEP session creation

```text
POST https://api.amazonvision.com/v1/devices/{device_id}/media/streaming/whep/sessions
Content-Type: application/sdp
Accept: application/sdp
Authorization: Bearer <server-side-token>

<raw SDP offer>
```

`component_id` is supported as an optional query parameter. The adapter requires
the documented HTTP 201 response, a `Location` header, and a non-empty SDP
answer. It returns session metadata for the current request only and does not
persist or expose the token.

## Playground versus Veylith

The official Playground interaction is evidence that the Playground can invoke
the documented flow. It is not evidence that this Veylith process has access to
the same token, device, or temporary WHEP session. Veylith's integration status
only marks an operation verified after the backend itself receives a successful
response.

The reported Playground Device Discovery response was `{ "data": [] }`, so no
device ID is available for an Event History or WHEP request. The simulated live
view flow is therefore not represented as a Veylith camera connection. No
device, video frame, or fabricated event is created by the adapter.

## HTTP endpoints exposed by Veylith

- `GET /api/ring/status`
- `GET /api/ring/device-discovery`
- `GET /api/ring/devices/{device_id}/event-history`
- `POST /api/ring/devices/{device_id}/whep-session` with raw SDP body

External HTTP is mocked only in `tests/test_ring.py`. The deterministic temporal
verifier remains independent of Ring availability and continues to operate on
synthetic scenarios.
