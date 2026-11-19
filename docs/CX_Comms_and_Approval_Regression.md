# CX Comms instructions and approval regression checks

CX Comms has an independent copy of the three active B2C instruction files:

| Source | CX Comms copy |
| --- | --- |
| B2C system instructions | `01_CX_COMMS_SYSTEM_INSTRUCTIONS.md` |
| B2C indexed template instructions | `02_CX_COMMS_CHANNEL_TEMPLATE_INSTRUCTIONS.md` |
| B2C user/admin guide | `03_CX_COMMS_USER_AND_ADMIN_GUIDE.md` |

Only channel references are substituted. Human labels use CX Comms; machine IDs and anchors use `CX-COMMS`, `CX_COMMS` or `cx-comms` as appropriate. Rules, examples, glossary entries and limits are preserved. The five selectable format parents (SMS, email, website, app and push) and indexed variants retain their parent dependencies. Retrieval reads CX Comms files, not B2C files. Future edits therefore remain independent. B2C database content, version history, local file hashes and channel configuration were checked before/after the copy and were unchanged. Previous CX files and the copy audit are backed up privately under `backups/channel-instructions/`.

The sidebar’s rounded **Managing channel** menu supports mouse/keyboard selection, Escape and outside-click dismissal. **+ New channel** opens a centered creation dialog for super admins only. Creating a channel still produces its own three starter files; this explicit CX copy does not make other new channels inherit B2C rules. People & access retains membership and deletion controls.

## Approval behavior and regression coverage

Automated tests in `test_approval_scenarios.py`, `test_approval_routing.py` and `test_approval.py` cover:

- B2B, B2C, Regulatory Compliance and CX Comms.
- Final layers 1, 2 and 3; English, Arabic and bilingual copies.
- One of multiple eligible reviewers is sufficient per required language/layer. A bilingual reviewer can approve both required languages in one action; an English-only reviewer cannot approve Arabic.
- Two simultaneous same-language approvals advance once. Two simultaneous bilingual final approvals produce one final decision and one final notification per recipient.
- Simultaneous English/Arabic reviews preserve both decisions without losing language approvals.
- A final-layer setting change does not rewrite a pending request’s captured route. Returned/rejected work adopts the new route when resubmitted. Concurrent routing-setting and approval writes preserve both changes.
- Rejection/return competing with approval applies one transition; later stale requests must refresh.
- Notes do not advance the route. Rejection, return and note actions require nonblank notes. Terminal copies cannot be reviewed again as if pending.
- Resubmission or return to layer 1 creates a new approval round. The interface supplies its round and layer, preventing a stale reviewer page from approving a newer round even when the layer number matches.
- Wrong role, channel, layer or language is denied; normal users and super admins do not gain reviewer decisions.

The existing shared storage lock serializes updates locally and locks the Oracle runtime revision row for cross-worker operations. Business scenarios use disposable fixtures; browser tests use mocked responses. They never approve real saved customer copies. Tests reduce regression risk; they do not guarantee that arbitrary future changes cannot break the workflow.
