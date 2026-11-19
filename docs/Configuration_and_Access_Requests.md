# Configuration and access requests

## Requesting access

1. On sign-in, select **Request an invite**.
2. Enter full name, work email and team/department. No list of channels is exposed.
3. In local/developer sign-in mode, choose a password of at least eight characters.
   With LDAP sign-in, no directory password is requested or stored by this form.
4. Submit. The confirmation is deliberately the same for an existing account or
   duplicate request, so the public form does not disclose registered people.

## Super-admin review

Open **Administration → People & access → Access requests**. The queue is global
and visible only to super admins. Select the channel and one of two access setups:

- **Channel admin — activate immediately:** creates an active channel administrator
  who can sign in and manage that channel.
- **Channel admin will activate access:** creates an inactive account in the selected
  channel. It cannot sign in until its channel admin completes access setup.

An optional note records the decision. Decline rejects the request without creating
an account. Reviewed requests remain available in the reviewed history. Simultaneous
reviews are serialized by the application storage lock; the second review receives
a conflict rather than creating another account.

## Channel-admin setup

1. Open **People & access** in the assigned channel.
2. Find the person labelled **Awaiting access setup** and select **Edit**.
3. Choose **User** or enable approval access, selecting the layer and review languages.
4. Select **Save access**. This activates the account and retains its chosen local
   password (or its normal LDAP sign-in). Channel admins cannot promote a person
   to channel admin or manage another channel's accounts.

This workflow does not send email. Administrators should tell applicants when access
has been activated. Public submissions are limited to ten attempts per address per
hour per backend process. A shared edge/gateway limit should be configured for a
multi-worker public deployment. The outstanding-request queue is also bounded.

## Persistence

Requests are saved as `access_requests` in the existing access-control repository:
Oracle `GENAI_HARF_RUNTIME_STATE.ACCESS_JSON` when Oracle is selected, or the local
access-control JSON when local storage is explicitly selected. Accounts also use
the existing user table projection. No additional schema migration is required.
Local password hashes are never returned by request-list or review endpoints.

## One runtime environment

The project root `.env` is the single private runtime configuration file. It holds
AI connections, text-specific `COPYWRITER_` overrides, Docling, authentication,
Oracle and admin-managed request/model/retention controls. Loading uses an absolute
path, so starting the backend from its own directory is supported.

The previous `backend/.env`, `Copywriter/backend/.env`, `oracle.local.env`,
`llm-rate.local.env` and `platform-policy.local.env` have been consolidated. Their
original contents and the original root file are backed up under ignored
`backups/config/20261109-110132/`. Do not publish these private backups.

The consolidation preserves the earlier effective Oracle values and text-specific
deployment values. Root `COPYWRITER_AZURE_OPENAI_*` variables preserve the previous
Copywriter-specific deployment. Credentials were not displayed or added to source
control. Admin writes update only their own keys and preserve other settings and
comments. Related writes are serialized within a backend process.

`.env.example` and feature-specific `*.env.example` files are documentation templates,
not active configuration. Existing explicit file-path overrides remain supported
for automated tests and specialised deployments. Normal startup uses only root `.env`.
Deployment-injected environment variables are not overwritten at startup. Connection
changes require a backend restart; admin-managed controls are read from the saved
file and reflected through their existing policy mechanisms.

## Tests

All 72 pre-existing test files were relocated, without removing test cases, into
`TEST/backend/` and `TEST/frontend/`. Python and JavaScript remain distinct suites.
The move manifest is `TEST/moved-files.json`. Imports and project-relative fixture
paths were adjusted. New invite and environment-preservation tests are alongside
the existing tests. Run commands are documented in `TEST/README.md`.
