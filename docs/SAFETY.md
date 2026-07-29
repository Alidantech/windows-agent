# Safety Model

Desktop agents can make real changes. This project therefore uses layered, local controls rather than relying only on a model prompt.

## Existing controls

- One action per model turn.
- Pydantic schema validation before execution.
- App-launch allow list.
- No arbitrary shell or code execution tool.
- Secret-shaped text is blocked from `type_text`.
- Selected hotkeys are blocked or require confirmation.
- PyAutoGUI top-left fail-safe and Ctrl+C.
- Maximum step limit.
- Repeated-action detector.
- Separate visual completion verifier.
- Saved screenshots and structured logs.
- Redaction of keys named like API keys, tokens, passwords, secrets, or authorization fields.
- Prompt instruction to treat on-screen text as untrusted.

## Do not use this project for

- passwords, recovery codes, API keys, private keys, or authentication setup;
- payments, banking, trading, gambling, or financial transfers;
- medical, legal, employment, insurance, or other high-impact decisions;
- deleting important files or accounts;
- administrator/elevated system changes;
- security bypass, surveillance, malware, credential access, or unauthorized activity;
- unattended operation on a machine containing valuable or sensitive data.

## Adding tools

Every new tool should have:

1. a narrow typed input model;
2. an allow list where possible;
3. local validation independent of the model;
4. risk classification and confirmation behavior;
5. a deterministic execution result;
6. redacted logging;
7. unit tests;
8. a documented emergency recovery path.

Avoid adding a general shell tool. Add narrow tools such as `open_known_project`, `read_safe_text_file`, or `create_draft_in_known_folder` instead.
