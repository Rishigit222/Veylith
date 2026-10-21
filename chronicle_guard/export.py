from __future__ import annotations

import hashlib
import json

from .model import Event
from .state import replay
from .verifier import enforce_temporal, verify


def evidence_export(events: list[Event], include_state: bool = True) -> dict:
    event_rows = [event.model_dump(mode="json") for event in events]
    previous_hash = "0" * 64
    hash_chain = []
    for row in event_rows:
        canonical = json.dumps({"previous_hash": previous_hash, "event": row}, sort_keys=True, separators=(",", ":"))
        current_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        hash_chain.append({"event_id": row["id"], "previous_hash": previous_hash, "hash": current_hash})
        previous_hash = current_hash
    result = {
        "format": "chronicle-guard-evidence-v1",
        "generated_at": "deterministic-from-input",
        "event_count": len(events),
        "events": event_rows,
        "hash_chain": hash_chain,
        "evidence_note": "Hash linkage makes later changes detectable; it does not prove event authenticity or truth.",
        "verification": verify(events).model_dump(mode="json"),
    }
    if include_state:
        result["state"] = replay(events).model_dump(mode="json")
        enforced_state, blocked_event_ids = enforce_temporal(events)
        result["enforcement"] = {
            "blocked_event_ids": blocked_event_ids,
            "protected_state": enforced_state.model_dump(mode="json"),
        }
    return result
