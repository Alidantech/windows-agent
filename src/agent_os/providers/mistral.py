from __future__ import annotations

import base64
from typing import Any, TypeVar

from pydantic import BaseModel

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings, provider_api_key
from agent_os.models import AgentDecision, TaskVerification
from agent_os.prompts import PromptBuilder
from agent_os.providers.base import CancellableProvider, ModelInfo

T = TypeVar("T", bound=BaseModel)


class MistralPlanner(CancellableProvider):
    name = "mistral"

    def __init__(self, settings: Settings, prompts: PromptBuilder, model: str, cancellation: CancellationToken | None = None) -> None:
        super().__init__(settings, model, cancellation)
        self.prompts = prompts
        try:
            try:
                from mistralai.client import Mistral
            except ImportError:
                from mistralai import Mistral
        except ImportError as exc:
            raise RuntimeError("Mistral support is optional. Install windows-agent[mistral].") from exc
        self._client_class: Any = Mistral
        self._api_key = provider_api_key(self.name)

    def _request(self, prompt: str, image_bytes: bytes, schema: type[T], system_instruction: str) -> tuple[T, str]:
        image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
        def operation() -> tuple[T, str]:
            client = self._client_class(api_key=self._api_key)
            response = client.chat.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": image_url},
                    ]},
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
            return (parsed if isinstance(parsed, schema) else schema.model_validate(parsed)), raw or schema.model_validate(parsed).model_dump_json()
        return self._with_retries(operation)

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]:
        return self._request(prompt, image_bytes, AgentDecision, self.prompts.system_instruction)

    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]:
        return self._request(prompt, image_bytes, TaskVerification, self.prompts.verifier_instruction)

    def list_models(self) -> list[ModelInfo]:
        client = self._client_class(api_key=self._api_key)
        result = client.models.list()
        data = getattr(result, "data", result) or []
        output: list[ModelInfo] = []
        for item in data:
            capabilities = getattr(item, "capabilities", None)
            vision = getattr(capabilities, "vision", None) if capabilities is not None else None
            model_id = str(getattr(item, "id", ""))
            if model_id and vision is not False:
                output.append(ModelInfo("mistral", model_id, vision=vision, details="account model"))
        return output
