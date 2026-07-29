from __future__ import annotations

import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from agent_os.config import Settings, gemini_api_key
from agent_os.models import AgentDecision, TaskVerification
from agent_os.prompts import PromptBuilder

T = TypeVar("T", bound=BaseModel)


class GeminiPlanner:
    def __init__(self, settings: Settings, prompts: PromptBuilder) -> None:
        self.settings = settings
        self.prompts = prompts
        self.client = genai.Client(api_key=gemini_api_key())

    def _request(
        self,
        prompt: str,
        image_bytes: bytes,
        schema: type[T],
        system_instruction: str,
    ) -> tuple[T, str]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.api_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.settings.model,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                raw = (response.text or "").strip()
                if not raw:
                    raise RuntimeError("Gemini returned an empty response.")
                return schema.model_validate_json(raw), raw
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.api_retries:
                    delay = self.settings.api_retry_base_seconds * (2 ** (attempt - 1))
                    time.sleep(delay)
        raise RuntimeError(
            f"Gemini request failed after {self.settings.api_retries} attempts: {last_error}"
        ) from last_error

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]:
        return self._request(
            prompt=prompt,
            image_bytes=image_bytes,
            schema=AgentDecision,
            system_instruction=self.prompts.system_instruction,
        )

    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]:
        return self._request(
            prompt=prompt,
            image_bytes=image_bytes,
            schema=TaskVerification,
            system_instruction=self.prompts.verifier_instruction,
        )
