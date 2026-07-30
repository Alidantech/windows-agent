from __future__ import annotations

import hashlib
import json

from agent_os.runlog import RunLogger


def _hash(record: dict[str, object]) -> str:
    payload = dict(record)
    payload.pop("event_hash", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_runlog_events_form_a_hash_chain(tmp_path) -> None:
    logger = RunLogger(tmp_path, "test task", "monitor:1", "test-model")
    logger.event("observation", summary="Captured state", observation_id="obs-1")
    logger.event("tool_result", summary="Clicked", status="verified_success")

    records = [
        json.loads(line)
        for line in logger.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["sequence"] for record in records] == [1, 2]
    assert records[0]["previous_hash"] == "GENESIS"
    assert records[1]["previous_hash"] == records[0]["event_hash"]
    assert records[0]["event_hash"] == _hash(records[0])
    assert records[1]["event_hash"] == _hash(records[1])

    manifest = json.loads(logger.manifest_path.read_text(encoding="utf-8"))
    assert manifest["event_log"]["events"] == 2
    assert manifest["event_log"]["head"] == records[1]["event_hash"]
