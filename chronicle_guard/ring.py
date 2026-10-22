from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .model import Event, EventKind


DEFAULT_RING_API_BASE_URL = "https://api.amazonvision.com"
DEVICE_DISCOVERY_PATH = "/v1/devices"
EVENT_HISTORY_PATH = "/v1/history/devices/{device_id}/events"
WHEP_SESSION_PATH = "/v1/devices/{device_id}/media/streaming/whep/sessions"


class RingIntegrationError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class RingJSONAPIResource(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    id: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, Any] = Field(default_factory=dict)


class RingJSONAPIResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[RingJSONAPIResource]
    meta: dict[str, Any] = Field(default_factory=dict)
    links: dict[str, Any] = Field(default_factory=dict)
    included: list[RingJSONAPIResource] = Field(default_factory=list)


class RingWHEPSession(BaseModel):
    location: str = Field(min_length=1)
    sdp_answer: str = Field(min_length=1)


@dataclass(frozen=True)
class RingConnectionStatus:
    configured: bool
    base_url: str
    last_test_at: str | None
    last_success: bool | None
    last_error_code: str | None
    last_error: str | None
    verified_operations: dict[str, bool]
    device_count: int | None
    source: str = "ring_api"
    simulator_separate: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "base_url": self.base_url,
            "last_test_at": self.last_test_at,
            "last_success": self.last_success,
            "last_error_code": self.last_error_code,
            "last_error": self.last_error,
            "verified_operations": self.verified_operations,
            "device_count": self.device_count,
            "source": self.source,
            "simulator_separate": self.simulator_separate,
        }


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch_ms(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value if value > 10_000_000_000 else value * 1000)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return _epoch_ms(int(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1000)
        except ValueError as exc:
            raise RingIntegrationError("Ring event timestamp is not parseable", code="malformed_payload") from exc
    raise RingIntegrationError("Ring event timestamp is missing or invalid", code="malformed_payload")


class RingAdapter:
    """Server-side adapter for documented Ring Partner API operations.

    The adapter never returns or logs the bearer token. HTTP calls are isolated
    here so the temporal verifier remains deterministic and testable without
    Ring credentials.
    """

    def __init__(self, *, access_token: str | None = None, base_url: str | None = None, client: httpx.Client | None = None):
        self.access_token = access_token if access_token is not None else os.getenv("RING_ACCESS_TOKEN", "").strip()
        self.base_url = (base_url or os.getenv("RING_API_BASE_URL", DEFAULT_RING_API_BASE_URL)).rstrip("/")
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.access_token)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self.configured:
            raise RingIntegrationError("RING_ACCESS_TOKEN is not configured", code="missing_token")
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers.setdefault("Accept", "application/json")
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.Client(base_url=self.base_url, timeout=15.0)
        try:
            response = client.request(method, path, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise RingIntegrationError("Ring API request could not be completed", code="network_error") from exc
        finally:
            if owns_client:
                client.close()
        if response.status_code in (401, 403):
            raise RingIntegrationError("Ring access token was rejected", code="unauthorized", status_code=response.status_code)
        if response.status_code >= 400:
            raise RingIntegrationError(f"Ring API returned HTTP {response.status_code}", code="http_error", status_code=response.status_code)
        return response

    @staticmethod
    def _json(response: httpx.Response) -> RingJSONAPIResponse:
        try:
            return RingJSONAPIResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise RingIntegrationError("Ring API returned a malformed JSON:API payload", code="malformed_payload") from exc

    @staticmethod
    def sanitize_resource(resource: RingJSONAPIResource) -> dict[str, Any]:
        return {
            "type": resource.type,
            "id": resource.id,
            "attributes": resource.attributes,
            "relationships": resource.relationships,
        }

    def discover_devices(self) -> dict[str, Any]:
        """Call the documented Device Discovery operation: GET /v1/devices."""
        response = self._request("GET", DEVICE_DISCOVERY_PATH)
        parsed = self._json(response)
        return {
            "data": [self.sanitize_resource(resource) for resource in parsed.data],
            "meta": parsed.meta,
            "links": parsed.links,
            "included": [self.sanitize_resource(resource) for resource in parsed.included],
            "operation": "device_discovery",
            "endpoint": DEVICE_DISCOVERY_PATH,
        }

    def event_history(self, device_id: str, *, event_types: list[str] | None = None, page_key: str | None = None) -> dict[str, Any]:
        """Call the documented Event History operation for one device."""
        params: dict[str, str] = {}
        if event_types:
            params["event_types"] = ",".join(event_types)
        if page_key:
            params["page[key]"] = page_key
        response = self._request("GET", EVENT_HISTORY_PATH.format(device_id=device_id), params=params)
        parsed = self._json(response)
        for resource in parsed.data:
            if resource.type != "history-events":
                raise RingIntegrationError("Ring Event History returned an unexpected resource type", code="malformed_payload")
        return {
            "data": [self.sanitize_resource(resource) for resource in parsed.data],
            "meta": parsed.meta,
            "links": parsed.links,
            "included": [self.sanitize_resource(resource) for resource in parsed.included],
            "operation": "event_history",
            "endpoint": EVENT_HISTORY_PATH.format(device_id=device_id),
        }

    def history_to_events(self, history: dict[str, Any], *, device_id: str) -> list[Event]:
        """Map validated Ring history resources into provenance-preserving facts."""
        events: list[Event] = []
        received_ms = int(time.time() * 1000)
        for resource in history.get("data", []):
            attributes = resource.get("attributes") or {}
            start_ms = _epoch_ms(attributes.get("start"))
            event_type = str(attributes.get("event_type") or "unknown")
            events.append(Event(
                id=f"ring:{device_id}:{resource['id']}",
                kind=EventKind.RING_EVENT,
                at=start_ms,
                workflow_id=f"ring-history:{device_id}",
                action_id=f"ring-device:{device_id}",
                source="ring_api",
                event_time=start_ms,
                processing_time=received_ms,
                correlation_id=f"ring:{device_id}",
                entity_id=device_id,
                actor="ring",
                provenance="ring_api",
                state_outcome="observed",
                payload={
                    "ring_resource_type": resource.get("type"),
                    "ring_event_type": event_type,
                    "is_third_party_reviewed": attributes.get("is_third_party_reviewed"),
                    "end": attributes.get("end"),
                    "relationships": resource.get("relationships") or {},
                },
            ))
        return events

    def create_whep_session(self, device_id: str, sdp_offer: str, *, component_id: str | None = None) -> RingWHEPSession:
        """Create a documented WHEP session using a raw SDP offer.

        The Ring API returns HTTP 201, an SDP answer in the response body, and
        a Location header for the temporary session. The session is not stored
        or reused by Veylith.
        """
        if not sdp_offer.strip():
            raise RingIntegrationError("SDP offer is required", code="invalid_request")
        params = {"component_id": component_id} if component_id else None
        response = self._request("POST", WHEP_SESSION_PATH.format(device_id=device_id), params=params, content=sdp_offer, headers={"Content-Type": "application/sdp", "Accept": "application/sdp"})
        location = response.headers.get("location", "").strip()
        answer = response.text.strip()
        if response.status_code != 201 or not location or not answer:
            raise RingIntegrationError("Ring WHEP response did not include a session Location and SDP answer", code="malformed_response", status_code=response.status_code)
        return RingWHEPSession(location=location, sdp_answer=answer)


def ring_status(*, last_test_at: str | None = None, last_success: bool | None = None, last_error_code: str | None = None, last_error: str | None = None, device_count: int | None = None, verified_operations: dict[str, bool] | None = None) -> dict[str, Any]:
    adapter = RingAdapter()
    return RingConnectionStatus(
        configured=adapter.configured,
        base_url=adapter.base_url,
        last_test_at=last_test_at,
        last_success=last_success,
        last_error_code=last_error_code,
        last_error=last_error,
        verified_operations=verified_operations or {"device_discovery": False, "event_history": False, "whep_session_creation": False},
        device_count=device_count,
    ).as_dict()
