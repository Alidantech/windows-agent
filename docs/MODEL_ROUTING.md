# Model routing

## Modes

`/model auto` builds an ordered route list from `WINDOWS_AGENT_AUTO_MODELS`. `/model provider:model` pins a preferred model while optional fallbacks may remain configured.

## Context preservation

A fallback receives the exact same system instruction, task and current step, screenshot bytes, control lease and capture token, recent action/result history, user guidance and persistent session context.

Switching providers therefore changes inference transport, not task state.

## Failure classification

Immediate fallback is allowed for rate limits, quota exhaustion, overloaded/unavailable service, transient server errors, DNS/connection failures and timeouts. Structured-output validation failures do not silently switch because they may indicate an incompatible model or programming error.

Per-day quota messages receive a long cooldown. Short transient failures use the configured cooldown or provider retry hint.

## Model discovery

`/models` queries the provider model-list API when its SDK and credential are ready. Mistral entries with `vision=false` are filtered. OpenAI and Gemini model listings do not always expose enough modality metadata, so the UI marks vision as unknown and the user should select an image-capable model.
