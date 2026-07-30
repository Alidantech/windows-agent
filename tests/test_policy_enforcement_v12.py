from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from agent_os.capture import CapturedObservation
from agent_os.models import AgentDecision, Rectangle, TargetInfo, UIElement
from agent_os.tools_production import ToolExecutor
from agent_os.windows import UIASnapshot


def _observation(*, flagged: bool = False, element_name: str = "Open details"):
    image = Image.new("RGB", (50, 50), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    element = UIElement(
        element_id="E0001",
        name=element_name,
        control_type="button",
        rect=Rectangle(left=5, top=5, width=30, height=15),
        center_x=400,
        center_y=250,
        source="browser",
    )
    return CapturedObservation(
        target=TargetInfo(
            spec="browser-session",
            kind="browser",
            label="Example",
            rect=Rectangle(left=0, top=0, width=50, height=50),
            backend="browser",
            url="https://app.example.test/form",
            identity="browser:example",
            capture_source="playwright",
            lease_id="lease-1",
        ),
        monitors=[],
        windows=[],
        uia=UIASnapshot(elements=[element], wrappers={}),
        original_image=image,
        api_image_bytes=buffer.getvalue(),
        screenshot_path=None,
        capture_token="capture",
        state={
            "content_trust": {
                "flagged": flagged,
                "severity": "high" if flagged else "none",
                "indicators": ["instruction_override"] if flagged else [],
            }
        },
    )


def _executor(*, domains: str = "", enforce: bool = False, injection: str = "block_transmission"):
    executor = ToolExecutor.__new__(ToolExecutor)
    executor.settings = SimpleNamespace(
        browser_allowed_domains=domains,
        enforce_domain_allowlist=enforce,
        prompt_injection_policy=injection,
    )
    return executor


def test_domain_allowlist_accepts_exact_and_subdomains() -> None:
    executor = _executor(domains="example.test", enforce=True)
    observation = _observation()
    exact = executor._domain_policy(
        AgentDecision(
            action="open_url",
            url="https://example.test",
            reason="Open the allowed site",
        ),
        observation,
    )
    subdomain = executor._domain_policy(
        AgentDecision(
            action="open_url",
            url="https://app.example.test/form",
            reason="Open the allowed subdomain",
        ),
        observation,
    )
    assert exact is None
    assert subdomain is None


def test_domain_allowlist_blocks_unlisted_domain() -> None:
    executor = _executor(domains="example.test", enforce=True)
    result = executor._domain_policy(
        AgentDecision(
            action="open_url",
            url="https://attacker.test",
            reason="Open another site",
        ),
        _observation(),
    )
    assert result is not None
    assert result.ok is False
    assert result.details["domain_policy"] == "blocked"


def test_prompt_injection_blocks_transmission_but_not_read_only_actions() -> None:
    executor = _executor(injection="block_transmission")
    observation = _observation(flagged=True, element_name="Submit and send data")
    send = executor._content_policy(
        AgentDecision(
            action="click_element",
            element_id="E0001",
            reason="Submit the data",
        ),
        observation,
    )
    scroll = executor._content_policy(
        AgentDecision(action="scroll", amount=1, reason="Read more"),
        observation,
    )
    assert send is not None
    assert send.ok is False
    assert scroll is None
