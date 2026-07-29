from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings, provider_api_key
from agent_os.models import AgentDecision, TaskVerification
from agent_os.prompts import PromptBuilder
from agent_os.providers.base import CancellableProvider, ModelInfo

T = TypeVar("T", bound=BaseModel)


class GeminiPlanner(CancellableProvider):
    name = "gemini"

    def __init__(self, settings: Settings, prompts: PromptBuilder, model: str, cancellation: CancellationToken | None = None) -> None:
        super().__init__(settings, model, cancellation)
        self.prompts = prompts
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Gemini support requires google-genai.") from exc
        self._genai: Any = genai
        self._types: Any = types
        self._api_key = provider_api_key(self.name)

    def _request(self, prompt: str, image_bytes: bytes, schema: type[T], system_instruction: str) -> tuple[T, str]:
        def operation() -> tuple[T, str]:
            client = self._genai.Client(
                api_key=self._api_key,
                http_options=self._types.HttpOptions(timeout=self.settings.api_timeout_ms),
            )
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=[prompt, self._types.Part.from_bytes(data=image_bytes, mime_type="image/png")],
                    config=self._types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                raw = (response.text or "").strip()
                if not raw:
                    raise RuntimeError("Gemini returned an empty response.")
                return schema.model_validate_json(raw), raw
            finally:
                try:
                    client.close()
                except Exception:
                    pass
        return self._with_retries(operation)

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]:
        return self._request(prompt, image_bytes, AgentDecision, self.prompts.system_instruction)

    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]:
        return self._request(prompt, image_bytes, TaskVerification, self.prompts.verifier_instruction)

    def list_models(self) -> list[ModelInfo]:
        client = self._genai.Client(api_key=self._api_key)
        try:
            output = []
            for item in client.models.list():
                actions = set(getattr(item, "supported_actions", None) or [])
                if actions and "generateContent" not in actions:
                    continue
                name = str(getattr(item, "name", "")).removeprefix("models/")
                if name:
                    output.append(ModelInfo("gemini", name, vision=None, details="generateContent"))
            return sorted(output, key=lambda item: item.model)[:80]
        finally:
            try:
                client.close()
            except Exception:
                pass
