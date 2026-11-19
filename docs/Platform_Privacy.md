# Platform administration privacy

Super administrators manage platform access, capacity and instruction files. Channel administrators own channel content and reviews.

| Capability | Super admin | Channel admin |
| --- | --- | --- |
| Create/delete channels, assign channel admins | Yes | No |
| Manage accounts and request allocations | All channels | Own channel |
| Models, routing and application rate limits | Yes | No |
| Use single/bulk writing, upload, edit and export | Yes | Yes |
| View other users’ briefs, generated copy, activity or feedback | No | Own channel only |
| View own saved copies and personal activity in the workspace | Yes | Yes |
| Read/edit instruction files and version history | All channels | Own channel only |
| Approve, reject or override review decisions | No | Own channel only |
| Administrative content notifications and approval queues | No | Own channel only |

The super-admin overview follows the selected administration channel. It shows generated language outputs, successful generation requests, aggregate active contributors, output trends, standard format/component/template/task/language counts, estimated hours saved, active accounts, recent account additions, monthly request usage/caps and reported input/output tokens. Time saved is an adjustable planning estimate, not measured working time. Custom labels are normalised to prevent content leakage. It does not expose individual identities, generation titles, products, file names, prompts, outputs, notes or approval states. People & access retains the account metadata needed to assign access. Super admins may assign reviewer access but cannot participate in content reviews with their super-admin identity.

These restrictions apply to administration and other users’ content. Super admins can open the welcome page, switch channels and use all writing features. Workspace archive, personal activity and author notifications are restricted to their own work. Direct requests for another user's saved copy remain denied, including known IDs and historical notifications. Super admins can submit their own work for review but cannot approve, reject or override decisions. Local development file serving denies backend data, channel prompt directories and private output/backup folders.

## Token figures

Only actual token usage returned by the model provider is aggregated, by channel and UAE calendar day. Counters include input, output, total tokens, measured calls and calls without usage reports. No prompts or generated text are passed to this reporting component. Historical consumption cannot be reconstructed and is shown as **Not recorded**. Token figures cover individual model calls; monthly request budgets count user actions, so the two counts are different.

The counters use the existing runtime access store (Oracle in the configured deployment). No schema migration or new database table is required. Account additions use stored creation dates; older accounts without dates are excluded and imports can carry import dates.

This is application role isolation. Operators with direct database, filesystem or server credentials remain infrastructure administrators and require their organisation's separate access controls.
