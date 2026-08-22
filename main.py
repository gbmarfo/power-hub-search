from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth.authentication import get_current_user
from routers import search_router, index_router, account_router, multimodal_router
from services.milvus_store import check_milvus_health
from database.database import Base, SessionLocal, engine
import config

title = "Power Hub + Search Service API"
description = """
Power Hub document vault (SharePoint-style) with enterprise search via Milvus,
keyword retrieval, and hybrid ranking.
"""
version = "0.3"

Path("./data").mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=title,
    description=description,
    version=version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS
    + [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
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

if config.POWERHUB_ENABLED:
    from powerhub.routers import auth_router, files_router, shares_router, admin_router
    import powerhub.models  # noqa: F401
    from powerhub.seed import seed_powerhub

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        try:
            seed_powerhub(db)
        except Exception as exc:  # pragma: no cover
            print(f"Power Hub seed warning: {exc}")

    app.include_router(auth_router.router, prefix="/api/v1/powerhub", tags=["Power Hub"])
    app.include_router(files_router.router, prefix="/api/v1/powerhub", tags=["Power Hub Files"])
    app.include_router(shares_router.router, prefix="/api/v1/powerhub", tags=["Power Hub Sharing"])
    app.include_router(admin_router.router, prefix="/api/v1/powerhub", tags=["Power Hub Admin"])

ADMIN_DIST = Path(__file__).resolve().parent / "admin" / "dist"
HUB_DIST = Path(__file__).resolve().parent / "powerhub-web" / "dist"


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
        "powerhub": {"enabled": config.POWERHUB_ENABLED},
        "version": version,
    }


@app.get("/api/v1/info")
def api_info(current_user: str = Depends(get_current_user)):
    return {
        "message": "Power Hub + Search Service API",
        "version": version,
        "user": current_user,
        "powerhub": config.POWERHUB_ENABLED,
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


if HUB_DIST.exists():
    assets_dir = HUB_DIST / "assets"
    if assets_dir.exists():
        app.mount("/hub/assets", StaticFiles(directory=assets_dir), name="hub-assets")

    @app.get("/hub/{full_path:path}")
    async def serve_hub(full_path: str = ""):
        requested = HUB_DIST / full_path
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(HUB_DIST / "index.html")

    @app.get("/hub")
    async def serve_hub_root():
        return FileResponse(HUB_DIST / "index.html")


@app.get("/")
def root():
    if HUB_DIST.exists():
        return FileResponse(HUB_DIST / "index.html")
    return {
        "message": "Power Hub + Search Service",
        "hub": "/hub",
        "admin": "/admin",
        "docs": "/docs",
    }
