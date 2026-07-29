# Changelog

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
- Introduced Gemini, OpenAI, and Mistral adapters.

## 0.4.0

- Added deterministic smoke-test evidence, cancellation, and safe overlay experiments.
