# Validation

Validated in the build environment on 2026-07-29:

- Python source and tests compile with `python -m compileall -q src tests`.
- 31 unit tests pass with `pytest -q`.
- CLI help loads and exposes the v0.3 commands and runtime policy options.
- Project metadata parses as version 0.3.0.
- Skill front matter parses and selects browser/smoke-testing skills for website tasks.

The build environment is Linux, so these behaviors could not be executed end-to-end here:

- Win32 HWND discovery and `PrintWindow` capture;
- physical multi-monitor placement;
- click-through Windows overlay behavior;
- visible Playwright browser launch on the user's Windows machine;
- UI Automation invocation against the user's installed applications.

Those platform-specific paths include runtime diagnostics and fail closed when screenshot/action alignment cannot be proven.
