# LLM request control

The super admin manages actual outbound model traffic in Administration → Request control → AI traffic per minute. Select the channel, set the application cap and that channel’s cap, then save. Changes take effect immediately. Channel admins, reviewers and normal users cannot read or edit this endpoint.

## Environment settings

Defaults are 50 calls per rolling 60 seconds for the application and 50 per channel. All channels share the application cap: channel limits never add capacity above it.

```dotenv
LLM_REQUESTS_PER_MINUTE=50
LLM_CHANNEL_REQUESTS_PER_MINUTE=50
LLM_CHANNEL_RATE_LIMITS={"b2b":20,"b2c":20,"security":10}
LLM_RATE_LIMIT_MAX_WAIT_SECONDS=120
```

The JSON mapping is optional. Unlisted and newly created channels use `LLM_CHANNEL_REQUESTS_PER_MINUTE`. Limits must be whole numbers from 1 to 5000. Raising the application setting does not raise the AI provider’s approved capacity; keep it within that capacity. These controls cover this application’s clients, not other applications sharing the same provider deployment.

Initial defaults may be supplied in the process environment or root `.env`. Super-admin edits write the effective values to `backend/llm-rate.local.env` and Oracle. This separate managed file contains no credentials, is ignored by Git, and persists across backend restarts. `LLM_RATE_ENV_FILE` optionally changes its location. See `backend/llm-rate.env.example` for a configuration template. Back up the managed settings file with deployment configuration; it is separate from content export artifacts.

After a super admin saves settings, Oracle’s persisted values are authoritative across workers. Subsequent changes should use Request control; editing the generic `.env` does not overwrite saved admin settings. The panel displays the effective values.

## What counts

Every attempted outbound LLM POST consumes a slot, including normal and streamed generation, translations, each repair or provider retry, context detection, guideline/source checks, instruction refinement/enhancement and image/scan OCR. An English/Arabic request or bulk action can therefore consume multiple LLM slots. A request attempted against a provider still counts if the provider rejects it or the connection fails. Cached results, local instruction lookup, exports and calls rejected locally before dispatch do not consume an outbound slot. Docling’s own remote internal processing is outside this application’s LLM client.

These minute limits are independent of monthly allocations, which count logical user actions. Existing monthly allocations and accounting remain in place.

## Enforcement and persistence

`backend/llm_rate_limits.py` enforces an exact rolling window before the SDK sends HTTP requests. Both application and channel reservations are checked and consumed in one transaction. Provider SDK retries pass through the same gate. Reducing a cap retains recent usage and waits until capacity becomes available.

Oracle mode stores rolling usage, effective settings and the last 100 setting changes in the `llm_rate` row of `HARF_RUNTIME_STATE`. Database row locks coordinate workers and application instances sharing Oracle; Oracle UTC timestamps avoid differences between application server clocks. This reuses the existing schema and requires no new tables or installation script. Local mode uses an atomic SQLite row in `backend/llm-rate-limits.sqlite3`.

No transaction stays open while waiting. Up to eight pending attempts per backend process may wait, for at most the configured number of seconds. Additional queued traffic receives a retryable capacity message. The limiter rechecks at most every two seconds while waiting so live admin changes take effect. Local queue exhaustion is marked non-retryable at the SDK layer to avoid hidden SDK retry loops; users can retry the action. Provider retries remain enabled and counted. Streamed responses already admitted continue normally.

Image extraction is dispatched off the asynchronous event loop, so waiting for an image OCR slot does not freeze unrelated API requests.

## Files and endpoints

- `backend/llm_rate_limits.py`: rolling budgets, shared state, managed environment updates and gated HTTP client.
- `backend/ai_service.py`: the shared Azure client uses the gate; generation contexts attribute calls to channels.
- `backend/request_limits.py`: channel context for user actions and instruction enhancement.
- `backend/copywriter.py`: channel context and thread dispatch for image/document extraction.
- `backend/admin.py`: super-admin-only GET and PUT `/api/access/llm-request-limits`, plus activity logging for changes.
- `backend/stream_errors.py`: a clear local AI-capacity message.
- `src/components/llm-request-limits.jsx`: application/channel controls and a refreshable last-60-seconds usage display.
- `src/components/request-limits.jsx`: integrates the controls above monthly allocations, visible only to the super admin.
- `backend/test_llm_rate_limits.py`: concurrency, rolling windows, live configuration, queue behavior, SDK retries/streaming and permissions.

The managed environment file must be writable by the backend service account. An environment write failure prevents the corresponding settings update from committing. The database settings audit and the activity tracker identify the actor and changed limits.
