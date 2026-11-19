from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from contextlib import suppress
from fastapi.middleware.cors import CORSMiddleware
from copywriter import router as copywriter_router
from admin import router as admin_router
from approval import router as approval_router
from feedback import router as feedback_router
from activity_tracker import router as activity_router
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from oracledb import Error as OracleError

@asynccontextmanager
async def lifespan(app):
    from storage_backend import oracle_enabled
    if oracle_enabled():
        from oracle_runtime import startup
        startup()
    from directory_provisioning import apply_deployment_updates
    apply_deployment_updates(strict=False)
    from channel_branding import migrate_regulatory_channel
    migrate_regulatory_channel()
    from platform_policy import retention_worker
    retention = asyncio.create_task(retention_worker())
    try:
        yield
    finally:
        retention.cancel()
        with suppress(asyncio.CancelledError):
            await retention
        if oracle_enabled():
            from oracle_runtime import pool
            pool().close()
            pool.cache_clear()


app = FastAPI(title="Harf API", lifespan=lifespan)
from inference_guard import InferenceGuard
app.add_middleware(InferenceGuard)
app.include_router(copywriter_router)
app.include_router(admin_router)
app.include_router(approval_router)
app.include_router(feedback_router)
app.include_router(activity_router)
from inference_admin import router as inference_router
app.include_router(inference_router)
from platform_policy import router as platform_policy_router
app.include_router(platform_policy_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(OracleError)
async def storage_unavailable(request, error):
    import logging
    code = getattr(error.args[0], 'code', None) if error.args else None
    logging.getLogger(__name__).error('Oracle storage operation failed code=%s', code or 'unknown')
    if code == 1536:
        return JSONResponse(status_code=503, content={'detail': 'Application database storage allowance is full. Please contact the administrator to increase the Oracle storage quota; retrying alone will not resolve this.'})
    return JSONResponse(status_code=503,content={'detail':'Application storage is temporarily unavailable. Please retry or contact the administrator.'})


@app.get('/api/health/storage')
def storage_health():
    from storage_backend import oracle_enabled
    if oracle_enabled():
        try:
            from oracle_runtime import transaction
            with transaction() as db, db.cursor() as cursor:
                cursor.execute("SELECT revision FROM genai_harf_runtime_state WHERE state_id='access'")
                if cursor.fetchone() is None:
                    raise RuntimeError('Missing runtime state')
        except Exception:
            raise HTTPException(status_code=503, detail='Application storage is temporarily unavailable.') from None
    return {'status':'ok','storage':'oracle' if oracle_enabled() else 'local'}

if __name__ == "__main__":
    import uvicorn
    print("API listening on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
