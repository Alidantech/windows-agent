# Troubleshooting

## Screenshot and controlled app differ

Prefer exact leases:

```bash
windows-agent screens
windows-agent run "TASK" --target hwnd:NUMBER
```

For websites, use `--control-mode browser`. Strict alignment should remain enabled. If a bound desktop app cannot be captured while another app is foreground, Windows Agent must stop instead of acting on unrelated pixels.

## Window title does not match

`window:` matching is fuzzy and ignores browser brand words, but exact HWND is strongest:

```bash
windows-agent screens
windows-agent lease-preview --target hwnd:NUMBER
```

## Agent interrupts my mouse or keyboard

Run with:

```bash
--control-mode browser --physical-input deny --conflict-policy cooperative
```

For desktop apps, UI Automation may still work with physical input denied. Unsupported controls require `--physical-input ask`.

## Playwright browser is missing

```bash
python -m playwright install chromium
```

Then run `windows-agent doctor`.

## Provider quota, authentication, or DNS failure

A rate-limit response is a provider quota issue. A `getaddrinfo failed` response is DNS/network resolution. Neither indicates a desktop-control failure. Windows Agent logs the failure and must not continue with an unparsed action.

## Monitor overlay appears in screenshots or looks opaque

Terminate stale processes, test the overlay independently, and disable it if necessary:

```bash
taskkill //F //IM windows-agent.exe //T
windows-agent overlay-test --target monitor:3 --seconds 8
windows-agent run "TASK" --target monitor:3 --no-overlay
```

## Ctrl+C cancellation

The task should cancel the active token and browser work. Provider calls also have a bounded timeout configured with:

```env
WINDOWS_AGENT_API_TIMEOUT_MS=30000
```

## Selected provider SDK is missing

Check provider status:

```bash
windows-agent providers
```

Install the selected optional adapter:

```bash
python -m pip install -e ".[openai]"
python -m pip install -e ".[mistral]"
```

Confirm that `WINDOWS_AGENT_PROVIDER`, `WINDOWS_AGENT_MODEL`, and the matching API key are configured.

## Smoke test completed but verifier rejected completion

A complete deterministic smoke-test report should be accepted as task evidence. The agent should not ask a screenshot-only verifier to locate report output inside the webpage.
