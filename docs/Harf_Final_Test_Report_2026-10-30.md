# Harf final regression and readiness report

Date: 30 October 2026, Asia/Dubai. Scope: the current local workspace, including the uncommitted changes already present. No commit, push or deployment was performed.

## Readiness decision

**Application regression checks passed. Final release is blocked by live storage capacity and unresolved scanned Arabic OCR.** Passing tests do not guarantee every future input or deployment will succeed.

## Changes completed

- Moved the existing Confidential document control underneath the brief drop area in single-copy mode and underneath the file drop area in bulk mode, across all workspaces.
- Preserved the confidentiality request header, protected routing, locked classification after a confidential brief is loaded, and New brief confirmation.
- Added bilingual approval regression scenarios across B2B, B2C, Regulatory Compliance and CX Comms. There was no need to weaken or replace the existing language approval gate.

## Approval rules verified

- English-only and Arabic-only requests require approval of their requested language.
- Bilingual requests remain at the current layer after either language approves. The next layer, or final approved state, opens only after both required languages are approved.
- One eligible reviewer per language is sufficient; additional same-language reviewers do not all need to approve. A reviewer assigned both languages can explicitly review both; a specialist cannot approve the other language.
- Both language orders were tested with final layers 1, 2 and 3 in every workspace: 24 sequential bilingual flows and 48 layer completions. The first language never completed a layer alone.
- Concurrent English/Arabic decisions preserve both approvals. Concurrent duplicate same-language decisions do not advance twice. Duplicate final approval produces one final approval notification per recipient.
- Rejections, returns, notes, resubmissions, required reasons, invalid roles/channels/layers/languages, and stale review rounds were tested. Returning and resubmitting clears previous language approvals; an old browser round cannot approve new work.
- Changes to the configured final layer preserve pending requests' captured route and apply to newly submitted or resubmitted work.

## Automated and browser results

| Check | Result | Boundary |
| --- | --- | --- |
| Full backend suite | 497 passed | Isolated fixtures, mocked providers; no real customer approvals changed |
| Frontend unit suite | 55 passed | Display helpers, editing/formatting/export metadata, permissions and tutorial logic |
| Dedicated approval suite | 30 passed | Includes the cross-workspace/language/layer matrix and races; included in the full suite |
| Lint | Passed | No reported lint errors |
| Production build | Passed | Existing warning: main JavaScript chunk exceeds 500 kB before gzip |
| Confidential upload browser checks | Passed | All four workspaces, single/bulk placement, desktop/mobile, protected headers, locked classification |
| Reviewer browser checks | Passed | Both language orders, three layers, 12 decisions; assigned-language output, correct identity/layer/round, disabled duplicate button |
| Tutorial browser walkthrough | Passed | 204 steps across 12 role/workspace combinations |
| Channel controls browser check | Passed | Role visibility, keyboard selection, centered creation dialog, refresh and mobile fit |
| Selected workspace overview | Passed | Aggregate figures, hours estimate, filters, switching, privacy and responsive layout |
| User-removal interface | Passed | Confirmation, cancel, protected accounts, refresh and reviewer roster |
| Archived component-set review | Passed | Expandable findings/evidence and mobile layout |
| Live Oracle connection and reads | Passed | Health reports Oracle; profile and runtime data are readable; 19 GENAI_HARF tables and zero invalid objects |
| Live Oracle concurrency lock | Passed | Two independent sessions enforce exclusive runtime-state access; locks released and transactions rolled back |
| Live Oracle application save | **Failed: ORA-01536** | Current USERS quota is 250 MB, with approximately 248 MB allocated |

Browser interaction tests used fictional accounts/content and mocked service responses. They verify the actual interface; backend tests separately verify API rules. Successful real-provider generation for every component, a production concurrency/load test and a corporate LDAP sign-in were not claimed.

Backend coverage includes source uploads and validation, indexed instruction selection, all 17 component schemas and their relevant repair/brand/character-limit rules, bilingual generation/recovery, review/source checks, quotas/rate limits, confidentiality/routing, LDAP/developer authentication behavior, user removal, instruction versions, feedback, analytics, storage/recovery and export structures. PDF/Word/text/Excel export behavior was covered by automated assertions; this does not constitute manual visual inspection of every possible user document.

## Blockers before finalization

### 1. Oracle storage capacity

The final live save test failed with `ORA-01536`. Renaming tables to GENAI_HARF_ and renaming the SQL Developer label to Harf Local do not increase the database user's quota. A correctly privileged SYSTEM/DBA session must increase the REWRITE_APP quota; then rerun a save/read test, actual generation/archive saving, and an end-to-end approval cycle. Do not grant DBA permissions to the application account. Installation scripts must not be rerun on the existing database.

Prepared script: `database/oracle/07_increase_local_storage_quota.sql`.

### 2. Arabic scanned PDF OCR

The approved page 4 of the supplied Arabic UWB PDF did not pass exact numeric verification. Source-only AI reads changed or omitted some dotted section labels or repeated numbers. Docling health succeeded, but conversions explicitly requesting Arabic failed with Internal processing error, including both tested EasyOCR and Tesseract presets. Server logs are needed to establish the cause; Arabic language-model availability is not proven by a healthy HTTP endpoint.

Numeric checks remain enforced. The required next step is to repair/validate the service's Arabic OCR configuration, then repeat page 4 and the complete document upload. A selectable-text PDF or Word source avoids this scan-only path. See `docs/Scanned_PDF_Number_Verification.md` for diagnostic details and supported optional settings.

## Deployment acceptance still required

After the two blockers are resolved, verify configured cloud and on-premise endpoints, a confidential scanned upload using the approved on-premise vision model, corporate LDAP sign-in, backups/restores, deployed proxy upload timeouts, request limits and representative multi-user load. Use fictional or explicitly approved test documents. No live service credentials or private source text belong in this report.
