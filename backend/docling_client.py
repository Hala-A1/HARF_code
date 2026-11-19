"""Optional Docling Serve extraction. Native exports do not depend on this service."""
import asyncio
import os
import re
import time
import logging
from urllib.parse import quote

import httpx


class DoclingError(Exception):
    pass


class DoclingBlockedByPolicyError(DoclingError):
    pass


def enabled():
    return os.getenv("DOCLING_ENABLED", "false").lower() == "true"


def parse_result(result):
    documents = result.get("documents") or [result.get("document") or result]
    if isinstance(documents, dict):
        documents = list(documents.values())
    parts = [doc.get("md_content", "") for doc in documents if isinstance(doc, dict)]
    text = "\n\n".join(parts)
    text = re.sub(r"!\[[^\]]*\]\(data:[^)]*\)", "", text)
    text = re.sub(r'<img\b[^>]*>', '', text, flags=re.IGNORECASE)
    return text.strip()


async def extract_document(filename, content, content_type):
    from inference import confidential
    if confidential():
        # The configured Docling service is external; never upload protected bytes.
        from ai_service import extract_uploaded_content
        if filename.lower().endswith('.pdf'):
            from scan_ocr import extract_scan_if_needed, page_inventory
            from inference import resolve
            if any(scanned for _, scanned in page_inventory(content)) and not resolve()['vision']:
                raise DoclingBlockedByPolicyError('Confidential scanned PDFs require an approved on-premise image-reading model. Ask the super admin to configure one, or upload a text-based PDF. No document was sent externally.')
            scanned = await asyncio.to_thread(extract_scan_if_needed, content)
            if scanned is not None:
                return scanned
        return await asyncio.to_thread(extract_uploaded_content, filename, content_type, content)
    if filename.lower().endswith('.pdf') and os.getenv('DOCLING_DO_OCR', 'false').lower() == 'true' and os.getenv('SCAN_OCR_FALLBACK_ENABLED', 'true').lower() == 'true':
        from scan_ocr import extract_scan_if_needed, ScanOCRError
        try:
            scanned = await asyncio.to_thread(extract_scan_if_needed, content)
        except ScanOCRError as error:
            raise DoclingError(str(error)) from error
        if scanned is not None:
            return scanned
    base = os.getenv("DOCLING_BASE_URL", "").rstrip("/")
    if not base.startswith("https://"):
        raise DoclingError("Docling requires a configured HTTPS service address.")
    timeout = float(os.getenv("DOCLING_POLL_MAX_TIME_S", "180"))
    headers = {}
    if os.getenv("DOCLING_API_KEY"):
        headers["X-Api-Key"] = os.environ["DOCLING_API_KEY"]

    async def checked(response):
        if response.status_code in {401, 403}:
            raise DoclingBlockedByPolicyError("Document processing is blocked by the configured service policy. Contact your administrator.")
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as error:
            raise DoclingError("The document service did not return a valid response.") from error

    try:
        async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30,
                                     trust_env=os.getenv("DOCLING_TRUST_ENV", "true").lower() == "true") as client:
            async with asyncio.timeout(timeout):
                options = {"to_formats": "md", "do_ocr": os.getenv("DOCLING_DO_OCR", "false"),
                           "image_export_mode": "placeholder", "do_picture_description": "false"}
                if options['do_ocr'].lower() == 'true':
                    languages = [language.strip() for language in os.getenv('DOCLING_OCR_LANGUAGES', '').split(',') if language.strip()]
                    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,24}', language) for language in languages):
                        raise DoclingError('Docling OCR languages are invalid. Contact the administrator.')
                    if languages:
                        options['ocr_lang'] = list(dict.fromkeys(languages))
                    preset = os.getenv('DOCLING_OCR_PRESET', '').strip()
                    if preset:
                        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', preset):
                            raise DoclingError('Docling OCR preset is invalid. Contact the administrator.')
                        options['ocr_preset'] = preset
                result = await checked(await client.post("/v1/convert/file/async",
                    files={"files": (filename, content, content_type or "application/octet-stream")},
                    data=options))
                task_id = result.get("task_id")
                if not task_id:
                    raise DoclingError("The document service did not return a task identifier.")
                task_id = quote(str(task_id), safe="")
                deadline = time.monotonic() + timeout
                for attempt in range(120):
                    status = await checked(await client.get(f"/v1/status/poll/{task_id}"))
                    state = status.get("task_status", status.get("status", ""))
                    if state in {"success", "completed"}:
                        converted = await checked(await client.get(f"/v1/result/{task_id}"))
                        text = parse_result(converted)
                        if not text:
                            raise DoclingError("No readable text was returned. Upload a clearer document or check the OCR service settings.")
                        return text
                    if state in {"failure", "failed", "error", "cancelled"}:
                        logging.getLogger(__name__).warning('Docling conversion failed task_id=%s state=%s', task_id, state)
                        if options['do_ocr'].lower() == 'true':
                            raise DoclingError(f'Docling could not complete OCR. Ask the administrator to check the configured OCR engine and language support. Reference: {task_id}')
                        raise DoclingError("Document conversion failed. Try another file.")
                    if time.monotonic() >= deadline:
                        break
                    await asyncio.sleep(min(2 + attempt * 0.25, 5))
                raise DoclingError("Document conversion timed out. Try a smaller file.")
    except DoclingError:
        raise
    except TimeoutError as error:
        raise DoclingError("Document conversion timed out. Try a smaller file.") from error
    except httpx.HTTPError as error:
        raise DoclingError("The document service could not be reached securely. Contact your administrator or retry later.") from error
