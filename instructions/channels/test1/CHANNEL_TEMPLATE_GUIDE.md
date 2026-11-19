# Template Instructions — Output Structure and Examples

This is a neutral starter. No template is configured until the channel administrator defines one below. Do not apply another channel's templates, products or terminology.

## How to configure a template
1. Open this channel's Instructions page and select this file.
2. Choose Edit file. Add a template name, intended use, ordered headings, required fields, optional fields, length limits and table columns.
3. State how missing information should appear. Use [Required input] rather than inventing facts.
4. Include a short example labelled as an example, not reusable facts.
5. Save changes, then test a new generation using the template name in the request title.

## Default output
Until a template is configured, provide clear headings, concise paragraphs and lists. Use a table only for information that benefits from comparison. Return ready-to-use content, not these instructions. Ask for clarification if a named template has not been defined.

## Channel templates
Add approved templates here. Preserve this channel's factual and behavioural rules.

## Platform privacy boundary — 30 October 2026

In administration, super admins manage channels, people, request budgets and models without access to other users’ content, feedback, activity or approval requests. They retain the main writing workspace: welcome page, channel switching, single and bulk generation, uploads, editing and exports. Their archive, personal activity and author notifications show their own work only. They can read, edit and restore instruction files and their history across channels. They cannot approve, reject or override review decisions. Channel admins retain those controls for their own channel. Reviewer assignment is account management and does not grant the super admin content access.

The super-admin overview contains aggregate active accounts, recent account additions, monthly request usage/limits and provider-reported token counts. Historical tokens that were not measured are shown as Not recorded. Account addition counts use stored creation dates. This boundary applies to the interface and direct API requests.

### Super-admin instruction access

Super admins can select any channel in **Administration → AI instructions**, read the formatted files, edit Markdown, save confirmed revisions, compare version history and restore older versions. The optional AI instruction helper remains available. Administrative content views, other users’ activity and feedback, approval queues and reviewer notifications remain unavailable to the super-admin role. This restriction does not remove the main writing workspace or the super admin’s own saved work and author notifications.

### Per-model token limits and operational log retention

Only the super admin manages model settings. Open **Models & routing → Token limits** to set different maximum input and output tokens for each model, then **Save model settings**. The Models, Token limits, Routing and Connections tabs keep these tasks separate and retain drafts while switching. Input includes retrieved guidelines, the brief, extra instructions and revision context. Each call uses its selected model’s input limit; oversized input stops before sending and is never silently truncated. Saved input overrides update `LLM_MODEL_INPUT_TOKEN_LIMITS` in `platform-policy.local.env` and apply immediately to new calls. `DEFAULT_MAX_INPUT_TOKENS` is only a seed for unconfigured models. Output limits remain separate. Local tokenizers count supported text models; unknown tokenizers and images use conservative estimates. Model-native combined context limits still apply. Request control contains monthly requests, user allocations, bulk limits, AI traffic and log retention only. Actual usage reporting remains; there is no monthly token budget.

Operational log retention defaults to **180 days**. The super admin can change the period (31–3650 days) or run cleanup after confirmation. Automatic cleanup runs at backend startup and hourly. Expired activity logs, notifications, past-month request records and usage metrics expire. Saved copies, source files, approval evidence, feedback, instruction files and all instruction versions remain. Undated records and current quotas are protected. External backups and infrastructure logs require separate policies. Admin saves update `platform-policy.local.env`; no database schema migration is required.
