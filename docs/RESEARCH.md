# Design and provider research notes

Windows Agent separates model planning from execution and prefers semantic or application-native input over shared hardware simulation:

1. Browser automation uses a Playwright persistent context and page-level virtual input.
2. Windows controls use UI Automation invocation and value patterns when available.
3. Win32 window handles provide stable identity and monitor placement.
4. `PrintWindow` provides independent bound-window pixels when supported.
5. Shared PyAutoGUI input remains an explicit fallback rather than the primary mechanism.
6. A separate verifier prevents attempted actions from becoming false completion evidence.
7. Deterministic link inventory is more reliable and economical than one model call per browser click.
8. AI providers implement one typed planner protocol and never execute operating-system actions directly.

The design does not claim to create a second native system cursor or keyboard in one Windows desktop session. Practical independence comes from isolated browser APIs, UI Automation, exact HWND leases, and refusing unsafe physical fallback.

## Provider implementation sources

The provider adapters follow official SDK capabilities:

- Gemini accepts image bytes and Pydantic-backed structured output through the Google Gen AI SDK.
- OpenAI's Responses API accepts image content and exposes structured response parsing in the Python SDK.
- Mistral's Python client exposes structured parsing and vision message content.

Provider SDKs are imported lazily. Selecting Gemini does not import OpenAI or Mistral. Optional provider installation failures are reported before a task begins.
