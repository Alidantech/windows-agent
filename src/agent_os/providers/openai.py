from __future__ import annotations

import base64
from typing import Any, TypeVar

from pydantic import BaseModel

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings, provider_api_key
from agent_os.models import AgentDecision, TaskVerification
from agent_os.prompts import PromptBuilder
from agent_os.providers.base import CancellableProvider

T = TypeVar("T", bound=BaseModel)


class OpenAIPlanner(CancellableProvider):
    """OpenAI Responses API planner with image input and Pydantic output parsing."""

    name = "openai"

    def __init__(
        self,
        settings: Settings,
        prompts: PromptBuilder,
        cancellation: CancellationToken | None = None,
    ) -> None:
        super().__init__(settings, cancellation)
        self.prompts = prompts
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI support is optional. Install it with "
                "'python -m pip install -e \".[openai]\"'."
            ) from exc
        self._client_class: Any = OpenAI
        self._api_key = provider_api_key(self.name)

    @staticmethod
    def _extract_parsed(response: Any, schema: type[T]) -> tuple[T, str]:
        parsed = getattr(response, "output_parsed", None)
        raw = (getattr(response, "output_text", "") or "").strip()
        if parsed is None:
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    parsed = getattr(content, "parsed", None)
                    if parsed is not None:
                        break
                if parsed is not None:
                    break
        if parsed is None and raw:
            parsed = schema.model_validate_json(raw)
        if parsed is None:
            raise RuntimeError("OpenAI returned no parsed structured output.")
        if not isinstance(parsed, schema):
            parsed = schema.model_validate(parsed)
        return parsed, raw or parsed.model_dump_json()

    def _request(
        self,
        prompt: str,
        image_bytes: bytes,
        schema: type[T],
        system_instruction: str,
    ) -> tuple[T, str]:
        image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")

        def operation() -> tuple[T, str]:
            client = self._client_class(
                api_key=self._api_key,
                timeout=self.settings.api_timeout_ms / 1000,
                max_retries=0,
            )
            try:
                response = client.responses.parse(
                    model=self.model,
                    instructions=system_instruction,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {
                                    "type": "input_image",
                                    "image_url": image_url,
                                    "detail": "high",
                                },
                            ],
                        }
                    ],
                    text_format=schema,
                )
                return self._extract_parsed(response, schema)
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()

        return self._with_retries(operation)

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]:
        return self._request(
            prompt,
            image_bytes,
            AgentDecision,
            self.prompts.system_instruction,
        )

    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]:
        return self._request(
            prompt,
            image_bytes,
            TaskVerification,
            self.prompts.verifier_instruction,
        )
