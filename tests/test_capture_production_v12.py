from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from agent_os.capture import CapturedObservation
from agent_os.capture_production import ScreenCapture
from agent_os.content_trust import ContentTrustAnalyzer
from agent_os.models import Rectangle, TargetInfo, UIElement
from agent_os.observation_contract import ObservationLedger
from agent_os.windows import UIASnapshot


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _observation() -> CapturedObservation:
    image = Image.new("RGB", (200, 100), "white")
    element = UIElement(
        element_id="E0001",
        name="Event title",
        control_type="textbox",
        rect=Rectangle(left=20, top=20, width=100, height=20),
        center_x=350,
        center_y=300,
        source="browser",
        editable=True,
        required=True,
    )
    return CapturedObservation(
        target=TargetInfo(
            spec="browser-session",
            kind="browser",
            label="Create Event",
            rect=Rectangle(left=0, top=0, width=200, height=100),
            backend="browser",
            url="https://example.test/events/create",
            identity="browser:create-event",
            capture_source="playwright",
            lease_id="lease-1",
        ),
        monitors=[],
        windows=[],
        uia=UIASnapshot(elements=[element], wrappers={}),
        original_image=image,
        api_image_bytes=_png(image),
        screenshot_path=None,
        capture_token="capture-1",
        state={},
    )


def _capture() -> ScreenCapture:
    capture = ScreenCapture.__new__(ScreenCapture)
    capture.settings = SimpleNamespace(
        screenshot_max_width=1600,
        screenshot_max_height=1200,
    )
    capture.ledger = ObservationLedger()
    capture.trust = ContentTrustAnalyzer()
    capture._lease_generation = 3
    capture._pending_zoom = None
    return capture


def test_production_capture_adds_geometry_capabilities_and_contract() -> None:
    capture = _capture()
    observation = capture._production(_observation())

    assert observation.state["image_geometry"]["original_width"] == 200
    assert observation.state["image_geometry"]["model_width"] == 200
    assert observation.state["capabilities"]["semantic_fill"] is True
    assert observation.state["observation_contract"]["lease_generation"] == 3
    assert observation.state["content_trust"]["flagged"] is False


def test_zoom_crop_is_inspection_only_and_has_scale_metadata() -> None:
    capture = _capture()
    capture.request_zoom((0, 0, 500, 1000))
    observation = capture._production(_observation())

    zoom = observation.state["zoom"]
    geometry = observation.state["image_geometry"]
    assert zoom["active"] is True
    assert zoom["crop_width"] == 100
    assert zoom["crop_height"] == 100
    assert geometry["model_width"] == 100
    assert geometry["scale_x"] == 2.0
    assert "inspection-only" in zoom["rule"]
