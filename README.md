# Harf

Rewrite provides a writing workspace for B2B, B2C, Regulatory Compliance and custom channels.

## Run locally

Start the backend and frontend in separate terminals from the project root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

```powershell
npm install
npm run dev
```

The backend listens at `http://127.0.0.1:8000`. Open `http://localhost:5173` for the app.
`run_all.bat` can also start both services; `run_all.bat --check` verifies dependencies.

## Text service configuration

Use the **project root `.env`** for all private runtime settings: AI gateways,
Docling, LDAP/developer mode, Oracle and admin-managed limits. The backend loads
this file regardless of its launch directory. Explicit deployment environment
variables take precedence at startup; admin-managed controls read their saved
values from the root file. `COPYWRITER_` settings retain text-specific overrides.

`.env.example` is a shareable setup template, not an active settings file.
Feature-specific `*.env.example` files are reference snippets only. The former
private backend environment files have been consolidated; originals are retained
under ignored `backups/config/`. Never commit `.env` or those private backups.
See [configuration and access guide](docs/Configuration_and_Access_Requests.md).

## Application structure

- `SDD/`: current solution design in Word and Markdown, with supporting diagrams.
- `src/`: sign-in, Rewrite, channel administration, guidelines, approvals and feedback.
- `backend/`: FastAPI routes, text generation, document processing, permissions and exports.
- `instructions/`: channel Markdown guidelines, templates and archived instruction modules.
- `public/`: PDF preview and channel administration help.

Rewrite supports creating, improving, reviewing and translating content; multiple components
or templates; uploaded briefs; editable outputs; guideline and source-fact assessment;
bulk processing; approval workflows; and PDF, Word, text and Excel exports.
Only Rewrite workspace permissions are supported. Channel administrators manage members,
reviewers, instructions and feedback; super admins also manage channels.

## Three-file channel instruction packs

B2B, B2C and Security each use a system instruction file, an indexed template instruction
file, and a user/admin guide under `instructions/channels/<channel>/`.
System rules apply to every request. Format-specific instructions are selected from the
template file; B2B website components and Google Paid Search remain separate scopes.
The guide is excluded from AI prompts, and only channel/super admins can read its admin part.
New channels receive three neutral starter files with the same separation and an empty
template index; they do not inherit another channel's brand rules or templates.

B2B original source documents, former instructions and a block-level preservation manifest
are retained under `output/b2b-instruction-pack/`. The active B2B library exposes exactly
three files. Historical source blocks are retained in full, while only relevant reference
examples are selected for generation. The updated component library remains authoritative
for Components 1–17; the older library is preserved as historical reference.

## Verification

```powershell
npm run build
npm test
backend/.venv/Scripts/python.exe TEST/run_backend.py
```

All automated test cases are in `TEST/`; see `TEST/README.md` for isolated runs.

The former `Copywriter/backend/prompt/` folder is now `instructions/`. All file
contents are preserved. Backup/recovery supports artifacts using either layout.
