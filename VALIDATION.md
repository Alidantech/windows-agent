# Validation

Windows Agent v0.6 was validated in the packaging environment with:

```text
python -m compileall src tests
pytest
```

Result: 48 tests passed.

The tests cover cancellation, deterministic completion, monitor geometry, targeting, browser link inventory, safety rules, provider candidate parsing, secure credential fallback, context-preserving model switching, persistent session memory and slash-command availability.

The packaging environment is not a Windows GUI session. The separate-process Tk overlay, Windows Credential Manager backend, Playwright window placement and prompt rendering must receive a supervised smoke test on the target Windows machine.
