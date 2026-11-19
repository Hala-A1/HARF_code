# B2B — User Guide and Administrator Maintenance Guide

Pack ID: B2B-CX | Document ID: B2B-GUIDE | Version: 1.0 | Prepared: 14 October 2026

Status: active B2B reference guide. Shared system rules and template instructions are connected to generation; this guide is excluded from AI prompts. The server serves Part A only to ordinary users and approval reviewers, and both parts to authorised channel administrators and super administrators.

## Part A — User guide

Audience: B2B users and reviewers.

### 1. What B2B means here

B2B means business-to-business: communications for individual customers, such as a welcome, service update, offer, bill reminder or support message. B2B is your application workspace. SMS, email, website, app and push notification are delivery channels within that workspace.

The Harf workspace can draft, improve, review and translate copy, using the instructions currently configured for B2B. It can work from pasted text or a brief, produce separate selected outputs, and help revise a draft. It cannot verify an offer just because it appears in an old example, approve its own copy or guarantee that a translation is ready to publish.

This new documentation pack separates shared rules, delivery formats and operating guidance. The system and template files now govern B2B generation. The original guidelines have been replaced for B2B.

### 2. Prepare a useful brief

Provide the objective, intended reader, desired format, product/service, verified facts, relevant dates/prices/conditions, next action and language. Include approved mandatory wording and links. Say what happened before this message and what should happen after it. If a fact is unknown, say so.

Example brief to adapt with real approved facts:

> Improve an SMS for existing B2B customers. Their add-on renews on [verified date] for [verified amount and currency] per [billing period]. Explain that renewal is automatic and tell them where to manage it using [approved link]. Keep the material conditions. Generate English and Arabic. Do not invent benefits or discounts.

The square brackets deliberately identify missing facts. Replace them before expecting a final customer-ready message.

### 3. Generate a single copy

1. Sign in with your own account and open Harf. Your assigned workspace/access controls what you can use.
2. Choose Single copy. In **What would you like to generate?**, describe the task and format, for example “Improve an SMS” or “Review this email”. If omitted, the current interface defaults the task to Improve.
3. Optionally use **Upload a brief** to add a .docx, .txt or .pdf, or paste content in the text box. Inspect the extracted text; a scanned or poorly extracted file may omit important facts. Check that uploading has not replaced text you intended to keep.
4. Expand **Components and templates** if you want one or more available output formats. Select only relevant B2B options. The available B2B choices come from the active template file: website Components 1–17; Google Paid Search can also be requested by name in the task title. SMS, email, app and push guidance applies to those requested delivery formats.
5. Add special requirements in the extra-instructions field. Use it for specific facts, audience, tone refinement or constraints, not to override mandatory rules.
6. Select English, Arabic or both. If using an optional character limit, choose a sensible one; template limits and mandatory disclosures still need checking.
7. Generate, then review every result. Multiple selected formats are shown separately for review. Check that each requested format and language is present.
8. Read the character counts and check actual customer-facing field lengths. The whole-output count is not a substitute for each app title/CTA limit. Real placeholder values may change the count.

There is no need to look for an “AI-detected context” panel or manual context-tag section; those are not part of this workflow. Put relevant corrections in the brief or extra instructions.

### 4. Edit and regenerate

Use the output editor to correct text or adjust formatting, then save the edit where offered. Tables can be edited, but check them after pasting and exporting. Formatting supported by the editor/exporter may differ from the external source.

Use **Not quite right? Tell us what to change** next to Regenerate for a precise instruction, such as “Shorten the first sentence and keep the price, renewal date and final CTA unchanged.” Review the regenerated result rather than assuming only the intended words changed. For batch regeneration, check each item: a failed request may leave some items updated and others unchanged.

Draft, returned and rejected copies can be edited according to ownership/access. In-review or approved records may be locked. Use the normal return/revision process rather than treating an exported edit as an approved version. Go back to writing to refine the source; use Archive to reopen the saved batch/result when available.

### 5. Work with multiple files

1. Choose Bulk files and upload up to 20 source files using the accepted types shown in that interface.
2. Review every file name and extracted source before generation.
3. Choose outputs carefully: the app limits the combination of files and selected formats to 20 generated items. For example, five files with two selected formats create ten items.
4. Generate and inspect each file's result and each selected language. Do not assume one successful item proves the entire batch is complete.
5. Edit or regenerate as needed, then use the batch download or approval controls.

### 6. Save, export and request approval

Use **Archive** beside the source/upload controls to find saved copies and batches. Download formats include PDF, Word (.docx), text (.txt) and Excel (.xlsx) where offered by the result controls. Review the exported file before use. PDF/Word can preserve formatted content; plain text cannot provide Word-style rich tables. Excel places generated text and metadata in separate columns; very long text is subject to Excel's per-cell length limit and the exporter's validation.

Check exported version, status, product, sequence, score, creator and reviewer metadata when available. Unknown metadata should not be interpreted as verified approval. A score is a writing assessment, not a legal or publishing clearance.

When ready, choose **MOVE TO APPROVAL**. The saved copy enters the configured review process. Reviewers work at their assigned layer and language; required language decisions must be completed before the normal process advances. Reviewers can provide notes and decisions according to their access. A return means the copy needs attention, not final approval. The final approved state is the publishing signal within this process; still follow the organisation's release rules.

Watch the notification bell and the saved batch's history/status. A channel administrator may use an authorised override with a recorded reason. Such an override should be visible in the audit history; never assume an ordinary reviewer has that permission. The Activity tracker is a record/status view, not the place to perform approvals; use the approval area.

### 7. Final human check

- Match every amount, date, condition, product name and link to the approved source.
- Check the message suits the reader, journey step and requested format.
- Verify field limits after dynamic values are substituted.
- Read Arabic independently for natural language, spelling, grammar and complete localisation.
- Check required disclosures and privacy, and obtain the appropriate review.
- Inspect the exported file, version and final status before sharing.

If generation fails, keep the source and requested changes, inspect which items completed, and retry only the needed items. Report the displayed reference code to an administrator. Do not repeatedly submit many duplicates or treat partial output as a complete approved batch.

---

### Leave feedback on an output

Use the thumbs-up or thumbs-down icons below a completed output. A thumbs-up is saved immediately. For a thumbs-down, explain what needs improving and choose **Send feedback**; a blank reason cannot be submitted. Each language and selected component/template can receive its own feedback. Feedback captures the version being rated, its source brief, generated copy and generation context; a later edit does not change that snapshot.

Feedback is visible to the assigned channel administrator only. It is separate from approval: a rating does not approve, reject or change the copy's approval status.

---

## Confidential documents

Select **Confidential document** before uploading or entering sensitive material. This applies to single and bulk copy, revisions, translation, instruction enhancement and guideline checks. Protected content uses on-premise AI only; cloud fallback and external Docling extraction are blocked. Native documents can be read locally; scanned files require approved on-premise image reading. If the internal gateway is not configured, AI processing is blocked.

The current brief keeps its protection while it contains content. **New brief** asks before clearing the workspace. Saved copies and identical re-uploaded protected files retain their classification. Do not remove the flag to work around an unavailable model.

<a id="b2b-admin-only"></a>
<!-- AUDIENCE_BOUNDARY: B2B-ADMIN-ONLY -->
## Part B — Administrator-only maintenance guide

Audience: authorised B2B channel administrators and super administrators.

**Access control:** the application API serves only Part A to ordinary users and approval reviewers. Part B is returned only to authorised B2B channel administrators and super administrators. Full downloaded Markdown files still contain both parts; distribute a Part-A-only copy outside the application when sharing with ordinary users.

### 1. Understand the three-file ownership model

| File | Put here | Do not put here |
|---|---|---|
| 01_B2B_SYSTEM_INSTRUCTIONS.md | Rules that apply across every B2B format; terminology; accuracy; Arabic quality; common style and validation | A specific SMS cap, email field list, push schema or a second copy of template examples |
| 02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md | Format index; channel-specific behaviour, fields, limits, variants, dependencies and examples | Repeated general voice/privacy/claim rules |
| 03_B2B_USER_AND_ADMIN_GUIDE.md | How to use the interface, maintain the pack, review changes and resolve gaps | New hidden generation rules or claims that an undocumented feature exists |

“System instructions” here means the shared writing document. It does not mean these files have been assigned an API system-message role. Likewise, an index is a list of stable identifiers and links, not a working search algorithm.

### 2. Edit an instruction already available in the current app

1. Sign in as an authorised B2B channel admin; verify that B2B is the selected workspace.
2. Open the top-right instructions icon in Harf, or the B2B administration instruction library. The dedicated guidelines page shows the relevant instruction files.
3. Select the intended active file. Read its description, scope, filename and file details before editing.
4. Save a versioned backup outside the live instruction text. Record the reason, source and intended impact of the change.
5. Edit the Markdown in the provided editor. Preserve required names, IDs and factual qualifications. A read-only file requires an authorised owner; changing your local view does not grant edit rights.
6. Select **Save changes**. Confirm success and reopen the file to verify the saved text.
7. Run representative new drafts in both languages and compare them with the previous approved behaviour. Saved instructions apply to future requests; they do not retroactively revise saved copies.
8. Record the review and approval of the instruction change. Restore the backed-up text if the change fails the checks.

These three files are now available in the B2B instruction library. Saving the system or template file applies its updated rules to future B2B requests. The guide is for reference and never sent to the AI. Older shared guidelines remain available to their other channels, but are no longer loaded for B2B.

### 3. Add or update a general rule

1. Identify the exact approved source, page/worksheet row, owner and effective date.
2. Decide whether the rule truly applies to every delivery channel. If not, place it in the relevant template entry.
3. Search for an existing rule with the same meaning. Update the canonical wording rather than appending a duplicate.
4. State the action and its scope clearly. Distinguish mandatory requirements, editorial targets and optional examples.
5. Resolve conflicts explicitly. Never “fix” an example by removing a legal qualification or silently changing a brand name.
6. Add the source reference and revision record, then review examples affected by the change.

Example: a new approved English/Arabic product spelling belongs in the system terminology table. A new push title cap belongs in the shared app/push schema or a documented push-specific override, not the general style paragraph.

### 4. Add a channel or template to the document index

1. Obtain an approved specification: purpose, supported fields, required inputs, limits, language behaviour and approved examples. Do not infer a schema from a visually attractive sample alone.
2. Reuse an existing parent if the new entry is only a journey variant. Otherwise create a new channel entry.
3. Assign the next unused permanent ID, such as `B2B-EMAIL-005`. Never reuse an old ID for a different meaning.
4. Add an explicit anchor matching the lower-case ID, then a heading and metadata block using the pattern below.
5. Add the entry to the index table with English/Arabic search aliases and its parent/dependencies.
6. Describe only its distinctive fields, behaviour and constraints. Link to shared rules and a parent instead of repeating them.
7. Add a source-backed example with a permanent example ID and provenance. Mark synthetic examples as synthetic, and use placeholders for unverified facts.
8. Check every anchor, ID, parent and limit; then record the revision and obtain content-owner review.

Documentation pattern — replace every placeholder before adoption:

```yaml
template_id: B2B-EMAIL-005
parent_id: B2B-EMAIL-001
aliases: [approved English alias, approved Arabic alias]
status: draft_pending_approval
source_refs: [source ID and page or worksheet row]
required_inputs: [facts this format needs]
fields: [only supported fields]
limits: approved limits or explicit not-specified status
```

Do not add guessed limits. Adding an index entry does not create a UI checkbox, enable retrieval, create an application workspace or grant user access. The current loader retains all template rules and dependencies and ranks optional examples. The format loader must retain the selected format and schema dependency, plus the shared system rules; dependencies must not be dropped to shorten the prompt.

### 5. Change or retire a template

For a wording update, retain its ID and increment the pack version. For a material change in purpose, allocate a new ID and record `replaces: [old ID]`. Mark the old entry deprecated with a replacement reference; do not silently break existing references. Remove obsolete examples from the active specification while retaining a versioned archive outside the runtime instructions. Do not accumulate all previous versions inside the active rule text.

If a shared field limit changes, review every dependent template. If an alias could match more than one format, distinguish it or require clarification; do not rely on an ambiguous word such as “message” to select a channel.

### 6. Maintain examples and Arabic terminology

Keep source row numbers, original before/after text and language context. Do not label a “Before” cell as approved copy. Corrected examples should be separately labelled editorial revisions; retain their original provenance. Check literal tokens against the sending system before renaming them.

Keep different meanings of a term separate. For example, active service and active account translations may differ. The glossary distinguishes a main **Plan** from an add-on **Pack**, and a support **Ticket** from a complaint. Do not translate brand names that the approved glossary explicitly keeps in English.

Have an Arabic reviewer check proposed changes for grammar and meaning. Do not retain a spelling error merely because it appears in a source note. Log corrections, and obtain owner approval for a terminology change that alters meaning. Historical offers should stay labelled examples, not become a live product catalogue.

### 7. Review access and approvals

Use **People and access** for a new or existing user. Select the correct channel and product access. For a reviewer, enable **Give approval access**, choose Layer 1, Layer 2 or Layer 3, and assign English, Arabic or both under **Reviewer language**. Save access and verify with a test account authorised for that role. Channel admins already have channel-level approval access; super admins manage broader channel access.

Reviewers should see the input, output, request and supporting context in the approval area before deciding. Keep normal layer/language review intact unless an authorised channel admin uses the explicit override with a required reason. Activity tracking should show submission and final outcome; do not use this guide to reintroduce approval controls into that page.

This guide contains no shared passwords, credentials or private account details. Only a super admin should create/delete application channels. Creating a delivery-format index entry is a separate documentation activity.

### 8. Acceptance checks before adopting a revision

| Check | Expected outcome |
|---|---|
| SMS and email with identical source facts | Each follows its own layout; no app field limits leak into email |
| App and push | Every included field meets its own limit in both languages |
| Missing price, expiry, eligibility or mandatory wording | A specific missing-input request; no invented commercial details |
| “Up to” discount or restricted benefit | Qualification retained in both languages |
| Dynamic tokens and links | Preserved exactly; counts explicitly provisional until substitution |
| Arabic labels and body | Fully localised except approved names/tokens; independent language review |
| Unknown audience | Inclusive plain language; no demographic assumptions |
| Crisis, suspension or complaint | Factual, empathetic and calm; no invented remedy or urgency |
| Multi-format request | Separate named outputs; no blended schema |
| Requested review | Findings and reasons rather than an unsolicited replacement |
| Document index | All links resolve; IDs unique; dependencies present; no duplicate general rules |
| Ordinary-user guide access | Only Part A is distributed; Part B requires actual access enforcement before app publication |

Use the acceptance checks above for new requests after every saved instruction change. Automated routing/access checks do not replace human review of AI-generated English and Arabic.

### Review user feedback

Open **Feedback** in the control centre. Filter by thumbs-up/down or review status, search submissions and select one to inspect its input, output, reason, task, instructions and related details. The input/output snapshot remains as submitted. Instruction versions shown here are captured when feedback is submitted, and are labelled accordingly; they are not claimed to be a historical generation-time record.

Add internal findings and select **Mark reviewed**, or save updated review notes. Use **Open AI instructions** to reach the channel's existing instruction editor. Feedback never automatically rewrites or publishes instructions. Only the matching channel admin can read or review the feedback; approval reviewers do not receive access.

### 9. Revision and rollout record

For each change record: version; date; author; reviewer; source; reason; affected rule/template IDs; checks performed; approval; rollout state; rollback location. Do not include credentials. Keep a compact current record here and detailed history in version control or an approved change log outside active prompts.

| Version | Date | Change | Rollout state |
|---|---|---|---|
| 1.0 | 14 October 2026 | Consolidated B2B shared rules, indexed templates, source examples and operating guide | Active B2B pack; brand/currency conflicts remain documented safeguards |

The pack is mapped only to B2B, superseded B2B guidelines are excluded, and Part B is protected by the application API. Resolve source conflicts explicitly with the content owner and verify representative English/Arabic drafts before publishing.


### B2B source preservation and format index maintenance

The three files retain every migrated source block and all original source text, examples, terms, limitations and repeated material. The source archive also retains original document binaries, component screenshots and document formatting. The preservation report lists source names, destination file, character count and SHA-256 checksums. Do not delete historical information merely to shorten these files.

1. Open the B2B Instructions page as the B2B channel administrator.
2. Edit **01_B2B_SYSTEM_INSTRUCTIONS.md** for rules that apply to every request: factual safeguards, brand terminology, language quality, voice principles and shared validation.
3. Edit **02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md** for format-specific guidance. Locate the stable index, then the matching anchor and section. Website rules belong under `<!-- B2B_SCOPE: website -->`; ads under `<!-- B2B_SCOPE: paid_search -->`; messaging formats under `<!-- B2B_SCOPE: messaging -->`. Shared template navigation uses `<!-- B2B_SCOPE: shared -->`.
4. To extend a component, retain its `B2B-COMPONENT-NNN` ID, anchor and `### Component N — Name` heading. Specify every required/optional field, exact maximum, visual requirement and validation. Component 8's name is unspecified in the source: do not invent a name. Existing component IDs cannot be reused for a different component.
5. To add a template, allocate a new stable ID, add an index row and unique anchor, state the matching format, system dependency, purpose, required/optional fields, output structure, limits, missing-input rules and labelled examples. A newly indexed section does not automatically create new application controls: request development support if the UI needs a new selectable option or format routing.
6. Keep website tone and paid-search tone separate. Website perspective forbids audience-facing you/your; paid search has its own promotional pair logic and 30/90 limits. Keep marketing examples as examples and never reuse their prices or discounts as facts.
7. Keep ordinary user help above `<a id="b2b-admin-only"></a>` in this guide and administrator instructions below it. This file never enters generation prompts. Never remove the access boundary.
8. Save and test a fresh fictional brief for every affected format and language. Check tone, mandatory details, each selected component, field counts, output readability and exports. Use the retrieval preview to verify exact file/section references. Existing outputs are not retroactively rewritten.
9. Preserve previous approved wording and the reason/date for changes in a labelled historical reference section. Consult feedback and approval notes before updating a rule. Review conflicts explicitly rather than silently deleting an instruction.

New channels use the same system/template/user-admin separation with neutral starter instructions. No new channel inherits B2B offers, terminology or templates.



## Preserved source — README.md

<!-- PRESERVED SOURCE: README.md -->

# Instruction Library — File Roles and Routing Guide

This folder converts the supplied etisalat source documents into modular Markdown instructions.

The modules in this folder supply B2B writing rules and the starter guides for new custom channels. B2C and Security use their own three-file packs under `../channels/`. Their generation rules and templates are isolated from B2B, and their administrator guide is excluded from generation prompts.

## Files
- `00_MASTER_INSTRUCTIONS.md` — orchestration, precedence, routing, factual safeguards, and validation.
- `01_BRAND_RULES.md` — standard brand naming, writing mechanics, CTA, UK English, currency, dates, punctuation, and formatting.
- `02_WEBSITE_CONTENT_INSTRUCTIONS.md` — website tone, perspective, structure, SEO/AEO/GEO, claim rules, inputs, output, and validation.
- `03_WEBSITE_COMPONENT_SCHEMA.md` — website component fields, mandatory/optional status, and character limits from the Updated Component Library.
- `04_GOOGLE_PAID_SEARCH_INSTRUCTIONS.md` — paid-search tone, pair logic, claims, hard limits, output format, and validation.
- `05_B2B_MESSAGING_EXAMPLES.md` — B2B before/after/Arabic examples and ready-to-send formatting patterns.

## Recommended loading
For website generation, load:
`Complete guide` + `01` + B2B messaging examples + `00` + `02` + `03`

For Google Paid Search, load:
`Complete guide` + `01` + B2B messaging examples + `00` + `04`

This avoids forcing website-specific component rules into ad generation while keeping shared brand rules consistent.




## Preserved source — README.md — original uploaded Markdown

<!-- PRESERVED SOURCE: README.md — original uploaded Markdown -->

# LLM Instruction Pack

This folder converts the supplied etisalat source documents into modular Markdown instructions.

## Files
- `00_MASTER_INSTRUCTIONS.md` — orchestration, precedence, routing, factual safeguards, and validation.
- `01_BRAND_TERMINOLOGY.md` — shared terminology, naming, commercial language, CTA, UK English, acronyms, and restricted terms.
- `02_WEBSITE_CONTENT_INSTRUCTIONS.md` — website tone, perspective, structure, SEO/AEO/GEO, claim rules, inputs, output, and validation.
- `03_WEBSITE_COMPONENT_SCHEMA.md` — website component fields, mandatory/optional status, and character limits from the Updated Component Library.
- `04_GOOGLE_PAID_SEARCH_INSTRUCTIONS.md` — paid-search tone, pair logic, claims, hard limits, output format, and validation.

## Recommended loading
For website generation, load:
`00` + `01` + `02` + `03`

For Google Paid Search, load:
`00` + `01` + `04`

This avoids forcing website-specific component rules into ad generation while keeping shared brand terminology consistent.

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
