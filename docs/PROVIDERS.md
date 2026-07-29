# AI providers

Windows Agent separates the control engine from the vision planner. The control engine consumes validated `AgentDecision` and `TaskVerification` objects and does not depend on a specific provider SDK.

## Installation

All built-in provider SDKs are installed by the normal project synchronization:

```bash
uv sync
```

Start the persistent console with:

```bash
uv run windows-agent
```

Then use:

```text
/key status
/key set gemini
/key set openai
/key set mistral
/models
/model auto
/model gemini:gemini-3.5-flash-lite
```

There are no provider/model command-line arguments in v0.6.

## Built-in adapters

| Provider | Installation | Credential | Default route |
|---|---|---|---|
| Gemini | `uv sync` | `GEMINI_API_KEY` or `/key set gemini` | `gemini-3.5-flash-lite` |
| OpenAI | `uv sync` | `OPENAI_API_KEY` or `/key set openai` | `gpt-5-mini` |
| Mistral | `uv sync` | `MISTRAL_API_KEY` or `/key set mistral` | `mistral-small-2603` |

Keys entered interactively are masked and stored with `keyring` in Windows Credential Manager. Environment variables remain supported for unattended execution.

## Auto routing

`/model auto` builds an ordered list from `WINDOWS_AGENT_AUTO_MODELS`. A rate-limit, quota, overload, transient server, connection, DNS, or timeout error can place the current route in cooldown and send the exact same prompt and image to the next ready route.

The prompt already includes the current task, screenshot/capture token, control lease, action history, tool results, user guidance, and bounded persistent session context. Switching providers therefore does not reset the task.

## Provider contract

```python
class PlannerProvider(Protocol):
    name: str
    model: str

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]: ...
    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]: ...
    def list_models(self) -> list[ModelInfo]: ...
    def close(self) -> None: ...
```

Factories are lazy, so only selected providers are instantiated. `/models` queries each configured provider's model endpoint and reports missing keys without terminating the console.
