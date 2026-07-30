# Cursor modes and reliable form control

Windows Agent separates browser input from cursor presentation.

## Rendering and control stack

- `prompt_toolkit`: persistent editable terminal prompt, history, completion and background output safety.
- `Rich`: panels, tables, status indicators and the action/result feed.
- `Playwright`: semantic browser locators, CSS-pixel virtual mouse, keyboard, scrolling and form input.
- `Pillow`: Set-of-Mark model images and the transparent hand cursor artwork.
- `Tkinter` plus `pywin32`: click-through focus-edge and virtual-cursor windows.
- Win32 `SetCursorPos`: optional control of the one shared Windows cursor.
- `pywinauto`: native Windows UI Automation.
- `PyAutoGUI`: last-resort physical desktop input when policy allows it.

## Cursor modes

Use one of these inside the persistent console:

```text
/set cursor virtual
/set cursor system
/set cursor off
```

### Virtual

`virtual` is the default. Playwright controls an independent browser mouse while Windows Agent renders a transparent pointing-hand overlay. The user's physical Windows cursor remains available.

The virtual cursor is generated as an RGBA hand image by Pillow. The cursor window uses Windows color-key transparency without global window alpha; this avoids the dark square produced by combining Tk transparency modes.

### System

`system` moves the normal shared Windows cursor to the calibrated browser target. Windows provides only one cursor on an interactive desktop, so the user cannot use the mouse independently while this mode is active.

Enable it explicitly:

```text
/set physical allow
/set cursor system
```

Playwright still performs semantic browser clicks and fills. Moving the real cursor is presentation and hover alignment; semantic Playwright input remains more reliable than coordinate-only physical clicks.

### Off

`off` hides pointer presentation while retaining semantic Playwright input.

## Form-state controller

Every browser observation now records:

- whether a control is editable, required, read-only or disabled;
- whether it currently has a value;
- value length and a non-password preview;
- validity and validation message;
- form identity;
- whether the control submits the form;
- active field and visible alerts;
- missing and invalid required fields.

`fill_element` verifies that the value remained and that browser validation accepted it. A submit/proceed click is considered failed when required fields are missing, validation errors remain, or no observable form/page state changed. The agent is instructed not to repeat the same submit click after that result.

## User-authored values

Windows Agent does not invent event titles, short names, URLs, dates, capacities, prices, categories or other required authored values. A required value must appear in the task or explicit user guidance. Otherwise, the persistent prompt asks for it and stores it in a one-time field-scoped local vault.

Optional fields remain blank unless the user supplies a value or explicitly asks for them to be completed.

## Windows limitation

A second native Windows cursor is not available in the same interactive desktop session. The two honest choices are:

1. an independent visual cursor paired with Playwright's virtual browser mouse; or
2. temporary control of the user's one shared system cursor.

A truly independent second physical pointer requires another Windows session, virtual machine or separate machine.

## Official references

- https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setcursorpos
- https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-sendinput
- https://playwright.dev/python/docs/actionability
- https://playwright.dev/python/docs/input
- https://playwright.dev/python/docs/api/class-locator
