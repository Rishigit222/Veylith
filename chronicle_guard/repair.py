from __future__ import annotations

from .model import RepairRequest
from .verifier import verify


def validate_repair(request: RepairRequest) -> dict:
    original = verify(request.events)
    dropped = set(request.drop_event_ids)
    repaired_events = [event for event in request.events if event.id not in dropped]
    repaired = verify(repaired_events)
    return {
        "original": original,
        "repaired": repaired,
        "valid_repair": (not original.valid) and repaired.valid,
        "events": repaired_events,
    }
