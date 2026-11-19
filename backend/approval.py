from datetime import datetime, timezone
from functools import wraps
from typing import Literal
from uuid import uuid4
from copy import deepcopy
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    current_user,
    DATA_LOCK,
    load_access_data,
    record_activity,
    require_channel_access,
    require_role,
    require_workspace_access,
    save_access_data,
)
from ai_service import enhance_bilingual_feedback, enhance_feedback
from generation_context import generation_request, current_generation, bind_generation
from request_limits import monthly_request
from archive_names import ensure_archive_names
from component_set_review import review_component_sets
from approval_policy import final_layer


router = APIRouter(prefix="/api", tags=["bulk-copy", "approvals"])
_GENERATION_SLOTS = BoundedSemaphore(2)


def _visible_batch(batch, user):
    """Keep review evidence and user requests, never disclose private AI rules."""
    if user['role'] != 'approval_admin':
        return batch
    result = deepcopy(batch)
    for item in result.get('items', []):
        item.pop('format_instructions', None)
        if 'generation_instructions' in item:
            item['generation_instructions'] = result.get('instructions', '')
    return result


def serialized_approval(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with DATA_LOCK:
            return function(*args, **kwargs)
    return wrapped


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BulkItem(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    text: str = Field(min_length=1, max_length=2000000)
    size_bytes: int = Field(default=0, ge=0)
    content_type: str = Field(default="", max_length=120)
    source_language: Literal['', 'en', 'ar'] = ''
    source_id: str = Field(default='', max_length=200000)
    source_metadata: dict[str, str] = Field(default_factory=dict, max_length=83)
    row_instructions: str = Field(default='', max_length=4000)


class BulkGenerateRequest(BaseModel):
    output_ids: list[str] = Field(default_factory=list, max_length=100)
    task: Literal["write", "improve", "review", "translate"] = "improve"
    items: list[BulkItem] = Field(min_length=1, max_length=100)
    channel: str = Field(default="Other", max_length=120)
    audience: str = Field(default="Unknown", max_length=120)
    product_type: str = Field(default="", max_length=160)
    team_channel: str = "b2b"
    instructions: str = Field(default="", max_length=4000)
    languages: list[Literal["en", "ar"]] = Field(default_factory=lambda: ["en", "ar"], min_length=1, max_length=2)
    preserve_source_languages: bool = False
    urgent: bool = False
    title: str = Field(default="", max_length=160)


class MoveRequest(BaseModel):
    note: str = Field(default="", max_length=2000)
    urgent: bool = False


class SavedCopyRequest(BaseModel):
    team_channel: str
    source: str = Field(max_length=2000000)
    filename: str = Field(default="Generated copy", max_length=240)
    english: str = Field(default="", max_length=200000)
    arabic: str = Field(default="", max_length=200000)
    product_type: str = Field(default="", max_length=160)
    scores: dict[Literal["en", "ar"], int] = Field(default_factory=dict)
    instructions: str = Field(default="", max_length=4000)
    task: Literal["write", "improve", "review", "translate"] = "improve"
    content_channel: str = Field(default="Other", max_length=120)
    audience: str = Field(default="Unknown", max_length=120)
    versions: dict[Literal["en", "ar", "original"], int] = Field(default_factory=dict)


@router.post("/approvals/draft")
@serialized_approval
def save_single_copy(request: SavedCopyRequest, user: dict = Depends(current_user)):
    require_channel_access(user, request.team_channel)
    require_workspace_access(user, "rewrite")
    generated = {lang: text for lang, text in [("en", request.english), ("ar", request.arabic)] if text.strip()}
    if not generated:
        raise HTTPException(status_code=422, detail="Generate copy before submitting it.")
    now = utc_now()
    batch = {"id": uuid4().hex, "title": request.filename, "channel_id": request.team_channel, "content_channel": "Compliance memo" if request.team_channel == "security" else "Single copy", "audience": "Internal" if request.team_channel == "security" else "Unknown", "languages": list(generated), "urgent": False, "status": "draft", "current_layer": 0, "progress": 0, "created_by": user["name"], "created_by_email": user["email"], "created_at": now, "updated_at": now, "submitted_at": None, "completed_at": None, "events": [], "items": [{"id": uuid4().hex, "filename": request.filename, "source": request.source, "source_details": {"words": len(request.source.split()), "characters": len(request.source)}, "generated": generated, "generated_details": {lang: {"words": len(text.split()), "characters": len(text)} for lang, text in generated.items()}}]}
    for language, score in request.scores.items():
        if language in generated and 0 <= score <= 100:
            batch["items"][0]["generated_details"][language]["score"] = score
    batch["created_by_id"] = user.get("directory_id") or "local:" + user["email"].casefold()
    batch.update(instructions=request.instructions, task=request.task, content_channel=request.content_channel, audience=request.audience)
    from inference import attribution
    batch.update(attribution())
    batch["product_type"] = request.product_type
    batch["items"][0]["initial_versions"] = {key: max(1, min(value, 1000000)) for key, value in request.versions.items()}
    _event(batch, user, "saved", "Saved generated copy for approval")
    ensure_archive_names(batch)
    data = load_access_data()
    data.setdefault("approval_batches", []).insert(0, batch)
    record_activity(data, user, "Copy saved for approval", request.filename, request.team_channel, {"batch_id": batch["id"]})
    save_access_data(data)
    return _visible_batch(batch, user)


class DecisionRequest(BaseModel):
    expected_layer: int | None = Field(default=None, strict=True, ge=1, le=3)
    expected_round: str | None = Field(default=None, min_length=1, max_length=64)
    language: Literal["en", "ar"] | None = None
    action: Literal["approve", "reject", "return_to_user", "return_to_layer_1", "note"]
    note: str = Field(default="", max_length=2000)


class AdminActionRequest(BaseModel):
    action: Literal["override_approve", "reject", "return_to_user", "urgent", "note", "warning"]
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/approvals/{batch_id}/admin-action")
@serialized_approval
def admin_action(batch_id: str, request: AdminActionRequest, user: dict = Depends(current_user)):
    data = load_access_data()
    batch = _batch_for(data, batch_id)
    if user["role"] != 'channel_admin' or not _can_view(user, batch):
        raise HTTPException(status_code=403, detail="Only this channel's administrator or a super admin can take this action.")
    reason = request.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A reason is required for every administrator action.")
    pending = batch.get("status", "").startswith("pending_layer_")
    if request.action in {"override_approve", "reject", "return_to_user", "urgent"} and not pending:
        raise HTTPException(status_code=409, detail="This action requires a batch awaiting approval. Refresh its status.")
    prior_layer = batch.get("current_layer", 0)
    now = utc_now()
    action = "admin_" + request.action
    if request.action == "override_approve":
        batch.update(status="approved", progress=100, completed_at=now,
                     approval_method="administrator_override")
        title = "Copy approved by administrator override"
    elif request.action == "reject":
        batch.update(status="rejected", completed_at=now)
        title = "Copy rejected by administrator"
    elif request.action == "return_to_user":
        batch.update(status="returned_to_user", current_layer=0, progress=0, completed_at=None)
        title = "Copy returned for changes"
    elif request.action == "urgent":
        batch["urgent"] = True
        title = "Urgent approval requested"
    else:
        title = "Administrator warning" if request.action == "warning" else "Administrator note"
    batch["updated_at"] = now
    _event(batch, user, action, reason, prior_layer, batch.get("current_layer"))
    recipients = [batch["created_by_email"]] + _admin_recipients(data, batch["channel_id"]) + _all_approval_recipients(data, batch["channel_id"])
    _notify(data, recipients, title, f"{batch['title']} — {user['name']}: {reason}", batch, action)
    record_activity(data, user, title, reason, batch["channel_id"], {
        "batch_id": batch_id, "decision": action, "reason": reason,
        "from_layer": prior_layer, "status": batch["status"],
        "approval_method": batch.get("approval_method", "normal_review"),
    })
    save_access_data(data)
    return _visible_batch(batch, user)


class RevisionRequest(BaseModel):
    item_id: str
    language: Literal["en", "ar"]
    text: str = Field(min_length=1, max_length=200000)
    change_request: str = Field(default="", max_length=2000)


@router.put("/approvals/{batch_id}/copy")
@serialized_approval
def revise_copy(batch_id: str, request: RevisionRequest, user: dict = Depends(current_user)):
    require_workspace_access(user, "rewrite")
    data = load_access_data()
    batch = _batch_for(data, batch_id)
    require_channel_access(user, batch["channel_id"])
    if batch["created_by_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Only the original author can revise the copy.")
    if batch["status"] not in {"draft", "returned_to_user", "rejected"}:
        raise HTTPException(status_code=409, detail="Copy cannot change while it is under review or approved.")
    item = next((entry for entry in batch["items"] if entry["id"] == request.item_id), None)
    if not item or request.language not in item["generated"]:
        raise HTTPException(status_code=404, detail="Output was not found.")
    item.setdefault("versions", []).append({"language": request.language, "text": item["generated"][request.language], "timestamp": utc_now()})
    item["generated"][request.language] = request.text
    item["generated_details"][request.language] = {"characters": len(request.text), "words": len(request.text.split())}
    for check in batch.get('component_set_checks', []):
        if item['id'] in check.get('item_ids', []):
            check['stale'] = True
    batch["updated_at"] = utc_now()
    if request.change_request:
        item.setdefault("revision_requests", []).append({"language": request.language, "instructions": request.change_request, "timestamp": batch["updated_at"], "actor": user["email"]})
    _event(batch, user, "copy_revised", f'{item["filename"]} — {request.change_request}' if request.change_request else item["filename"])
    record_activity(data, user, "Copy revised", item["filename"], batch["channel_id"], {
        "batch_id": batch_id, "language": request.language, "filename": item["filename"],
        "source": item.get("source", ""), "generated": {request.language: request.text},
        "instructions": request.change_request, "task": "Revise", "content_channel": batch.get("content_channel", ""),
        "product_type": batch.get("product_type", ""), "audience": batch.get("audience", ""),
    })
    save_access_data(data)
    return _visible_batch(batch, user)


def _batch_for(data: dict, batch_id: str) -> dict:
    batch = next((item for item in data.get("approval_batches", []) if item["id"] == batch_id), None)
    if not batch:
        raise HTTPException(status_code=404, detail="Approval batch was not found.")
    return batch


def _can_view(user: dict, batch: dict) -> bool:
    if user["role"] == "super_admin":
        return user['email'] == batch.get('created_by_email')
    if user.get("channel_id") != batch.get("channel_id"):
        return False
    if user["role"] in {"channel_admin", "approval_admin"}:
        return True
    return user["email"] == batch.get("created_by_email")


def _notify(data: dict, recipients: list[str], title: str, message: str, batch: dict, kind: str) -> None:
    allowed = {item['email'] for item in data['users'] if item.get('active', True) and (item['role'] != 'super_admin' or item['email'] == batch.get('created_by_email'))}
    for recipient in dict.fromkeys(recipients):
        if not recipient or recipient not in allowed:
            continue
        data.setdefault("notifications", []).insert(0, {
            "id": uuid4().hex,
            "recipient_email": recipient,
            "title": title,
            "message": message,
            "kind": kind,
            "batch_id": batch["id"],
            "channel_id": batch["channel_id"],
            "urgent": batch.get("urgent", False),
            "created_at": utc_now(),
            "read": False,
        })
    data["notifications"] = data.get("notifications", [])[:2000]


def _layer_recipients(data: dict, channel_id: str, layer: int, languages: list[str] | None = None) -> list[str]:
    return [
        item["email"] for item in data["users"]
        if item.get("active", True)
        and item.get("channel_id") == channel_id
        and item.get("role") == "approval_admin"
        and item.get("approval_layer") == layer
        and (not languages or set(item.get("review_languages", ["en", "ar"])) & set(languages))
    ]


def _admin_recipients(data: dict, channel_id: str) -> list[str]:
    return [
        item["email"] for item in data["users"]
        if item.get("active", True) and item.get("role") == "channel_admin" and item.get("channel_id") == channel_id
    ]


def _all_approval_recipients(data: dict, channel_id: str) -> list[str]:
    return [
        item["email"] for item in data["users"]
        if item.get("active", True) and item.get("role") == "approval_admin" and item.get("channel_id") == channel_id
    ]


def _event(batch: dict, user: dict, action: str, note: str = "", from_layer: int | None = None, to_layer: int | None = None) -> None:
    batch.setdefault("events", []).append({
        "id": uuid4().hex,
        "action": action,
        "note": note.strip(),
        "actor": user["name"],
        "actor_email": user["email"],
        "actor_role": user["role"],
        "from_layer": from_layer,
        "to_layer": to_layer,
        "timestamp": utc_now(),
    })


@router.post("/bulk/generate")
@monthly_request
@generation_request
def bulk_generate(request: BulkGenerateRequest, user: dict = Depends(current_user)):
    from bulk_limits import channel_bulk_limit
    capacity = channel_bulk_limit(require_channel_access(user, request.team_channel))
    require_workspace_access(user, "rewrite")
    outputs = []
    from copywriter import output_catalog
    catalog = {item['id']: item for item in output_catalog(request.team_channel)}
    selections = list(dict.fromkeys(request.output_ids))
    if any(key not in catalog for key in selections):
        raise HTTPException(status_code=422, detail="A selected component or template is not available for this channel.")
    if len(request.items) * max(1, len(selections)) > capacity:
        raise HTTPException(status_code=422, detail=f"This channel allows {capacity} file/format combinations per batch. Select fewer files or formats, or ask an administrator to increase the bulk limit. English and Arabic share one combination.")
    languages = list(dict.fromkeys(request.languages))
    contextual_instructions = request.instructions.strip()
    if request.product_type:
        contextual_instructions = f"{contextual_instructions}\nProduct type: {request.product_type}".strip()
    jobs = [(source, catalog[key] if key else None) for source in request.items for key in (selections or [None])]
    instruction_context = current_generation()
    def generate_pair(pair):
        source, selection = pair
        with _GENERATION_SLOTS, bind_generation(instruction_context):
            item_instructions = contextual_instructions
            if source.row_instructions:
                item_instructions += '\nAdditional instructions for this row:\n' + source.row_instructions
            if source.source_metadata:
                item_instructions += '\nPreserve all dynamic placeholders in the source exactly, including spelling, case and delimiters. Operational identifiers are metadata, not customer content.'
            if selection:
                item_instructions = f"Selected output: {selection['name']}. Generate ONLY this selected format; ignore other component/template requests in the source.\n{item_instructions}\nSelected format rules:\n{selection['instructions']}"
            output_languages = [source.source_language] if request.preserve_source_languages and source.source_language else languages
            if len(output_languages) == 2:
                result = enhance_bilingual_feedback(
                    source.text, request.task, request.channel, request.audience,
                    request.team_channel, item_instructions,
                )
                generated = {"en": result["english"], "ar": result["arabic"]}
            else:
                language = output_languages[0]
                generated = {language: enhance_feedback(
                    source.text, request.task, request.channel, request.audience,
                    request.team_channel, item_instructions, language,
                )}
            return {
                "id": uuid4().hex,
                "filename": f"{source.filename} — {selection['name']}" if selection else source.filename,
                "generation_instructions": item_instructions,
                "format_instructions": selection["instructions"] if selection else "",
                "output_id": selection['id'] if selection else None,
                "output_name": selection['name'] if selection else source.filename,
                "source_filename": source.filename,
                "source": source.text,
                "source_language": source.source_language,
                "source_id": source.source_id,
                "source_metadata": source.source_metadata,
                "source_details": {
                    "characters": len(source.text),
                    "words": len(source.text.split()),
                    "size_bytes": source.size_bytes,
                    "content_type": source.content_type,
                },
                "generated": generated,
                "generated_details": {
                    language: {"characters": len(text), "words": len(text.split())}
                    for language, text in generated.items()
                },
            }
    try:
        if request.team_channel == 'b2b' and len(jobs) > 1:
            pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='copy-component')
            try:
                futures = [pool.submit(generate_pair, pair) for pair in jobs]
                # Render/save in the user's selected order even when completion order differs.
                for (source, selection), future in zip(jobs, futures):
                    outputs.append(future.result())
            finally:
                pool.shutdown(wait=True, cancel_futures=True)
        else:
            for source, selection in jobs:
                outputs.append(generate_pair((source, selection)))
    except Exception as error:
        import traceback
        from stream_errors import stream_error_details
        details = stream_error_details(error)
        reference = uuid4().hex[:12]
        frames = traceback.extract_tb(error.__traceback__)
        stage = f'{frames[-1].name}:{frames[-1].lineno}' if frames else 'unknown'
        logging.getLogger(__name__).warning(
            'Bulk generation failed reference=%s type=%s code=%s output_id=%s completed=%s stage=%s',
            reference, type(error).__name__, details['code'], selection['id'] if selection else None, len(outputs), stage,
        )
        message = getattr(error, 'public_message', None) or details['message']
        if selection:
            message = f'{selection["name"]}: {message}'
        status = 422 if details['code'] == 'component_validation_failed' else 413 if details['code'] == 'input_token_limit' else 429 if details['code'] == 'rate_limit_exceeded' else 502
        raise HTTPException(status_code=status, detail=f'{message} (Reference: {reference})') from error

    now = utc_now()
    batch = {
        "id": uuid4().hex,
        "title": request.title.strip() or f"{len(outputs)}-file copy batch",
        "channel_id": request.team_channel,
        "content_channel": request.channel,
        "audience": request.audience,
        "product_type": request.product_type,
        "instructions": request.instructions,
        "task": request.task,
        "languages": list(dict.fromkeys(language for item in outputs for language in item['generated'])) if request.preserve_source_languages else languages,
        "urgent": request.urgent,
        "status": "draft",
        "current_layer": 0,
        "progress": 0,
        "created_by": user["name"],
        "created_by_email": user["email"],
        "created_by_id": user.get("directory_id") or "local:" + user["email"].casefold(),
        "created_at": now,
        "updated_at": now,
        "submitted_at": None,
        "completed_at": None,
        "items": outputs,
        "component_set_checks": review_component_sets(request, jobs, outputs),
        "events": [],
    }
    from inference import attribution
    batch.update(attribution())
    _event(batch, user, "generated", f"Generated {len(outputs)} personalised file copies.", None, 0)
    ensure_archive_names(batch)
    with DATA_LOCK:
        data = load_access_data()
        data.setdefault("approval_batches", []).insert(0, batch)
        record_activity(data, user, "Bulk copy generated", f"Generated {len(outputs)} files in {batch['title']}.", request.team_channel, {
            "batch_id": batch["id"], "status": "draft", "files": [item["filename"] for item in outputs],
            "file_count": len(outputs), "content_channel": request.channel, "audience": request.audience,
            "product_type": request.product_type, "urgent": request.urgent,
        })
        save_access_data(data)
    return _visible_batch(batch, user)


@router.get("/approvals")
def approvals(channel_id: str | None = None, summary: bool = False, submitted_only: bool = False, user: dict = Depends(current_user)):
    data = load_access_data()
    batches = [item for item in data.get("approval_batches", []) if _can_view(user, item)]
    if submitted_only:
        batches = [item for item in batches if item.get('status') != 'draft']
    if channel_id:
        require_channel_access(user, channel_id)
        batches = [item for item in batches if item["channel_id"] == channel_id]
    if summary:
        return {'batches': [{**{key: value for key, value in batch.items() if key not in {'items', 'events', 'instructions'}},
                             'items': [], 'events': [], 'summary': True} for batch in batches]}
    return dict(batches=[_visible_batch(batch, user) for batch in batches])


@router.get("/approvals/{batch_id}")
def approval_detail(batch_id: str, user: dict = Depends(current_user)):
    data = load_access_data()
    batch = _batch_for(data, batch_id)
    if not _can_view(user, batch):
        raise HTTPException(status_code=403, detail="You do not have access to this approval batch.")
    return _visible_batch(batch, user)


@router.post("/approvals/{batch_id}/move")
@serialized_approval
def move_to_approval(batch_id: str, request: MoveRequest, user: dict = Depends(current_user)):
    data = load_access_data()
    batch = _batch_for(data, batch_id)
    if not _can_view(user, batch) or (user["email"] != batch["created_by_email"] and user["role"] not in {"super_admin", "channel_admin"}):
        raise HTTPException(status_code=403, detail="Only the original user or a channel administrator can submit this batch.")
    if batch["status"] not in {"draft", "returned_to_user", "rejected"}:
        raise HTTPException(status_code=409, detail="This batch is already in the approval process.")
    channel = next(item for item in data['channels'] if item['id'] == batch['channel_id'])
    batch['final_approval_layer'] = final_layer(channel)
    batch.update({
        "status": "pending_layer_1", "current_layer": 1, "progress": 0,
        "urgent": request.urgent or batch.get("urgent", False), "updated_at": utc_now(),
        "submitted_at": utc_now(), "completed_at": None,
        "approval_round": uuid4().hex,
    })
    batch["language_approvals"] = {}
    batch.pop("approval_method", None)
    _event(batch, user, "submitted", request.note, 0, 1)
    prefix = "URGENT: " if batch["urgent"] else ""
    _notify(data, _layer_recipients(data, batch["channel_id"], 1, batch["languages"]) + _admin_recipients(data, batch["channel_id"]), f"{prefix}Layer 1 approval requested", f"{batch['title']} is ready for review.", batch, "approval_request")
    record_activity(data, user, "Moved to approval", f"Submitted {batch['title']} to approval layer 1.", batch["channel_id"], {
        "batch_id": batch["id"], "status": batch["status"], "file_count": len(batch["items"]), "urgent": batch["urgent"],
    })
    save_access_data(data)
    return _visible_batch(batch, user)


@router.post("/approvals/{batch_id}/decision")
@serialized_approval
def approval_decision(batch_id: str, request: DecisionRequest, user: dict = Depends(current_user)):
    require_role(user, 'channel_admin', 'approval_admin')
    data = load_access_data()
    batch = _batch_for(data, batch_id)
    layer = int(batch.get("current_layer") or 0)
    if request.expected_layer is not None and request.expected_layer != layer:
        raise HTTPException(status_code=409, detail='This request has already moved to another layer. Refresh its status before acting.')
    last_layer = final_layer(batch)
    if layer not in {1, 2, 3} or batch.get("status") != f"pending_layer_{layer}":
        raise HTTPException(status_code=409, detail="This batch is not waiting for an approval decision.")
    permitted = (user["role"] == "channel_admin" and user.get("channel_id") == batch["channel_id"]) or (
        user["role"] == "approval_admin"
        and user.get("channel_id") == batch["channel_id"]
        and user.get("approval_layer") == layer
    )
    if not permitted:
        raise HTTPException(status_code=403, detail=f"This decision must be made by approval layer {layer}.")
    if request.expected_round is not None and request.expected_round != batch.get('approval_round'):
        raise HTTPException(status_code=409, detail='This copy was returned or resubmitted since you opened it. Refresh before reviewing the current approval round.')
    if request.action in {'reject', 'return_to_user', 'return_to_layer_1', 'note'} and not request.note.strip():
        raise HTTPException(status_code=422, detail='A note is required when rejecting, returning or adding a review note.')
    if request.action == "return_to_layer_1" and layer == 1:
        raise HTTPException(status_code=422, detail="Layer 1 cannot return a batch to itself.")

    required_languages = set(batch.get("languages", []))
    assigned = set(user.get("review_languages", ["en", "ar"])) if user["role"] == "approval_admin" else {"en", "ar"}
    selected_languages = {request.language} if request.language else required_languages & assigned
    if not selected_languages or not selected_languages <= (required_languages & assigned):
        raise HTTPException(status_code=403, detail="You can only review outputs in your assigned language.")
    prior_layer = layer
    if request.action == "note":
        if not request.note.strip():
            raise HTTPException(status_code=422, detail="Enter a note before saving it.")
        _event(batch, user, "note_added", request.note, layer, layer)
        batch["updated_at"] = utc_now()
        _notify(data, [batch["created_by_email"]], "Approval note added", request.note, batch, "note")
    elif request.action == "approve":
        approvals = batch.setdefault("language_approvals", {}).setdefault(str(layer), {})
        remaining = selected_languages - set(approvals)
        if not remaining:
            raise HTTPException(status_code=409, detail="Your selected language has already been approved at this layer.")
        for language in remaining:
            approvals[language] = {"actor": user["name"], "actor_email": user["email"], "timestamp": utc_now()}
        if not required_languages <= set(approvals):
            batch["updated_at"] = utc_now()
            _event(batch, user, "language_approved", request.note, layer, layer)
            batch["events"][-1]["languages"] = sorted(remaining)
            waiting = sorted(required_languages - set(approvals))
            _notify(data, _layer_recipients(data, batch["channel_id"], layer, waiting) + [batch["created_by_email"]], "Language review completed", f"{batch['title']}: awaiting {' / '.join(waiting).upper()} review at layer {layer}.", batch, "language_review")
            record_activity(data, user, "Language approved", request.note, batch["channel_id"], {"batch_id": batch_id, "languages": sorted(remaining), "awaiting_languages": waiting, "layer": layer})
            save_access_data(data)
            return _visible_batch(batch, user)
        if layer < last_layer:
            next_layer = layer + 1
            batch.update({"status": f"pending_layer_{next_layer}", "current_layer": next_layer, "progress": int(layer * 100 / last_layer), "updated_at": utc_now()})
            _event(batch, user, "approved", request.note, layer, next_layer)
            prefix = "URGENT: " if batch.get("urgent") else ""
            _notify(data, _layer_recipients(data, batch["channel_id"], next_layer, batch["languages"]) + _admin_recipients(data, batch["channel_id"]), f"{prefix}Layer {next_layer} approval requested", f"{batch['title']} passed layer {layer}. Review its full history and notes.", batch, "approval_request")
        else:
            batch.update({"status": "approved", "current_layer": layer, "progress": 100, "updated_at": utc_now(), "completed_at": utc_now()})
            _event(batch, user, "final_approved", request.note, layer, None)
            _notify(data, [batch["created_by_email"]] + _admin_recipients(data, batch["channel_id"]) + _all_approval_recipients(data, batch["channel_id"]), "Copy approved — green light", f"{batch['title']} has passed all {last_layer} required approval layer(s) and is ready to use.", batch, "final_approval")
    elif request.action == "reject":
        batch.update({"status": "rejected", "progress": max(0, int((layer - 1) * 100 / last_layer)), "updated_at": utc_now(), "completed_at": utc_now()})
        _event(batch, user, "rejected", request.note, layer, None)
        _notify(data, [batch["created_by_email"]] + _admin_recipients(data, batch["channel_id"]), "Approval rejected", f"{batch['title']} was rejected at layer {layer}. Review the note before resubmitting.", batch, "rejected")
    elif request.action == "return_to_user":
        batch.update({"status": "returned_to_user", "current_layer": 0, "progress": 0, "updated_at": utc_now(), "completed_at": None})
        _event(batch, user, "returned_to_user", request.note, layer, 0)
        _notify(data, [batch["created_by_email"]] + _admin_recipients(data, batch["channel_id"]), "Copy returned for changes", f"{batch['title']} was returned by approval layer {layer}. Review the note and resubmit when ready.", batch, "returned")
    else:
        batch["language_approvals"] = {}
        batch.update({"status": "pending_layer_1", "current_layer": 1, "progress": 0, "updated_at": utc_now(), "completed_at": None, "approval_round": uuid4().hex})
        _event(batch, user, "returned_to_layer_1", request.note, layer, 1)
        _notify(data, _layer_recipients(data, batch["channel_id"], 1, batch["languages"]) + _admin_recipients(data, batch["channel_id"]), "Approval returned to layer 1", f"{batch['title']} was returned from layer {layer}. Review the note and prior history.", batch, "returned")

    batch["events"][-1]["languages"] = sorted(selected_languages)
    record_activity(data, user, "Approval decision", f"{request.action.replace('_', ' ').title()} for {batch['title']} at layer {prior_layer}.", batch["channel_id"], {
        "batch_id": batch["id"], "decision": request.action, "note": request.note, "from_layer": prior_layer,
        "to_layer": batch.get("current_layer"), "status": batch["status"], "file_count": len(batch["items"]),
    })
    save_access_data(data)
    return _visible_batch(batch, user)


@router.get("/notifications")
def notifications(user: dict = Depends(current_user)):
    data = load_access_data()
    items = [item for item in data.get("notifications", []) if _notification_visible(user, item, data)]
    return {"notifications": items, "unread_count": sum(not item.get("read") for item in items)}


@router.post("/notifications/{notification_id}/read")
@serialized_approval
def mark_notification_read(notification_id: str, user: dict = Depends(current_user)):
    data = load_access_data()
    item = next((entry for entry in data.get("notifications", []) if entry["id"] == notification_id and _notification_visible(user, entry, data)), None)
    if not item:
        raise HTTPException(status_code=404, detail="Notification was not found.")
    item["read"] = True
    item["read_at"] = utc_now()
    save_access_data(data)
    return item


def _notification_visible(user: dict, notification: dict, data: dict) -> bool:
    if notification.get('recipient_email') != user['email']:
        return False
    if user['role'] != 'super_admin':
        return True
    return any(batch['id'] == notification.get('batch_id') and _can_view(user, batch)
               for batch in data.get('approval_batches', []))
