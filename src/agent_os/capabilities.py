from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_os.capture import CapturedObservation


@dataclass(frozen=True)
class CapabilityProfile:
    surface: str
    semantic_elements: bool
    accessibility_text: bool
    visual_capture: bool
    semantic_click: bool
    semantic_fill: bool
    semantic_select: bool
    targeted_scroll: bool
    coordinate_fallback: bool
    zoom_inspection: bool
    occlusion_resistant_capture: bool

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def capability_profile(observation: CapturedObservation) -> CapabilityProfile:
    browser = observation.target.backend == "browser"
    elements = observation.uia.elements
    roles = {item.control_type.casefold() for item in elements}
    semantic = bool(elements)
    accessibility = bool(
        observation.state.get("aria_snapshot")
        or observation.state.get("desktop_semantic_map")
        or semantic
    )
    return CapabilityProfile(
        surface="browser" if browser else "windows",
        semantic_elements=semantic,
        accessibility_text=accessibility,
        visual_capture=bool(observation.api_image_bytes),
        semantic_click=semantic,
        semantic_fill=bool(
            roles & {"textbox", "edit", "document", "combobox"}
            or any(item.editable for item in elements)
        ),
        semantic_select=browser and bool(roles & {"combobox", "select", "listbox"}),
        targeted_scroll=browser,
        coordinate_fallback=True,
        zoom_inspection=True,
        occlusion_resistant_capture=(
            observation.target.capture_source in {"print-window", "playwright"}
        ),
    )
