# ADR-143: Backend Proxy for Local Inference — LM Studio Model Discovery and Remote VRAM Loading Across LAN/Mobile Devices

## Status
Accepted

## Date
2026-11-04

## Context
ReadOmni AI is deployed in a local network topology where the FastAPI backend, database, and local LLM engines (LM Studio running on GPU) reside on a host PC, while users frequently access the web interface from mobile devices (smartphones, tablets) or secondary laptops over Wi-Fi (`http://<PC_IP>:8000` or `http://<PC_IP>:5173`).

While translating novel chapters worked seamlessly from mobile devices (because translation HTTP requests are dispatched to the backend, which accesses `http://localhost:1234` on the same host machine), users reported that **model discovery, model changing, and model loading failed completely on mobile devices**:
- In [`src/pages/SettingsPage.tsx`](file:///D:/code_xI/Translator_Web/src/pages/SettingsPage.tsx) and [`src/pages/TranslatePage.tsx`](file:///D:/code_xI/Translator_Web/src/pages/TranslatePage.tsx), the model selection dropdowns remained empty or threw `Connection Refused / Failed to Fetch`.

### Root Cause Analysis
1. **Client-Side Loopback Resolution Trap**:
   - The frontend directly executed browser-side `fetch(`${lmUrl}/v1/models`)` where `lmUrl` defaulted to `http://localhost:1234`.
   - In mobile browsers, `localhost` (and `127.0.0.1`) resolves to the mobile phone itself, not the host PC running LM Studio. Since smartphones do not run LM Studio on port 1234, requests were rejected immediately by the mobile OS network stack.
2. **CORS & Network Binding Barriers**:
   - Even if `lmUrl` was manually configured to the host PC's local LAN IP (e.g. `http://192.168.1.100:1234`), requests were blocked by browser Cross-Origin Resource Sharing (CORS) policies or by LM Studio servers configured to listen exclusively on loopback interfaces (`127.0.0.1`).
3. **Absence of a Server-Side Management Bridge**:
   - The platform had no backend proxy endpoint to inspect or command local LM Studio state, forcing the client UI to attempt direct out-of-band communication.

---

## Decisions

### 1. Server-Side Model Discovery Proxy (`GET /api/settings/lm-studio/models`)
- Implemented [`get_lm_studio_models`](file:///D:/code_xI/Translator_Web/backend/routers/settings.py) in [`backend/routers/settings.py`](file:///D:/code_xI/Translator_Web/backend/routers/settings.py):
  - Bridges remote/mobile client requests to the host PC's LM Studio instance.
  - Implements **dual-stack loopback resolution**: automatically falls back between `localhost` and `127.0.0.1` to bypass Windows IPv4/IPv6 socket binding discrepancies:
    ```python
    urls_to_try = [primary]
    if "localhost" in primary:
        urls_to_try.append(primary.replace("localhost", "127.0.0.1"))
    elif "127.0.0.1" in primary:
        urls_to_try.append(primary.replace("127.0.0.1", "localhost"))
    ```
  - Enforces a 6.0s connection timeout and returns structured JSON:
    ```json
    { "status": "connected", "data": [...models], "lm_url": "http://localhost:1234" }
    ```

### 2. Remote VRAM Model Loading Proxy (`POST /api/settings/lm-studio/load`)
- Implemented [`load_lm_studio_model`](file:///D:/code_xI/Translator_Web/backend/routers/settings.py) in [`backend/routers/settings.py`](file:///D:/code_xI/Translator_Web/backend/routers/settings.py):
  - Atomically updates `GlobalSetting.lm_model` in the SQLite database so both PC and mobile devices share identical active model state.
  - Commands LM Studio to pre-load the model into GPU VRAM across multiple LM Studio API tiers:
    1. Tries LM Studio REST API v0: `POST /api/v0/models/load` with `{"model": req.model}`.
    2. Tries LM Studio REST API v1: `POST /v1/models/load`.
    3. Fallback JIT Probe: dispatches a lightweight 1-token dummy chat completion to trigger LM Studio's Just-In-Time (JIT) model auto-loader.
  - Returns confirmation status (`{"status": "ok", "model": "...", "loaded": true}`).

### 3. Frontend Multi-Tier Fetch & Model Sync
- In [`src/pages/SettingsPage.tsx`](file:///D:/code_xI/Translator_Web/src/pages/SettingsPage.tsx) and [`src/pages/TranslatePage.tsx`](file:///D:/code_xI/Translator_Web/src/pages/TranslatePage.tsx):
  - Prioritizes querying the backend proxy via `getApiUrl('/api/settings/lm-studio/models')`.
  - Retains direct client fetch as a secondary fallback for local desktop browser sessions.
  - Hooked `handleModelChange` to asynchronously trigger `/api/settings/lm-studio/load` with user toast feedback.

---

## Consequences

### Positive
- **Full Mobile Feature Parity**: Mobile users can discover models, switch active models, and preload VRAM directly from their phone over local Wi-Fi without connection errors.
- **CORS Elimination**: The mobile browser only communicates with the FastAPI backend port, completely bypassing cross-origin restrictions on LM Studio's port 1234.
- **Dual-Stack Resiliency**: Resolves both `localhost` and `127.0.0.1` transparently on Windows host environments.
- **Automated Verification**: Covered by unit tests in [`backend/tests/test_routers/test_lm_studio_proxy.py`](file:///D:/code_xI/Translator_Web/backend/tests/test_routers/test_lm_studio_proxy.py) with 100% pass rate.

### Trade-offs & Limitations
- **Host Dependency**: The host PC running LM Studio must remain awake and connected to the same local network for model discovery and inference to succeed.
