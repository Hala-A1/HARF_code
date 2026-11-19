# Channel administrator guide

Last reviewed: 27 October 2026.

## Update instructions

1. Sign in using your channel administrator account.
2. Open Copywriter and select the guidelines icon at the top right, or open Administration → AI instructions.
3. Select the right file: **System** for rules shared by all outputs; **Templates** for indexed formats, components, fields, limits and examples; **Guide** for user help and administrator procedures. The Guide is reference material and is not sent to the AI for writing requests.
4. Files open as readable, formatted content in both views. Click **Edit file** to switch to Markdown. The User and Administrator Guide also has **Edit guide** above its content in Administration. **Cancel** in the guideline library, or **Cancel editing** in Administration, discards unsaved changes and returns to the formatted view.
5. Open **Version history** to review saved versions. The existing instructions are captured as the starting version automatically; a local backup is optional.
6. Update rules under the relevant headings. For a new writing requirement, state when it applies, required fields, output format, limits and an example. To remove a writing requirement, delete or replace the corresponding rule and any conflicting examples.
7. Keep factual safeguards and missing-information rules. Preserve stable template IDs, index links, component headings and field-limit syntax so routing can read them. Keep the Guide's existing admin-only boundary marker intact; it protects administrator procedures from regular users. You may edit the help on either side of that marker.
8. Click **Save changes**, add an optional change note, then choose **Confirm and save** in the centered confirmation. The edit creates a new saved version with your name and the save time. Your channel's copy is updated; other channels' files are unchanged. Future generation requests use the saved copy.
9. Return to Copywriter. Enter a request such as **Improve Component 4**, **Review this email**, or **Template 1 — Compliance Memo**, and generate using a small representative input.
10. Check the output against the edited rules in each affected format and language. Guideline checking is manual: click **Check this copy**, then inspect the scores, source references and findings. Also review facts, field limits and exports. Guide edits change the displayed help rather than the generated copy. If needed, open **Version history**, select an older version, read its saved content and choose **Restore this version**. Add a reason and confirm. Restoring creates a new version; the older versions remain available. Save any unsaved draft first if you want to keep it.

History starts with the current file when versioning first captures it; earlier edits are not reconstructed. Saving identical content creates no duplicate version. If another admin changes the file while you are editing, reload the latest version and reconcile your draft before saving. Channel admins can see only their own channel's history; super admins can read, edit and restore instruction files and history across channels. History persists across backend restarts.

## What editing Markdown can change

Markdown controls writing requirements, terminology, style, content structure and examples. It does not create application screens, upload formats, access roles or new software features. Changes to those capabilities require development. New template routing or new component numbers beyond the supported catalogue may also require development.

## Channel boundaries

Each channel's administrator can edit only their channel's active instructions. Approval reviewers cannot access the AI instruction library or version history. Shared starting files remain the defaults until a channel copy is saved. Regulatory Compliance uses its compliance policy and memo template; B2B and B2C use their respective active writing instructions.

## Assign English and Arabic reviewers

1. Open **Administration → People & access** and select **Edit** for a reviewer, or enter a new colleague's details.
2. Set **Access level** to **User with approval access** (or enable **Give approval access** for a new or existing user).
3. Choose their **Approval layer** (1, 2, or 3). Multiple reviewers can share a layer. All receive its requests, but the first approval per required language is enough.
4. Select **Reviewer language**: English, Arabic, or English and Arabic. Save access. The reviewer should sign out and sign in again to refresh their interface.
5. Assign coverage for every output language at every layer. Existing reviewers retain both languages until changed.
6. Open **Approval workflow** to inspect the original input, user instructions, task, audience, product and available format details for submitted copies. Expand the generated files to read the output. Approval decisions belong in this workflow; the activity tracker shows submission and final approval status only.
7. Approve the assigned language. A bilingual batch advances only when both languages are approved at that layer. Each language decision records the reviewer and time. Returning and resubmitting content starts fresh language approvals.

Channel admins retain their reason-required final approval override. Older saved copies show only the context recorded when they were created; missing historical details are labelled rather than reconstructed.

## Collapse the component catalogue

Click **Components and templates** to collapse or expand it. Selected components remain selected, and the heading shows the selection count. The instructions icon opens the reference panel and expands the catalogue.

## Review a related component set

When Write or Improve generates two or more B2B website components from the same brief, **Component set check** appears with the results. Open it for suggestions about unnecessary repetition, contradictory details and narrative progression, with exact supporting quotes from different components. Necessary brand names, legal terms and standalone card details may repeat. Separate uploaded briefs are checked independently; single components, other channels, Translate and Review tasks do not trigger this extra check.

The check is advisory and never rewrites the copies, changes field limits or grants approval. Apply useful suggestions through the existing editor or regeneration controls. Saved edits mark earlier set findings as outdated; they do not automatically run another review. Check this copy remains the separate, manually requested guideline/source assessment.

Each eligible brief uses one extra AI review call covering all its selected components and languages. It is part of the existing monthly generation action, while its actual model call counts toward requests-per-minute limits. Large sets may be reviewed in excerpts; the interface discloses that scope. If the check fails, generated copies remain available and the interface asks for manual review rather than claiming that the check passed.


### Review user feedback

Open **Feedback** in the control centre. Filter by thumbs-up/down or review status, search submissions and select one to inspect its input, output, reason, task, instructions and related details. The input/output snapshot remains as submitted. Instruction versions shown here are captured when feedback is submitted, and are labelled accordingly; they are not claimed to be a historical generation-time record.

Add internal findings and select **Mark reviewed**, or save updated review notes. Use **Open AI instructions** to reach the channel's existing instruction editor. Feedback never automatically rewrites or publishes instructions. Only the matching channel admin can read or review the feedback; approval reviewers do not receive access.

# Activity, request limits and suggested instruction placement

## Find where to paste a refined instruction

1. Open the relevant instruction file and describe your new rule in **Turn your instructions into Markdown**.
2. Choose the applicable format or guide part if asked, then click **Refine instructions**.
3. Review the draft and warnings. Click **Copy Markdown**.
4. Click **Go to section · line**. The editor opens at the suggested insertion point. Check the surrounding rules, then paste manually.
5. Save through the version confirmation. A recommendation does not change or save any file. If the file changed after the recommendation, refine again to get a current location.

## Allocate monthly requests

1. The super admin opens **Request control**, selects a channel and saves its monthly channel cap. Application and channel requests-per-minute controls are separate from this monthly budget and are editable only by the super admin.
2. The channel admin opens the same tab to view that budget and allocate requests to users. Include an allocation for administrators who generate copy or refine instructions.
3. Save each allocation. The total cannot exceed the channel budget; limits cannot be reduced below usage already recorded this month.
4. Users can view their own activity and request usage from the workspace's activity area. Channel admins see their channel's allocations and usage; super admins manage all channels.

One Generate, Regenerate, Translate or instruction-refinement action counts once, including bilingual and multi-copy batches. Failed operations release their reservation. Automatic repairs, context detection, guideline checks, edits, exports and approvals do not add requests. Usage resets each calendar month in UAE time, while allocations remain until changed. Until a channel cap is configured, existing accounts remain uncapped. Once configured, an unallocated user has zero requests.

LDAP settings and a local developer-mode switch are configured through the deployment environment. Live directory sign-in requires working directory credentials and connectivity. Request allocations follow linked accounts through their stable directory identity; administrators still assign roles and channels explicitly.

## Navigate activity and channel controls

- Excel downloads automatically assess missing or stale output scores, without requiring **Check this copy** first. Each language/output receives its own Score column value out of 10. Current scores are reused in the open workspace. Progress and **Cancel export** are available; large batches take longer and use AI calls within the configured traffic limits. If the service cannot assess a score, the copies remain downloadable and the cell says **Score unavailable**. Partial assessments are identified in a cell note.

- In **People & access → Approval settings**, select layer 1, 2 or 3 as the **Final approval** layer and save. For example, choose layer 2 for a two-stage regulatory compliance review. The final layer approves the copy for use and notifies the original author. This applies to new submissions/resubmissions; requests already under review keep their saved route.
- In **People & access → Approval settings**, expand a layer and choose **Add reviewer** or **Edit**. Assign multiple people to the same approval layer if required. Every eligible reviewer receives the request, but only one approval per required language is needed; reviewers do not all have to approve. Separate English and Arabic responsibilities still apply. Concurrent approvals cannot advance the request twice.

- **Overview → Channel performance** shows recorded outputs, daily activity, active contributors, popular formats/components and saved batch status. Choose 7, 30 or 90 days, select chart bars for details, and use Refresh for the latest figures. English and Arabic count as separate outputs. Historical single-copy figures can be incomplete where older activity was removed.
- **Estimated hours saved** uses a transparent planning calculation. Open **How these figures are calculated** to adjust manual-work and AI-review minutes in your view. These are estimates, not tracked working hours.
- **Request control → Bulk generation limit** lets a channel admin set their own channel's batch capacity; a super admin can set any channel's capacity. Enter a whole number from 1 to 100 and choose **Save bulk limit**. The default is 20. Files or imported spreadsheet rows multiplied by selected formats must fit the capacity; English and Arabic share one space. Existing saved batches remain available. This setting does not increase monthly allocations or AI calls per minute.

- Activity uses a single searchable table with separate input, output, task, instruction, file and final approval columns. Use **Choose columns** to hide columns you do not need. Expand the arrow in a long cell to read its complete contents.
- Users and reviewers see their own records, channel admins see their channel, and super admins see only their own records in the personal workspace. The super-admin administration has no activity tracker.
- Approval actions remain in **Approvals**. The tracker shows submission and final approval status only.
- Super admins can find **Delete channel** only in **People & access**. The centered confirmation explains what will happen. Cancelling leaves the channel unchanged.



## Remove a channel member

Open **People & access**, choose **Remove** beside a user or reviewer, and confirm **Remove access**. Channel admins can remove only users and reviewers in their own channel. Only a super admin can remove a channel admin; self-removal and super-admin removal are blocked. Removal disables application access, releases the request allocation and retains saved work, usage and review history. Assign access can restore the person later. If a reviewer is removed, check that their layer still has language coverage. The company directory account is not deleted.

## Platform privacy boundary — 30 October 2026

In administration, super admins manage channels, people, request budgets and models without access to other users’ content, feedback, activity or approval requests. They retain the main writing workspace: welcome page, channel switching, single and bulk generation, uploads, editing and exports. Their archive, personal activity and author notifications show their own work only. They can read, edit and restore instruction files and their history across channels. They cannot approve, reject or override review decisions. Channel admins retain those controls for their own channel. Reviewer assignment is account management and does not grant the super admin content access.

The super-admin overview contains aggregate active accounts, recent account additions, monthly request usage/limits and provider-reported token counts. Historical tokens that were not measured are shown as Not recorded. Account addition counts use stored creation dates. This boundary applies to the interface and direct API requests.

### Super-admin instruction access

Super admins can select any channel in **Administration → AI instructions**, read the formatted files, edit Markdown, save confirmed revisions, compare version history and restore older versions. The optional AI instruction helper remains available. Administrative content views, other users’ activity and feedback, approval queues and reviewer notifications remain unavailable to the super-admin role. This restriction does not remove the main writing workspace or the super admin’s own saved work and author notifications.

### Per-model token limits and operational log retention

Only the super admin manages model settings. Open **Models & routing → Token limits** to set different maximum input and output tokens for each model, then **Save model settings**. The Models, Token limits, Routing and Connections tabs keep these tasks separate and retain drafts while switching. Input includes retrieved guidelines, the brief, extra instructions and revision context. Each call uses its selected model’s input limit; oversized input stops before sending and is never silently truncated. Saved input overrides update `LLM_MODEL_INPUT_TOKEN_LIMITS` in `platform-policy.local.env` and apply immediately to new calls. `DEFAULT_MAX_INPUT_TOKENS` is only a seed for unconfigured models. Output limits remain separate. Local tokenizers count supported text models; unknown tokenizers and images use conservative estimates. Model-native combined context limits still apply. Request control contains monthly requests, user allocations, bulk limits, AI traffic and log retention only. Actual usage reporting remains; there is no monthly token budget.

Operational log retention defaults to **180 days**. The super admin can change the period (31–3650 days) or run cleanup after confirmation. Automatic cleanup runs at backend startup and hourly. Expired activity logs, notifications, past-month request records and usage metrics expire. Saved copies, source files, approval evidence, feedback, instruction files and all instruction versions remain. Undated records and current quotas are protected. External backups and infrastructure logs require separate policies. Admin saves update `platform-policy.local.env`; no database schema migration is required.
