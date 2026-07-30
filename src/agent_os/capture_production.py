from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image

from agent_os.capabilities import capability_profile
from agent_os.capture import CapturedObservation
from agent_os.capture_runtime import ScreenCapture as BaseScreenCapture
from agent_os.content_trust import ContentTrustAnalyzer
from agent_os.observation_contract import ObservationLedger


class ScreenCapture(BaseScreenCapture):
    """Stamp single-use observations and choose semantic, visual, or hybrid context."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ledger = ObservationLedger()
        self.trust = ContentTrustAnalyzer()
        self._lease_generation = 0
        self._pending_zoom: tuple[int, int, int, int] | None = None

    def set_lease_generation(self, generation: int) -> None:
        self._lease_generation = int(generation)

    def request_zoom(self, region: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = region
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Zoom region must have positive width and height.")
        self._pending_zoom = region

    @staticmethod
    def _api_dimensions(data: bytes) -> tuple[int, int]:
        with Image.open(BytesIO(data)) as image:
            return image.width, image.height

    @staticmethod
    def _accessibility_quality(observation: CapturedObservation) -> dict[str, object]:
        elements = observation.uia.elements
        named = sum(bool(item.name.strip()) for item in elements)
        actionable = sum(
            item.control_type.casefold()
            in {
                "button",
                "link",
                "textbox",
                "edit",
                "combobox",
                "listbox",
                "checkbox",
                "radio",
                "menuitem",
                "tab",
            }
            for item in elements
        )
        focused = next((item.element_id for item in elements if item.focused), None)
        quality = (
            "strong"
            if actionable >= 3 and named >= max(1, actionable // 2)
            else "partial"
            if elements
            else "none"
        )
        return {
            "quality": quality,
            "element_count": len(elements),
            "named_count": named,
            "actionable_count": actionable,
            "focused_element_id": focused,
        }

    @staticmethod
    def _desktop_semantic_map(observation: CapturedObservation) -> dict[str, object]:
        controls = []
        for item in observation.uia.elements[:180]:
            controls.append(
                {
                    "element_id": item.element_id,
                    "role": item.control_type,
                    "name": item.name,
                    "enabled": item.enabled,
                    "focused": item.focused,
                    "editable": item.editable,
                    "automation_id": item.automation_id,
                    "rect": item.rect.model_dump(),
                }
            )
        target_window = next(
            (item for item in observation.windows if item.hwnd == observation.target.hwnd),
            None,
        )
        return {
            "window": target_window.model_dump() if target_window else None,
            "controls": controls,
            "focused": next((item for item in controls if item["focused"]), None),
            "rule": (
                "Desktop element indexes belong only to this observation. Re-observe after every "
                "click, key, scroll, focus change, modal, resize, or window change."
            ),
        }

    def _apply_zoom(self, observation: CapturedObservation) -> None:
        region = self._pending_zoom
        if region is None:
            return
        self._pending_zoom = None
        width, height = observation.original_image.size
        x1, y1, x2, y2 = region
        left = max(0, min(width - 1, round(x1 * max(1, width - 1) / 1000)))
        top = max(0, min(height - 1, round(y1 * max(1, height - 1) / 1000)))
        right = max(left + 1, min(width, round(x2 * max(1, width - 1) / 1000)))
        bottom = max(top + 1, min(height, round(y2 * max(1, height - 1) / 1000)))
        crop = observation.original_image.crop((left, top, right, bottom))
        observation.api_image_bytes = self._api_bytes(crop)
        observation.state["zoom"] = {
            "active": True,
            "source_observation_region_normalized": [x1, y1, x2, y2],
            "source_region_pixels": [left, top, right, bottom],
            "crop_width": crop.width,
            "crop_height": crop.height,
            "rule": (
                "The model image is a zoomed inspection crop. Do not use its coordinates "
                "for input; return to a fresh full observation before acting."
            ),
        }

    def _production(self, observation: CapturedObservation) -> CapturedObservation:
        self._apply_zoom(observation)
        model_width, model_height = self._api_dimensions(observation.api_image_bytes)
        original_width, original_height = observation.original_image.size
        quality = self._accessibility_quality(observation)
        observation_mode = (
            "semantic"
            if quality["quality"] == "strong" and observation.target.backend == "browser"
            else "hybrid"
            if quality["quality"] != "none"
            else "visual"
        )
        observation.state.update(
            {
                "observation_mode": observation_mode,
                "accessibility_quality": quality,
                "image_geometry": {
                    "original_width": original_width,
                    "original_height": original_height,
                    "model_width": model_width,
                    "model_height": model_height,
                    "scale_x": original_width / max(1, model_width),
                    "scale_y": original_height / max(1, model_height),
                    "coordinate_rule": (
                        "Normalized input coordinates are valid only for this observation. "
                        "Zoom crops are inspection-only; semantic element actions are preferred."
                    ),
                },
            }
        )
        if observation.target.backend == "desktop":
            observation.state["desktop_semantic_map"] = self._desktop_semantic_map(observation)
            if observation.target.hwnd and hasattr(self.windows, "owned_windows"):
                observation.state["owned_modals"] = self.windows.owned_windows(
                    observation.target.hwnd
                )
        trust = self.trust.analyze(observation)
        observation.state["content_trust"] = trust.as_dict()
        observation.state["capabilities"] = capability_profile(observation).as_dict()
        self.ledger.stamp(
            observation,
            lease_generation=self._lease_generation,
        )
        return observation

    def capture(self, *args: Any, **kwargs: Any) -> CapturedObservation:
        return self._production(super().capture(*args, **kwargs))

    def capture_browser(self, *args: Any, **kwargs: Any) -> CapturedObservation:
        return self._production(super().capture_browser(*args, **kwargs))


__all__ = ["ScreenCapture"]
