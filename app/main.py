"""
astro-engine — natal harita hesap servisi.

Dışarıya AÇIK DEĞİL: yalnız 127.0.0.1'e bind edilir ve tek istemcisi
Next.js route handler'ıdır. Nginx'te bu servise location açılmaz.
Bu yüzden burada auth yok — yetki kontrolü Next tarafında.

Çalıştırma:
    uvicorn app.main:app --host 127.0.0.1 --port 8787 --workers 1
"""

import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .chart import build_natal, health_check
from .schemas import EngineError, NatalRequest, NatalResponse

logger = logging.getLogger("astro-engine")

#: Geliştirmede `/docs` arayüzünü açar (ASTRO_ENGINE_DEV=1).
#:
#: Üretimde KAPALI: servis kimlik doğrulaması olmayan bir iç servis ve
#: şema dökümünü yayınlamasının bir faydası yok. Yerelde ise POST ucunu
#: denemenin en kolay yolu — tarayıcıdan form doldurup yanıtı görürsünüz.
DEV_MODE = os.getenv("ASTRO_ENGINE_DEV") == "1"

app = FastAPI(
    title="astro-engine",
    docs_url="/docs" if DEV_MODE else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DEV_MODE else None,
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


@app.post("/v1/natal", response_model=NatalResponse, response_model_by_alias=True)
async def natal_endpoint(request: NatalRequest) -> NatalResponse:
    return build_natal(request)
