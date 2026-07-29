# Architecture

## Control lease

`LeaseManager` converts a requested target into a mutable `TargetLease` containing:

- lease ID and generation;
- assigned monitor geometry;
- backend (`desktop` or `browser`);
- exact HWND/title/process for desktop control;
- current state and binding reason.

A monitor-only lease begins in discovery state. After `launch_app`, system `open_url`, or `activate_window`, destination windows are scored using new-window status, foreground state, browser process, monitor overlap, domain/title tokens, and app terms. The selected HWND is optionally moved to the assigned monitor and bound.

An isolated `open_url` directly changes the lease backend to browser.

## Capture alignment

Desktop bound-window capture attempts Win32 `PrintWindow`. If it fails:

- strict mode permits a screen fallback only when the bound HWND owns foreground;
- otherwise the run stops before Gemini receives unrelated pixels.

Every observation includes a target identity and capture token derived from target metadata plus PNG bytes. The prompt receives the token, lease, monitor, HWND/browser identity, and source.

## Browser backend

`BrowserController` launches a persistent visible Playwright context on the monitor geometry. All clicks, text, keyboard, and scrolling occur through Playwright page APIs. DOM controls are converted to the same `UIElement` representation used by desktop UI Automation.

`smoke_test_site` inventories unique same-origin anchors and tests each in a temporary page. It captures status, final URL, title, page errors, request failures, elapsed time, and a screenshot.

## Desktop backend

The desktop backend uses UI Automation semantic patterns first. Shared physical PyAutoGUI input is a fallback gated by conflict and physical-input policies. A pre-action guard verifies that the observation HWND equals the leased HWND and overlaps the assigned monitor.

## Overlay

A transparent, click-through, non-activating Tk/Win32 overlay marks the assigned monitor and shows a virtual agent cursor. It requests display-affinity exclusion from capture where Windows supports it.

## Planner and verifier

Gemini receives one screenshot and structured context per step. The planner returns a typed `AgentDecision`. A separate typed verifier checks candidate completion. Deterministic tool evidence is included in history and observation state.
