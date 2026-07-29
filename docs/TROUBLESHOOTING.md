# Troubleshooting

## Screenshot and controlled app differ

Use v0.3 exact leases. Prefer:

```bash
agent-os screens
agent-os run "TASK" --target hwnd:NUMBER
```

For websites, use `--control-mode browser`. Strict alignment should remain enabled. If a bound desktop app cannot be captured with `PrintWindow` while another app is foreground, Agent OS stops instead of acting.

## Window title does not match

`window:` matching is fuzzy and ignores browser brand words, but exact HWND is strongest:

```bash
agent-os screens
agent-os lease-preview --target hwnd:NUMBER
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

Then run `agent-os doctor`.

## Isolated Chrome channel cannot launch

Agent OS automatically falls back to Playwright Chromium. Install Chromium using the command above. You may also set:

```env
AGENT_OS_BROWSER_CHANNEL=chromium
```

## Gemini quota or DNS failure

A `429 RESOURCE_EXHAUSTED` response is a model quota issue. A `getaddrinfo failed` response is DNS/network resolution. Neither indicates a desktop-control failure. Agent OS logs the failure and does not continue with an unparsed action.

## Monitor overlay appears in screenshots

Windows normally excludes the overlay using display affinity. If the OS does not support that behavior, disable it:

```bash
agent-os run "TASK" --no-overlay
```
