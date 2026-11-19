# Copywriter V2 — Testing branch

Branch: `copywriter_V2_Testing`

Saved: 24 October 2026

Base: `rewrite_V1`, commit `d8533b4`

This branch saves the current application for testing, including the changes made since the V1 release.

## Included changes

- Unified red and neutral application theme, Articulate branding, balanced writing/output panels, updated sign-in/welcome and administration styling, and a 90% default screen scale.
- Inline editing of rendered copy, bilingual English/Arabic output views, stable language ordering during approval, and an adaptive full-width output view for longer content with navigation back to the input.
- Manual guideline/source checks with compact scores, expandable evidence and source references, and a section that collapses before or after checking. Automatic post-generation checks are disabled.
- Cleaner Excel exports: five essential output columns, complete text in one wrapped cell per output, proper date cells, Arabic reading direction, readable sizing, and source references on a separate sheet when needed.
- Configurable application/channel LLM requests-per-minute caps, persisted super-admin controls, and bounded queuing. Monthly request budgets remain separate.
- LDAP configuration compatibility and an environment-controlled local developer mode, with authentication tests. A live LDAP connection still requires valid local directory credentials and connectivity.
- Indexed instruction selection, glossary filtering, cached retrieval and request-scoped reuse of general instructions. The preview now uses the same B2C format routing as generation; unrelated example catalogues are omitted from selected format prompts. The preview exposes selected sections, format/component scope, cache information and instruction-text reduction.
- Clearer handling of empty, malformed or interrupted API responses and development proxy failures.
- The existing Security template clarification for regulatory memo background sections is retained.

## Validation at save time

- 358 backend tests passed using isolated local test storage and mocked external services where applicable.
- Retrieval parity checked for all 17 B2B components, five B2C formats and explicit template IDs, plus Security. Tests cover caching, instruction changes, channel isolation and general-rule reuse across ten parallel components.
- Frontend lint, unit tests and production build checked before push.
- Running backend restarted successfully with Oracle storage healthy; live B2C SMS retrieval preview returned only the SMS template family.

These checks do not certify real model outputs for every brief or a live LDAP login. Retrieval text reductions are character measurements, not exact token billing or end-to-end speed guarantees. See [Instruction retrieval](Instruction_Retrieval.md) and [LLM request control](LLM_Request_Control.md) for implementation details.

## Configuration and data

Private environment files, credentials, local databases, uploaded documents, test previews, logs and generated exports are excluded from this branch. Configure the destination environment using the supplied example files. Pushing this branch does not deploy the application or migrate its Oracle data.
