# Validation

Windows Agent v0.6.1 uses uv for all project commands.

Run the validation suite with:

```bash
uv sync
uv run python -m compileall src tests
uv run pytest
uv run ruff check .
```

The v0.6 runtime suite previously passed 48 tests. The tests cover cancellation, deterministic completion, monitor geometry, targeting, browser link inventory, safety rules, provider candidate parsing, secure credential fallback, context-preserving model switching, persistent session memory, and slash-command availability.

The packaging environment is not a Windows GUI session. The separate-process Tk overlay, Windows Credential Manager backend, Playwright window placement, and prompt rendering must receive a supervised smoke test on the target Windows machine.
