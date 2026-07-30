# Semantic Browser Control

Windows Agent browser control follows a semantic-first, self-healing architecture.
The model chooses a meaningfully identified control and a typed operation. It does
not choose a screen point when the page exposes a usable DOM or accessibility target.

## Production control order

1. Purpose-built API or connector when the operation is not inherently visual.
2. Playwright semantic locator using stable ID/name, current captured selector,
   associated label, ARIA role plus accessible name, exact text, placeholder, and
   Playwright actionability checks.
3. Accessibility/ARIA page snapshot for page hierarchy and state.
4. Full-document semantic map for content above, visible in, and below the viewport.
5. Current high-resolution screenshot and Set-of-Mark labels for visual context.
6. Raw coordinates only when no semantic or accessibility target exists.

The visible cursor is telemetry. It must follow the Playwright pointer, but it is not
used to decide which element receives an action.

## Stable model handles

The model sees compact `E####` handles. A handle is keyed by a semantic fingerprint:

- page URL;
- form identity;
- role and accessible name;
- stable element ID or name;
- tag and input type;
- placeholder and link target;
- occurrence among genuine semantic duplicates.

The handle does not depend on a React component retaining an injected DOM attribute.
Immediately before an action, the executor resolves the current node again using a
ranked locator cascade:

1. stable `id`;
2. stable `name`;
3. the captured selector while its original node still exists;
4. associated label;
5. ARIA role plus exact accessible name;
6. exact visible text for button/link/option-like controls;
7. placeholder.

If React destroys and recreates a dropdown option, the captured selector becomes empty
and the current role/name match is used. A stale injected attribute is therefore not
automatically a failed task.

## Typed actions

Browser planning uses these operations:

- `click_element(element_id)` for buttons, links, radio buttons, checkboxes, tabs,
  and ordinary controls;
- `fill_element(element_id, text)` for editable text/date/time/number controls;
- `select_option(element_id, option)` for native selects and ARIA comboboxes;
- `scroll(amount, element_id?)` for the document or a specific container;
- keyboard actions only for a currently focused semantic control;
- coordinate actions only as a last resort.

A model must not click a transient dropdown option by its temporary node ID. It selects
through the owning combobox with an exact option label. The executor opens the current
popup, discovers the current options, scrolls the option into view, selects it, and
verifies the resulting state.

## Full-page understanding

Every browser observation includes:

- current URL and title;
- an ARIA snapshot when supported by the installed Playwright version;
- document `scrollTop`, maximum scroll, viewport height, content height, and depth percent;
- whether the document can scroll up or down;
- headings classified as above, visible, or below the viewport;
- actionable controls classified as above, visible, or below;
- required, enabled, expanded, checked, selected, and value-presence state;
- visible nested scroll containers with their own position, maximum, and depth percent;
- form validity, missing required fields, validation messages, and visible alerts.

The prompt builder programmatically ranks and limits full-page candidates. Visible,
required, expanded, task-relevant, and nearby controls are retained first so the model
gains page-wide awareness without receiving an unbounded DOM dump.

A click-through scroll HUD is rendered inside the controlled page. It shows the current
scroll target and depth without controlling the action itself.

## Cursor synchronization

In virtual-cursor mode, each eased movement step updates both:

- Playwright's page mouse; and
- the in-page `👆🏻` telemetry cursor.

The click pulse is emitted only after both reach the same CSS coordinate. In system
cursor mode, the single shared Windows cursor remains subject to physical-input policy.

## Verification and recovery

After every select, fill, scroll, submit, or navigation action, Windows Agent reads the
fresh page state. It verifies:

- selected option and current control state;
- value persistence and browser validity;
- measured scroll movement and boundaries;
- changed URL, form state, alerts, or workflow state;
- missing and invalid fields before another submit.

The planner must not repeat a failed click, an already-open combobox click, a boundary
scroll, or a no-op submit. It changes strategy using the current semantic map.

## Safety boundary

Autonomy applies to reversible non-personal configuration such as titles, slugs,
categories, timezones, future dates, capacities, seating, and ordinary toggles.
Windows Agent still interrupts for personal identity, credentials, CAPTCHA/OTP, legal
consent, payment, publishing, sending, deletion, and other consequential actions.

## Accuracy target

No arbitrary website automation system can promise universal 100% task success.
Production grade means:

- deterministic semantic actions on supported controls;
- self-healing after ordinary DOM rerenders;
- measured and verified state changes;
- coordinate fallback only when necessary;
- explicit failure instead of an unverified click;
- site/workflow benchmarks with replayable evidence.
