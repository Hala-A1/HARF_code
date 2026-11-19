# AI models and confidential documents

## Local setup and activation

The new gateway URLs and keys are intentionally blank in the private root `.env`.
Standard generation retains the existing Azure connection while `MODEL_PROVIDER` is blank.
Confidential requests never use that legacy connection: they require the on-premise gateway,
even before live routing is activated. Until it is configured, they return a clear error.
The model screen explicitly reports whether standard live routing is active.

1. Copy the fields from `backend/inference.env.example` into the root `.env` as needed.
2. IT supplies `APIM_BASE_URL`, `APIM_API_KEY`, `APIM_API_VERSION`,
   `LITELLM_BASE_URL` and `LITELLM_API_KEY`.
3. Cloud uses `APIM_API_TYPE=responses`; on-premise uses
   `LITELLM_API_TYPE=chat_completions`. These protocols are deliberately enforced.
4. The cloud base stops before `/responses`. The internal base stops before
   `/chat/completions`; no `/v1` is added automatically. Use the exact IT-approved base.
5. Keep HTTPS certificate validation enabled. IT must correct hostname/certificate
   mismatches and provide corporate DNS/VPN connectivity. Redirects are disabled.
6. Restart the backend, sign in as super admin and open **Models & routing**.
   Test each model with the provided connection test. It sends only a fictional
   request asking for “OK”, never a document.
7. After validation, set `MODEL_PROVIDER=live` and restart to activate the new router
   for standard requests too. `MODEL_PROVIDER=mock` blocks all live AI calls; it
   does not fabricate successful content or guideline scores.

Connections are environment-owned (`INFERENCE_CONNECTION_SOURCE=environment`).
Database-owned connections and credential encryption/key rotation are not implemented.
Never place credentials in model rows, source control or client code. Use a secret manager
to supply the same environment variables when deploying. API credentials pasted into chats
should be replaced before production use.

## Super-admin workflow

Only super admins can access the model inventory, update policy, or run connection tests.
Channel admins, approvers and ordinary users cannot change routing through these APIs.

- Choose the application default model for standard work.
- Optionally choose a different standard model for each channel.
- Choose an enabled **on-premise** model for confidential work. Cloud selection is rejected
  by the server even if someone changes the browser request manually.
- Add or disable models, update display/deployment names and output token limits.
- Enable **Approved for image reading** only after confirming the deployment supports images.
- Save before testing. Configured inventory means administrator-configured, not dynamically
  discovered or proven available. The three initial on-premise IDs are `llama4-scout`,
  `gpt-oss-120b` and `Qwen3-Coder-Next`; availability depends on the actual gateway.
- Environment deployment allowlists remain enforced. A nonempty allowlist must be updated
  by IT before adding a new upstream ID. An omitted/empty list leaves inventory to the admin.
- Concurrent edits use a revision check, and changes are recorded in the existing audit log.
  Requests already in progress retain their routing snapshot; new requests use saved policy.

The initial cloud model is the application's existing Azure deployment. Recognized existing
vision deployments retain image support. On-premise image support defaults to off until approved.
Temperature is omitted unless explicitly set in a model's policy, because not every deployment
accepts that parameter. The default output budget is `DEFAULT_MAX_TOKENS` (initially 4096).

## User workflow and protection boundaries

Select **Confidential document** before uploading or entering confidential material.
This applies to single copy, bulk copy and all channels, including Regulatory Compliance.
The flag covers context detection, instruction enhancement, generation, translation,
component repair, revisions, coherence checks, guideline checks and automatic export scoring.

- Confidential requests resolve only to the configured on-premise model. There is no cloud
  fallback when that model, its credentials, DNS or connectivity is unavailable.
- Source text, generated outputs and uploaded file bytes receive channel-scoped SHA-256
  fingerprints. Previously classified content and identical re-uploaded files remain
  restricted even if the request omits the browser checkbox/header.
- Saved copies retain their confidentiality flag, gateway and model. Reopening them restores
  the flag, and saved-copy operations enforce it independently on the server.
- Native TXT, DOCX and spreadsheet extraction runs locally. Confidential PDFs bypass the
  external Docling service. Scanned PDFs/images require approved on-premise image reading;
  without it processing is blocked. No OCR request is rerouted to the cloud.
- The flag remains locked while the current brief contains content. **New brief** confirms
  before clearing the workspace; it does not declassify or delete archived copies.
- Standard uploads may use existing external extraction. Mark confidential material before
  upload: marking it afterwards cannot undo an earlier external upload.

This is an application routing boundary, not endpoint attestation, encryption at rest,
network-level DLP or semantic detection of all confidential paraphrases. IT must ensure
the configured internal gateway itself does not forward requests to cloud services.
Retyped/transformed content without its classification or provenance cannot be recognized
reliably by exact fingerprints. Existing document/storage retention and access rules continue
to apply. Nothing in this feature sends notifications or content to a new third party.

## Storage and implementation

No Oracle schema change is needed. Model policy and confidentiality fingerprints are stored
in the existing access/runtime state (Oracle when enabled; local JSON otherwise). Saved-copy
metadata uses the existing batch store. Back up this state with the application; deleting
the fingerprint registry loses protection for detached text/file copies.

| File | Responsibility |
| --- | --- |
| `backend/inference.py` | Gateway validation, policy resolution, adapter for Responses/Chat Completions, streaming normalization and route identity for score caches |
| `backend/inference_guard.py` | Request classification, file/content fingerprints, stream provenance and persisted-copy enforcement |
| `backend/inference_admin.py` | Super-admin inventory, routing policy, revision checks and synthetic connection tests |
| `backend/generation_context.py` | Carries the private routing snapshot through parallel workers and nested requests |
| `backend/docling_client.py` | Bypasses external extraction for confidential documents |
| `src/components/inference-models.jsx` | Super-admin model controls |
| `src/auth.js`, `src/pages/copywriter.jsx` | Per-user/channel confidential workspace selection and protected archive reopening |

Every outbound AI attempt continues through the existing application/channel minute limiter.
Monthly logical quotas are unchanged. Assessment caches include route, model, protocol,
classification and policy revision, so a cloud assessment cannot silently substitute for an
on-premise confidential assessment. Responses requests set `store=false`.

The Responses streaming adapter follows the official event lifecycle:
[`response.output_text.delta`, `response.completed` and error events](https://developers.openai.com/api/docs/guides/streaming-responses).
## Synchronizing configuration and administrator changes

Models added to the configured `AZURE_EXPLICIT_DEPLOYMENTS` / `ON_PREM_EXPLICIT_MODELS` lists appear in Models & routing even when a policy was previously saved. Configuration defaults such as `DEFAULT_MAX_TOKENS` update existing rows only where the administrator has not overridden the old default. Models added or edited in the application remain stored in Oracle/local runtime storage and are used by new requests. Changes within an already-running request remain pinned to that request's route.

Use **Refresh models** to reload the effective catalog; this button is disabled while there are unsaved edits. Concurrent catalog changes advance the policy revision, so an outdated administrator save is rejected rather than overwriting new configuration. Removed configuration-managed models are disabled; a selected missing/disabled model requires an explicit replacement, with no automatic gateway fallback.

For live file-based changes, set `INFERENCE_CATALOG_ENV_FILE` to a shared UTF-8 environment file containing only deployment lists and optional `DEFAULT_MAX_TOKENS`. It is reread on new policy/route resolutions without restarting. Ordinary process environment/code changes require the normal backend reload. This file does not own connection secrets or replace database administrator overrides. Environment deployment allowlists and confidential on-premise restrictions remain enforced.

**Models & routing** has Models, Token limits, Routing and Connections tabs. Each model has its own `max_input_tokens` and `max_tokens` output setting. Saved input limits are mirrored to `LLM_MODEL_INPUT_TOKEN_LIMITS` in the managed platform-policy environment file and read on each new AI call. There is no global input-limit control in Request control. See Input_Tokens_and_Retention.md for counting, defaults and migration details.

