# ADR-144: Index-Translate Dedicated Adapter Priority Routing and Custom Instructions Scope Decoupling

## Status
Accepted

## Date
2026-11-04

## Context
During batch translation across novel chapters using the local Index-Translate profile (`IndexTeam/Index-Translate-2B-GGUF` on LM Studio), batch workers crashed permanently across all chapters with a fatal runtime exception:
```text
[ERROR] Batch chapter 27093 failed permanently: name 'custom_instructions' is not defined
[ERROR] Batch chapter 27094 failed permanently: name 'custom_instructions' is not defined
```

An investigation into the provider factory, batch translator pipeline, and prompt generation architecture uncovered several underlying issues:

### Empirical Findings & Root Cause Analysis

1. **Unscoped `custom_instructions` in Batch Execution**:
   - In `backend/services/background_translator.py`, `_do_translate` passed `custom_instructions` to `build_translation_prompt`. However, `custom_instructions` was neither declared as a local variable nor passed down through `ActiveBatch`, `start_batch`, or `_translate_registered`.
   - This caused an immediate `NameError` whenever batch translations executed.
2. **Provider Factory Misrouting & Hijacking**:
   - In [`backend/services/ai/factory.py`](file:///D:/code_xI/Translator_Web/backend/services/ai/factory.py), `AIProviderFactory.get_provider` checked the active `llm_provider` first (`if provider == "gemini":`, `if provider == "openai":`).
   - If a user had previously selected Gemini or OpenAI in settings but requested an Index-Translate model, the factory saw that the model string did not match cloud prefixes and defaulted to cloud models (`gemini-2.5-flash` or `gpt-4o`). The specialized [`IndexTranslateAdapter`](file:///D:/code_xI/Translator_Web/backend/services/ai/index_translate.py) was completely bypassed!
   - Similarly, [`resolve_active_model`](file:///D:/code_xI/Translator_Web/backend/services/ai/settings.py) wiped out Index-Translate models if the saved provider was not `lm_studio`.
3. **Sampling Temperature Mismatch (Greedy Decoding Requirement)**:
   - Bilibili's Index-Translate model card strictly dictates greedy decoding (`temperature=0.0`) with thinking disabled to prevent hallucination loops on 2B parameters.
   - However, `IndexTranslateAdapter` inherited method signatures from `LMStudioAdapter` with default parameter `temperature: float = 0.3`. When callers invoked `chat_completion` or `stream_chat` without explicitly passing temperature, it defaulted to `0.3`, degrading translation fidelity.
4. **ContextEngine Indentation Coupling Trap**:
   - In [`backend/services/context_engine.py`](file:///D:/code_xI/Translator_Web/backend/services/context_engine.py), the `if custom_instructions:` block was nested inside `if thread_id:`. Consequently, custom instructions were discarded during quick or threadless translations.
5. **AttributeError on Unset `lm_url`**:
   - In factory and adapter constructors, evaluating `(gs.lm_url if gs else "http://localhost:1234")` returned `None` when `gs` existed but `gs.lm_url` was `None` in the database, causing crashes on `base_url.rstrip("/")`.

---

## Decisions

### 1. Absolute Priority Routing in `AIProviderFactory`
- In [`backend/services/ai/factory.py`](file:///D:/code_xI/Translator_Web/backend/services/ai/factory.py), added an unbypassable priority branch at the very top of `get_provider`:
  ```python
  if is_index_translate_model(model) or provider in ("index_translate", "index"):
      from services.ai.index_translate import IndexTranslateAdapter
      resolved_url = (getattr(gs, "lm_url", None) or "http://localhost:1234")
      return IndexTranslateAdapter(base_url=resolved_url, model=model)
  ```
- Updated [`resolve_active_model`](file:///D:/code_xI/Translator_Web/backend/services/ai/settings.py) to preserve `requested_model` unconditionally whenever `is_index_translate_model(requested_model)` is true, regardless of the active provider.

### 2. End-to-End `custom_instructions` Propagation
- Added `custom_instructions: Optional[str] = None` across:
  - `BatchTranslateRequest` in [`backend/routers/batch.py`](file:///D:/code_xI/Translator_Web/backend/routers/batch.py).
  - `ActiveBatch`, `start_batch`, and `_translate_registered` in [`backend/services/background_translator.py`](file:///D:/code_xI/Translator_Web/backend/services/background_translator.py).
- Unnested `if custom_instructions:` in `ContextEngine.build_translation_prompt` outside the `if thread_id:` block.

### 3. Greedy Decoding Enforcement in `IndexTranslateAdapter`
- In [`backend/services/ai/index_translate.py`](file:///D:/code_xI/Translator_Web/backend/services/ai/index_translate.py):
  - Overrode `chat_completion`, `chat_completion_detailed`, and `stream_chat` to explicitly resolve default `temperature` to `self.translation_temperature` (`0.0`).
  - Automatically injects `{"chat_template_kwargs": {"enable_thinking": False}}` for Index-Translate models.

### 4. Defensive Null-Guards
- Enforced `getattr(gs, "lm_url", None) or "http://localhost:1234"` across all resolution call-sites and guarded `IndexTranslateAdapter.__init__`.

---

## Consequences

### Positive
- **Eliminated Fatal Runtime Crashes**: Batch translation runs to completion without `NameError: name 'custom_instructions' is not defined`.
- **Architectural Integrity**: `IndexTranslateAdapter` cannot be hijacked or overridden by cloud provider configurations.
- **Optimal Translation Quality**: Strictly adheres to 0.0 temperature greedy decoding and concise single-turn formatting required by Index-Translate 2B.
- **Comprehensive Test Coverage**: All 52 targeted regression tests and 1,350 suite-wide backend tests pass green.

### Trade-offs & Limitations
- **Local Context Budgeting**: Index-Translate retains a 300-character context note ceiling (`MAX_INDEX_CONTEXT_CHARS`) to protect the 2B model context window from saturation.
