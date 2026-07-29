# Architecture

## Persistent session

`windows-agent` starts one long-lived `prompt_toolkit` session. Normal input queues tasks. Slash commands inspect or change the running controller. A bounded session memory summarizes completed tasks and is included in later planning prompts.

## Provider routing

`RoutingPlanner` owns an ordered list of `provider:model` routes. Every fallback receives the exact same current prompt and screenshot; the prompt already contains the current task, action history, tool results, guidance, lease metadata and persistent session context.

## Control lease

A task begins with a target lease. Once a browser or desktop window is bound, every screenshot, element snapshot and action carries that lease identity. Strict mode refuses to execute when pixels and target differ.

## Browser backend

Playwright runs a visible isolated browser on the assigned monitor. Its page-level virtual input does not move the user's physical pointer or type through the physical keyboard. Deterministic tools such as `smoke_test_site` produce machine-readable evidence and can complete a run without a vision-only verifier.

## Desktop backend

Desktop control prefers UI Automation patterns. Physical mouse and keyboard input are policy-controlled fallbacks. Cooperative mode refuses to steal focus.

## Overlay

The overlay is a dedicated child process. It creates only four thin border strips, a small status badge and a small virtual-cursor badge. No monitor-sized Tk window exists, and all Tcl objects are created and destroyed inside the same process.

## Cancellation

The prompt thread captures Ctrl+C, marks a shared cancellation token and closes owned browser resources. Provider calls run in cancellable worker threads with bounded HTTP timeouts. The persistent console remains active after cancellation.
