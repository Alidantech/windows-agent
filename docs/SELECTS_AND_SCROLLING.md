# Selects, comboboxes, and scrolling

Windows Agent v0.6.3 treats selection and scrolling as verified browser operations instead of repeated coordinate clicks.

## Selecting options

For an HTML `select` or an ARIA combobox, the planner uses `fill_element` with the exact visible option label.

The browser controller then:

1. Detects whether the target is a native select or a custom ARIA combobox.
2. Uses Playwright `locator.select_option()` for native selects.
3. Opens custom comboboxes with a click or `ArrowDown` fallback.
4. Finds visible `role=option` elements by accessible name.
5. Scrolls the matching option into view.
6. Clicks it and verifies that the selected state changed.

A combobox may be clicked once to inspect its visible options. Repeated clicks on an already-open combobox are rejected with guidance to select an option or scroll its listbox.

## Scrolling

The `scroll` action accepts:

- a positive `amount` for downward movement;
- a negative `amount` for upward movement;
- an optional `element_id` for a listbox, dialog, menu, sidebar, or other visible container.

The browser controller selects the nearest movable scrollable ancestor. When no element is supplied, it tries the active control, the largest visible movable container, and finally the document.

Scrolling first uses Playwright `mouse.wheel()`. Because wheel dispatch does not wait for scrolling to finish, Windows Agent waits and measures the target's `scrollTop`. If no movement occurs, it applies a direct DOM fallback and measures again.

Every result reports:

- target label;
- requested CSS pixels;
- observed CSS pixels;
- before and after positions;
- maximum scroll position;
- whether the target is at the top or bottom;
- whether wheel-only or wheel-plus-fallback was used.

A zero-movement result is a failure and instructs the planner not to repeat the same direction.

## Planner rules

- Do not select an arbitrary first option when the user did not specify a value.
- Do not repeatedly click an open combobox.
- Do not treat typed search text as proof that an option was selected.
- After scrolling, use the fresh screenshot and element inventory.
- A vague cursor test must not modify unrelated form controls.

## References

- https://playwright.dev/python/docs/api/class-locator
- https://playwright.dev/python/docs/api/class-mouse
- https://playwright.dev/python/docs/input
- https://www.w3.org/WAI/ARIA/apg/patterns/combobox/
- https://www.w3.org/WAI/ARIA/apg/patterns/listbox/
