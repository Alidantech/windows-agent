# Changelog

## 0.6.4

- Added multiline paste support to the persistent console.
- Pasted slash-command blocks are processed one command per line in their original order.
- Mixed command/task blocks are dispatched line by line, while multiline prose without slash commands remains one task.
- Enter continues to submit normally; Alt+Enter inserts a manual newline.
- Sensitive answers remain a single response and are not split into commands.

## 0.6.3

- Added verified native-select handling through Playwright `locator.select_option()`.
- Added custom ARIA combobox opening, visible option discovery, option scrolling, selection, and selected-state verification.
- Added targeted scrolling for listboxes, dialogs, sidebars, nested containers, and the document.
- Added measured Playwright wheel scrolling with a DOM fallback only when wheel movement is zero.
- Added boundary reporting so the planner cannot repeatedly scroll at the top or bottom.
- Added planner rules that prevent repeated combobox clicks and arbitrary form changes during vague cursor tests.

## 0.6.2

- Replaced the Tk-based virtual cursor window with an in-page Playwright `👆🏻` cursor rendered through `page.evaluate()` and isolated shadow DOM.
- Added `pointer-events: none`, CSS-pixel animation, click-pulse feedback, and screenshot hiding for the browser cursor.
- Split the Windows overlay into an edge-only focus process that never creates a cursor-shaped window.
- Removed the legacy hand-overlay runtime from the active inheritance path so the black-square cursor implementation is never instantiated.
- Added `virtual`, `system`, and `off` cursor modes. System mode deliberately moves the one shared Windows cursor and requires physical-input permission.
- Added browser form-state capture for value presence, validity, validation messages, missing required fields, visible alerts, submit controls, and meaningful post-click state changes.
- Added verified `fill_element` results so a fill fails when the value does not remain or browser validation rejects it.
- Added verified submit/proceed results so missing fields, invalid fields, or a no-op click are reported as failures instead of triggering repeated blind clicks.
- Required user-authored values such as event titles, slugs, dates, capacities, categories, locations, and prices are requested from the user instead of being fabricated as placeholders.
- Optional fields remain untouched unless the user supplies a value or explicitly requests completion.
- Added active-browser continuation routing for requests such as `create an event` and `follow event creation process`.
- Added immutable navigation-only task contracts so visiting a URL cannot drift into unrelated clicks, forms, or creation workflows.
- Added CSS-pixel browser screenshots and Per Monitor v2 DPI handling so model coordinates, Playwright input, and the visible overlay share one calibrated geometry.
- Added stable semantic browser element IDs, richer ARIA roles including dropdown options, actionability checks, and automatic scroll-into-view.
- Added Set-of-Mark high-contrast model images while preserving clean screenshots as evidence.
- Replaced opaque focus strips and the large banner with an edge-only transparent gradient whose center is completely uncovered.
- Added signed, measured virtual mouse-wheel scrolling for focused and nested browser scroll containers.
- Added focused-locator sequential typing fallback for widgets that require keyboard events.
- Fixed the form-safety regex that matched `city` inside `capacity`, causing Max capacity to be misclassified as an address field.
- Added deterministic intent routing so greetings and general questions are answered in the terminal without screenshots or the desktop completion verifier.
- Added persistent-browser continuation routing for follow-up tasks such as account creation, form completion, login, and verification.
- Added user-data gates that prevent the planner from inventing names, email addresses, phone numbers, addresses, usernames, passwords, PINs, OTPs, or other identity details.
- Added explicit confirmation before accepting terms, privacy policies, subscriptions, marketing consent, or other legal consent.
- Added user takeover for CAPTCHA and human-verification controls.
- Added masked prompt input and history suppression for passwords, OTPs, PINs, API keys, and verification codes.
- Added a fresh post-action browser capture before completion verification.
- Bounded rejected completion claims so an unsupported `done` response cannot consume the full step budget.
- Updated system and verifier prompts to distinguish terminal conversation, actionable computer work, deterministic evidence, and verification checkpoints.

## 0.6.1

- Replaced manual virtual-environment and pip setup with an uv-only project workflow.
- Added `.python-version` pinned to Python 3.12.
- Moved development tools to uv's `dev` dependency group.
- Made Gemini, OpenAI, and Mistral SDKs part of the standard synchronized environment.
- Added `uv` installation, synchronization, launch, update, lockfile, and troubleshooting documentation.
- Updated setup scripts and Windows launcher to use `uv sync` and `uv run`.
- Removed `requirements.txt` as a duplicated dependency source.

## 0.6.0

- Replaced the argument-heavy CLI with one persistent `windows-agent` console.
- Added a permanent prompt, fuzzy slash commands, history, task queue, and agent-question routing.
- Added Claude-style `⏺` / `⎿` action-result hierarchy and quieter metadata.
- Added `/models`, `/model`, `/key`, `/set`, `/status`, `/queue`, `/cancel`, `/doctor`, `/logs`, and `/memory`.
- Added Windows Credential Manager storage through `keyring` with hidden API-key input.
- Added automatic context-preserving model/provider fallback and cooldowns.
- Added live model discovery through Gemini, OpenAI, and Mistral model APIs.
- Restored deterministic tool completion so smoke tests do not enter visual-verifier loops.
- Restored cancellable provider/browser operations and force cleanup of owned browser processes.
- Moved Tk overlay rendering into a dedicated process.
- Replaced the full-monitor overlay with four thin strips and small badges, fixing black monitors.
- Removed the `agent-os` executable and legacy `AGENT_OS_*` configuration support.

## 0.5.0

- Rebranded the package as Windows Agent.
- Introduced Gemini, OpenAI and Mistral adapters.

## 0.4.0

- Added deterministic smoke-test evidence, cancellation and safe overlay experiments.
