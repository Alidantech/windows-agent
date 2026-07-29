# Research and Design Sources

Research date: 2026-07-29.

## Gemini model and API

- Gemini 3.6 Flash is documented as a stable multimodal model with image input, structured outputs, function calling, spatial reasoning, and computer-use capability. It is the default model in this project.
  - https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash
- Google's current Computer Use documentation describes the screenshot/action/result loop, normalized execution mapping, safety decisions, prompt-injection concerns, and the need for client-side execution and a secure environment.
  - https://ai.google.dev/gemini-api/docs/computer-use
- Google recommends the Interactions API for new agent projects, but the current implementation deliberately keeps a small client-side typed action loop using `generate_content`; this makes the local tool set, confirmations, logs, and recovery behavior explicit and testable.
  - https://ai.google.dev/gemini-api/docs/interactions-overview
- The Google Gen AI Python SDK supports `types.Part.from_bytes` for local images and typed JSON output using response schemas.
  - https://googleapis.github.io/python-genai/
- Structured output documentation demonstrates Pydantic JSON schemas for predictable agentic outputs.
  - https://ai.google.dev/gemini-api/docs/structured-output

## Screen capture

- Python MSS is designed for fast multi-monitor screenshot capture and exposes one region per monitor plus virtual-desktop information.
  - https://python-mss.readthedocs.io/
  - https://python-mss.readthedocs.io/latest/examples.html

## Windows UI Automation

- pywinauto can start or connect to Windows applications and supports both Win32 and Microsoft UI Automation backends. This project uses the UIA backend for window/control metadata while keeping PyAutoGUI as the visual fallback.
  - https://pywinauto.readthedocs.io/en/latest/getting_started.html
  - https://pywinauto.readthedocs.io/en/latest/

## Important engineering choices

1. **Normalized coordinates:** avoid the original resized-image/full-screen scaling bug and support negative monitor coordinates.
2. **Semantic tools first:** opening Start with the Windows key and launching allow-listed apps are more reliable than pixel guessing.
3. **One target at a time:** reduce visual ambiguity and token cost when multiple monitors or apps exist.
4. **Pixels plus accessibility metadata:** combine universal screenshots with labeled UI controls when available.
5. **External prompts and skills:** make behavior auditable and editable without changing the execution engine.
6. **Local safety enforcement:** the executor validates and confirms actions after the model responds.
7. **No arbitrary shell:** optimize computer use with narrow tools rather than giving the model unrestricted command execution.
8. **Persistent run evidence:** screenshots and JSONL logs make failures reproducible.
9. **Separate completion verification:** prevent the planner from ending solely because it attempted the expected action.
10. **Stuck recovery:** repeated identical action signatures are blocked before the loop can continue indefinitely.
