from __future__ import annotations

from agent_os.browser import BrowserElementRef
from agent_os.models import ExecutionResult
from agent_os.tools_runtime import ToolExecutor as BaseToolExecutor


class ToolExecutor(BaseToolExecutor):
    """Add verified semantic select and measured scroll behavior."""

    @staticmethod
    def _is_select_control(element) -> bool:
        role = str(element.control_type or "").casefold()
        tag = str(element.tag or "").casefold()
        return tag == "select" or role in {
            "select",
            "combobox",
            "listbox",
        }

    def _select_result(self, decision, observation) -> ExecutionResult:
        assert decision.element_id is not None
        wrapper, element = self._element(observation, decision.element_id)
        if not isinstance(wrapper, BrowserElementRef) or element is None:
            return ExecutionResult(
                ok=False,
                summary=(
                    f"Select target {decision.element_id} is unavailable in the captured map. "
                    "Capture a fresh semantic page state and retry the same semantic field."
                ),
            )
        if not self._is_select_control(element):
            return ExecutionResult(
                ok=False,
                summary=(
                    f"{element.name!r} is not a select or combobox. "
                    "Use fill_element for text fields or click_element for buttons."
                ),
                details={"element_id": decision.element_id},
            )
        requested = decision.option if decision.action == "select_option" else decision.text
        assert requested is not None
        summary, state = self.browser.select_option_state(
            wrapper,
            element,
            requested,
        )
        return ExecutionResult(
            ok=True,
            summary=summary,
            details={
                "input": "browser-semantic-select",
                "element_id": decision.element_id,
                "requested_option": requested,
                **state,
            },
        )

    def _browser_execute(self, decision, observation, lease, artifact_dir):
        action = decision.action

        if action == "select_option":
            return self._select_result(decision, observation)

        # Backward compatibility for models that still use fill_element on a select.
        if action == "fill_element" and decision.element_id:
            wrapper, element = self._element(observation, decision.element_id)
            if (
                isinstance(wrapper, BrowserElementRef)
                and element is not None
                and self._is_select_control(element)
            ):
                return self._select_result(decision, observation)

        if action == "scroll":
            assert decision.amount is not None
            wrapper = None
            element = None
            if decision.element_id:
                wrapper, element = self._element(observation, decision.element_id)
                if not isinstance(wrapper, BrowserElementRef) or element is None:
                    return ExecutionResult(
                        ok=False,
                        summary=(
                            f"Scroll target {decision.element_id} is unavailable. "
                            "Use the current semantic page map to select a visible scroll container, "
                            "or omit element_id to scroll the best current container."
                        ),
                    )
            summary, state = self.browser.scroll_state(
                decision.amount,
                wrapper if isinstance(wrapper, BrowserElementRef) else None,
            )
            moved = int(state.get("observed_pixels") or 0)
            if moved == 0:
                boundary = (
                    "bottom"
                    if decision.amount > 0 and state.get("at_end")
                    else "top"
                    if decision.amount < 0 and state.get("at_start")
                    else "a non-scrollable boundary"
                )
                return ExecutionResult(
                    ok=False,
                    summary=(
                        f"No scrolling occurred; the target is already at {boundary}. "
                        "Do not repeat the same scroll. Choose another scroll container, "
                        "reverse direction, or continue with a visible semantic element."
                    ),
                    details={"input": "browser-wheel", **state},
                )
            return ExecutionResult(
                ok=True,
                summary=summary,
                details={"input": "browser-wheel", **state},
            )

        if action == "click_element" and decision.element_id:
            wrapper, element = self._element(observation, decision.element_id)
            if isinstance(wrapper, BrowserElementRef) and element is not None:
                tag = str(element.tag or "").casefold()
                role = str(element.control_type or "").casefold()
                if tag == "select":
                    return ExecutionResult(
                        ok=False,
                        summary=(
                            f"{element.name!r} is a native select. Use select_option on this "
                            "same semantic element with an exact available option label."
                        ),
                        details={
                            "input": "browser-select-guidance",
                            "element_id": decision.element_id,
                        },
                    )
                if role == "combobox":
                    if element.aria_expanded is True:
                        return ExecutionResult(
                            ok=False,
                            summary=(
                                f"Combobox {element.name!r} is already open. Do not click it "
                                "again. Use select_option with an exact visible option, or scroll "
                                "the listbox when the desired option is below the viewport."
                            ),
                            details={
                                "input": "browser-select-guidance",
                                "element_id": decision.element_id,
                                "aria_expanded": True,
                            },
                        )
                    summary, state = self.browser.open_combobox_state(wrapper, element)
                    return ExecutionResult(
                        ok=True,
                        summary=summary,
                        details={"input": "browser-combobox", **state},
                    )

        return super()._browser_execute(decision, observation, lease, artifact_dir)


__all__ = ["ToolExecutor"]
