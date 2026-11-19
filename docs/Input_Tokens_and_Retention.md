# Input token limits and operational log retention

Super admins open **Models & routing → Token limits** to set different input and output limits for each model. The section has four tabs: **Models**, **Token limits**, **Routing**, **Connections**. Request control contains request quotas, batch capacity, traffic and retention only. Monthly token budgeting remains removed.

## Input enforcement

Each model row has `max_input_tokens` and separate `max_tokens` for output. Both accept positive whole numbers without an application-imposed upper ceiling; the configured model and gateway must support the chosen values. Calls use the selected model’s input limit, including cloud Responses and on-premise Chat Completions, legacy Azure calls, streaming, generation, translation, analysis, instruction helpers, OCR and repair calls. Legacy requests match the actual Azure deployment instead of using a different selected gateway model. The full assembled messages are checked after instruction retrieval, with extra response-format schema and a framing allowance included. Each call in a bulk job is checked separately, not the sum of all outputs in that job.

Text is counted locally using bundled tiktoken vocabularies for recognised model names. Unknown model/deployment names use a conservative UTF-8 byte estimate; images use a conservative vision allowance. These are preflight counts/estimates, not a promise to match a provider’s private message or image accounting exactly. Actual provider-reported usage remains in the overview. No source text is sent to a token-counting service or saved in the input guard.

Oversized calls raise `input_token_limit` before the SDK sends them. Non-streaming routes return HTTP 413 with the required count and configured limit; streaming routes return a non-retryable error message. The user can shorten the source or ask the super admin to raise the limit. Instructions and facts are never silently truncated. A provider’s native context window must still accommodate its input and output; increasing the platform limit does not increase the model’s capacity. Already-sent calls finish under their earlier settings.

## Persistence and immediate updates

**Save model settings** saves model rows in Oracle/local runtime storage and a model-ID-to-limit JSON map in `LLM_MODEL_INPUT_TOKEN_LIMITS` in **backend/platform-policy.local.env**, using an atomic write under the shared storage lock. New AI calls reread that map, so connected workers use the selected model’s new limit without a restart. `DEFAULT_MAX_INPUT_TOKENS=64000` is only a bootstrap default for models without a configured limit; it is not a shared cap. Existing models retain their current value during upgrade and can then be edited independently. The former global `LLM_MAX_INPUT_TOKENS` is read only as an upgrade seed and is removed from the active file during migration.

`PLATFORM_POLICY_ENV_FILE` can select another shared configuration-file path. Distributed hosts need that same shared file or equivalent configuration propagation. Channel admins and ordinary users cannot edit model policy. Failed model persistence rolls the environment file back; retention saves preserve all model limits. Code/config edits to the per-model map synchronize back into the catalog on its next read. Draft changes remain while switching Models & routing tabs; saving applies all tabs together. Conflicting stale revisions are rejected.

`backend/platform-policy.env.example` is the deployment template. Removed monthly token cap variables are no longer read, and the monthly reservation/charging code has been deleted. Historical actual usage counts remain intact. No Oracle schema migration is required.

## Log retention

The existing **180-day** default stays configurable by the super admin under **Log retention**, from **31–3650 days**, using `USER_LOG_RETENTION_DAYS`. Cleanup runs at startup and hourly, or after confirmation on demand. Increasing retention cannot recover previously deleted records.

Expired activity logs, notifications, past-month request usage, daily token usage, daily contributor metrics and rate-setting audit logs expire. Current-month quota counters, live requests and undated activity/notification records are protected. Earlier count-based log caps can remove records sooner; retention is a maximum age, not guaranteed full history.

Users/channels, saved briefs and copies, uploaded files, saved-copy approval evidence, feedback, instruction files and every instruction version, confidentiality provenance, model settings and request allocations stay. External backups, server logs and storage require separate organisational retention policies.
