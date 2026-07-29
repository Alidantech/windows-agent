# AI providers

Windows Agent separates desktop control from model access. The control engine does not know whether a decision came from Gemini, OpenAI, Mistral, or a custom provider; it only consumes the validated `AgentDecision` and `TaskVerification` models.

## Built-in providers

| Provider | Configuration | Install |
|---|---|---|
| Gemini | `WINDOWS_AGENT_PROVIDER=gemini`, `GEMINI_API_KEY` | Included in the base install |
| OpenAI | `WINDOWS_AGENT_PROVIDER=openai`, `OPENAI_API_KEY` | `python -m pip install -e ".[openai]"` |
| Mistral | `WINDOWS_AGENT_PROVIDER=mistral`, `MISTRAL_API_KEY` | `python -m pip install -e ".[mistral]"` |

Set the model generically:

```env
WINDOWS_AGENT_PROVIDER=openai
WINDOWS_AGENT_MODEL=gpt-5-mini
OPENAI_API_KEY=...
```

Provider-specific model variables remain supported as fallbacks:

```env
GEMINI_MODEL=gemini-3.5-flash-lite
OPENAI_MODEL=gpt-5-mini
MISTRAL_MODEL=mistral-small-latest
```

`WINDOWS_AGENT_MODEL` takes precedence.

## Runtime selection

Global provider options must appear before the command:

```bash
windows-agent --provider openai --model gpt-5-mini run \
  "Open example.com" \
  --target monitor:3
```

List provider installation status:

```bash
windows-agent providers
```

## Architecture

```text
DesktopAgent
  └── PlannerProvider protocol
      ├── GeminiPlanner
      ├── OpenAIPlanner
      ├── MistralPlanner
      └── custom provider
```

Every provider must implement:

```python
class PlannerProvider(Protocol):
    name: str
    model: str

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]: ...
    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]: ...
    def close(self) -> None: ...
```

Providers are registered through `agent_os.providers.register_provider`. Imports are lazy, so selecting Gemini does not require the OpenAI or Mistral SDK.

## Compatibility

- `windows-agent` is the primary CLI.
- `agent-os` remains as a temporary command alias.
- `WINDOWS_AGENT_*` is the primary environment prefix.
- Existing `AGENT_OS_*` values are promoted automatically when the corresponding `WINDOWS_AGENT_*` variable is absent.
- Internal Python imports remain under `agent_os` for package compatibility in v0.5.
