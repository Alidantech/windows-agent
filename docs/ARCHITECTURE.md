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
- otherwise the run stops before the selected AI provider receives unrelated pixels.

Every observation includes a target identity and capture token derived from target metadata plus PNG bytes. The prompt receives the token, lease, monitor, HWND/browser identity, and source.

## Browser backend

`BrowserController` launches a persistent visible Playwright context on the monitor geometry. All clicks, text, keyboard, and scrolling occur through Playwright page APIs. DOM controls are converted to the same `UIElement` representation used by desktop UI Automation.

`smoke_test_site` inventories unique same-origin anchors and tests each in a temporary page. It captures status, final URL, title, page errors, request failures, elapsed time, and a screenshot.

## Desktop backend

The desktop backend uses UI Automation semantic patterns first. Shared physical PyAutoGUI input is a fallback gated by conflict and physical-input policies. A pre-action guard verifies that the observation HWND equals the leased HWND and overlaps the assigned monitor.

## Overlay

A transparent, click-through, non-activating Tk/Win32 overlay marks the assigned monitor and shows a virtual agent cursor. It requests display-affinity exclusion from capture where Windows supports it.

## Planner, provider registry, and verifier

`DesktopAgent` depends on the `PlannerProvider` protocol rather than a specific model SDK. The lazy registry currently supplies Gemini, OpenAI, and Mistral adapters. Each adapter receives one screenshot plus structured context and returns the same typed `AgentDecision` or `TaskVerification` models.

The provider never receives direct operating-system capabilities. It can only select from the locally validated tool schema. A separate typed verifier checks candidate completion, while deterministic tool evidence is accepted without an unnecessary model call.

## Cancellation path

The CLI installs an interrupt guard while a task is running. Ctrl+C cancels the shared token, aborts Windows Agent-owned browser work, records interruption evidence, stops the overlay, and exits or recreates the chat controller.

Provider requests execute in daemon workers and are polled by the main thread. Browser loops and delays check the same token.

## Safe overlay

No top-level window should span the monitor interior. The overlay consists of four border strips plus small banner and cursor windows. Each window is marked click-through, non-activating, tool-window, topmost, and excluded from capture where Windows supports display affinity.

## Deterministic terminal tools

Tools may return structured completion evidence. The agent accepts deterministic tool evidence directly and does not ask a screenshot-only verifier to validate off-screen artifacts. Website smoke testing uses this path.
