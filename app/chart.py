"""
Kerykeion sarmalayıcı.

Bu dosyanın tek işi: dışa açtığımız okunabilir sözleşmeyi Kerykeion'ın
gerçek API'sine çevirmek ve çıktısını sabit bir şekle sokmak. Kerykeion'ın
isimlendirmesi (üç harfli burçlar, `Eleventh_House`, tek harfli ev sistemi
kodu) API sözleşmemize sızmaz.

API imzaları 5.12.9 üzerinde ÇALIŞTIRILARAK doğrulandı, ezberden yazılmadı.
"""

from datetime import datetime, timezone as dt_timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from kerykeion import (
    AstrologicalSubjectFactory,
    ChartDataFactory,
    ChartDrawer,
    to_context,
)

from .schemas import (
    Aspect,
    BigThree,
    Distributions,
    EngineError,
    House,
    Meta,
    MoonPhase,
    NatalRequest,
    NatalResponse,
    Point,
    ResolvedTime,
    Subject,
)

ENGINE_VERSION = "5.12.9"

#: Kerykeion ev sistemini TEK HARFLE alıyor. Dışarıya okunabilir ad veriyoruz.
HOUSE_SYSTEM_CODES = {
    "Placidus": "P",
    "WholeSign": "W",
    "Koch": "K",
    "Equal": "A",
    "Regiomontanus": "R",
}

#: Kerykeion burçları üç harfle döndürüyor ("Can", "Vir").
SIGNS = {
    "Ari": ("Aries", "Koç"),
    "Tau": ("Taurus", "Boğa"),
    "Gem": ("Gemini", "İkizler"),
    "Can": ("Cancer", "Yengeç"),
    "Leo": ("Leo", "Aslan"),
    "Vir": ("Virgo", "Başak"),
    "Lib": ("Libra", "Terazi"),
    "Sco": ("Scorpio", "Akrep"),
    "Sag": ("Sagittarius", "Yay"),
    "Cap": ("Capricorn", "Oğlak"),
    "Aqu": ("Aquarius", "Kova"),
    "Pis": ("Pisces", "Balık"),
}

PLANET_TR = {
    "Sun": "Güneş",
    "Moon": "Ay",
    "Mercury": "Merkür",
    "Venus": "Venüs",
    "Mars": "Mars",
    "Jupiter": "Jüpiter",
    "Saturn": "Satürn",
    "Uranus": "Uranüs",
    "Neptune": "Neptün",
    "Pluto": "Plüton",
    "Chiron": "Chiron",
    "Mean_Lilith": "Lilith",
    "True_North_Lunar_Node": "Kuzey Ay Düğümü",
    "True_South_Lunar_Node": "Güney Ay Düğümü",
    "Ascendant": "Yükselen",
    "Medium_Coeli": "Tepe Noktası",
    "Descendant": "Alçalan",
    "Imum_Coeli": "Dip Nokta",
}

ASPECT_TR = {
    "conjunction": "Kavuşum",
    "opposition": "Karşıt",
    "trine": "Üçgen",
    "square": "Kare",
    "sextile": "Altmışlık",
    "quintile": "Beşlik",
    "semi-sextile": "Yarım altmışlık",
    "semi-square": "Yarım kare",
    "sesquiquadrate": "Bir buçuk kare",
    "biquintile": "İki beşlik",
    "quincunx": "Yüz ellilik",
}

MAJOR_ASPECTS = {"conjunction", "opposition", "trine", "square", "sextile"}

#: Yanıtta "planets" altında dönecekler. Eksenler ayrı listede.
PLANET_KEYS = [
    "sun", "moon", "mercury", "venus", "mars", "jupiter",
    "saturn", "uranus", "neptune", "pluto", "chiron", "mean_lilith",
    "true_north_lunar_node", "true_south_lunar_node",
]

AXIS_KEYS = ["ascendant", "medium_coeli", "descendant", "imum_coeli"]

HOUSE_KEYS = [
    "first_house", "second_house", "third_house", "fourth_house",
    "fifth_house", "sixth_house", "seventh_house", "eighth_house",
    "ninth_house", "tenth_house", "eleventh_house", "twelfth_house",
]

HOUSE_NUMBERS = {name: index + 1 for index, name in enumerate(HOUSE_KEYS)}

MOON_PHASE_TR = {
    "New Moon": "Yeni Ay",
    "Waxing Crescent": "Büyüyen Hilal",
    "First Quarter": "İlk Dördün",
    "Waxing Gibbous": "Büyüyen Şişkin Ay",
    "Full Moon": "Dolunay",
    "Waning Gibbous": "Küçülen Şişkin Ay",
    "Last Quarter": "Son Dördün",
    "Waning Crescent": "Küçülen Hilal",
}


def _sign(abbr: str) -> tuple[str, str]:
    return SIGNS.get(abbr, (abbr, abbr))


def _house_number(raw: Any) -> Optional[int]:
    if not isinstance(raw, str):
        return None
    return HOUSE_NUMBERS.get(raw.lower())


def _point(raw: dict[str, Any]) -> Point:
    sign_en, sign_tr = _sign(raw.get("sign", ""))
    name = raw.get("name", "")

    return Point(
        name=name,
        name_tr=PLANET_TR.get(name, name),
        sign=sign_en,
        sign_tr=sign_tr,
        degree_in_sign=round(raw.get("position", 0.0), 4),
        abs_degree=round(raw.get("abs_pos", 0.0), 4),
        house=_house_number(raw.get("house")),
        retrograde=raw.get("retrograde"),
        speed=raw.get("speed"),
        element=raw.get("element"),
        quality=raw.get("quality"),
    )


def _parse_date(value: str) -> tuple[int, int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise EngineError("INVALID_DATE", "Tarih YYYY-AA-GG biçiminde olmalı.", "date") from exc

    if not 1800 <= parsed.year <= 2100:
        raise EngineError(
            "OUT_OF_EPHEMERIS_RANGE",
            "Yıl 1800–2100 aralığında olmalı.",
            "date",
        )

    return parsed.year, parsed.month, parsed.day


def _parse_time(value: Optional[str], time_known: bool) -> tuple[int, int]:
    """
    Saat bilinmiyorsa 12:00 varsayılır — gün ortası, gün sınırına en uzak
    nokta. Bu bir tahmin değil, açıkça işaretlenen bir varsayım:
    `timeKnown: false` yanıtta dönüyor ve UI Ascendant/MC/evleri soluk
    gösteriyor. Sessizce normal harita gibi sunmak kabul edilemez.
    """
    if not time_known:
        return 12, 0

    if not value:
        raise EngineError("INVALID_TIME", "Doğum saati zorunlu.", "time")

    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise EngineError("INVALID_TIME", "Saat SS:DD biçiminde olmalı.", "time") from exc

    return parsed.hour, parsed.minute


def _resolve_timezone(name: str) -> ZoneInfo:
    """
    IANA zone ADI şart. Sayısal offset ("+03:00") kabul edilmez: 2016
    öncesi Türkiye doğumlarında yaz saati vardı ve sabit offset o kayıtları
    bir saat kaydırır — yükselen ve tüm ev sistemi değişir.
    """
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise EngineError(
            "UNKNOWN_TIMEZONE",
            f"Bilinmeyen saat dilimi: {name}",
            "timezone",
        ) from exc


def build_natal(request: NatalRequest) -> NatalResponse:
    year, month, day = _parse_date(request.date)
    hour, minute = _parse_time(request.time, request.time_known)
    zone = _resolve_timezone(request.timezone)

    warnings: list[str] = []
    if not request.time_known:
        warnings.append(
            "Doğum saati bilinmiyor; 12:00 varsayıldı. Yükselen, tepe noktası, "
            "ev cuspları ve Ay derecesi güvenilmez."
        )

    # Offset ve yaz saati bilgisi, Kerykeion'dan BAĞIMSIZ olarak zoneinfo'dan
    # alınıyor: iki kaynak da aynı şeyi söylüyorsa güven artar, ayrışırsa
    # golden test yakalar.
    local_dt = datetime(year, month, day, hour, minute, tzinfo=zone)
    offset = local_dt.utcoffset()
    dst = local_dt.dst()

    try:
        subject = AstrologicalSubjectFactory.from_birth_data(
            name=_display_name(request),
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            lng=request.longitude,
            lat=request.latitude,
            tz_str=request.timezone,
            # ŞART: varsayılan True ve o hâlde GeoNames'e gidip
            # `geonames_username` istiyor. Mimarinin "tek dış çağrı
            # geocoding" kuralı bu bayrakla korunuyor.
            online=False,
            # city/nation geçilmezse Kerykeion etiketi "Greenwich, GB"
            # yapıyor — hesap doğru çıkıyor ama llmContext ve çark yanlış
            # yeri yazıyor.
            city=request.place_label,
            nation="",
            zodiac_type=request.zodiac_type,
            houses_system_identifier=HOUSE_SYSTEM_CODES[request.house_system],
            suppress_geonames_warning=True,
        )
    except EngineError:
        raise
    except Exception as exc:  # noqa: BLE001 — dışarıya sızmayan tek nokta
        raise EngineError(
            "ENGINE_ERROR",
            "Harita hesaplanamadı.",
            status_code=500,
        ) from exc

    data = subject.model_dump()
    chart_data = ChartDataFactory.create_natal_chart_data(subject)
    chart_dump = chart_data.model_dump()

    svg: Optional[str] = None
    if request.include_svg:
        drawer = ChartDrawer(
            chart_data,
            theme=request.chart_theme,
            chart_language=request.chart_language,
        )
        svg = (
            drawer.generate_wheel_only_svg_string()
            if request.wheel_only
            else drawer.generate_svg_string()
        )

    lunar = data.get("lunar_phase") or {}
    phase_name = lunar.get("moon_phase_name", "")
    degrees = lunar.get("degrees_between_s_m", 0.0)

    elements = chart_dump.get("element_distribution", {})
    qualities = chart_dump.get("quality_distribution", {})

    return NatalResponse(
        meta=Meta(
            engine="kerykeion",
            engine_version=ENGINE_VERSION,
            computed_at=datetime.now(dt_timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            time_known=request.time_known,
            house_system=request.house_system,
            zodiac_type=request.zodiac_type,
        ),
        resolved_time=ResolvedTime(
            local_iso=data["iso_formatted_local_datetime"],
            utc_iso=data["iso_formatted_utc_datetime"].replace("+00:00", "Z"),
            utc_offset_hours=round(offset.total_seconds() / 3600, 2) if offset else 0.0,
            is_dst=bool(dst and dst.total_seconds() != 0),
            timezone=request.timezone,
            julian_day=data["julian_day"],
        ),
        subject=Subject(
            display_name=_display_name(request),
            place_label=request.place_label,
            latitude=request.latitude,
            longitude=request.longitude,
        ),
        big_three=BigThree(
            sun=_sign(data["sun"]["sign"])[1],
            moon=_sign(data["moon"]["sign"])[1],
            ascendant=_sign(data["ascendant"]["sign"])[1],
        ),
        planets=[_point(data[key]) for key in PLANET_KEYS if data.get(key)],
        axes=[_point(data[key]) for key in AXIS_KEYS if data.get(key)],
        houses=[_house(data[key], key) for key in HOUSE_KEYS if data.get(key)],
        aspects=[_aspect(item) for item in chart_dump.get("aspects", [])],
        distributions=Distributions(
            elements={
                "fire": elements.get("fire_percentage", 0),
                "earth": elements.get("earth_percentage", 0),
                "air": elements.get("air_percentage", 0),
                "water": elements.get("water_percentage", 0),
            },
            modalities={
                "cardinal": qualities.get("cardinal_percentage", 0),
                "fixed": qualities.get("fixed_percentage", 0),
                "mutable": qualities.get("mutable_percentage", 0),
            },
        ),
        moon_phase=MoonPhase(
            name=phase_name,
            name_tr=MOON_PHASE_TR.get(phase_name, phase_name),
            # Elongasyondan aydınlanma oranı: (1 - cos θ) / 2
            illumination=round(_illumination(degrees), 1),
            degrees_between_sun_moon=round(degrees, 4),
        ),
        svg=svg,
        llm_context=to_context(chart_data),
        warnings=warnings,
    )


def _display_name(request: NatalRequest) -> str:
    return " ".join(part for part in (request.first_name, request.last_name) if part).strip()


def _house(raw: dict[str, Any], key: str) -> House:
    sign_en, sign_tr = _sign(raw.get("sign", ""))

    return House(
        number=HOUSE_NUMBERS[key],
        sign=sign_en,
        sign_tr=sign_tr,
        degree_in_sign=round(raw.get("position", 0.0), 4),
        abs_degree=round(raw.get("abs_pos", 0.0), 4),
    )


def _aspect(raw: dict[str, Any]) -> Aspect:
    name = raw.get("aspect", "")
    p1 = raw.get("p1_name", "")
    p2 = raw.get("p2_name", "")

    return Aspect(
        p1=p1,
        p1_tr=PLANET_TR.get(p1, p1),
        p2=p2,
        p2_tr=PLANET_TR.get(p2, p2),
        aspect=name,
        aspect_tr=ASPECT_TR.get(name, name),
        aspect_degrees=int(raw.get("aspect_degrees", 0)),
        orb=round(abs(raw.get("orbit", 0.0)), 4),
        applying=raw.get("aspect_movement") == "Applying",
        is_major=name in MAJOR_ASPECTS,
    )


def _illumination(degrees_between: float) -> float:
    import math

    return (1 - math.cos(math.radians(degrees_between))) / 2 * 100


def health_check() -> dict[str, Any]:
    """
    Sadece {"ok": true} DEĞİL: gerçek bir hesap yapar. Efemeris dosyaları
    eksik ya da bozuksa bunu yalnız gerçek bir hesap yakalar; boş bir
    sağlık ucu servisi "ayakta" gösterip her isteği patlatırdı.
    """
    subject = AstrologicalSubjectFactory.from_birth_data(
        name="health", year=2000, month=1, day=1, hour=12, minute=0,
        lng=0.0, lat=51.48, tz_str="UTC", online=False,
        zodiac_type="Tropical", houses_system_identifier="P",
        suppress_geonames_warning=True,
    )
    data = subject.model_dump()

    return {
        "ok": True,
        "engine": "kerykeion",
        "engineVersion": ENGINE_VERSION,
        "selfTest": {
            "julianDay": data["julian_day"],
            "sunSign": _sign(data["sun"]["sign"])[0],
            "ascendantSign": _sign(data["ascendant"]["sign"])[0],
        },
    }
