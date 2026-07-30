from __future__ import annotations

from agent_os.capture import CapturedObservation, ScreenCapture as BaseScreenCapture
from agent_os.visual_grounding import render_set_of_mark, save_grounding_image


class ScreenCapture(BaseScreenCapture):
    """Capture normal evidence while sending a grounded model-only image."""

    def _ground(self, observation: CapturedObservation) -> CapturedObservation:
        if not observation.uia.elements:
            observation.state.update(
                {
                    "visual_grounding": "none",
                    "coordinate_space": "normalized-0-1000 over the captured target",
                }
            )
            return observation

        marked = render_set_of_mark(
            observation.original_image,
            observation.uia.elements,
            max_marks=self.settings.max_grounding_marks,
        )
        grounded_path = save_grounding_image(observation.screenshot_path, marked)
        observation.api_image_bytes = self._api_bytes(marked)
        observation.state.update(
            {
                "visual_grounding": "set-of-mark",
                "grounding_image": str(grounded_path) if grounded_path else None,
                "grounding_marks": min(
                    len(observation.uia.elements),
                    self.settings.max_grounding_marks,
                ),
                "coordinate_space": (
                    "element rectangles use browser CSS pixels for browser captures; "
                    "decision x/y use normalized 0-1000 coordinates"
                ),
            }
        )
        return observation

    def capture(self, *args, **kwargs) -> CapturedObservation:
        return self._ground(super().capture(*args, **kwargs))

    def capture_browser(self, *args, **kwargs) -> CapturedObservation:
        return self._ground(super().capture_browser(*args, **kwargs))
