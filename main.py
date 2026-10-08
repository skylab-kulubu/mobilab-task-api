"""
MOBILAB Task API
Etkinlik Keşif Uygulaması görevi için küçük, salt-okunur bir etkinlik API'si.

Çalıştırma:
    pip install -r requirements.txt
    uvicorn main:app --reload

Ortam değişkenleri:
    CHAOS_ENABLED     "true" / "false"  -> gecikme ve rastgele hata simülasyonu (varsayılan: true)
    CHAOS_ERROR_RATE  0.0 - 1.0         -> isteklerin ne kadarı 500 dönsün (varsayılan: 0.1)
    CHAOS_MIN_DELAY   saniye            -> minimum yapay gecikme (varsayılan: 0.3)
    CHAOS_MAX_DELAY   saniye            -> maksimum yapay gecikme (varsayılan: 1.5)
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Ayarlar
# ---------------------------------------------------------------------------

DATA_PATH = Path(__file__).resolve().parent / "events.json"

CHAOS_ENABLED = os.getenv("CHAOS_ENABLED", "true").lower() == "true"
CHAOS_ERROR_RATE = float(os.getenv("CHAOS_ERROR_RATE", "0.1"))
CHAOS_MIN_DELAY = float(os.getenv("CHAOS_MIN_DELAY", "0.3"))
CHAOS_MAX_DELAY = float(os.getenv("CHAOS_MAX_DELAY", "1.5"))

# Kaos uygulanmayacak yollar (sağlık kontrolü ve dokümantasyon)
CHAOS_EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}

# ---------------------------------------------------------------------------
# Veri
# ---------------------------------------------------------------------------


def _load_events() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    events = raw["events"]
    # Pagination tutarlı olsun diye her zaman başlangıç tarihine göre sıralı tut
    events.sort(key=lambda e: datetime.fromisoformat(e["startDate"]))
    return events


EVENTS: list[dict] = _load_events()
EVENTS_BY_ID: dict[str, dict] = {e["id"]: e for e in EVENTS}

# Liste uç noktasında dönmeyecek alanlar (detay için /events/{id} kullanılmalı)
LIST_EXCLUDED_FIELDS = {"description"}


def _normalize(text: str) -> str:
    """Türkçe karakterlere duyarlı, büyük/küçük harf duyarsız karşılaştırma."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def _summary(event: dict) -> dict:
    return {k: v for k, v in event.items() if k not in LIST_EXCLUDED_FIELDS}


# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MOBILAB Task API",
    description=(
        "Etkinlik Keşif Uygulaması görevi için etkinlik API'si.\n\n"
        "**Not:** Bu API gerçek dünyayı taklit eder; bazı istekler yavaş gelebilir, "
        "bazıları da hata dönebilir. Uygulaman bu durumlarla başa çıkabilmeli."
    ),
    version="1.0.0",
)

class StripVercelPrefixMiddleware:
    """
    Vercel, vercel.json'daki rewrite yüzünden isteği uygulamaya '/api/index/...'
    yoluyla iletebiliyor. Bu katman o öneki silip asıl yolu (/docs, /events...) geri getirir.
    Yerelde ve Docker'da hiçbir etkisi yoktur.
    """

    PREFIXES = ("/api/index", "/api")

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            for prefix in self.PREFIXES:
                if path == prefix or path.startswith(prefix + "/"):
                    new_path = path[len(prefix):] or "/"
                    scope = dict(scope, path=new_path, raw_path=new_path.encode())
                    break
        await self.app(scope, receive, send)


app.add_middleware(StripVercelPrefixMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    if CHAOS_ENABLED and request.url.path not in CHAOS_EXEMPT_PATHS:
        await asyncio.sleep(random.uniform(CHAOS_MIN_DELAY, CHAOS_MAX_DELAY))
        if random.random() < CHAOS_ERROR_RATE:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": "Sunucuda beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
                },
            )
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"error": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail)


# ---------------------------------------------------------------------------
# Uç noktalar
# ---------------------------------------------------------------------------


@app.get("/", tags=["genel"])
def root():
    return {
        "name": "MOBILAB Task API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "GET /events",
            "GET /events/{id}",
            "GET /categories",
        ],
    }


@app.get("/health", tags=["genel"])
def health():
    return {"status": "ok"}


@app.get("/categories", tags=["etkinlikler"])
def list_categories():
    """Mevcut tüm kategoriler, alfabetik sırada."""
    categories = sorted({e["category"] for e in EVENTS}, key=_normalize)
    return {"items": categories}


@app.get("/events", tags=["etkinlikler"])
def list_events(
    q: Optional[str] = Query(None, description="Başlık ve etiketlerde arama"),
    category: Optional[str] = Query(None, description="Kategoriye göre filtre (ör. Workshop)"),
    online: Optional[bool] = Query(None, description="Sadece online (true) ya da yüz yüze (false)"),
    page: int = Query(1, ge=1, description="Sayfa numarası (1'den başlar)"),
    limit: int = Query(10, ge=1, le=50, description="Sayfa başına kayıt (1-50)"),
):
    """
    Etkinlik listesi. Başlangıç tarihine göre sıralı gelir.
    Liste yanıtında `description` alanı yoktur; detay için `/events/{id}` kullan.
    """
    results = EVENTS

    if q:
        needle = _normalize(q.strip())
        results = [
            e for e in results
            if needle in _normalize(e["title"])
            or any(needle in _normalize(tag) for tag in e.get("tags", []))
        ]

    if category:
        cat = _normalize(category.strip())
        results = [e for e in results if _normalize(e["category"]) == cat]

    if online is not None:
        results = [e for e in results if e["isOnline"] == online]

    total = len(results)
    start = (page - 1) * limit
    items = [_summary(e) for e in results[start:start + limit]]

    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "hasMore": start + limit < total,
    }


@app.get("/events/{event_id}", tags=["etkinlikler"])
def get_event(event_id: str):
    """Tek bir etkinliğin tüm detayları."""
    event = EVENTS_BY_ID.get(event_id)
    if event is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"'{event_id}' id'li etkinlik bulunamadı."},
        )
    return event