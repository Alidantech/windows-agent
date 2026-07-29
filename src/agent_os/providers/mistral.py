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


class MistralPlanner(CancellableProvider):
    """Mistral vision planner using chat.parse structured outputs."""

    name = "mistral"

    def __init__(
        self,
        settings: Settings,
        prompts: PromptBuilder,
        cancellation: CancellationToken | None = None,
    ) -> None:
        super().__init__(settings, cancellation)
        self.prompts = prompts
        try:
            try:
                from mistralai.client import Mistral
            except ImportError:
                from mistralai import Mistral
        except ImportError as exc:
            raise RuntimeError(
                "Mistral support is optional. Install it with "
                "'python -m pip install -e \".[mistral]\"'."
            ) from exc
        self._client_class: Any = Mistral
        self._api_key = provider_api_key(self.name)

    def _request(
        self,
        prompt: str,
        image_bytes: bytes,
        schema: type[T],
        system_instruction: str,
    ) -> tuple[T, str]:
        image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")

        def operation() -> tuple[T, str]:
            client = self._client_class(api_key=self._api_key)
            response = client.chat.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": image_url},
                        ],
                    },
                ],
                response_format=schema,
                temperature=0,
            )
            message = response.choices[0].message
            raw = (message.content or "").strip()
            parsed = getattr(message, "parsed", None)
            if parsed is None:
                if not raw:
                    raise RuntimeError("Mistral returned an empty response.")
                parsed = schema.model_validate_json(raw)
            if not isinstance(parsed, schema):
                parsed = schema.model_validate(parsed)
            return parsed, raw or parsed.model_dump_json()

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
