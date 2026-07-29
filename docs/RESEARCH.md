# Research and design decisions

Windows Agent v0.6 is based on application-native control and one persistent terminal session rather than repeated one-shot CLI invocations.

## Persistent terminal

`prompt_toolkit.PromptSession` supports a reusable prompt application, persistent `FileHistory`, formatted prompts, completions, auto-suggestion, a dynamic bottom toolbar and configurable interrupt behavior. `patch_stdout` allows worker output to be printed while preserving the editable prompt.

Rich supplies terminal capability detection, structured tables/panels, semantic colors and temporary status spinners. The permanent action history remains normal terminal output, while only current planning/verification uses an animated status.

Official sources:

- https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html
- https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html
- https://rich.readthedocs.io/en/latest/console.html
- https://rich.readthedocs.io/en/stable/reference/status.html

## Credential storage

The interactive `/key set PROVIDER` flow uses a masked prompt without history and stores the secret through Python `keyring`. On Windows, keyring supports Windows Credential Locker. Provider environment variables remain a fallback for unattended installations.

Official source:

- https://keyring.readthedocs.io/en/latest/

## Browser independence

Playwright browser contexts provide independent browser sessions and pages. Its page-level keyboard API dispatches browser input events instead of using the physical Windows keyboard. This lets the user continue using another monitor while browser automation runs with physical input denied.

Official sources:

- https://playwright.dev/python/docs/api/class-browsercontext
- https://playwright.dev/python/docs/api/class-keyboard

## Model discovery and routing

Model names and availability can change, so `/models` queries each configured provider account rather than relying only on a static catalog:

- Gemini uses the Google Gen AI SDK model-list operation.
- OpenAI uses `GET /v1/models` through the official SDK.
- Mistral uses the Model Management list endpoint.

The default route list is only a starting preference. Auto mode transfers the exact same current prompt and screenshot to the next ready route after quota, rate-limit, timeout, DNS/connection, overload or transient server failures. The prompt already includes lease identity, capture token, action history, tool results, user guidance and bounded session context, so switching transport does not reset the task.

Current model references used when v0.6 was authored:

- Gemini 3.6 Flash: `gemini-3.6-flash`
- Gemini 3.5 Flash-Lite: `gemini-3.5-flash-lite`
- Gemini 3.1 Flash-Lite: `gemini-3.1-flash-lite`
- OpenAI GPT-5 mini: `gpt-5-mini`
- Mistral Small 4: `mistral-small-2603`

Official sources:

- https://ai.google.dev/gemini-api/docs/generate-content/latest-model
- https://ai.google.dev/gemini-api/docs/pricing
- https://platform.openai.com/docs/api-reference/models/object
- https://platform.openai.com/docs/quickstart/make-your-first-api-request
- https://docs.mistral.ai/api/endpoint/models
- https://docs.mistral.ai/models/model-cards/mistral-small-4-0-26-03

## Overlay isolation

The earlier black-monitor failure came from relying on transparency for a monitor-sized Tk window. v0.6 removes that failure mode: the overlay process creates four thin border windows and two small badges only. It never owns a monitor-sized surface. Keeping every Tk object in a dedicated process also avoids destroying Tcl handlers from the wrong thread.

## Deterministic completion

`smoke_test_site` inventories links through the DOM, visits each unique same-origin URL, records HTTP/final URL/title/browser failures, saves screenshots and writes a report. This structured result is stronger evidence than asking a vision model to see a JSON file inside a webpage, so successful tool evidence completes the run directly.

## Remaining limits

Windows still has one shared system pointer and foreground keyboard focus per interactive desktop. Independent browser input is provided by Playwright; desktop applications use UI Automation first. A truly independent physical cursor/keyboard for arbitrary native applications requires another Windows session, VM or machine.
