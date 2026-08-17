"""
Yerel önizleme: motora bir istek atar, çarkı ve özet tabloyu tarayıcıda
açılabilir bir HTML dosyasına yazar.

Next.js sayfası henüz yokken motoru gözle doğrulamanın en hızlı yolu.
Üretimde kullanılmaz.

Kullanım (astro-engine klasöründen):

    .venv/Scripts/python.exe tools/preview.py
    .venv/Scripts/python.exe tools/preview.py 1990-05-17 14:30 41.0082 28.9784 "Istanbul"
    .venv/Scripts/python.exe tools/preview.py 1985-07-14 --no-time     # saat bilinmiyor
"""

import html
import json
import sys
import urllib.request
import webbrowser
from pathlib import Path

ENGINE = "http://127.0.0.1:8787"
OUTPUT = Path(__file__).resolve().parent / "chart.html"


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--no-time"]
    time_known = "--no-time" not in sys.argv

    date = args[0] if len(args) > 0 else "1985-07-14"
    time = args[1] if len(args) > 1 else "10:30"
    lat = float(args[2]) if len(args) > 2 else 38.41273
    lng = float(args[3]) if len(args) > 3 else 27.13838
    place = args[4] if len(args) > 4 else "İzmir"

    payload = {
        "firstName": "Önizleme",
        "date": date,
        "time": time if time_known else None,
        "timeKnown": time_known,
        "latitude": lat,
        "longitude": lng,
        "timezone": "Europe/Istanbul",
        "placeLabel": place,
        "houseSystem": "Placidus",
        "zodiacType": "Tropical",
        "chartTheme": "black-and-white",
        "chartLanguage": "TR",
        "includeSvg": True,
        "wheelOnly": True,
    }

    request = urllib.request.Request(
        f"{ENGINE}/v1/natal",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        print("Motor hata döndü:", exc.read().decode()[:400])
        return 1
    except urllib.error.URLError as exc:
        print(f"Motora ulaşılamadı ({ENGINE}). Çalışıyor mu?\n  {exc.reason}")
        return 1

    OUTPUT.write_text(render(data), encoding="utf-8")
    print(f"Yazıldı: {OUTPUT}")
    webbrowser.open(OUTPUT.as_uri())
    return 0


def rows(items: list[dict], columns: list[tuple[str, str]]) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for label, _ in columns)
    body = ""

    for item in items:
        cells = ""
        for _, key in columns:
            value = item.get(key)
            if isinstance(value, float):
                value = f"{value:.4f}"
            elif isinstance(value, bool):
                value = "evet" if value else "—"
            cells += f"<td>{html.escape(str(value if value is not None else '—'))}</td>"
        body += f"<tr>{cells}</tr>"

    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render(data: dict) -> str:
    rt = data["resolvedTime"]
    meta = data["meta"]
    subject = data["subject"]

    debug = [
        ("Yerel", rt["localIso"]),
        ("UTC", rt["utcIso"]),
        ("Offset", f"{rt['utcOffsetHours']} saat"),
        ("Yaz saati", "EVET" if rt["isDst"] else "hayır"),
        ("Zaman dilimi", rt["timezone"]),
        ("Jülyen günü", rt["julianDay"]),
        ("Ev sistemi", meta["houseSystem"]),
        ("Zodyak", meta["zodiacType"]),
        ("Saat biliniyor", "evet" if meta["timeKnown"] else "HAYIR"),
        ("Motor", f"{meta['engine']} {meta['engineVersion']}"),
    ]

    warnings = "".join(
        f"<p class='warn'>{html.escape(w)}</p>" for w in data.get("warnings", [])
    )

    big = data["bigThree"]

    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<title>Natal önizleme — {html.escape(subject['displayName'])}</title>
<style>
  body {{ font: 15px/1.6 system-ui, sans-serif; max-width: 1100px; margin: 2rem auto;
         padding: 0 1.5rem; color: #111; }}
  h1 {{ font-size: 1.6rem; margin-bottom: .25rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2.5rem; border-bottom: 1px solid #ddd;
        padding-bottom: .35rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; margin-top: .5rem; }}
  th, td {{ text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #eee; }}
  th {{ color: #666; font-weight: 600; }}
  td {{ font-variant-numeric: tabular-nums; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 2rem; }}
  .big {{ display: flex; gap: 2rem; margin: 1rem 0; }}
  .big div {{ background: #f6f6f6; padding: .75rem 1.25rem; border-radius: 8px; }}
  .big span {{ display: block; color: #666; font-size: 13px; }}
  .warn {{ background: #fff4e5; border-left: 3px solid #d68000; padding: .6rem .9rem;
           margin: 1rem 0; }}
  .chart {{ max-width: 760px; margin: 1rem 0; }}
  .chart svg {{ width: 100%; height: auto; }}
  details {{ margin-top: 2rem; }}
  pre {{ background: #f6f6f6; padding: 1rem; overflow: auto; font-size: 12px;
         max-height: 400px; }}
</style></head><body>

<h1>{html.escape(subject['displayName'])}</h1>
<p>{html.escape(subject['placeLabel'])} · {subject['latitude']:.4f}, {subject['longitude']:.4f}</p>

{warnings}

<div class="big">
  <div><span>Güneş</span><strong>{html.escape(big['sun'])}</strong></div>
  <div><span>Ay</span><strong>{html.escape(big['moon'])}</strong></div>
  <div><span>Yükselen</span><strong>{html.escape(big['ascendant'])}</strong></div>
</div>

<h2>Çark</h2>
<div class="chart">{data.get('svg') or '<p>SVG istenmedi.</p>'}</div>

<h2>Debug — saat dilimi çözümü</h2>
{rows([{ 'k': k, 'v': v } for k, v in debug], [('Alan', 'k'), ('Değer', 'v')])}

<div class="grid">
  <div>
    <h2>Gezegenler</h2>
    {rows(data['planets'], [('Planet', 'name'), ('Sign', 'sign'),
                            ('Degree', 'degreeInSign'), ('House', 'house'), ('R', 'retrograde')])}
    <h2>Eksenler</h2>
    {rows(data['axes'], [('Point', 'name'), ('Sign', 'sign'), ('Degree', 'degreeInSign')])}
  </div>
  <div>
    <h2>Evler</h2>
    {rows(data['houses'], [('House', 'number'), ('Sign', 'sign'), ('Degree', 'degreeInSign')])}
  </div>
</div>

<h2>Açılar ({len(data['aspects'])})</h2>
{rows(sorted(data['aspects'], key=lambda a: a['orb'])[:20],
      [('', 'p1'), ('Aspect', 'aspect'), ('', 'p2'), ('Orb', 'orb'), ('Applying', 'applying')])}
<p style="color:#666;font-size:13px">Orb'a göre en yakın 20 açı gösteriliyor.</p>

<h2>Dağılımlar</h2>
<div class="grid">
  <div>{rows([{'k': k, 'v': f"%{v:.0f}"} for k, v in data['distributions']['elements'].items()],
             [('Element', 'k'), ('Oran', 'v')])}</div>
  <div>{rows([{'k': k, 'v': f"%{v:.0f}"} for k, v in data['distributions']['modalities'].items()],
             [('Nitelik', 'k'), ('Oran', 'v')])}</div>
</div>

<details><summary>Ham JSON</summary>
<pre>{html.escape(json.dumps({k: v for k, v in data.items() if k != 'svg'},
                        indent=2, ensure_ascii=False))}</pre></details>

<details><summary>LLM bağlamı (llmContext)</summary>
<pre>{html.escape(data['llmContext'])}</pre></details>

</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
