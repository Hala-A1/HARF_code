import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, Header, HTTPException
from storage_backend import oracle_enabled
from storage_lock import StorageLock


DATA_FILE = Path(__file__).parent / "access-control.json"
from instruction_locations import INSTRUCTIONS_ROOT
CHANNEL_PROMPT_DIR = INSTRUCTIONS_ROOT / "channels"
INSTRUCTION_PACK_DIR = INSTRUCTIONS_ROOT / "instruction-pack"
COMPLETE_CX_GUIDE_FILE = INSTRUCTIONS_ROOT / "eand_CX_Writing_AI_Instructions_SLIDE_FORMAT_EN_AR.md"

DATA_LOCK = StorageLock()
ROLES = {"super_admin", "channel_admin", "approval_admin", "user"}
WORKSPACES = {"rewrite"}
DEFAULT_WORKSPACES = ["rewrite"]


def password_hash(password: str) -> str:
    return hashlib.sha256(f"ai-content-accelerator::{password}".encode("utf-8")).hexdigest()

INSTRUCTION_MODULES = {
    "CX_COMMS_SYSTEM": {"filename": "01_CX_COMMS_SYSTEM_INSTRUCTIONS.md", "name": "System — Shared Writing Rules and Terminology", "scope": "All CX Comms writing tasks", "applies_to": "global", "always_active": True, "channel_id": "cx-comms", "description": "Independent CX Comms copy of the consumer writing standards and terminology."},
    "CX_COMMS_TEMPLATES": {"filename": "02_CX_COMMS_CHANNEL_TEMPLATE_INSTRUCTIONS.md", "name": "Templates — Indexed Channels, Formats and Examples", "scope": "CX Comms delivery formats", "applies_to": "global", "always_active": True, "channel_id": "cx-comms", "description": "Independent indexed SMS, email, web, app, push and UX formats."},
    "CX_COMMS_USER_GUIDE": {"filename": "03_CX_COMMS_USER_AND_ADMIN_GUIDE.md", "name": "Guide — User Help and Administrator Maintenance", "scope": "Reference only", "applies_to": "reference", "channel_id": "cx-comms", "description": "CX Comms user workflow and protected administrator maintenance guidance; excluded from generation."},
    "B2B_SYSTEM": {"filename": "01_B2B_SYSTEM_INSTRUCTIONS.md", "name": "System — Shared Writing Rules and Terminology", "scope": "All B2B requests", "applies_to": "global", "always_active": True, "channel_id": "b2b", "description": "Shared factual safeguards, brand governance, English–Arabic terminology and writing standards, with full source preservation."},
    "B2B_TEMPLATES": {"filename": "02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md", "name": "Templates — Indexed Components, Formats and Examples", "scope": "B2B delivery formats", "applies_to": "global", "always_active": True, "channel_id": "b2b", "description": "Indexed Components 1–17, website tone, Google Paid Search rules and preserved messaging/source examples; routed by format."},
    "B2B_USER_GUIDE": {"filename": "03_B2B_USER_AND_ADMIN_GUIDE.md", "name": "Guide — User Help and Administrator Maintenance", "scope": "Reference only", "applies_to": "reference", "channel_id": "b2b", "description": "User workflow and protected administrator instructions for extending this three-file pack; excluded from generation."},
    "CHANNEL_SYSTEM": {"filename": "01_SYSTEM_INSTRUCTIONS.md", "name": "System Instructions — Shared Channel Rules", "scope": "All channel requests", "applies_to": "global", "always_active": True, "custom_channel_only": True, "description": "Channel-specific behaviour, terminology and factual safeguards."},
    "CHANNEL_TEMPLATES": {"filename": "02_CHANNEL_TEMPLATE_INSTRUCTIONS.md", "name": "Template Instructions — Indexed Formats", "scope": "Channel templates", "applies_to": "global", "always_active": True, "custom_channel_only": True, "description": "Indexed templates, fields, limits and labelled examples."},
    "CHANNEL_USER_ADMIN_GUIDE": {"filename": "03_USER_AND_ADMIN_GUIDE.md", "name": "User Guide and Administrator Maintenance", "scope": "Reference only", "applies_to": "reference", "custom_channel_only": True, "description": "User workflow and protected administrator setup instructions; excluded from generation."},
    "B2C_SYSTEM": {"filename": "01_B2C_SYSTEM_INSTRUCTIONS.md", "name": "System — Shared Writing Rules and Terminology", "scope": "All B2C writing tasks", "applies_to": "global", "always_active": True, "channel_id": "b2c", "description": "Shared consumer voice, factual safeguards, English–Arabic terminology and validation."},
    "B2C_TEMPLATES": {"filename": "02_B2C_CHANNEL_TEMPLATE_INSTRUCTIONS.md", "name": "Templates — Indexed Channels, Formats and Examples", "scope": "B2C delivery formats", "applies_to": "global", "always_active": True, "channel_id": "b2c", "description": "SMS, email, website, app and push structures with indexed variants and source examples."},
    "B2C_USER_GUIDE": {"filename": "03_B2C_USER_AND_ADMIN_GUIDE.md", "name": "Guide — User Help and Administrator Maintenance", "scope": "Reference only", "applies_to": "reference", "channel_id": "b2c", "description": "User instructions and a protected administrator maintenance section; excluded from AI prompts."},
    "CHANNEL_TEMPLATE_GUIDE": {"filename": "CHANNEL_TEMPLATE_GUIDE.md", "name": "Template Instructions — Output Structure and Examples", "scope": "Custom channel", "applies_to": "global", "always_active": True, "custom_channel_only": True, "description": "Define output sections, fields, tables and examples for this channel."},
    "CHANNEL_USER_GUIDE": {"filename": "CHANNEL_USER_GUIDE.md", "name": "User Guidelines — Briefs, Editing and Approval", "scope": "Custom channel", "applies_to": "global", "always_active": True, "custom_channel_only": True, "description": "How users provide facts and how admins maintain the channel's instructions."},
    "B2B_BRAND_DICTIONARY": {"filename": "B2B_BRAND_DICTIONARY.md", "name": "Brand Dictionary — Product Names and Approved Terms", "scope": "B2B terminology", "applies_to": "global", "always_active": True, "channel_id": "b2b", "description": "Approved names, preferred and restricted terminology from the supplied brand dictionary."},
    "B2B_WEBSITE_TOV": {"filename": "B2B_WEBSITE_TOV.md", "name": "Website Tone of Voice — Perspective and Writing Standards", "scope": "B2B website", "applies_to": "website", "always_active": True, "channel_id": "b2b", "description": "Website voice, perspective, commercial transparency and component writing rules."},
    "SECURITY_POLICY": {"filename": "01_REGULATORY_COMPLIANCE_SYSTEM_INSTRUCTIONS.md", "name": "System — Shared Writing Rules and Terminology", "scope": "All Regulatory Compliance requests", "applies_to": "global", "always_active": True, "channel_id": "security", "description": "Shared evidence hierarchy, summarisation, factual safeguards, language rules and exclusions."},
    "SECURITY_MEMO": {"filename": "02_REGULATORY_COMPLIANCE_CHANNEL_TEMPLATE_INSTRUCTIONS.md", "name": "Templates — Indexed Channels, Formats and Examples", "scope": "Regulatory Compliance templates", "applies_to": "global", "always_active": True, "channel_id": "security", "description": "Indexed Template 1, section budgets, full authoring requirements, references and rendering rules."},
    "SECURITY_USER_GUIDE": {"filename": "03_REGULATORY_COMPLIANCE_USER_AND_ADMIN_GUIDE.md", "name": "Guide — User Help and Administrator Maintenance", "scope": "Reference only", "applies_to": "reference", "channel_id": "security", "description": "User workflow and a protected administrator section for editing rules and extending the template index."},
    "CX_WRITING_COMPLETE_GUIDE": {
        "filename": "eand_CX_Writing_AI_Instructions_SLIDE_FORMAT_EN_AR.md",
        "name": "Customer Communications — English and Arabic Writing Standards",
        "scope": "Always active · All Copywriter tasks",
        "applies_to": "global",
        "always_active": True,
        "description": "Complete bilingual CX writing guidance and English–Arabic glossary shared by every Copywriter task.",
    },
    "00_MASTER_INSTRUCTIONS": {
        "filename": "00_MASTER_INSTRUCTIONS.md",
        "name": "AI Writing Rules — Instruction Priority and Fact Validation",
        "scope": "Always active",
        "applies_to": "global",
        "description": "Precedence, routing, factual safeguards and validation.",
    },
    "01_BRAND_RULES": {
        "filename": "01_BRAND_RULES.md",
        "name": "Brand Style — Naming, Grammar and Formatting",
        "scope": "Always active · All Copywriter tasks",
        "applies_to": "global",
        "always_active": True,
        "description": "Brand naming, writing mechanics, UK English, currency, dates, CTAs, punctuation and formatting.",
    },
    "02_WEBSITE_CONTENT_INSTRUCTIONS": {
        "filename": "02_WEBSITE_CONTENT_INSTRUCTIONS.md",
        "name": "Website Copy — Page Structure, SEO and Content Validation",
        "scope": "Website",
        "applies_to": "website",
        "description": "Tone, perspective, SEO, claims, required inputs and output rules.",
    },
    "03_WEBSITE_COMPONENT_SCHEMA": {
        "filename": "03_WEBSITE_COMPONENT_SCHEMA.md",
        "name": "Website Component Library — Fields and Character Limits",
        "scope": "Website",
        "applies_to": "website",
        "description": "Components 1–17, required fields and character limits.",
    },
    "04_GOOGLE_PAID_SEARCH_INSTRUCTIONS": {
        "filename": "04_GOOGLE_PAID_SEARCH_INSTRUCTIONS.md",
        "name": "Google Search Ads — Headlines, Descriptions and Character Limits",
        "scope": "Google Paid Search",
        "applies_to": "paid_search",
        "description": "Ad pair logic, claims, character limits and output structure.",
    },
    "05_B2B_MESSAGING_EXAMPLES": {
        "filename": "05_B2B_MESSAGING_EXAMPLES.md",
        "name": "Messaging Examples — Before, After and Arabic Copy",
        "scope": "Always active · B2B only",
        "applies_to": "global",
        "always_active": True,
        "channel_id": "b2b",
        "description": "Before, preferred English, and Arabic examples from the B2B messaging bank.",
    },
    "README": {
        "filename": "README.md",
        "name": "Instruction Library — File Roles and Routing Guide",
        "scope": "Reference only",
        "applies_to": "reference",
        "description": "Explains how the instruction modules work together.",
    },
}

DEFAULT_B2B_MODULES = [
    "00_MASTER_INSTRUCTIONS",
    "02_WEBSITE_CONTENT_INSTRUCTIONS",
    "03_WEBSITE_COMPONENT_SCHEMA",
    "04_GOOGLE_PAID_SEARCH_INSTRUCTIONS",
]

DEFAULT_DATA = {
    "channels": [
        {"id": "b2b", "name": "B2B", "instruction_modules": DEFAULT_B2B_MODULES},
        {"id": "b2c", "name": "B2C", "instruction_modules": []},
        {"id": "security", "name": "Regulatory Compliance", "instruction_modules": []},
    ],
    "users": [{"email": "developer@eand.ae", "username": "developer", "name": "Development Team", "role": "super_admin", "channel_id": None, "workspaces": DEFAULT_WORKSPACES, "auth_source": "developer_backup"}],
    "activity": [],
    "approval_batches": [],
    "notifications": [],
}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def channel_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise HTTPException(status_code=422, detail="Channel name must contain letters or numbers.")
    return slug


def load_access_data() -> dict:
    if oracle_enabled():
        from oracle_runtime import load_access
        return load_access()
    with DATA_LOCK:
        if not DATA_FILE.exists():
            DATA_FILE.write_text(json.dumps(DEFAULT_DATA, indent=2), encoding="utf-8")
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        changed = False
        if not any(item["id"] == "security" for item in data["channels"]):
            data["channels"].append({"id": "security", "name": "Regulatory Compliance", "instruction_modules": []})
            changed = True
        for channel in data["channels"]:
            if channel["id"] == "consumer":
                channel.update({"id": "b2c", "name": "B2C"})
                changed = True
            if "instruction_modules" not in channel:
                channel["instruction_modules"] = DEFAULT_B2B_MODULES.copy() if channel["id"] == "b2b" else []
                changed = True
        if "activity" not in data:
            data["activity"] = []
            changed = True
        if "approval_batches" not in data:
            data["approval_batches"] = []
            changed = True
        from archive_names import ensure_archive_names
        for batch in data['approval_batches']:
            if ensure_archive_names(batch): changed = True
        if "notifications" not in data:
            data["notifications"] = []
            changed = True
        for user in data["users"]:
            if user.get("channel_id") == "consumer":
                user["channel_id"] = "b2c"
                changed = True
            if user["email"] == "consumer.admin@eand.ae":
                user.update({"email": "b2c.admin@eand.ae", "name": "B2C Team Admin"})
                changed = True
            valid_workspaces = [item for item in user.get("workspaces", DEFAULT_WORKSPACES) if item in WORKSPACES]
            if user.get("workspaces") != valid_workspaces:
                user["workspaces"] = valid_workspaces
                changed = True
        if changed:
            DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return data


def save_access_data(data: dict) -> None:
    if oracle_enabled():
        from oracle_runtime import save_access
        save_access(data)
        return
    with DATA_LOCK:
        DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_user(email: str) -> dict | None:
    normalized = _normalize_email(email)
    return next((user for user in load_access_data()["users"] if user["email"] == normalized and user.get("active", True)), None)


def public_user(user: dict) -> dict:
    return {key: value for key, value in user.items() if key != "password_hash"}


def current_user(x_user_email: str = Header(default="", alias="X-User-Email"), authorization: str = Header(default='', alias='Authorization')) -> dict:
    from directory_auth import enabled, verify_token
    if enabled():
        if not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail='Sign in with your directory account.')
        identity = verify_token(authorization[7:])
        user = get_user(identity['email'])
        if not user or user.get('directory_id') != identity['directory_id']:
            raise HTTPException(status_code=401, detail='This directory identity is not assigned access.')
        return user
    user = get_user(x_user_email)
    if not user:
        raise HTTPException(status_code=401, detail="This account has not been assigned access.")
    from directory_auth import _boolean
    if user.get('auth_source') in {'ldap', 'developer_backup'} and (user.get('auth_source') == 'ldap' or not _boolean('DEVELOPER_MODE')):
        raise HTTPException(401, 'Use the corporate directory or explicitly enable developer mode for the backup account.')
    return user


def require_role(user: dict, *roles: str) -> None:
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")


def require_content_access(user: dict) -> None:
    if user['role'] == 'super_admin':
        raise HTTPException(status_code=403, detail='Other users’ channel content and administrative review controls are private to the channel. Super admins retain access to their own writing workspace.')


def channel_content_user(user: dict = Depends(current_user)):
    require_content_access(user)
    return user


def platform_channel(channel):
    return {key: channel[key] for key in ('id', 'name', 'created_at', 'bulk_file_limit') if key in channel}


def available_channels(user: dict, data: dict | None = None) -> list[dict]:
    data = data or load_access_data()
    if user["role"] == "super_admin":
        return [platform_channel(channel) for channel in data["channels"] if not channel.get("deleted_at")]
    return [channel for channel in data["channels"] if channel["id"] == user.get("channel_id") and not channel.get("deleted_at")]


def require_channel_access(user: dict, channel_id: str) -> dict:
    data = load_access_data()
    channel = next((item for item in data["channels"] if item["id"] == channel_id and not item.get("deleted_at")), None)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel was not found.")
    if user["role"] != "super_admin" and user.get("channel_id") != channel_id:
        raise HTTPException(status_code=403, detail="You do not have access to this channel.")
    return channel


def require_workspace_access(user: dict, workspace: str) -> None:
    if workspace not in WORKSPACES:
        raise HTTPException(status_code=422, detail="Unknown workspace.")
    if user['role'] != 'super_admin' and workspace not in user.get("workspaces", DEFAULT_WORKSPACES):
        label = "Harf"
        raise HTTPException(status_code=403, detail=f"Your account does not have access to {label}.")


def prompt_path(channel_id: str) -> Path:
    if channel_id == 'cx-comms':
        return instruction_path('CX_COMMS_SYSTEM', channel_id)
    if has_three_file_pack(channel_id):
        return instruction_path("B2B_SYSTEM" if channel_id == "b2b" else "CHANNEL_SYSTEM", channel_id)
    if channel_id == "b2c":
        return instruction_path("B2C_SYSTEM", channel_id)
    if channel_id == "security":
        return instruction_path("SECURITY_POLICY", channel_id)
    safe_id = channel_slug(channel_id)
    path = CHANNEL_PROMPT_DIR / f"{safe_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="This channel does not have a prompt file.")
    return path


def has_three_file_pack(channel_id: str) -> bool:
    filename = "01_CX_COMMS_SYSTEM_INSTRUCTIONS.md" if channel_id == 'cx-comms' else "01_B2B_SYSTEM_INSTRUCTIONS.md" if channel_id == "b2b" else "01_SYSTEM_INSTRUCTIONS.md"
    return channel_id not in {"b2c", "security"} and (CHANNEL_PROMPT_DIR / channel_slug(channel_id) / filename).exists()


def instruction_path(module_id: str, channel_id: str | None = None) -> Path:
    module = INSTRUCTION_MODULES.get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Instruction module was not found.")
    if channel_id and oracle_enabled():
        from oracle_runtime import cache_instruction
        cached = cache_instruction(channel_id, module_id)
        if cached is not None:
            return cached
    path = COMPLETE_CX_GUIDE_FILE if module_id == "CX_WRITING_COMPLETE_GUIDE" else INSTRUCTION_PACK_DIR / module["filename"]
    if channel_id:
        override = CHANNEL_PROMPT_DIR / channel_slug(channel_id) / module["filename"]
        if override.exists():
            return override
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{module['filename']} has not been added yet.")
    return path


def used_instruction_ids(channel_id: str) -> list[str]:
    if channel_id == 'cx-comms':
        return ['CX_COMMS_SYSTEM', 'CX_COMMS_TEMPLATES', 'CX_COMMS_USER_GUIDE']
    if has_three_file_pack(channel_id):
        return (["B2B_SYSTEM", "B2B_TEMPLATES", "B2B_USER_GUIDE"] if channel_id == "b2b"
                else ["CHANNEL_SYSTEM", "CHANNEL_TEMPLATES", "CHANNEL_USER_ADMIN_GUIDE"])
    if channel_id == "b2c":
        return ["B2C_SYSTEM", "B2C_TEMPLATES", "B2C_USER_GUIDE"]
    if channel_id == "security":
        return ["SECURITY_POLICY", "SECURITY_MEMO", "SECURITY_USER_GUIDE"]
    if channel_id not in {"b2b", "b2c", "security"}:
        return ["CHANNEL_TEMPLATE_GUIDE", "CHANNEL_USER_GUIDE"]
    enabled = set(enabled_instruction_ids(channel_id))
    return [key for key, module in INSTRUCTION_MODULES.items()
            if key not in {"B2B_SYSTEM", "B2B_TEMPLATES", "B2B_USER_GUIDE"}
            and not module.get("custom_channel_only") and (channel_id != "security" or module.get("channel_id") == "security")
            and (not module.get("channel_id") or module["channel_id"] == channel_id)
            and module["applies_to"] != "reference"
            and (module.get("always_active") or key in enabled)]


def has_website_components(channel_id: str) -> bool:
    return channel_id == "b2b" and (has_three_file_pack(channel_id) or "03_WEBSITE_COMPONENT_SCHEMA" in enabled_instruction_ids(channel_id))


def enabled_instruction_ids(channel_id: str, data: dict | None = None) -> list[str]:
    data = data or load_access_data()
    channel = next((item for item in data["channels"] if item["id"] == channel_id and not item.get("deleted_at")), None)
    return list(channel.get("instruction_modules", [])) if channel else []


def instruction_bundle(channel_id: str, content_channel: str | None = None, query: str = "") -> dict:
    """Resolve authorised channel modules before search; keep rules, rank optional examples."""
    from structure_retrieval import select_instructions, indexed_file
    import time
    started = time.perf_counter()
    normalized = (content_channel or "").strip().lower()
    if channel_id == "b2b" and normalized in {"", "other"} and re.search(
        r"\bcomponent\s*(?:number|no)?\s*#?\s*\d+\b|(?:المكوّن|المكون|مكوّن|مكون)\s*(?:رقم\s*)?\d+", query, re.IGNORECASE,
    ):
        normalized = "website"
    scope = "paid_search" if normalized == "google paid search" else "website" if normalized == "website" else None
    paths = [] if channel_id in {"b2c", "security"} or has_three_file_pack(channel_id) else [("channel_foundation", prompt_path(channel_id))]
    for module_id in used_instruction_ids(channel_id):
        module = INSTRUCTION_MODULES[module_id]
        if module["applies_to"] in {"global", scope}:
            paths.append((module_id, instruction_path(module_id, channel_id)))
    if channel_id == "b2b":
        # General rules precede the more specific website/ads guide. Examples are never authority.
        priority = {name: position for position, name in enumerate([
            "CX_WRITING_COMPLETE_GUIDE", "channel_foundation", "00_MASTER_INSTRUCTIONS",
            "01_BRAND_RULES", "B2B_BRAND_DICTIONARY", "05_B2B_MESSAGING_EXAMPLES",
            "02_WEBSITE_CONTENT_INSTRUCTIONS", "03_WEBSITE_COMPONENT_SCHEMA",
            "04_GOOGLE_PAID_SEARCH_INSTRUCTIONS", "B2B_WEBSITE_TOV",
        ])}
        paths.sort(key=lambda item: priority.get(item[0], -1))
    texts, reports = [], []
    for module_id, path in paths:
        def retrieve(selection_query):
            if module_id == "B2B_TEMPLATES":
                from structure_retrieval import select_b2b_templates
                return select_b2b_templates(path, selection_query, scope or "messaging")
            if module_id == "B2B_SYSTEM":
                return select_instructions(path, selection_query, references=True, glossary=True)
            if module_id in {"B2C_TEMPLATES", "CX_COMMS_TEMPLATES"}:
                from structure_retrieval import select_b2c_templates
                return select_b2c_templates(path, selection_query, content_channel)
            if selection_query or module["applies_to"] == 'global':
                return select_instructions(path, selection_query, examples=module_id in {"05_B2B_MESSAGING_EXAMPLES", "B2C_TEMPLATES"}, references=module_id == "CX_WRITING_COMPLETE_GUIDE")
            index, hit = indexed_file(path)
            text = index["text"]
            return text, {"filename": path.name, "version": index["version"], "cache_hit": hit,
                          "original_characters": len(text), "selected_characters": len(text), "sections": []}

        from generation_context import current_generation
        context = current_generation()
        format_modules = {"B2B_TEMPLATES", "B2C_TEMPLATES", "CX_COMMS_TEMPLATES", "SECURITY_MEMO", "CHANNEL_TEMPLATES", "CHANNEL_TEMPLATE_GUIDE"}
        shared = (module_id not in format_modules and
                  (module_id == "channel_foundation" or INSTRUCTION_MODULES[module_id]["applies_to"] == "global"))
        if context is not None and context.channel == channel_id:
            text, report = context.select(module_id, path, scope or normalized, query, shared, retrieve)
        else:
            text, report = retrieve(query)
        texts.append(text.strip())
        reports.append({"module": module_id, **report})
    return {"text": "\n\n---\n\n".join(texts), "files": reports,
            "original_characters": sum(item["original_characters"] for item in reports),
            "selected_characters": sum(item["selected_characters"] for item in reports),
            "retrieval_ms": round((time.perf_counter() - started) * 1000, 2)}


def instruction_text_for(channel_id: str, content_channel: str | None = None, query: str = "") -> str:
    return instruction_bundle(channel_id, content_channel, query)["text"]


def record_activity(
    data: dict, actor: dict, action: str, detail: str, channel_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor["name"],
        "actor_email": actor["email"],
        "actor_id": actor.get('directory_id') or 'local:' + actor['email'].casefold(),
        "action": action,
        "detail": detail,
        "channel_id": channel_id,
    }
    if metadata:
        event["metadata"] = metadata
    from channel_performance import record_generation
    record_generation(data, event)
    data.setdefault("activity", []).insert(0, event)
    data["activity"] = data["activity"][:1000]
