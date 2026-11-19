# Regulatory Compliance — User Guide and Administrator Maintenance Guide

Access update — 15 October 2026: approval reviewers cannot open the AI instruction library or other users' activity. Their review area retains the submitted source, generated copy, user-provided brief and approval notes; private template-rule text is excluded from reviewer responses. Ordinary users retain the permitted user-help access described below. Channel/super admins maintain the instructions.

Document ID: REGULATORY-COMPLIANCE-GUIDE | Version: 1.0 | Updated: 13 October 2026
Status: active reference guide; excluded from generation prompts.

## Part A — User guide

Audience: Regulatory Compliance users and approval reviewers.

### What this workspace does

The Regulatory Compliance workspace converts a detailed uploaded regulatory document into a concise, evidence-based internal memo. It summarises the important obligations, supported changes, consequences and decisions without reproducing the whole policy. Currently the approved output is **Template 1 — Compliance Memo**.

The policy is input; the completed memo is output. The configured QoS files show the relationship between a detailed policy, a selective executive memo and a memo layout with six sections and a recommendation table. They are examples, not default facts for your next document.

### Prepare the source

Use the authoritative policy or regulatory instrument. Add supporting correspondence if receipt dates, internal owners or deadlines matter. Provide only metadata you know: Ref, Date, From, To, CC, intended memo title and any confirmed action assignments. If these are unknown, leave them unknown. Do not borrow names, signatures or dates from a sample memo.

For a single brief the interface accepts PDF, Word (.docx) and text (.txt). Regulatory Compliance uploads allow up to 50 MB and 2,000,000 extracted characters; larger documents must be split. Large extracted documents are reviewed in segments. A scan without readable text may require OCR or a better source; inspect the extracted text before generating and do not assume every table was read correctly. Keep source documents within your organisation's authorised data-handling rules.

### Generate Template 1

1. Sign in with your Regulatory Compliance account and open Harf.
2. In **What would you like to generate?**, enter “Template 1 — Compliance Memo”, or select Template 1 in **Components and templates**.
3. Upload the source under **Upload a brief**, or paste readable source text in the text box. Inspect the extracted content.
4. Add relevant metadata, supporting facts and specific requirements in the extra-instructions field. Distinguish a regulatory deadline from a proposed internal action date.
5. Choose English, Arabic or both and generate.
6. Check the source-specific title, header metadata and the six sections: Regulatory Instrument Details; Background; Executive Summary of the Regulatory Requirements; Cost of Non-Compliance; Recommendation; Attachments.
7. Confirm that ordinary narrative uses paragraphs/bullets and section 5 contains the action table. The entire memo must not be wrapped in one table.
8. Verify the dates, principal obligations, exceptions, consequences and short source section references against your uploaded document.

The executive summary is intentionally concise. Recommendation is limited to a few priority actions and 120 words for the whole section. Missing owners/deadlines are marked for confirmation; unsupported metadata is marked as not provided. CTIO and its expanded or translated equivalent are excluded; a replacement owner is never guessed.

### Edit, regenerate and export

Review the editable output and save changes where offered. Use **Not quite right? Tell us what to change** for a precise revision, for example: “Shorten section 3, retain the source-backed reporting deadline, and keep the recommendation table unchanged.” Check the revised draft against the source again.

Use Archive to reopen a saved result. PDF and Word exports should preserve paragraphs and genuine tables; inspect the exported file before sharing. Text exports represent tables in plain text rather than Word-style formatting. Excel is available where offered for saved/bulk results, with copy text and metadata in separate cells. Confirm the version and approval state on every export; an edited download is not automatically an approved version.

For bulk requests, upload up to 20 files and review each generated memo independently. The combination of files and selected formats must fit the app's 20-item limit. A partial failure must not be mistaken for a complete batch.

### Approval and notifications

Choose **MOVE TO APPROVAL** when the draft is ready. Reviewers need the input, output, request, extra instructions and relevant supporting details to understand the context. Review follows the configured approval layers and language access; read notes and respond to returns before resubmitting. Use the notification bell, Archive and batch history to track progress.

The Activity tracker shows activity and final approval state; approval actions belong in the approval area. An authorised channel admin can override with a recorded reason. Generated or exported copy alone is not approved. Human review must verify regulatory accuracy and both languages before release.

### Final checklist

- Distinguish issue, receipt, communication and effective dates.
- Verify mandatory versus monitoring obligations and any supported changes.
- Keep essential exceptions and source references.
- Confirm that penalties, deadlines, owners and attachments are actually supported.
- Check concise executive-level coverage and the section 5 table/budget.
- Remove the excluded role and any guessed historical metadata.
- Read the Arabic independently for correct meaning, spelling, grammar and fully translated labels.
- Review export layout, version and approval status before sharing.

If a file cannot be read or generation fails, keep the source and error reference, inspect which items completed, and contact your administrator. Do not invent missing facts to bypass an extraction problem.

---

### Leave feedback on an output

Use the thumbs-up or thumbs-down icons below a completed output. A thumbs-up is saved immediately. For a thumbs-down, explain what needs improving and choose **Send feedback**; a blank reason cannot be submitted. Each language and selected component/template can receive its own feedback. Feedback captures the version being rated, its source brief, generated copy and generation context; a later edit does not change that snapshot.

Feedback is visible to the assigned channel administrator only. It is separate from approval: a rating does not approve, reject or change the copy's approval status.

---

## Confidential documents

Select **Confidential document** before uploading or entering sensitive material. This applies to single and bulk copy, revisions, translation, instruction enhancement and guideline checks. Protected content uses on-premise AI only; cloud fallback and external Docling extraction are blocked. Native documents can be read locally; scanned files require approved on-premise image reading. If the internal gateway is not configured, AI processing is blocked.

The current brief keeps its protection while it contains content. **New brief** asks before clearing the workspace. Saved copies and identical re-uploaded protected files retain their classification. Do not remove the flag to work around an unavailable model.

<a id="regulatory-compliance-admin-only"></a>
<!-- AUDIENCE_BOUNDARY: REGULATORY-COMPLIANCE-ADMIN-ONLY -->
## Part B — Administrator-only maintenance guide

Audience: authorised Regulatory Compliance channel administrators and super administrators.

The server returns only Part A to ordinary users and approval reviewers. Full Markdown downloads contain both parts; distribute a Part-A-only copy to ordinary users outside the app. Keep the `regulatory-compliance-admin-only` boundary intact when editing. Visibility must be protected by the API, not merely hidden in the browser.

### File ownership

| File | Owns | Generation use |
|---|---|---|
| 01_REGULATORY_COMPLIANCE_SYSTEM_INSTRUCTIONS.md | Shared evidence hierarchy, factual accuracy, source treatment, summarisation, exclusions and language safeguards | Every Regulatory Compliance request |
| 02_REGULATORY_COMPLIANCE_CHANNEL_TEMPLATE_INSTRUCTIONS.md | Permanent template index, aliases, fields, six-section memo specification, budgets, rendering and source examples | Current configured template |
| 03_REGULATORY_COMPLIANCE_USER_AND_ADMIN_GUIDE.md | Operating help, administration, safe maintenance and future extension procedure | Reference only; never sent to AI |

The three former Regulatory Compliance files are preserved in a separate backup. This restructure keeps their substantive requirements, including the detailed QoS calibration example. B2B/B2C instruction modules are not loaded into Regulatory Compliance.

### Edit existing instructions

1. Sign in as a Regulatory Compliance channel admin and select the Regulatory Compliance workspace.
2. Open the top-right instructions icon in Harf, or the administration instruction library.
3. Choose the correct file and inspect its scope, filename and word/character details.
4. Back up the current content and record the source, reason and intended effect of the revision.
5. Use **Edit file** or the administration editor. Put a shared rule in the system file, an output requirement in the template file, and interface guidance in this guide.
6. Preserve source qualifications, exclusions and missing-information behaviour. Keep the admin boundary in this file.
7. Select **Save changes**, confirm success, and reopen the file to verify it. Updated generation instructions apply to future requests, not to already saved copies.
8. Test representative source documents in English and Arabic and obtain appropriate content-owner review before publishing the revised output. Restore the backed-up text if necessary.

### Add a future template to the index

1. Obtain an approved purpose, source relationship and complete output specification. Do not infer requirements merely from an attractive sample.
2. Choose the next unused ID, for example `REGULATORY-COMPLIANCE-TEMPLATE-002`. Keep Template 1's ID unchanged.
3. Add an explicit `<a id="regulatory-compliance-template-002"></a>` anchor, matching heading and index row to the template file.
4. Add metadata: template ID, display name, English/Arabic aliases, status, required/optional inputs, output format, languages, source references and `system_dependency: REGULATORY-COMPLIANCE-SYSTEM`.
5. Define the exact header, sections/fields, required versus optional content, length/character budgets, table rules and missing-information handling. Place all these details in the template file only.
6. Include a clearly labelled example and its source. Historical names, prices, owners, signatures or dates are never standing facts.
7. Confirm the index link works, the ID is unique, aliases are unambiguous and general rules have not been duplicated.
8. Record the revision and obtain owner approval. A future template remains draft until the app's supported template catalogue/routing is deliberately updated and tested. Adding text to the index does not automatically enable generation.

Use this documentation pattern, replacing placeholders with approved details:

```yaml
template_id: REGULATORY-COMPLIANCE-TEMPLATE-002
display_name: approved template name
aliases: [approved English alias, approved Arabic alias]
status: draft_pending_approval
system_dependency: REGULATORY-COMPLIANCE-SYSTEM
required_input: approved source requirement
optional_inputs: approved supporting context
output_format: approved structure
languages: [English, Arabic]
source_references: [source name and version]
```

Do not reuse an ID for a different purpose. For a replacement, allocate a new ID and record which old ID it replaces. Deprecate a retired template with a replacement reference in version history; do not silently break saved references. If a rule applies to every future template, move it to the system file rather than repeating it.

### Reviewer access and oversight

In **People and access**, choose the correct Regulatory Compliance user, enable **Give approval access**, set Layer 1, 2 or 3 and the reviewer language: English, Arabic or both. Save and verify the role. Reviewer access is distinct from channel-admin editing rights. Only super admins create/delete application channels.

Use the approval area to inspect full source/generation context and take permitted decisions. Preserve reasons, notes, language decisions and history. Use an override only with a recorded reason and appropriate administrator authority. The Activity tracker remains a record/status view.

### Regression checks after an instruction change

| Scenario | Required result |
|---|---|
| Policy with several dates | Issue, receipt, communication and effective dates remain distinct |
| Missing owner or deadline | Confirmation marker; no guessed executive, department or internal date |
| Excluded role in source | CTIO, expanded title and translated equivalent omitted from output |
| Unsupported penalties or older-version comparison | Uncertainty preserved; no invented fine, suspension or change claim |
| Annex definitions and exceptions | No automatic conversion of monitoring definitions into reporting duties |
| Large source | Every extracted segment reviewed; essential evidence retained |
| Template 1 | Six sections in order, narrative paragraphs and recommendation table |
| Brevity | Section budgets applied; recommendation no more than 120 words; accuracy takes priority over padding |
| Arabic/bilingual | Labels and markers translated; figures and legal meaning preserved; language reviewed |
| PDF/Word/text/Excel export | Appropriate formatting, full supported copy and correct metadata/status |
| Guide access | Users/reviewers receive Part A only; admins can maintain both parts |
| Unconfigured template name | Missing approved specification requested; no guessed template |

### Review user feedback

Open **Feedback** in the control centre. Filter by thumbs-up/down or review status, search submissions and select one to inspect its input, output, reason, task, instructions and related details. The input/output snapshot remains as submitted. Instruction versions shown here are captured when feedback is submitted, and are labelled accordingly; they are not claimed to be a historical generation-time record.

Add internal findings and select **Mark reviewed**, or save updated review notes. Use **Open AI instructions** to reach the channel's existing instruction editor. Feedback never automatically rewrites or publishes instructions. Only the matching channel admin can read or review the feedback; approval reviewers do not receive access.

### Revision record

Record version, date, author, reviewer, source, reason, affected IDs, checks, approval and rollback location. Keep long version histories outside active prompts.

| Version | Date | Change | Scope |
|---|---|---|---|
| 1.0 | 13 October 2026 | Three existing Regulatory Compliance files reorganised into shared rules, indexed Template 1 and a protected user/admin guide | Existing source requirements retained; no new regulatory facts or invented templates |

## Configure approval routing and shared reviewers

1. Open Administration > People & access > Approval settings.
2. Select layer 1, 2 or 3 as Final approval and choose Save approval routing. For a two-stage process, select layer 2.
3. Expand a layer in Approval settings, then choose Add reviewer or Edit to open the access form. Give each colleague approval access, assign the same layer to multiple people if needed, and select English, Arabic or both review languages.
4. Every eligible reviewer at the active layer receives the request. The first approval per required language is sufficient; all reviewers do not need to approve. Bilingual copies still require both language reviews.
5. The configured final layer completes approval and notifies the original author. A route is saved when the copy is submitted or resubmitted; requests already under review retain their existing route. Their timeline shows the required layers.


## AI model routing administration

Only the super admin can open **Administration > Models & routing**. Choose the application default, optional channel selections, and an enabled on-premise model for confidential documents. Expand channel selections to configure individual channels. Add or disable model rows, confirm exact deployment IDs, and approve image reading only for supported models. Save before using Test connection, which sends fictional input only. Configured does not mean connected.

Connections and credentials are environment-owned. This local setup retains the existing standard-generation connection; IT will supply real gateway URLs/keys and activate live routing later. Channel admins cannot change model routing, and no administrator can select a cloud confidential model through this API. Confidential processing remains blocked until an approved on-premise gateway is available.


## Remove a channel member

1. Open **Administration > People & access** and choose **Remove** beside a user or reviewer.
2. Review the centered confirmation, then choose **Remove access** or Cancel.
3. Channel admins may remove only their own channel users and reviewers. Only the super admin may remove channel admins. Self-removal and super-admin removal are blocked.
4. Access and sign-in are disabled, and the request allocation is released. Saved copies, feedback, activity, usage and approval history remain. The company directory account is not deleted.
5. If a reviewer was removed, assign another reviewer or check the layer's language coverage. Use **Assign access** with the same email to restore application access later, and allocate requests as needed.

## Platform privacy boundary — 30 October 2026

In administration, super admins manage channels, people, request budgets and models without access to other users’ content, feedback, activity or approval requests. They retain the main writing workspace: welcome page, channel switching, single and bulk generation, uploads, editing and exports. Their archive, personal activity and author notifications show their own work only. They can read, edit and restore instruction files and their history across channels. They cannot approve, reject or override review decisions. Channel admins retain those controls for their own channel. Reviewer assignment is account management and does not grant the super admin content access.

The super-admin overview contains aggregate active accounts, recent account additions, monthly request usage/limits and provider-reported token counts. Historical tokens that were not measured are shown as Not recorded. Account addition counts use stored creation dates. This boundary applies to the interface and direct API requests.

### Super-admin instruction access

Super admins can select any channel in **Administration → AI instructions**, read the formatted files, edit Markdown, save confirmed revisions, compare version history and restore older versions. The optional AI instruction helper remains available. Administrative content views, other users’ activity and feedback, approval queues and reviewer notifications remain unavailable to the super-admin role. This restriction does not remove the main writing workspace or the super admin’s own saved work and author notifications.

### Per-model token limits and operational log retention

Only the super admin manages model settings. Open **Models & routing → Token limits** to set different maximum input and output tokens for each model, then **Save model settings**. The Models, Token limits, Routing and Connections tabs keep these tasks separate and retain drafts while switching. Input includes retrieved guidelines, the brief, extra instructions and revision context. Each call uses its selected model’s input limit; oversized input stops before sending and is never silently truncated. Saved input overrides update `LLM_MODEL_INPUT_TOKEN_LIMITS` in `platform-policy.local.env` and apply immediately to new calls. `DEFAULT_MAX_INPUT_TOKENS` is only a seed for unconfigured models. Output limits remain separate. Local tokenizers count supported text models; unknown tokenizers and images use conservative estimates. Model-native combined context limits still apply. Request control contains monthly requests, user allocations, bulk limits, AI traffic and log retention only. Actual usage reporting remains; there is no monthly token budget.

Operational log retention defaults to **180 days**. The super admin can change the period (31–3650 days) or run cleanup after confirmation. Automatic cleanup runs at backend startup and hourly. Expired activity logs, notifications, past-month request records and usage metrics expire. Saved copies, source files, approval evidence, feedback, instruction files and all instruction versions remain. Undated records and current quotas are protected. External backups and infrastructure logs require separate policies. Admin saves update `platform-policy.local.env`; no database schema migration is required.
