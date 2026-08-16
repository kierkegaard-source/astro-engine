"""
Yer arama: Open-Meteo Geocoding + timezonefinder.

Motorun TEK dış çağrısı burası. Kerykeion `online=False` ile çağrıldığı
için efemeris tarafı tamamen çevrimdışı; zaman dilimi de yerel veriden
(timezonefinder) çözülüyor, ağ gerektirmiyor.

Open-Meteo anahtarsız ve ücretsiz. İleride GeoNames dump'ı MySQL'e alınıp
bu bağımlılık da sıfırlanabilir (NATAL-PLAN.md Bölüm 9).
"""

from functools import lru_cache
from typing import Any

import httpx
from timezonefinder import TimezoneFinder

from .schemas import EngineError, GeocodeResult

OPEN_METEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT_SECONDS = 8.0


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    """
    Ağır veri dosyalarını bir kez yükler (~50MB). İstek başına kurmak
    her aramaya saniyeler eklerdi.
    """
    return TimezoneFinder()


def timezone_at(latitude: float, longitude: float) -> str:
    """
    Koordinatın IANA zone adı. Bulunamazsa UTC — okyanus ortası gibi
    durumlarda `None` dönüyor ve çağıran tarafı patlatmasın.
    """
    zone = _finder().timezone_at(lat=latitude, lng=longitude)
    return zone or "UTC"


async def search(query: str, limit: int = 5) -> list[GeocodeResult]:
    if not query.strip():
        return []

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(
                OPEN_METEO_URL,
                params={
                    "name": query,
                    "count": max(1, min(limit, 10)),
                    "language": "tr",
                    "format": "json",
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
    except httpx.HTTPError as exc:
        raise EngineError(
            "GEOCODE_FAILED",
            "Yer arama servisine ulaşılamadı.",
            "placeLabel",
            status_code=502,
        ) from exc

    results: list[GeocodeResult] = []

    for item in payload.get("results") or []:
        latitude = item.get("latitude")
        longitude = item.get("longitude")
        if latitude is None or longitude is None:
            continue

        results.append(
            GeocodeResult(
                name=item.get("name", ""),
                admin1=item.get("admin1"),
                country=item.get("country"),
                country_code=item.get("country_code"),
                latitude=latitude,
                longitude=longitude,
                # Open-Meteo'nun kendi `timezone` alanı var ama koordinattan
                # yeniden çözüyoruz: tek bir kaynak olsun ve elle girilen
                # koordinatlarla aynı yoldan geçsin.
                timezone=timezone_at(latitude, longitude),
            )
        )

    return results
