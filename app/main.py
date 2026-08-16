"""
astro-engine — natal harita hesap servisi.

Dışarıya AÇIK DEĞİL: yalnız 127.0.0.1'e bind edilir ve tek istemcisi
Next.js route handler'ıdır. Nginx'te bu servise location açılmaz.
Bu yüzden burada auth yok — yetki kontrolü Next tarafında.

Çalıştırma:
    uvicorn app.main:app --host 127.0.0.1 --port 8787 --workers 1
"""

import logging

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from . import geocode
from .chart import build_natal, health_check
from .schemas import (
    EngineError,
    GeocodeResponse,
    NatalRequest,
    NatalResponse,
)

logger = logging.getLogger("astro-engine")

app = FastAPI(
    title="astro-engine",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.exception_handler(EngineError)
async def engine_error_handler(_request, exc: EngineError) -> JSONResponse:
    """Tek biçimli hata gövdesi. Yığın izi ASLA dışarı çıkmaz."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "field": exc.field,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(_request, exc: Exception) -> JSONResponse:
    # Ayrıntı log'a, kullanıcıya yalnız kod. Hata mesajları dosya yolu ve
    # kütüphane iç yapısı sızdırmaya çok müsait.
    logger.exception("Beklenmeyen hata", exc_info=exc)

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "ENGINE_ERROR",
                "message": "Beklenmeyen bir hata oluştu.",
                "field": None,
            }
        },
    )


@app.get("/health")
async def health() -> dict:
    """
    Gerçek bir hesap yaparak yanıtlar. Boş bir `{"ok": true}` efemeris
    dosyaları eksikken de yeşil görünür ve sorunu gizlerdi.
    """
    try:
        return health_check()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Sağlık kontrolü başarısız", exc_info=exc)
        raise EngineError(
            "ENGINE_ERROR",
            "Efemeris hesabı yapılamıyor.",
            status_code=503,
        ) from exc


@app.get("/v1/geocode", response_model=GeocodeResponse, response_model_by_alias=True)
async def geocode_endpoint(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=5, ge=1, le=10),
) -> GeocodeResponse:
    return GeocodeResponse(results=await geocode.search(q, limit))


@app.post("/v1/natal", response_model=NatalResponse, response_model_by_alias=True)
async def natal_endpoint(request: NatalRequest) -> NatalResponse:
    return build_natal(request)
