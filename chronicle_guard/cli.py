from __future__ import annotations

import argparse
import json
from pathlib import Path

from .export import evidence_export
from .scenarios import SCENARIOS
from .verifier import enforce_temporal, reduce_counterexample, verify


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Chronicle Guard deterministic traces")
    parser.add_argument("command", choices=["list", "run", "replay"])
    parser.add_argument("value", nargs="?", default="revoked_approval_race")
    args = parser.parse_args()

    if args.command == "list":
        print(json.dumps([factory().model_dump(mode="json") for factory in SCENARIOS.values()], indent=2))
        return

    if args.command == "run":
        scenario = SCENARIOS[args.value]()
        events = scenario.events
    else:
        payload = json.loads(Path(args.value).read_text(encoding="utf-8"))
        events = payload["events"]
        from .model import Event
        events = [Event.model_validate(event) for event in events]

    result = verify(events)
    enforced_state, blocked = enforce_temporal(events)
    output = {
        "valid": result.valid,
        "violations": result.model_dump(mode="json")["violations"],
        "counterexample_event_ids": [event.id for event in reduce_counterexample(events)],
        "blocked_event_ids": blocked,
        "protected_state": enforced_state.model_dump(mode="json"),
        "evidence": evidence_export(events),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
