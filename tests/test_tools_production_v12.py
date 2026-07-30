from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from agent_os.capture import CapturedObservation
from agent_os.confirmation_policy import ConfirmationPolicy
from agent_os.lease import TargetLease
from agent_os.metrics import RunMetrics
from agent_os.models import AgentDecision, ExecutionResult, Rectangle, TargetInfo
from agent_os.observation_contract import ObservationLedger
from agent_os.recovery import RecoveryTracker
from agent_os.tools_controls import ToolExecutor as BaseToolExecutor
from agent_os.tools_production import ToolExecutor
from agent_os.windows import UIASnapshot


def _observation() -> CapturedObservation:
    image = Image.new("RGB", (40, 40), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return CapturedObservation(
        target=TargetInfo(
            spec="browser-session",
            kind="browser",
            label="Example",
            rect=Rectangle(left=0, top=0, width=40, height=40),
            backend="browser",
            url="https://example.test",
            identity="browser:example",
            capture_source="playwright",
            lease_id="lease-1",
        ),
        monitors=[],
        windows=[],
        uia=UIASnapshot(elements=[], wrappers={}),
        original_image=image,
        api_image_bytes=buffer.getvalue(),
        screenshot_path=None,
        capture_token="capture-1",
        state={"content_trust": {"flagged": False}},
    )


def _lease() -> TargetLease:
    return TargetLease(
        requested_spec="monitor:1",
        controller_hwnd=10,
        controller_title="Controller",
        lease_id="lease-1",
        backend="browser",
        state="bound",
        generation=0,
    )


class _Capture:
    def __init__(self) -> None:
        self.zoom = None

    def request_zoom(self, region) -> None:
        self.zoom = region

    def set_lease_generation(self, _generation: int) -> None:
        return None


def _executor(capture=None) -> ToolExecutor:
    executor = ToolExecutor.__new__(ToolExecutor)
    executor.settings = SimpleNamespace(
        max_repeated_strategy=2,
        max_unknown_outcomes=1,
        max_locator_recoveries=2,
        max_coordinate_fallbacks=3,
        max_consecutive_no_change=2,
        enforce_domain_allowlist=False,
        browser_allowed_domains="",
        prompt_injection_policy="block_transmission",
    )
    executor.capture = capture or _Capture()
    executor.confirmations = ConfirmationPolicy()
    executor.recovery = RecoveryTracker()
    executor.metrics = RunMetrics()
    executor.task = "Inspect the page"
    executor._current_observation = None
    executor.windows = SimpleNamespace()
    executor.configure_run(executor.task)
    return executor


def _stamp(observation: CapturedObservation, lease: TargetLease) -> str:
    identity = ObservationLedger().stamp(
        observation,
        lease_generation=lease.generation,
    )
    return identity.observation_id


def test_replayed_observation_is_rejected(tmp_path) -> None:
    observation = _observation()
    lease = _lease()
    observation_id = _stamp(observation, lease)
    executor = _executor()
    decision = AgentDecision(
        action="inspect_region",
        observation_id=observation_id,
        x=0,
        y=0,
        x2=500,
        y2=500,
        reason="Inspect the upper-left region",
    )

    first = executor.execute(decision, observation, lease, tmp_path)
    second = executor.execute(decision, observation, lease, tmp_path)

    assert first.status == "verified_success"
    assert second.status == "verified_failure"
    assert "already consumed" in second.summary


def test_type_text_requires_fresh_verified_focus(tmp_path) -> None:
    observation = _observation()
    lease = _lease()
    observation_id = _stamp(observation, lease)
    executor = _executor()
    result = executor.execute(
        AgentDecision(
            action="type_text",
            observation_id=observation_id,
            text="unsafe free typing",
            reason="Type into the page",
        ),
        observation,
        lease,
        tmp_path,
    )

    assert result.ok is False
    assert result.status == "verified_failure"
    assert result.details["focus_contract"] == "failed"


def test_inspect_region_queues_zoom_without_input(tmp_path) -> None:
    observation = _observation()
    lease = _lease()
    observation_id = _stamp(observation, lease)
    capture = _Capture()
    executor = _executor(capture)
    result = executor.execute(
        AgentDecision(
            action="inspect_region",
            observation_id=observation_id,
            x=100,
            y=200,
            x2=700,
            y2=800,
            reason="Read small text",
        ),
        observation,
        lease,
        tmp_path,
    )

    assert result.ok is True
    assert capture.zoom == (100, 200, 700, 800)
    assert result.details["input"] == "inspection-only"
    assert (tmp_path / "metrics.json").exists()


def test_refresh_failure_returns_unknown_outcome(monkeypatch, tmp_path) -> None:
    observation = _observation()
    lease = _lease()
    observation_id = _stamp(observation, lease)
    executor = _executor()

    monkeypatch.setattr(
        BaseToolExecutor,
        "execute",
        lambda _self, _decision, _observation, _lease, _artifact_dir: ExecutionResult(
            ok=True,
            summary="Input was sent.",
            details={"input": "browser-semantic"},
        ),
    )

    def fail_refresh(_lease):
        raise RuntimeError("capture unavailable")

    executor._refresh = fail_refresh
    result = executor.execute(
        AgentDecision(
            action="click_element",
            observation_id=observation_id,
            element_id="E0001",
            reason="Click the control",
            expected_change="The panel opens",
        ),
        observation,
        lease,
        tmp_path,
    )

    assert result.ok is False
    assert result.status == "unknown_outcome"
    assert result.details["required_next_action"] == "observe"
    assert "Do not repeat" in result.summary
