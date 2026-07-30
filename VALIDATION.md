# Validation

Windows Agent v0.6.1 uses uv for all project commands.

Run the validation suite with:

```bash
uv sync
uv run python -m compileall src tests
uv run pytest
uv run ruff check .
```

The v0.6 runtime suite previously passed 48 tests. Later focused suites cover:

- greetings and ordinary questions using terminal conversation;
- screen-dependent questions using desktop observation;
- explicit browser-action questions using desktop control;
- persistent-browser continuation, including `create an event` and `follow event creation process`;
- blocking invented personal and required authored values;
- permitting explicitly supplied and field-scoped local values;
- explicit terms consent and CAPTCHA takeover;
- masked local-value token routing and cleanup;
- navigation-only task contracts;
- Set-of-Mark rendering and edge-only overlay geometry;
- capacity/address regression;
- cursor mode defaults;
- form submit summaries for missing and invalid fields.

Changed Python modules passed bytecode compilation in the packaging environment. The focused routing, interaction-policy, local-value, grounding, form, and cursor tests passed there. The complete repository suite and Ruff check must be run with `uv run pytest` and `uv run ruff check .` after pulling because the packaging environment could not resolve and execute the complete Windows dependency graph.

The packaging environment is not a Windows GUI session. The following require supervised validation on the target Windows machine:

- transparent Pillow/Tk hand-cursor rendering;
- shared system-cursor movement through Win32 `SetCursorPos`;
- edge-gradient placement at mixed monitor DPI scales;
- Playwright window placement, locator actionability and form-state capture;
- Windows Credential Manager;
- prompt rendering and masked local-value entry;
- native UI Automation and physical fallbacks.

## Supervised cursor tests

Virtual cursor, independent of the user's pointer:

```text
/set control browser
/set physical deny
/set cursor virtual
/set overlay on
```

Shared normal Windows cursor:

```text
/set control browser
/set physical allow
/set cursor system
/set overlay on
```

System mode necessarily moves the one shared Windows cursor. Do not use the mouse concurrently.

## Supervised form test

After opening a browser form, request a workflow without supplying required values. Expected behavior:

1. Windows Agent asks for each missing required authored value instead of inventing placeholders.
2. Optional fields remain blank unless requested.
3. Filled values are verified for persistence and browser validity.
4. A failed submit result lists missing/invalid fields or reports no meaningful state change.
5. The planner does not blindly repeat the same submit click.
