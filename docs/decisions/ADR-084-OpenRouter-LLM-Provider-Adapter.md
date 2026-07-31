# ADR-084: OpenRouter LLM Provider Adapter

## Status
Accepted

## Date
2026-07-26

## Context
The translation engine supported LM Studio (local), Google Gemini, and OpenAI API adapters (ADR-029). Users requested native integration with **OpenRouter**, an aggregator API that provides access to hundreds of open-source and proprietary cloud models (DeepSeek-V3/R1, Claude 3.5 Sonnet, Llama 3.3, Qwen 2.5, etc.) through a single API key.

OpenRouter follows OpenAI chat completions format but requires specific custom HTTP headers (`HTTP-Referer` and `X-Title`) for application attribution and rate limit accounting.

## Decision
1. Add `openrouter` as a supported `llm_provider` option in `GlobalSetting` and `AIProviderFactory`.
2. Implement `OpenRouterAdapter` in `backend/services/ai/openrouter.py` inheriting from `OpenAIAdapter`, with custom header injection (`HTTP-Referer: https://readomni.ai`, `X-Title: ReadOmni AI`).
3. Add `openrouter_model`, `openrouter_api_key`, `openrouter_api_keys`, and `openrouter_active_key_index` fields to `GlobalSetting` with SQLite auto-migrations.
4. Extend secret key loading (`load_secrets`, `save_secrets`, `get_active_api_key`, `rotate_api_key`) to support OpenRouter key rotation.
5. Update `SettingsPage.tsx` to include OpenRouter in the provider selection grid, with model presets (`deepseek/deepseek-chat`, `anthropic/claude-3.5-sonnet`, `meta-llama/llama-3.3-70b-instruct`, etc.), custom model text input, and multiple key rotation management.

## Alternatives Considered

### Relying on generic OpenAI Base URL customization
- Pros: No new provider adapter required.
- Cons: Missing required OpenRouter headers (`HTTP-Referer`, `X-Title`), manual model string typing required, no dedicated key rotation pool.
- Rejected: Native provider support offers superior UX and reliability.

## Consequences
- Users can translate web novels using any OpenRouter model with seamless key rotation.
- `AIProviderFactory` automatically resolves `openrouter` endpoints when selected.
- All 88 backend unit tests pass, confirming backward compatibility with existing adapters.
