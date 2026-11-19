export function tutorialKey(profile) {
  return `rewrite-tutorial-v1:${profile?.email || ''}:${profile?.active_channel_id || ''}:${profile?.role || ''}:${(profile?.review_languages || []).join(',')}`
}

export function tutorialSteps(profile) {
  if (!profile) return []
  const channel = profile.active_channel_id || profile.channel_id || profile.channels?.[0]?.id || ''
  const consumer = ['b2c', 'cx-comms'].includes(channel)
  const admin = ['channel_admin', 'super_admin'].includes(profile.role)
  const reviewer = profile.role === 'approval_admin'
  const canWrite = (profile.workspaces || ['rewrite']).includes('rewrite')
  const adminUrl = tab => `/admin/${encodeURIComponent(channel)}?tab=${tab}`
  const steps = []
  const add = (id, group, title, summary, bullets, path, target, example) => steps.push({ id, group, title, summary, bullets, path, target, example })
  if (profile.role === 'super_admin') {
    add('overview', 'Platform administration', 'Your selected workspace overview', 'Review performance, adoption and usage without opening individual content.', [
      'Choose the channel in the administration selector. View generated outputs, estimated hours saved, active contributors, popular formats and daily trends, plus active accounts, recent additions, request usage and reported tokens.',
      'Select a reporting period, explore the chart bars and switch between format, component/template, task and language breakdowns. Time saved is an adjustable planning estimate, not measured working time.',
      'Earlier token usage is unavailable. Requests this month count user actions, while measured tokens cover individual model calls.',
      'Channel content, activity, feedback, approvals and related notifications stay private. Your role cannot approve or override reviews.',
    ], adminUrl('overview'), '.platform-overview')
    add('people', 'Platform administration', 'Manage channels and access', 'Open People & access for the selected channel.', [
      'Switch channels using the rounded Managing channel menu. Create a channel with + New channel directly below it. People & access is for assigning channel admins and managing user/reviewer access; only super admins can create or delete channels.',
      'Remove access with confirmation. Saved work remains private and retained. You cannot remove yourself or another super admin.',
    ], adminUrl('people'), '.people-layout')
    add('limits', 'Platform administration', 'Manage request budgets', 'Allocate monthly channel budgets and control application capacity.', [
      'Set monthly channel caps and manage allocations. Requests per minute and batch capacity have separate controls.',
      'Use the Monthly budget, User allocations, Bulk limits, AI traffic and Log retention tabs. Input/output token limits are managed per model in Models & routing → Token limits. Log retention defaults to 180 days; saved content and instruction history stay.',
      'These screens show account and usage metadata only, without briefs, generated copy or approval decisions.',
    ], adminUrl('limits'), '.request-limits')
    add('instructions', 'Platform administration', 'Manage channel instructions', 'Choose a channel to read and maintain its writing guidelines.', ['Read rendered instructions, edit Markdown, save a new version and compare or restore earlier versions.', 'The optional AI helper drafts instruction additions for review. Changing instructions does not grant access to channel copies or approvals.'], adminUrl('instructions'), '.instruction-layout')
    add('models', 'Platform administration', 'Manage AI routing', 'Choose default models and configure confidential processing policies.', [
      'Only super admins manage Models & routing. Connection secrets stay in the environment.',
      'Use the Models, Token limits, Routing and Connections tabs. In Token limits, set different maximum input and output values for each model, then Save model settings. Input overrides are stored in the environment and apply immediately to new calls using that model.',
      'Confidential work requires on-premise processing with no cloud fallback. Connection tests use fictional input, never channel content.',
    ], adminUrl('models'), '.inference-models')
    const workspaceSteps = tutorialSteps({ ...profile, role: 'user', workspaces: ['rewrite'] })
      .filter(step => step.id !== 'user-guide')
      .map(step => step.id === 'profile' ? { ...step, bullets: [
        'Open your profile to check your name and role.',
        'Use Switch team channel to open the writing workspace for another channel.',
        'Your own saved copies remain available. Other users’ content stays private.',
      ] } : step.id === 'welcome' ? { ...step, summary: 'This tour covers your writing workspace and platform administration.' } : step)
    return [...workspaceSteps.filter(step => step.id !== 'finish'), ...steps, workspaceSteps.find(step => step.id === 'finish')]
  }
  add('welcome', 'Getting started', 'Your workspace', 'Welcome. This walkthrough is tailored to your access and available tools.', [
    `You are signed in as ${({ user: 'a user', channel_admin: 'an administrator', approval_admin: 'a reviewer' })[profile.role] || 'an authorised user'}. Your assigned writing instructions and formats are already configured.`,
    'Use Next and Back, or the keyboard shortcuts, to follow the tour. Each step opens the relevant page and highlights the feature.',
    'Nothing is generated, uploaded, saved, approved or deleted automatically. You choose every action. Close at any time. Opening the tutorial again starts from step one.',
  ], '/choose', '.welcome-banner-copy')
  add('profile', 'Getting started', 'Your profile', 'Check who you are working as before you begin.', [
    'Open the profile icon at the top right to check your name and access level.',
    'Your administrator manages your access. Contact them if your permissions need updating.',
    'Sign out is at the left of the welcome banner. Keep confidential source material within your authorised workspace.',
  ], '/choose', '.workspace-profile-button')
  if (canWrite) {
    const sample = channel === 'security'
      ? 'Template 1 — Compliance Memo. Summarise the attached policy for internal review. Use only facts in the document; flag missing sender, recipient, deadlines and action owners.'
      : channel === 'b2b'
        ? 'Improve Component 4 for Business Cloud Backup. Confirmed facts: automatic daily backups, fast file recovery and 24/7 support. Keep the required component fields and character limits. Do not invent prices or offers.'
        : consumer
          ? 'Write an SMS confirming a mobile plan renewal tomorrow. The monthly price is AED 100 including VAT. Do not invent a link or an account number. Use clear, reassuring language.'
          : 'Improve this customer message for clarity. Preserve all confirmed facts. Use the formats and instructions configured for this channel.'
    add('request', 'Writing', 'Tell Harf what you need', 'Use the title bar above the text box to describe the task and output format.', [
      'Ask to write, improve, review or translate. Include the intended audience and purpose when relevant.',
      channel === 'security' ? 'Name Template 1 — Compliance Memo. The policy document supplies the facts; the template instructions shape the memo.' : channel === 'b2b' ? 'Specify a component number or name, such as Component 4. Website components and Google Paid Search have different formats and tone rules.' : consumer ? 'Specify SMS, email, website, app or push notification. Each format uses its own indexed instructions.' : 'Choose an available format. Ask your administrator if the format you need is not configured.',
      'Paste the original copy or source facts in Your content. Generation needs readable source text, not just a task name.',
    ], '/copywriter', '.request-title-bar', sample)
    add('brief', 'Writing', 'Upload a brief or paste your text', channel === 'security' ? 'Upload the source policy or document for your memo.' : 'Upload a brief when you have supporting facts, or paste your source text.', [
      'Select Confidential document before adding sensitive material. All related AI work then requires an on-premise model, with no cloud fallback. If the internal gateway is not configured, processing is blocked. New brief confirms before clearing the workspace.',
      'Upload DOCX, TXT, PDF, Excel or CSV, or a clear PNG, JPG or WebP screenshot. Review extracted text or imported rows before generating.',
      'Use a readable PDF text layer where possible. Scanned documents may need OCR; extraction depends on the configured document service.',
      channel === 'security' ? 'Upload source documents within the displayed limits. Add known memo details and ask for concise summaries; missing facts must be flagged.' : 'The file provides context and facts. Your writing guidelines still apply; source documents do not override the application rules.',
    ], '/copywriter', '.brief-dropzone || .workflow-selector')
    add('formats', 'Writing', channel === 'security' ? 'Choose the memo template' : 'Choose components and templates', 'Select one format or several to produce separate outputs from the same brief.', [
      channel === 'b2b' ? 'Select the website components you need. Each selected component receives its own output, title and field limits.' : consumer ? 'Choose the delivery formats you need, such as SMS and email. They receive separate outputs.' : channel === 'security' ? 'Select Template 1 for the compliance memo. The output uses paragraphs and tables where appropriate, following the active memo instructions.' : 'Use the available formats. Ask your administrator to configure missing instructions.',
      'Open Instructions beside the selection area to inspect available format details. Collapse Components and templates to save space.',
      'Your channel administrator sets the batch capacity. Files multiplied by selected formats must fit within that limit; English and Arabic share one space.',
    ], '/copywriter', '.output-picker')
    add('directions', 'Writing', 'Add precise requirements', 'Use Specific details and instructions to guide this particular request.', [
      'Include the tone, audience, mandatory wording, CTA, exclusions and confirmed offer conditions. Supply exact dates, prices and VAT treatment when needed.',
      'Your request cannot override mandatory channel instructions or justify inventing missing commercial or compliance facts.',
      'Review character counts under the input and output. If needed, set the optional character limit; format-specific limits still apply.',
    ], '/copywriter', '#copywriter-instructions || #bulk-instructions')
    add('languages', 'Writing', 'Choose English, Arabic or both', 'Use the language buttons before generating.', [
      'Choose both for bilingual outputs. Each selected format is generated in the requested languages.',
      'Arabic should convey the intended meaning naturally, with correct spelling and grammar. Review names, numbers, dates and technical terminology in both languages.',
      'Generate starts an AI request. A bilingual or multi-copy batch counts as one monthly action; failed attempts and automatic repairs do not add requests.',
    ], '/copywriter', '.copywriter-languages')
    add('bulk', 'Writing', 'Work with multiple files', 'Switch from Single copy to Bulk files when each source needs its own tailored output.', [
      'Upload files within your channel’s batch limit, inspect their word/character counts and remove files you do not need.',
      'Add shared batch instructions, choose languages and formats, and check the total output limit before Generate.',
      'Drag files into the bulk upload area or browse to select them. Duplicate files are skipped; check the upload progress and remaining spaces.',
    ], '/copywriter', '.workflow-selector')
    add('results', 'Reviewing your content', 'Review, refine and send for approval', 'Finish your content in one place: edit it, check it, share feedback and submit it when ready.', [
      'Review every component and language in Output. Use the editor to change wording or paste tables, then save. Back to input and Back to output keep your brief and results accessible. Expand output gives longer copies more room; restore the first version where available.',
      'For an AI revision, use “Not quite right? Tell us what to change”. Be specific; a batch revision applies to every copy in that batch.',
      'Choose Check this copy under Guidelines & source check when ready. Review the score out of 10, guideline strength, What needs attention, Source details and file/section references in Files & review coverage. Collapse and reopen the check after it runs. Recheck after edits; wording overlap does not prove factual accuracy.',
      'Use thumbs up or thumbs down on the final output. Thumbs down requires a reason; only your channel admin receive the feedback and its generation context.',
      'When all copies are ready, choose MOVE TO APPROVAL. The configured layers review the required languages in sequence. One eligible reviewer per required language is enough at each layer. If returned, follow the notes, revise and resubmit. Only final approval gives the green light; unsent drafts stay outside the approval queue.',
    ], '/copywriter', '.output-panel || .bulk-results-panel')
    add('archive', 'Saving and sharing', 'Find a saved copy in Archive', 'Open Archive beside the upload controls to return to saved work.', [
      'Entries now have short content-based names. Expand the file list to see the named copies within a batch.',
      'Use the date, output languages, copy count and approval status to distinguish similar work. Original source filenames are retained for traceability.',
      'Opening an archived batch returns to its generated copies. A fresh unsaved single-copy draft is not automatically an archive entry; saving it for approval creates an entry.',
    ], '/copywriter', '.copywriter-source-actions [aria-haspopup="dialog"]')
    add('exports', 'Saving and sharing', 'Copy or export your final content', 'Choose the format that fits the next step in your work.', [
      'Copy the complete text, or use Copy ready content where available to omit reference/validation notes.',
      'PDF opens an independent preview. Press Print / Save as PDF there. Creator and creation time appear once in small text at the top left; Word uses the same compact attribution.',
      'Word preserves editable content and tables. Text is plain text. Excel places each full generated output in one cell with separate metadata columns and automatically checks missing scores during export. Progress and Cancel export are available. Excel has a 32,767-character cell limit.',
    ], '/copywriter', '.copywriter-downloads')
  }
  if (canWrite || reviewer || admin) add('notifications', 'Your account', 'Keep up with notifications', 'Check the bell or Notifications tab for updates relevant to your work.', [
    'Open unread messages to see new review requests, returned work and final decisions.',
    'Read a notification before marking it as read. Follow its details to the relevant copy or queue; the notification itself is not an approval.',
    'If a request is returned, read the reviewer note, update the original copy and resubmit when ready.',
  ], admin || reviewer ? adminUrl('notifications') : '/copywriter', admin || reviewer ? '.notification-panel' : '.copywriter-notification-menu')
  add('activity', 'Your account', 'Track activity and monthly requests', 'Open My activity & requests from the welcome page.', [
    profile.role === 'super_admin' ? 'You can filter activity across all channels.' : profile.role === 'channel_admin' ? 'You can see all activity within your channel.' : 'You see only your own activities, including when you also have approval access.',
    'Search the table, choose columns, use page navigation and expand long cells with the arrow. Approval columns show submission and final status, not approval controls.',
    admin ? 'Use Request control → Monthly budget and User allocations to manage requests. The platform administrator assigns the workspace budget; you allocate it among your users, including yourself when generating.' : 'Check your monthly allocation and remaining requests. Ask your administrator for an allocation when needed. Usage resets each calendar month in UAE time.',
  ], '/activity', '.activity-workspace')
  if (profile.role === 'user') {
    add('user-guide', 'Your account', 'Read your channel user guide', 'The instructions icon opens the guidance available to your account.', [
      'Read the user-facing guide for your channel to understand inputs, supported formats and expected outputs.',
      'Use the jump-to-top and jump-to-bottom controls for long guidance. System/template instruction editing and protected administrator guidance remain restricted.',
      'Contact your channel admin if guidance is unclear or a required format is missing. Use output feedback for a specific generated-copy issue.',
    ], `/guidelines?channel=${encodeURIComponent(channel)}`, '.guidelines-document')
  }
  if (reviewer || admin) {
    add('reviewer', 'Approvals', reviewer ? `Review layer ${profile.approval_layer || 1}` : 'Manage approval requests', reviewer ? `Your review languages: ${(profile.review_languages || ['en', 'ar']).map(language => language === 'ar' ? 'Arabic' : 'English').join(' and ')}.` : 'Your channel approval queue includes the full generation context and review history.', [
      'Open Approvals in administration. Select a submitted request, then use Generated copy, Brief & instructions and Review history to inspect the full context. Search or filter the queue; unsent drafts do not appear.',
      reviewer ? 'Act only at your assigned layer and for your assigned language(s). Every required output language must be approved before the request moves to the next layer.' : 'Use the normal language review workflow, or an administrator action when authorised. Final approval override bypasses remaining layers and requires a recorded reason.',
      'Approve, reject, add a note, return to the author, or return to layer 1 where available. Reasons are required for rejection, return and administrator actions. A note alone does not approve the copy.',
      'Refresh after a copy is returned or resubmitted. An old review page cannot approve a newer review round. Simultaneous decisions are checked so the request advances only once.',
      ...(reviewer ? ['Approval access does not grant access to private AI instruction files or other users’ activity.'] : ['Choose the final approval layer in People & access → Approval settings. Expand a layer to add or edit reviewers; one approval per required language is enough. Routing changes apply to new submissions and resubmissions.']),
    ], adminUrl('approvals'), '.approval-layout')
  }
  if (admin) {
    if (profile.role === 'super_admin') add('models', 'Administration', 'Choose AI models safely', 'Models & routing controls the application default, channel selections and confidential model.', [
      'Only super admins can manage this inventory. Connections and credentials stay in the environment for IT to configure; the screen reports whether new routing is active.',
      'Cloud models use Responses; on-premise models use Chat Completions. Confidential documents always require an enabled on-premise model, even when a channel normally uses cloud.',
      'Save model changes, then test connections using fictional input only. Approve image reading only for deployments that support it. Configured models are not guaranteed available until tested.',
    ], adminUrl('models'), '.inference-models')
    add('overview', 'Administration', 'Understand your control centre', 'Use the administration button on the welcome page.', [
      'Overview summarises generated outputs, estimated hours saved, popular formats, trends, members, active instructions, pending reviews and recent changes.',
      'Your administrative controls apply to your assigned workspace and its members.',
      'Approvals, Activity tracker, Request control, Feedback, Notifications, People & access and AI instructions each have a dedicated tab.',
    ], adminUrl('overview'), '.admin-sidebar')
    add('people', 'Administration', 'Manage people and review access', 'Open People & access to assign a new colleague or edit an existing account.', [
      'Search by corporate username and select the correct full name and email from LDAP. Choose the channel and access level; enable approval access and its layer and language when needed.',
      'Give approval access where needed, then choose layer 1, 2 or 3 and English, Arabic or both review languages.',
      'Use Remove beside a member and confirm to revoke application access. Channel admins can remove their users and reviewers; only super admins can remove channel admins. Saved work and review history are retained, and Assign access can restore an account.',
      'You can manage assigned users and reviewers. Only the super admin can assign administrators.',
    ], adminUrl('people'), '.people-layout')
    add('limits', 'Administration', 'Allocate the monthly request budget', 'Open Request control and use Monthly budget, User allocations and Bulk limits.', [
      profile.role === 'super_admin' ? 'Choose a channel and set its monthly cap. Then allocate requests to users, or let its channel admin do so.' : 'View the channel cap assigned by the super admin, then save individual user allocations within that budget.',
      'The allocation total cannot exceed the channel cap. Include admins who generate or refine instructions. Limits cannot be reduced below this month’s recorded usage.',
      'Usage resets monthly; allocations recur until changed. Your IT team manages directory sign-in configuration. Linking an account carries forward existing usage and allocations; it does not grant roles automatically.',
    ], adminUrl('limits'), '.request-limits')
    add('instructions', 'Administration', 'Maintain the three instruction files', 'Open AI instructions for the selected channel.', [
      'System instructions hold shared rules. Indexed template instructions hold format/component requirements. The user/admin guide explains use and maintenance; it is not included in generation prompts.',
      'Use Turn your instructions into Markdown to refine a draft. Review warnings, copy the snippet, and use Go to section · line to locate a suggested insertion point. Nothing is pasted or saved automatically.',
      'Preserve stable IDs, anchors and user/admin boundaries. Adding writing guidance is different from adding application functionality; new features or routing may require development.',
    ], adminUrl('instructions'), '.instruction-refiner')
    add('versions', 'Administration', 'Confirm, compare and restore instructions', 'Every saved instruction edit has a retained version.', [
      'Edit the selected file, choose Save changes, add a change note and confirm in the centered dialog.',
      'Use Version history to inspect previous saved content. Restore an older version with a reason; restoration creates a new version and retains the history.',
      'Test a representative fictional brief before relying on updated guidance. Changing Markdown does not guarantee an error-free AI response.',
    ], adminUrl('instructions'), '.instruction-editor')
    add('admin-feedback', 'Administration', 'Turn feedback into better guidelines', 'Open Feedback to investigate output quality with context.', [
      'Filter feedback and open an entry to read the source input, output, task, user comments and generation details.',
      'Identify whether the cause is a missing rule, ambiguous template, inaccurate source fact or model error. Avoid weakening mandatory safeguards to fix a single example.',
      'Update the relevant instruction file if needed, record the change as a new version and test the affected format. Only the matching channel admin can see the feedback.',
    ], adminUrl('feedback'), '.admin-main')
  }
  add('finish', 'Next steps', 'Ready for your next task', 'You can revisit this tutorial from the welcome page whenever you need it.', [
    'Start with a clear brief, choose the right format and review the output against the source facts.',
    'Your channel admin can help with access, request allocations and writing instructions. Important communications still need human review.',
    'Opening the tutorial from the welcome page always starts a fresh tour from step one, tailored to your current account, channel and role.',
  ], '/choose', '.welcome-introduction')
  // Keep routing IDs internal. User-facing guidance describes only the assigned
  // workspace and never advertises other channels or platform-wide management.
  const wording = value => value
    .replace(/\bchannel administrators\b/gi, 'administrators')
    .replace(/\bchannel administrator\b/gi, 'administrator')
    .replace(/\bchannel admins\b/gi, 'administrators')
    .replace(/\bchannel admin\b/gi, 'administrator')
    .replace(/\bteam channel\b/gi, 'workspace')
    .replace(/\bchannel\b/gi, 'workspace')
  return steps.map(step => ({ ...step, title: wording(step.title), summary: wording(step.summary), bullets: step.bullets.map(wording), ...(step.example && { example: wording(step.example) }) }))
}
