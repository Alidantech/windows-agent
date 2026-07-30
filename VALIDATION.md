# Validation

Windows Agent uses uv for all project commands.

Run the validation suite with:

```bash
uv sync
uv run python -m compileall src tests
uv run pytest
uv run ruff check .
```

The repository suite covers:

- greetings and ordinary questions using terminal conversation;
- screen-dependent questions using desktop observation;
- explicit browser-action questions using desktop control;
- persistent-browser continuation, including typo-tolerant event creation;
- autonomous reversible demo/form defaults and stable per-task plans;
- protected personal values, credentials, consent, CAPTCHA, payment, and consequential actions;
- masked local-value token routing and cleanup;
- navigation-only task contracts;
- Set-of-Mark rendering and edge-only overlay geometry;
- virtual/system cursor modes and default policy;
- form submit summaries for missing and invalid fields;
- native and ARIA select verification;
- measured document and nested-container scrolling;
- typed `select_option` schema validation;
- stable semantic browser references;
- live role/name recovery when a captured React option selector becomes stale;
- full-page semantic candidate pruning without dropping required task-relevant controls;
- activation of `agent_os.runtime_v11`.

The complete repository suite and Ruff check must be run on the target checkout after
pulling. The packaging environment used for connector-backed updates cannot resolve
GitHub or execute the complete Windows dependency graph.

## Windows-only supervised checks

The following require a real Windows GUI session:

- Playwright Chrome placement on the selected monitor;
- mixed-DPI viewport geometry;
- shared system-cursor movement through Win32 `SetCursorPos`;
- the in-page virtual cursor and click pulse;
- scroll-depth HUD placement and updates;
- semantic locator actionability on the live DefyTickets React application;
- Windows Credential Manager;
- prompt rendering and masked local-value entry;
- native UI Automation and physical fallbacks.

## Semantic browser regression

Configure the isolated browser:

```text
/set control browser
/set physical deny
/set cursor virtual
/set overlay on
/model auto
```

Run:

```text
Open app.defytickets.co and complete the Create Event setup using coherent demo values.
Follow every reversible setup step and save it as a draft. Do not publish, accept terms,
or perform payment.
```

Expected behavior:

1. Visible browser controls use stable `E####` handles.
2. The observation contains `semantic_page`, document depth, headings, actionable counts,
   nested scroll containers, and an ARIA snapshot when supported.
3. The right-side HUD shows the current page or container scroll depth.
4. Event title, URL, category, timezone, future dates, capacity, seating, and ordinary
   toggles are selected autonomously.
5. Dropdowns use `select_option` on the owning combobox with an exact available label.
6. A React rerender may destroy the captured option node, but execution re-resolves the
   current role/name control instead of timing out on the old injected selector.
7. The cursor moves with Playwright's actual eased pointer path and pulses at the final
   semantic action point.
8. Scroll results report the target, requested pixels, observed pixels, maximum, and
   boundaries. Boundary scrolls are not repeated.
9. Filled values and selections are verified after each action.
10. Missing or invalid fields are corrected before another submit.
11. Personal identity, credentials, CAPTCHA/OTP, consent, payment, publishing, sending,
    deletion, and other consequential actions still interrupt or stop safely.

## Focused stale-option test

On the Category combobox, select an exact visible option such as `Live Performance`.
The executor must select through the Category combobox. It must not depend on a transient
option handle such as the old `B0059` surviving a React rerender.

## System cursor test

To test the shared Windows cursor deliberately:

```text
/set physical allow
/set cursor system
```

System mode necessarily moves the one shared Windows cursor. Do not use the mouse
concurrently. Return to independent browser telemetry with:

```text
/set cursor virtual
/set physical deny
```
