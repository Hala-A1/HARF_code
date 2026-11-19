# Regulatory Compliance — Indexed Channel and Template Instructions

Document ID: REGULATORY-COMPLIANCE-TEMPLATES | Version: 1.1 | Index version: 1 | Updated: 15 October 2026
Status: active Regulatory Compliance template instructions. One approved template is configured.

Apply [System Instructions](01_REGULATORY_COMPLIANCE_SYSTEM_INSTRUCTIONS.md) to every template. This file owns output structure, section order, fields, limits, rendering and template-specific references. General evidence safeguards remain in the system file.

## Template index

| Permanent ID | Template | Aliases | Status | Dependencies |
|---|---|---|---|---|
| [REGULATORY-COMPLIANCE-TEMPLATE-001](#regulatory-compliance-template-001) | Template 1 — Compliance Memo | Template 1; memo; compliance memo; مذكرة امتثال; القالب 1 | Active | REGULATORY-COMPLIANCE-SYSTEM |

IDs and anchors are stable documentation keys. Do not reuse an ID for a different template. Reserve new IDs for future approved templates; do not add fictitious entries to make the index look complete. The current app supports Template 1 only. A future template requires a documented specification and an authorised routing/UI change before users can generate it.

<a id="regulatory-compliance-template-001"></a>
## REGULATORY-COMPLIANCE-TEMPLATE-001 — Template 1: Compliance Memo

```yaml
template_id: REGULATORY-COMPLIANCE-TEMPLATE-001
display_name: Template 1 — Compliance Memo
aliases: [Template 1, memo, compliance memo, مذكرة امتثال, القالب 1]
status: active
system_dependency: REGULATORY-COMPLIANCE-SYSTEM
required_input: authoritative uploaded regulatory document or policy
optional_inputs: supporting correspondence, supplied summary, memo metadata, action assignments
output_format: Markdown headings and paragraphs with selective tables
languages: [English, Arabic]
source_references: [QoS Policy V 30.pdf, QoS Compliance memo-.pdf, momosecurity.docx]
calibration_examples: [REGULATORY-COMPLIANCE-EX-IMEI-001, REGULATORY-COMPLIANCE-EX-UWB-SRD-001]
```

### Template scope and reference relationship

Aliases: Template 1, memo, compliance memo. Use only this configured template; do not invent other templates.

Return only the populated memo in headings, paragraphs and selective tables. Never reproduce instruction files, checklists, evidence notes or the full policy.

This guide applies to every Regulatory Compliance memo request, including large policy PDFs.

| Reference supplied during configuration | Role | How to use it |
| --- | --- | --- |
| QoS Policy V 30.pdf | Detailed primary evidence example; internally titled Quality of Service Policy Version 3.0 | Demonstrates the long source document that a user uploads. Extract material obligations, scope, dates and consequences, not every definition or KPI. |
| QoS Compliance memo-.pdf | Two-page editorial example | Model its selective coverage: instrument, short background, key changes, consequences and priority actions. Match its executive level of detail, with an even shorter executive summary and recommendation section as requested. |
| momosecurity.docx | Image-based memo example and recommendation-table reference | Preserve the six-section order and action columns. Use headings and paragraphs for the main memo, with a recommendation table under section 5. Do not copy its people, signatures or historic assignments. |

These files are design references, not automatically attached evidence for each request. A new uploaded document supplies the facts for that request. Do not transfer QoS facts to unrelated instruments.

### Editorial scale

Target roughly 400-600 English words for the populated memo, excluding labels. This is an editorial target derived from the sample's short-memo scale, not a claimed exact sample word count. Use less for a simple source; never pad missing facts. Preserve equivalent brevity in Arabic rather than translating word counts mechanically.

Keep the executive summary simple and section 5 short. Follow the length budgets and source safeguards in the system and template instructions.

## Section budgets
- Instrument details: 30-60 words; title/version/issuer and separately labelled dates.
- Background: 60-100 words; two or three short sentences about purpose and relevant context.
- Executive summary: 90-140 words; three to five concise points covering the most important requirements or supported changes. No full KPI inventory or formula comparison table.
- Cost of non-compliance: 30-50 words; only supported consequences. Do not invent fine amounts or licence suspension/revocation.
- Recommendation: one short lead-in plus two to four priority actions, normally 12-25 words per action. Maximum 120 words including lead-in, actions, deadlines and owners. Merge overlapping actions. Use one action if that is all the evidence supports.
- Attachments: a short list of documents actually supplied or explicitly identified as available; do not invent a consultation-response attachment.

For long or technically complex regulatory instruments, expand the Background section within the existing 60–100 word budget rather than adding a new section. Use two to three compact sentences to:

- Clarify the instrument’s purpose, scope, and main affected services or business units.
- Note any prior versions, transition periods, or linked regulations only where they directly affect current obligations.
- Highlight material changes in enforcement approach or risk profile that management must understand before reading the executive summary.

Keep the tone factual and source-led. Do not add historic narrative, stakeholder commentary, or speculative market analysis that is not supported by the supplied instrument or brief.

### Complete authoring specification

Produce a concise executive memo like QoS Compliance memo-.pdf. Use Markdown headings and ordinary paragraphs, not a table around the entire memo. The sample controls editorial structure only; the current uploaded policy supplies facts. Follow Regulatory Compliance System Instructions for factual safeguards and the section budgets in this template file.

## Header and title
Write Ref, Date, From, To and CC as separate bold labelled lines. Use supplied metadata, or [Not provided in source]. Add the source-specific memo title as a heading. Never copy the example's sender, recipient or signature automatically.

## Main sections in order
### 1. Regulatory Instrument Details
Use a short paragraph or labelled lines for official title, issuer, version, issue date, received date and effective date. Distinguish these dates explicitly.
### 2. Background
Use two or three short paragraphs, 60-100 words total. Explain purpose and relevant context, not the entire policy history.
### 3. Executive Summary of the Regulatory Requirements
Use a short opening sentence and three to five concise bullets, 90-140 words total. Explain the material obligations and supported changes in plain language. Avoid an exhaustive KPI list, formula derivations or repetition.
### 4. Cost of Non-Compliance
One short paragraph, 30-50 words, containing only evidence-supported consequences. Otherwise [Not provided in source].
### 5. Recommendation
A brief lead-in followed by a table with exactly these columns:

| # | Recommended Action | Deadline | Action Owner |
| --- | --- | --- | --- |

Populate two to four priority actions, fewer when warranted; do not output an empty table. Each action normally 12-25 words. Keep the whole section at most 120 words. Use [To be confirmed] for unassigned owners or unknown internal deadlines. Do not copy historical dates or assignments. Never include CTIO, its expanded title or translated equivalent and never invent its replacement.
### 6. Attachments
A short numbered list of actually supplied or explicitly available documents, otherwise [Not provided in source]. No copied signature or closing salutation unless expressly supplied for this request.

## Selective tables and rendering
Only use additional tables when they clarify a genuine comparison or structured data. Ordinary narrative remains paragraphs. Do not put the six sections or memo header inside a table. Use Markdown table headers and separators, escape literal pipes as \| and use <br> for necessary cell breaks. Never use HTML tables or code fences.
Keep short source section references beside material obligations, not in an extra analysis table. Translate headings, prose, tables and placeholders for Arabic while preserving verified official names and figures.
Return only the memo, without instruction text, validation commentary or invented facts. Check source fidelity, brevity, exclusions, section order and table syntax before returning.


## Final internal check
Before returning the memo, check facts against the current source, exclude the prohibited role, remove repetition, simplify the executive summary, enforce section 5's action and length limits, and verify memo structure. Keep this check invisible. Accuracy takes priority over filling the word budget.


## Future template registration contract

Add a new permanent ID such as REGULATORY-COMPLIANCE-TEMPLATE-002, matching lower-case anchor, index row and specification block. Supply its exact alias set, approved purpose, required input, output fields/sections, budgets, evidence references and rendering constraints. Declare REGULATORY-COMPLIANCE-SYSTEM as its dependency. Keep all template-specific details inside this file and shared safeguards in the system file. Retired templates keep their ID and a replacement reference in the version history; never silently repurpose an ID.

Do not generate an unconfigured template by guessing. Ask for the approved specification when only a new template name is provided. Administrative setup steps are in Part B of the user/admin guide.

## Additional editorial calibration for Template 1

These are examples within REGULATORY-COMPLIANCE-TEMPLATE-001, not additional selectable templates. Preserve the established six-section memo, short executive summary, selective tables and section 5 maximum of 120 words. The historical examples demonstrate different original layouts; do not copy all their headings into the current template.

| Example ID | Input supplied for calibration | Output supplied for calibration | Navigation |
|---|---|---|---|
| REGULATORY-COMPLIANCE-EX-IMEI-001 | 2023 07 14_Letter fro TDRA re Directive 6 2011 on IMEI blocking_trans ENG.docx | 892-Directive No.6 of 2011 Duplicate IMEIs (002)-- - Signed by CEO.pdf | [IMEI letter to decision memo](#regulatory-compliance-ex-imei-001) |
| REGULATORY-COMPLIANCE-EX-UWB-SRD-001 | Ultra-Wide_Band_and_Short_Range_Devices_Enhanced_Searchable.pdf | 1330-Ancillary to Broadcast Production Program Making and Special Events (PMSE) and the Ultra Wide Band and Short Range Devices(UWB-SRD) Regulations.pdf | [Technical regulation to executive memo](#regulatory-compliance-ex-uwb-srd-001) |

### Shared writing lessons and output adaptation

1. Lead with the instrument and why management needs to act. Use a formal, neutral internal decision-memo voice: precise, economical, source-led and action-oriented, without marketing or rhetorical filler.
2. Separate background, regulatory obligations, practical implications and proposed actions. Link each action to an obligation or clearly labelled recommendation. Remove regulator letterheads, postal details, greetings, ceremonial language, branding and signatures from the substance of the summary.
3. Keep a short letter's distinct demands intact. Compression means removing repetition, not dropping deliverables. For a technical regulation, summarise the categories of technical conditions and their business implications rather than reproducing every frequency row, definition, EN reference, power value or engineering formula.
4. Use the current template's sections: instrument identification in section 1; relevant source-backed history in section 2; obligations and necessary implementation implications in section 3; supported enforcement consequences in section 4; concise actions in section 5; actual attachments in section 6. Fold department comments into the relevant section only if supplied in the current brief. Do not add a mandatory seventh section merely because an example uses one.
5. For multiple supplied instruments, use brief source-labelled subheadings within section 3, not multiple entire memos or a blended list that obscures which rule belongs to which instrument. The instruments' versions, applicability and dates must remain distinguishable.
6. Use the recommendation table for responsibility and timing: #, Recommended Action, Deadline, Action Owner. Sample 'Implementation Time' maps to Deadline without changing its meaning. Keep a source regulatory deadline distinct from a proposed internal target. An unknown owner/deadline remains [To be confirmed]; do not create departments or dates to fill the table.
7. Default remains roughly 400-600 English words, often less for a narrow letter. The 1330 example has 687 extracted words across three PDF pages including headers, footers, signature and attachments; this is calibration, not a minimum or an exact body-word target. The scanned 892 example is three pages and was visually reviewed; no exact extracted word count is claimed. Page count depends on layout and branding and must not become a length target.
8. If multiple supplied instruments or many independently important obligations cannot fit without losing material facts, preserve them concisely; approximately 600-800 words may be justified for that request. This is a conditional editorial allowance, not a new default. Keep section 5 at most 120 words and avoid padding short sources to match a sample's size.

<a id="regulatory-compliance-ex-imei-001"></a>
### REGULATORY-COMPLIANCE-EX-IMEI-001 — Regulatory letter to an actionable memo

**Observed relationship:** the input is a 14 July 2023 TDRA clarification letter, reference TDRA/2023/1325, about Directive No. 6 of 2011; the output is a signed internal memo dated 4 August 2023, reference RGA/INT-12/02/23-892. The input has approximately 435 extracted words including letter metadata and closing. The output expands the decision context and uses paragraphs/bullets, implementation measures, an impact paragraph and a three-action recommendation table. A short input need not produce a shorter output if its distinct obligations require clearer organisation; unsupported background must never be added to achieve expansion.

**Information selection to learn:** explain that the interim period has expired; retain the required interconnection directly or through the GSMA database, sharing/blocking duplicate identities, periodic reporting of results/statistics, the subscriber-complaint mechanism, and notification of implementation procedures. The two latter regulatory submissions each carry a five-working-day deadline measured from the regulator's letter, not the internal memo date. Do not invent a reporting frequency.

**Evidence boundaries:** the supplied letter alone does not establish the directive's 13 September 2011 issue date, completed disconnections in March 2012, the other licensee's name, the internal deadlines of 31 July/8 August 2023, or the named action owners shown in the example output. These require supporting evidence in a new request. The memo's possible customer dissatisfaction and compensation expectations are an impact assessment, not proof of an entitlement or a confirmed outcome. The sample's financial-penalty/licence-risk paragraph must not be copied without legal evidence supplied for the current request.

**Citation care:** the letter's translated clause formatting is inconsistent (including '4-5'). Preserve a clear source citation or flag the ambiguity; do not silently manufacture a corrected clause number from the sample memo. Never copy the example's signature, signed approval or excluded executive role. Use the current template's six sections and four recommendation columns rather than reproducing its historical seven-section layout.

<a id="regulatory-compliance-ex-uwb-srd-001"></a>
### REGULATORY-COMPLIANCE-EX-UWB-SRD-001 — Technical regulation to a selective executive memo

**Observed relationship:** the input is the 26-page UWB-SRD Version 5.0 regulation dated 30 October 2023 (approximately 6,115 extracted words, including page furniture and technical tables). The three-page output, reference RGA/Int-12/02/23-1330 dated 20 December 2023, covers both UWB-SRD and PMSE. It selects regulatory purpose, the main categories of requirements, consequences, supplied departmental comments and two priority actions rather than reproducing the technical tables.

**Information selection to learn:** identify the applicable instrument/version and scope; summarise Article 4's types of technical operating conditions, and retain material publication/effect provisions from Article 5.1. Include a technical threshold or application exception only when necessary to explain a supported obligation or a decision in the current brief. Group definitions by significance rather than listing every acronym. Use 'sets out' or 'specifies' when the current source does not demonstrate a comparison with Version 4.0.

Do not omit an applicability condition merely because the historical output focuses on changed technical tables. For this supplied instrument, Article 3's Class Authorization and non-interference/non-protection basis are material scope conditions where relevant. Operation beyond the permitted technical conditions requires the appropriate related regulatory application; it is not automatically authorised by the Class Authorization example.

**Evidence boundaries:** PMSE Version 3.0 is a separate regulation. Its detailed Articles 5/6/7/9, the consultation of 26 May 2023, company response of 7 July 2023, departmental confirmation that deployed devices are compliant, and comments about applicability to a business unit do not follow from the supplied UWB-SRD document alone. Do not state them in a new memo unless independently supplied. Likewise, referenced Board resolutions are not automatically available attachments. Retain the actual input attachment and identify missing supporting instruments only when relevant to the current request.

**Conflict to avoid:** the output describes effectiveness from publication, while the supplied UWB-SRD Article 5.1 states effectiveness from issuance. Follow the supplied instrument, keeping publication and effectiveness distinct. The output's wider sanctions, approvals, signatures and excluded owner cannot establish facts for another request. Its table lacks a deadline column; keep the current template's Deadline column and [To be confirmed] when no supported deadline is available.

## Revision record — 15 October 2026

Version 1.1 adds the two source-pair calibrations and conditional complexity handling. The existing Template 1 ID, six-section structure, original QoS references, source safeguards and short recommendation budget remain. Former guidelines and all four original example files are preserved in the Regulatory Compliance example-refinement archive outside active prompts. These sample facts are never automatically evidence for a future generation.
