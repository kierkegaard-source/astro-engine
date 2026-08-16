"""
İstek/yanıt sözleşmesi.

Python içinde snake_case, dışarıya camelCase — TS tarafı ve Drizzle
casing'iyle tutarlı olsun diye. Dönüşüm `alias_generator` ile otomatik;
elle iki isim tutmak er ya da geç ayrışır.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

HouseSystem = Literal["Placidus", "WholeSign", "Koch", "Equal", "Regiomontanus"]
ZodiacType = Literal["Tropical", "Sidereal"]
ChartTheme = Literal["light", "dark", "dark-high-contrast", "classic", "black-and-white"]
ChartLanguage = Literal["TR", "EN"]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        # Bilinmeyen alan sessizce yutulmasın: TS tarafı yanlış isim
        # gönderirse burada patlasın, üretimde fark edilmesin diye değil.
        extra="forbid",
    )


# --------------------------------------------------------------------- #
# İstek                                                                  #
# --------------------------------------------------------------------- #


class NatalRequest(CamelModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: Optional[str] = Field(default=None, max_length=80)

    #: "1985-07-14"
    date: str
    #: "10:30" — time_known False ise yok sayılır.
    time: Optional[str] = None
    time_known: bool = True

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    #: IANA zone ADI. Sayısal offset ASLA kabul edilmez (bkz. chart.py).
    timezone: str = Field(min_length=1)
    place_label: str = Field(min_length=1)

    house_system: HouseSystem = "Placidus"
    zodiac_type: ZodiacType = "Tropical"
    chart_theme: ChartTheme = "black-and-white"
    chart_language: ChartLanguage = "TR"
    include_svg: bool = True
    #: Açı ızgarası SVG'yi ~50KB büyütüyor; sayfa varsayılanı yalnız çark.
    wheel_only: bool = True


# --------------------------------------------------------------------- #
# Yanıt                                                                  #
# --------------------------------------------------------------------- #


class Meta(CamelModel):
    engine: str
    engine_version: str
    computed_at: str
    time_known: bool
    house_system: HouseSystem
    zodiac_type: ZodiacType


class ResolvedTime(CamelModel):
    """
    Test edilebilirliğin tamamı bu bloktan geliyor: saat dilimi hatası
    başka hiçbir alandan görülmez, sonuç yalnızca "biraz farklı" çıkar.
    """

    local_iso: str
    utc_iso: str
    utc_offset_hours: float
    is_dst: bool
    timezone: str
    julian_day: float


class Subject(CamelModel):
    display_name: str
    place_label: str
    latitude: float
    longitude: float


class Point(CamelModel):
    name: str
    name_tr: str
    sign: str
    sign_tr: str
    degree_in_sign: float
    abs_degree: float
    house: Optional[int] = None
    retrograde: Optional[bool] = None
    speed: Optional[float] = None
    element: Optional[str] = None
    quality: Optional[str] = None


class House(CamelModel):
    number: int
    sign: str
    sign_tr: str
    degree_in_sign: float
    abs_degree: float


class Aspect(CamelModel):
    p1: str
    p1_tr: str
    p2: str
    p2_tr: str
    aspect: str
    aspect_tr: str
    aspect_degrees: int
    orb: float
    applying: bool
    is_major: bool


class Distributions(CamelModel):
    elements: dict[str, float]
    modalities: dict[str, float]


class MoonPhase(CamelModel):
    name: str
    name_tr: str
    #: 0–100
    illumination: float
    degrees_between_sun_moon: float


class BigThree(CamelModel):
    sun: str
    moon: str
    ascendant: str


class NatalResponse(CamelModel):
    meta: Meta
    resolved_time: ResolvedTime
    subject: Subject
    big_three: BigThree
    planets: list[Point]
    axes: list[Point]
    houses: list[House]
    aspects: list[Aspect]
    distributions: Distributions
    moon_phase: MoonPhase
    svg: Optional[str] = None
    llm_context: str
    warnings: list[str]


# --------------------------------------------------------------------- #
# Geocoding                                                              #
# --------------------------------------------------------------------- #


class GeocodeResult(CamelModel):
    name: str
    admin1: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    latitude: float
    longitude: float
    timezone: str


class GeocodeResponse(CamelModel):
    results: list[GeocodeResult]


# --------------------------------------------------------------------- #
# Hata                                                                   #
# --------------------------------------------------------------------- #

ErrorCode = Literal[
    "INVALID_DATE",
    "INVALID_TIME",
    "UNKNOWN_TIMEZONE",
    "GEOCODE_FAILED",
    "OUT_OF_EPHEMERIS_RANGE",
    "ENGINE_ERROR",
]


class ErrorBody(CamelModel):
    code: ErrorCode
    message: str
    field: Optional[str] = None


class ErrorResponse(CamelModel):
    error: ErrorBody


class EngineError(Exception):
    """Yığın izi dışarı sızmasın diye tüm hatalar buna çevrilir."""

    def __init__(
        self,
        code: str,
        message: str,
        field: Optional[str] = None,
        status_code: int = 422,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.status_code = status_code
