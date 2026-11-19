# Corporate username sign-in and deployment setup

## Production configuration

Configure the backend's injected environment or root `.env`:

```dotenv
AUTH_PROVIDER=ldap
DEVELOPER_MODE=false
LDAP_SUPER_ADMIN_USERNAMES=bmahrouseh,selkhiat,mohmay,haamir
```

Keep the approved LDAP server, TLS, service-bind account, password, search base
and JWT_SECRET configured. The service account needs directory search permission
for sAMAccountName, displayName, mail/userPrincipalName and objectGUID. Supply the
trusted corporate CA through LDAP_CA_CERT_FILE where needed. No passwords go in
frontend configuration or the administrator username allowlist.

Users enter their corporate username and password. Email-format validation and
the example email are removed. The requested button label is “Sign in with SSO”.
Authentication is an LDAP bind; this does not implement browser redirects,
passwordless Windows integrated authentication, SAML or OIDC federation.

The four allowlisted usernames resolve to actual directory identities and become
super administrators without invitations. Their passwords still belong to LDAP.
Other valid directory users require an administrator's explicit channel/role
assignment. Names, email and stable identity come from LDAP, not client-supplied
form text. Changing the allowlist requires deployment/restart; previously managed
administrators removed from the list are deactivated by setup.

## Pipeline step

After the Oracle schema and runtime data are installed/imported, and before
starting backend workers, run with the deployment's configured Python environment:

```powershell
python backend/directory_provisioning.py
```

This strict pipeline command resolves all four users first and fails if directory
lookups fail, without applying account changes. There is no CI configuration in
this repository, so add this command to the team's actual deployment pipeline.
Startup also applies the idempotent data update. If LDAP is temporarily unavailable
at startup, it logs that provisioning is deferred; an already-running application
does not become unavailable solely because a directory lookup failed. After a
successful LDAP password bind, an allowlisted administrator can also be provisioned
on first sign-in. Unknown usernames are never automatically assigned privileges.

## CX Comms registration

The three CX Comms Markdown files were already tracked in Git. The channel itself
was stored in the original application's database, so deploying Git files alone
did not register it in another Oracle database. Setup creates the missing
`cx-comms` channel and missing `CX_COMMS_SYSTEM`, `CX_COMMS_TEMPLATES`, and
`CX_COMMS_USER_GUIDE` instruction records with baseline history. Existing Oracle
instruction content and versions are preserved; B2C instructions are unchanged.
An explicitly soft-deleted channel is not reactivated by setup.

## People & access

Type at least two characters of a corporate username. Select a result showing
its full name and email, choose the channel/role and save. The backend resolves
the exact account again before saving, so editing a request cannot substitute a
different email or identity. Search is restricted to super/channel admins and
their authorized channel; results are capped at ten. Approval access uses two
buttons in the application red, followed by layer and language controls.

## Removed accounts and access requests

Known legacy seeded demo accounts are removed from the active account store and
Oracle user projections, and are no longer reinserted on reads. Existing genuine
LDAP identities are retained. Saved copies and review history are retained.
The developer account remains as an explicit local backup. It cannot sign in in
LDAP production mode: using it requires DEVELOPER_MODE=true and its existing local
password, or HARF_DEVELOPER_PASSWORD when no stored backup password exists.

The invite form, request dashboard and public request/review endpoints are removed.
Setup clears the current runtime `access_requests` collection and its review
activity events. Oracle has no dedicated access-request table in this schema.
Private recovery backups and immutable migration snapshots are retained; they are
not live invitations. Take a controlled backup before running setup in production.

## Verification

1. Run the setup command in the deployed environment; confirm four directory admins.
2. Sign in with one approved username and its real LDAP password.
3. Confirm CX Comms appears to the super admin and has its three instruction files.
4. Add a directory user from search and verify channel/language reviewer permissions.
5. Confirm old demo accounts and access-request endpoints are unavailable.
6. Run the command again; verify existing instructions and history remain unchanged.

Local regression tests use fictional directory entries and transaction-capable
Oracle SQL doubles. They cannot certify connectivity to the company LDAP server.
