# Validation

Windows Agent v0.6.1 uses uv for all project commands.

Run the validation suite with:

```bash
uv sync
uv run python -m compileall src tests
uv run pytest
uv run ruff check .
```

The v0.6 runtime suite previously passed 48 tests. The current task-routing change adds tests for:

- greetings and ordinary questions using terminal conversation;
- screen-dependent questions using desktop observation;
- explicit browser-action questions using desktop control;
- persistent-browser continuation;
- blocking invented email values;
- permitting explicitly supplied values;
- explicit terms consent;
- CAPTCHA user takeover;
- sensitive-question detection.

The seven standalone intent-routing tests passed in the packaging environment. All changed Python files passed bytecode compilation. The complete repository suite and Ruff check must be run with `uv run pytest` and `uv run ruff check .` after pulling because the packaging environment could not resolve the full Windows project dependency graph.

The packaging environment is not a Windows GUI session. The separate-process Tk overlay, Windows Credential Manager backend, Playwright window placement, prompt rendering, sensitive answer masking, persistent-browser continuation, and fresh post-submit capture require a supervised smoke test on the target Windows machine.
