# Changelog

## 0.2.0

- Protect the Agent OS terminal from accidental self-typing, self-clicking, and self-scrolling.
- When `active-window` is the controller terminal, observe the desktop so the planner can select the real destination.
- Foreground explicit window targets immediately before keyboard, mouse, and scroll input.
- Add safe `open_url` action for direct website navigation.
- Resolve Chrome, Edge, and Brave from Windows App Paths and common installation directories.
- Restore the destination window after interactive `ask_user` answers.
- Print the exact observed target and screenshot path for every step.
- Print completion-verifier rejection evidence instead of appearing to ignore `done`.
- Reject `done` after a failed action and discourage repeated false-completion decisions.
- Handle `EOFError` and Ctrl+C cleanly in the interactive console.
- Add controller-protection, URL model, and URL safety tests.
