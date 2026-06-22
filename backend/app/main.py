from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
from urllib.parse import quote, urlparse

from bson import ObjectId
import httpx
from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from app.logging_config import configure_logging
from app.settings import settings
from app.db import init_db, close_db, get_client
from app.public_cache import ttl_cache_maintenance_loop

# v1 routers
from app.routers.v1.pages import router as pages_v1
from app.routers.v1.sections import router as sections_v1
from app.routers.v1.headers import router as headers_v1
from app.routers.v1.assets import router as assets_v1
from app.routers.v1.design import router as design_v1
from app.routers.v1.blog import router as blog_v1
from app.routers.v1.faq import router as faq_v1
from app.routers.v1.program import router as program_v1
from app.routers.v1.auth import router as auth_v1
from app.routers.v1.admin_design import router as admin_design_v1
from app.routers.v1.admin_devops import router as admin_devops_v1
from app.routers.v1.admin_media import router as admin_media_v1
from app.routers.v1.admin_templates import router as admin_templates_v1
from app.routers.v1.backup import router as backup_v1
from app.routers.v1.integrations import router as integrations_v1
from app.routers.v1.admin_users import router as admin_users_v1
from app.routers.v1.sitemap import router as sitemap_v1
from app.sitemap import (
    build_public_robots_payload,
    build_public_sitemap_payload,
    get_custom_robots_text,
    resolve_public_base_url_from_request,
)


configure_logging()

STATIC_CACHE_HEADERS = {"Cache-Control": "public, max-age=604800"}
CRAWLER_CACHE_HEADERS = {"Cache-Control": "no-cache, max-age=0"}


def _normalize_download_filename(value: str, fallback: str = "media") -> str:
    raw = str(value or "").replace("\\", "/").split("/")[-1].strip()
    if not raw:
        raw = fallback
    raw = raw.replace("\r", " ").replace("\n", " ").strip()
    return raw or fallback


def _build_download_content_disposition(filename: str) -> str:
    normalized = _normalize_download_filename(filename)
    ascii_filename = "".join(
        char if 32 <= ord(char) < 127 and char not in {'"', "\\", ";"} else "_"
        for char in normalized
    )
    if not ascii_filename:
        ascii_filename = "media"
    encoded = quote(normalized, safe="")
    return f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded}"


def _coerce_downloadable_flag(raw) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _asset_ref_query(asset_ref: str) -> dict:
    ref = str(asset_ref or "").strip()
    clauses = []
    if ref:
        clauses.append({"media_hash": ref.lower()})
        try:
            clauses.append({"_id": ObjectId(ref)})
        except Exception:
            pass
    if not clauses:
        return {"_id": None}
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def _resolve_download_source_url(raw_url: str, request: Request) -> str:
    source_url = str(raw_url or "").strip()
    if source_url.startswith("/") and not source_url.startswith("//"):
        return f"{resolve_public_base_url_from_request(request)}{source_url}"

    parsed = urlparse(source_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return source_url
    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    ttl_cache_task = asyncio.create_task(ttl_cache_maintenance_loop())
    try:
        yield
    finally:
        ttl_cache_task.cancel()
        with suppress(asyncio.CancelledError):
            await ttl_cache_task
        await close_db()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# One combined router for v1 (keeps /docs unified)
v1 = APIRouter(prefix="/api/v1")
v1.include_router(pages_v1)
v1.include_router(sections_v1)
v1.include_router(headers_v1)
v1.include_router(assets_v1)
v1.include_router(design_v1)
v1.include_router(blog_v1)
v1.include_router(faq_v1)
v1.include_router(program_v1)
v1.include_router(auth_v1)
v1.include_router(admin_design_v1)
v1.include_router(admin_devops_v1)
v1.include_router(admin_media_v1)
v1.include_router(admin_templates_v1)
v1.include_router(backup_v1)
v1.include_router(integrations_v1)
v1.include_router(admin_users_v1)
v1.include_router(sitemap_v1)


# System endpoints on v1 router (must be defined before include_router)
@v1.get("/system/time", tags=["system"])
async def get_server_time():
    """Get current server time - useful for scheduling UI."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    berlin_tz = ZoneInfo("Europe/Berlin")
    server_time = datetime.now(berlin_tz)
    return {
        "server_time": server_time.isoformat(),
        "server_timezone": "Europe/Berlin"
    }


app.include_router(v1)


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(request: Request):
    db = get_client()[settings.mongo_db]
    payload = await build_public_sitemap_payload(
        db,
        public_base_url=resolve_public_base_url_from_request(request),
    )
    if not payload.get("enabled", True):
        return Response(status_code=404, content="sitemap disabled for subdomain instances\n", media_type="text/plain")
    return Response(
        content=payload["xml"],
        media_type="application/xml",
        headers=CRAWLER_CACHE_HEADERS,
    )


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt(request: Request):
    db = get_client()[settings.mongo_db]
    custom_text = await get_custom_robots_text(db)
    payload = await build_public_robots_payload(
        db,
        public_base_url=resolve_public_base_url_from_request(request),
        custom_robots_txt=custom_text,
    )
    return Response(
        content=payload["merged_text"],
        media_type="text/plain",
        headers=CRAWLER_CACHE_HEADERS,
    )


@app.get("/download/{asset_ref}/{requested_name}", include_in_schema=False)
async def download_media(asset_ref: str, requested_name: str, request: Request):
    db = get_client()[settings.mongo_db]
    asset = await db["assets"].find_one(
        _asset_ref_query(asset_ref),
        {"url": 1, "filename": 1, "content_type": 1, "downloadable": 1},
    )
    if not asset or not _coerce_downloadable_flag(asset.get("downloadable")):
        return Response(status_code=404, content="not found\n", media_type="text/plain")

    source_url = _resolve_download_source_url(str(asset.get("url") or ""), request)
    if not source_url:
        return Response(status_code=404, content="not found\n", media_type="text/plain")

    client: httpx.AsyncClient | None = None
    source_response: httpx.Response | None = None
    try:
        client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        request_upstream = client.build_request("GET", source_url)
        source_response = await client.send(request_upstream, stream=True)
    except httpx.HTTPError:
        if client is not None:
            await client.aclose()
        return Response(status_code=502, content="download source unavailable\n", media_type="text/plain")
    if source_response.status_code >= 400:
        await source_response.aclose()
        await client.aclose()
        return Response(
            status_code=source_response.status_code,
            content="not found\n",
            media_type="text/plain",
        )

    filename = _normalize_download_filename(str(asset.get("filename") or requested_name or "media"))
    content_type = str(
        asset.get("content_type")
        or source_response.headers.get("content-type")
        or "application/octet-stream"
    )

    async def iter_download():
        try:
            async for chunk in source_response.aiter_bytes():
                if chunk:
                    yield chunk
        finally:
            await source_response.aclose()
            await client.aclose()

    headers = {
        "Content-Disposition": _build_download_content_disposition(filename),
    }
    upstream_content_length = str(source_response.headers.get("content-length") or "").strip()
    if upstream_content_length.isdigit():
        headers["Content-Length"] = upstream_content_length

    return StreamingResponse(
        iter_download(),
        media_type=content_type,
        headers=headers,
    )


@app.get("/health", tags=["system"])
async def health():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    berlin_tz = ZoneInfo("Europe/Berlin")
    server_time = datetime.now(berlin_tz)
    return {
        "ok": True,
        "env": settings.environment,
        "server_time": server_time.isoformat(),
        "server_timezone": "Europe/Berlin"
    }
