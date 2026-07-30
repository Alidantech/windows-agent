from __future__ import annotations

from io import BytesIO

from PIL import Image

from agent_os.capture import CapturedObservation
from agent_os.confirmation_policy import ConfirmationMode
from agent_os.confirmation_policy_v2 import ConfirmationPolicy
from agent_os.models import AgentDecision, Rectangle, TargetInfo, UIElement
from agent_os.windows import UIASnapshot


def _email_observation() -> CapturedObservation:
    image = Image.new("RGB", (80, 40), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    element = UIElement(
        element_id="E0001",
        name="Email address",
        control_type="textbox",
        rect=Rectangle(left=5, top=5, width=60, height=20),
        center_x=450,
        center_y=375,
        source="browser",
        editable=True,
    )
    return CapturedObservation(
        target=TargetInfo(
            spec="browser-session",
            kind="browser",
            label="Contact form",
            rect=Rectangle(left=0, top=0, width=80, height=40),
            backend="browser",
            url="https://example.test/contact",
            identity="browser:contact",
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
        state={},
    )


def _decision() -> AgentDecision:
    return AgentDecision(
        action="fill_element",
        element_id="E0001",
        text="person@example.com",
        reason="Fill the email field",
    )


def test_sensitive_form_entry_requires_destination_specific_approval() -> None:
    assessment = ConfirmationPolicy().assess(
        _decision(),
        _email_observation(),
        task="Review the contact form",
    )
    assert assessment.mode == ConfirmationMode.PREAPPROVAL
    assert assessment.risk_code == "TRANSMIT_SENSITIVE_DATA"


def test_explicit_sensitive_destination_preapproval_is_accepted() -> None:
    assessment = ConfirmationPolicy().assess(
        _decision(),
        _email_observation(),
        task=(
            "Enter my email address person@example.com into the contact form at "
            "example.test."
        ),
    )
    assert assessment.mode == ConfirmationMode.ALLOW
    assert assessment.risk_code == "SENSITIVE_TRANSMISSION_PREAPPROVED"
