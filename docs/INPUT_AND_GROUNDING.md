# Input, visual grounding, and focus design

This document records the production control design introduced after auditing the run `20260729-200917-open-chrome-and-visit-app-defytickets-co`.

## Failure reconstructed

The task was only to open Chrome and visit `app.defytickets.co`. The browser reached the requested site, but the planner then waited, clicked **Create event**, filled unrelated form fields, repeatedly clicked **Save & continue**, lost the category-option target, and misclassified **Max capacity** as an address field.

The failure had multiple causes:

1. no immutable task-completion contract for navigation-only requests;
2. screenshots and browser mouse coordinates could use different DPI scales;
3. element IDs were rebuilt as simple sequential snapshot IDs;
4. custom dropdown roles such as `option` and `listbox` were missing from grounding;
5. the model saw a normal screenshot rather than a high-contrast element map;
6. the virtual cursor teleported and did not represent the actual Playwright target;
7. wheel scrolling had unclear direction and did not report the container that moved;
8. form-safety matching allowed `city` to match the substring in `capacity`.

## Immutable task contracts

Obvious navigation-only requests are completed deterministically:

```text
open chrome and visit app.defytickets.co
```

Windows Agent opens the requested URL in its isolated browser, captures the resulting URL, confirms that the host/path matches or validly redirects, and stops. It does not ask a model to invent a next step.

Longer requests remain agentic:

```text
open app.defytickets.co and create an event
```

The task contract is also included in every planning and verification prompt. The model is explicitly forbidden from entering adjacent workflows merely because a prominent button exists.

## Browser coordinate model

Playwright mouse coordinates are CSS pixels relative to the page viewport. Browser screenshots are therefore captured with `scale="css"`. Windows Agent no longer maps a screenshot in device pixels onto a browser mouse in CSS pixels.

For model-generated coordinates:

- `x` and `y` remain normalized from 0 to 1000;
- the executor converts them to current CSS viewport pixels;
- the overlay converts the same CSS point to calibrated physical screen coordinates;
- Per Monitor v2 DPI awareness is enabled before Win32 geometry is read;
- raw and DPI-scaled browser window candidates are compared against the assigned monitor.

Element IDs remain preferred over coordinates.

## Semantic browser inventory

The inventory includes native controls and ARIA controls:

- links, buttons, inputs, textareas, selects, and options;
- `button`, `link`, `textbox`, `combobox`, `option`, and `listbox` roles;
- menu items, checkboxes, radios, switches, tabs, and tree items;
- contenteditable, focusable, and click-handler elements.

Each element receives a stable `data-windows-agent-id` for the lifetime of that DOM node. Accessible names are resolved from ARIA labels, labelled-by content, associated labels, placeholders, visible text, title, and field name—in that order. Input values are not used as element names.

The inventory records visibility, enabled state, required/read-only state, focus, selection/check state, editability, CSS bounds, and whether the center currently receives pointer events.

## Set-of-Mark grounding

The clean screenshot remains saved as evidence. A separate model-only image adds high-contrast boxes and labels matching the semantic element IDs.

Color meaning:

- green: buttons;
- cyan: text inputs;
- purple: combobox/select controls;
- magenta: dropdown options;
- amber: checkboxes/radios;
- yellow: links.

Focused controls receive a thicker outline. Disabled controls are crossed. The model can match a visible `B0007` mark directly to `ui_elements[element_id=B0007]` instead of estimating a coordinate from pixels alone.

## Precise pointer and click execution

Element actions use Playwright locators. Before a click, Windows Agent:

1. scrolls the locator into view;
2. runs a trial click to enforce Playwright actionability checks;
3. reads the current bounding box;
4. moves the virtual browser mouse to the exact CSS center with eased intermediate events;
5. animates the visible AI cursor to the same calibrated physical point;
6. performs the real click;
7. emits a click pulse.

This keeps the visible cursor, DOM hover state, and actual browser click aligned.

## Typing

`fill_element` focuses the exact locator and uses Playwright `fill` where supported. For controls that require real key events, it falls back to `Control+A` plus sequential key presses. `type_text` uses the currently focused locator when one is proven.

The physical Windows keyboard remains unnecessary in isolated browser mode.

## Scrolling

Positive scroll amounts move down; negative amounts move up. The wheel is dispatched at the focused control when it is visible, otherwise at the viewport center. Windows Agent walks up from that point to identify the nearest scrollable container, performs the wheel action, waits briefly for asynchronous scrolling, and reports the observed movement.

## Focus overlay

The focus overlay never creates a monitor-sized window. It consists of:

- forty narrow edge-only windows forming a 28-pixel green/cyan gradient;
- an almost transparent inner edge;
- a completely uncovered monitor center;
- one small transparent AI pointer window.

Every overlay window is topmost, click-through, non-activating, excluded from capture where Windows supports it, and owned by a separate DPI-aware process. The old black square cursor and status banner have been removed.

## Safety correction

Form-field safety now uses accessible labels first. Automation IDs are only a fallback when no accessible label exists. The address regex uses whole alternatives, so `city` can no longer match the substring inside `capacity`.

## Validation

Run:

```bash
uv sync
uv run python -m compileall src tests
uv run pytest
uv run ruff check .
```

Then perform the supervised Windows checks described in the release response. The packaging environment cannot validate live multi-monitor Win32 placement, Tk transparency, Chrome DPI behavior, or real site interaction.

## Primary design references

- Playwright locators and actionability: https://playwright.dev/python/docs/locators and https://playwright.dev/python/docs/actionability
- Playwright mouse and CSS-pixel coordinates: https://playwright.dev/python/docs/api/class-mouse
- Set-of-Mark prompting: https://arxiv.org/abs/2310.11441
- OmniParser structured screen parsing: https://arxiv.org/abs/2408.00203
- Windows layered windows: https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-updatelayeredwindow
- Windows display affinity: https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity
- Per Monitor v2 DPI awareness: https://learn.microsoft.com/windows/win32/hidpi/dpi-awareness-context
