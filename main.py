from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth.authentication import get_current_user
from routers import search_router, index_router, account_router, multimodal_router
from services.milvus_store import check_milvus_health
import config

title = "Search Service API"
description = """
Enterprise search API with Milvus vector search, keyword retrieval, and hybrid ranking.
"""
version = "0.2"

app = FastAPI(
    title=title,
    description=description,
    version=version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(index_router.router, prefix="/api/v1/index", tags=["Index"])
app.include_router(account_router.router, prefix="/api/v1/account", tags=["Account"])
if config.MULTIMODAL_ENABLED:
    app.include_router(
        multimodal_router.router,
        prefix="/api/v1/multimodal",
        tags=["Multimodal RAG"],
    )

ADMIN_DIST = Path(__file__).resolve().parent / "admin" / "dist"


@app.get("/health")
def health_check():
    milvus = check_milvus_health()
    status = "ok" if milvus.get("status") == "ok" else "degraded"
    multimodal = {"enabled": config.MULTIMODAL_ENABLED}
    if config.MULTIMODAL_ENABLED:
        try:
            from services.multimodal_encoder import get_multimodal_encoder

            multimodal["encoder"] = get_multimodal_encoder().status()
        except Exception as exc:
            multimodal["encoder"] = {"available": False, "error": str(exc)}
        multimodal["reranker_configured"] = bool(config.OPENAI_API_KEY)
    return {
        "status": status,
        "milvus": milvus,
        "multimodal": multimodal,
        "version": version,
    }


@app.get("/api/v1/info")
def api_info(current_user: str = Depends(get_current_user)):
    return {
        "message": "Search Service API",
        "version": version,
        "user": current_user,
    }


if ADMIN_DIST.exists():
    assets_dir = ADMIN_DIST / "assets"
    if assets_dir.exists():
        app.mount("/admin/assets", StaticFiles(directory=assets_dir), name="admin-assets")

    @app.get("/admin/{full_path:path}")
    async def serve_admin(full_path: str = ""):
        requested = ADMIN_DIST / full_path
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(ADMIN_DIST / "index.html")

    @app.get("/admin")
    async def serve_admin_root():
        return FileResponse(ADMIN_DIST / "index.html")
