from __future__ import annotations

import httpx
import pytest

from fastapi.testclient import TestClient

from chronicle_guard.app import app
from chronicle_guard.ring import RingAdapter, RingIntegrationError


def make_client(handler):
    return httpx.Client(base_url="https://api.amazonvision.com", transport=httpx.MockTransport(handler))


def test_connection_endpoint_reports_missing_token_without_exposing_secret(monkeypatch):
    monkeypatch.delenv("RING_ACCESS_TOKEN", raising=False)
    client = TestClient(app)
    response = client.get("/api/ring/device-discovery")
    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "missing_token"
    assert "Bearer" not in str(body)


def test_ring_status_is_sanitized_and_reports_server_side_base_url(monkeypatch):
    monkeypatch.setenv("RING_ACCESS_TOKEN", "never-return-this-token")
    client = TestClient(app)
    body = client.get("/api/ring/status").json()
    assert body["configured"] is True
    assert body["base_url"] == "https://api.amazonvision.com"
    assert "never-return-this-token" not in str(body)


def test_device_discovery_success_preserves_json_api_shape_without_token_leak():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/devices"
        assert request.headers["authorization"] == "Bearer server-token"
        return httpx.Response(200, json={"data": [], "meta": {"request_id": "req-1"}})

    result = RingAdapter(access_token="server-token", client=make_client(handler)).discover_devices()
    assert result["operation"] == "device_discovery"
    assert result["data"] == []
    assert "server-token" not in str(result)


def test_missing_token_is_rejected_before_network_call():
    adapter = RingAdapter(access_token="")
    with pytest.raises(RingIntegrationError, match="not configured") as error:
        adapter.discover_devices()
    assert error.value.code == "missing_token"


def test_expired_token_http_error_is_sanitized():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errors": [{"detail": "expired"}]})

    with pytest.raises(RingIntegrationError) as error:
        RingAdapter(access_token="expired-token", client=make_client(handler)).discover_devices()
    assert error.value.code == "unauthorized"
    assert "expired-token" not in str(error.value)


def test_http_error_is_reported_without_response_body_leakage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="provider internal details")

    with pytest.raises(RingIntegrationError) as error:
        RingAdapter(access_token="server-token", client=make_client(handler)).discover_devices()
    assert error.value.code == "http_error"
    assert error.value.status_code == 500
    assert "provider internal" not in str(error.value)


def test_malformed_device_discovery_payload_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"id": "not-a-list"}})

    with pytest.raises(RingIntegrationError) as error:
        RingAdapter(access_token="server-token", client=make_client(handler)).discover_devices()
    assert error.value.code == "malformed_payload"


def test_event_history_request_and_provenance_mapping():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/history/devices/device-1/events"
        assert request.url.params["event_types"] == "motion,ding"
        assert request.url.params["page[key]"] == "next-1"
        return httpx.Response(200, json={
            "data": [{
                "type": "history-events",
                "id": "event-1",
                "attributes": {"event_type": "motion", "is_third_party_reviewed": False, "start": "2026-10-21T10:00:00Z", "end": "2026-10-21T10:00:02Z"},
                "relationships": {"source": {"data": {"type": "devices", "id": "device-1"}}},
            }],
            "meta": {"next_page_key": "next-2"},
        })

    adapter = RingAdapter(access_token="server-token", client=make_client(handler))
    history = adapter.event_history("device-1", event_types=["motion", "ding"], page_key="next-1")
    events = adapter.history_to_events(history, device_id="device-1")
    assert len(events) == 1
    assert events[0].kind.value == "ring_event"
    assert events[0].source == "ring_api"
    assert events[0].provenance == "ring_api"
    assert events[0].entity_id == "device-1"
    assert events[0].payload["ring_event_type"] == "motion"
    assert events[0].event_time == 1792576800000


def test_malformed_event_history_resource_type_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"type": "devices", "id": "device-1", "attributes": {}}]})

    with pytest.raises(RingIntegrationError) as error:
        RingAdapter(access_token="server-token", client=make_client(handler)).event_history("device-1")
    assert error.value.code == "malformed_payload"


def test_whep_session_creation_uses_raw_sdp_and_requires_location():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/devices/device-1/media/streaming/whep/sessions"
        assert request.url.params["component_id"] == "camera"
        assert request.headers["content-type"] == "application/sdp"
        assert request.content == b"v=0\r\n"
        return httpx.Response(201, headers={"Location": "/v1/whep/sessions/session-1"}, text="v=0\r\nanswer")

    session = RingAdapter(access_token="server-token", client=make_client(handler)).create_whep_session("device-1", "v=0\r\n", component_id="camera")
    assert session.location.endswith("session-1")
    assert session.sdp_answer.startswith("v=0")


def test_whep_malformed_response_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, text="v=0\r\nanswer")

    with pytest.raises(RingIntegrationError) as error:
        RingAdapter(access_token="server-token", client=make_client(handler)).create_whep_session("device-1", "v=0\r\n")
    assert error.value.code == "malformed_response"
