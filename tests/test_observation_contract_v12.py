from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from agent_os.capture import CapturedObservation
from agent_os.lease import TargetLease
from agent_os.models import ExecutionResult, Rectangle, TargetInfo
from agent_os.observation_contract import ObservationContractError, ObservationLedger
from agent_os.windows import UIASnapshot


def _png() -> bytes:
    image = Image.new("RGB", (20, 20), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _observation(lease_id: str = "lease-1") -> CapturedObservation:
    image = Image.new("RGB", (20, 20), "white")
    return CapturedObservation(
        target=TargetInfo(
            spec="browser-session",
            kind="browser",
            label="Test page",
            rect=Rectangle(left=0, top=0, width=20, height=20),
            backend="browser",
            url="https://example.test/form",
            identity="browser:chromium:https://example.test/form",
            capture_source="playwright",
            lease_id=lease_id,
        ),
        monitors=[],
        windows=[],
        uia=UIASnapshot(elements=[], wrappers={}),
        original_image=image,
        api_image_bytes=_png(),
        screenshot_path=None,
        capture_token="capture-1",
        state={},
    )


def _lease(lease_id: str = "lease-1") -> TargetLease:
    return TargetLease(
        requested_spec="monitor:1",
        controller_hwnd=100,
        controller_title="Controller",
        lease_id=lease_id,
        backend="browser",
        state="bound",
        generation=0,
    )


def test_observation_is_consumed_exactly_once() -> None:
    observation = _observation()
    lease = _lease()
    ledger = ObservationLedger()
    identity = ledger.stamp(observation, lease_generation=lease.generation)

    consumed = ledger.consume(
        observation,
        lease,
        action="click_element",
        requested_observation_id=identity.observation_id,
    )

    assert consumed == identity.observation_id
    assert observation.state["observation_contract"]["status"] == "consumed"
    with pytest.raises(ObservationContractError, match="already consumed"):
        ledger.consume(observation, lease, action="click_element")


def test_observation_rejects_wrong_id_and_lease_generation() -> None:
    observation = _observation()
    lease = _lease()
    ledger = ObservationLedger()
    ledger.stamp(observation, lease_generation=0)

    with pytest.raises(ObservationContractError, match="does not match"):
        ledger.consume(
            observation,
            lease,
            action="scroll",
            requested_observation_id="obs-wrong",
        )

    lease.generation = 1
    with pytest.raises(ObservationContractError, match="lease changed"):
        ledger.consume(observation, lease, action="scroll")


def test_unknown_outcome_is_never_reported_as_ok() -> None:
    result = ExecutionResult(
        ok=True,
        status="unknown_outcome",
        summary="Input may have happened but refresh failed.",
    )

    assert result.ok is False
    assert result.status == "unknown_outcome"
