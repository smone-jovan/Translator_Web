# ADR-086: Text-Only Gemini & Gemma Model Catalog

## Status
Accepted

## Date
2026-08-01

## Context
Google AI Studio updated its model lineup with new generations (`gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemma-4-31b`, `gemma-4-26b`). The system's model list contained outdated RPM/RPD parameters and included non-translation multimodal models (audio TTS, image generation Nano Banana, embeddings, robotics, and agents).

## Decision
1. **Filter Non-Text Models**: Explicitly filter out image generation (*Nano Banana*), audio TTS, embeddings, robotics, and agent models.
2. **Text-Out LLM Catalog**: Retain only valid text generation LLMs capable of web novel translation (`gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`, `gemma-4-31b`, `gemma-4-26b`, `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-3.1-pro`, `gemini-2.5-pro`, `gemini-2-flash`, `gemini-2-flash-lite`).
3. **RPM Pacing Updates**: Update rate-limiting delays in `background_translator.py` (e.g., 4.2s for 15 RPM models, 2.2s for 30 RPM Gemma models) to prevent HTTP 429 errors during batch translation.

## Consequences
- Clean UI model selector displaying accurate free-tier RPM and RPD quotas.
- Efficient rate limiting without hitting API quota bans.
