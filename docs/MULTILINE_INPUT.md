# Multiline console input

Windows Agent 0.6.4 preserves newlines from bracketed terminal paste.

## Paste several slash commands

Paste the block and press Enter once:

```text
/set control browser
/set physical deny
/set cursor virtual
/set overlay on
```

The console processes each non-empty line in order and prints:

```text
⎿ Processing 4 pasted entries.
⎿ OK Set control to browser.
⎿ OK Set physical to deny.
⎿ OK Set cursor to virtual.
⎿ OK Set overlay to on.
```

## Paste a multiline task

A pasted block with no slash-command lines remains one task:

```text
Open the event creation page.
Select Africa/Nairobi as the timezone.
Stop after the selection is visibly confirmed.
```

It is not split into three queued tasks.

## Mixed blocks

When a pasted block contains at least one slash command, every non-empty line is dispatched in its original order. Slash lines run as commands; other lines are queued as tasks.

## Keyboard behavior

- `Enter`: submit the current input.
- `Alt+Enter`: insert a newline manually without submitting.
- Pasted newlines are preserved automatically.
- When the agent is asking for a password, OTP, API key, or another sensitive answer, the complete input is treated as one answer and is never interpreted as slash commands.
