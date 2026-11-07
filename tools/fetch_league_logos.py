"""One-off helper (runs in GitHub Actions, which has open internet): download each league's logo
from its Wikipedia infobox into league-logos/<key>.png. Review the result before use."""
import io, json, sys
from pathlib import Path
import requests, cairosvg
from PIL import Image

UA = {"User-Agent": "WBN-Instagram-Bot/1.0 (+https://worldbaseballnews.org; standings visuals)"}
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "league-logos"
OUT.mkdir(exist_ok=True)
TITLES = {
 "mlb": "Major League Baseball", "lmb": "Mexican League", "lidom": "Dominican Professional Baseball League",
 "lmp": "Mexican Pacific League", "lvbp": "Venezuelan Professional Baseball League",
 "lbprc": "Liga de Béisbol Profesional Roberto Clemente", "afl": "Arizona Fall League",
 "lpb": "Colombian Professional Baseball League", "il": "International League", "pcl": "Pacific Coast League",
 "eastern": "Eastern League (baseball)", "southern": "Southern League (baseball)", "texas": "Texas League",
 "sally": "South Atlantic League", "midwest": "Midwest League", "northwest": "Northwest League",
 "carolina": "Carolina League", "fsl": "Florida State League", "california": "California League",
 "atlantic": "Atlantic League of Professional Baseball", "aapb": "American Association of Professional Baseball",
 "frontier": "Frontier League", "cbl": "Canadian Baseball League", "apbn": "Nicaraguan Professional Baseball League",
 "hoofdklasse": "Honkbal Hoofdklasse", "dbl": "Baseball-Bundesliga", "seriea": "Italian Baseball League",
 "extraliga": "Czech Baseball Extraliga", "d1": "Division Élite (baseball)", "dhb": "División de Honor de Béisbol",
 "belgium": "Belgian Baseball League", "austria": "Austrian Baseball League", "nla": "Swiss Baseball and Softball Federation",
 "elitserien": "Elitserien (baseball)", "nbl": "National Baseball League (Great Britain)",
 "npb": "Nippon Professional Baseball", "npbfarm": "Nippon Professional Baseball",
 "cpbl": "Chinese Professional Baseball League", "cpb": "China Baseball League", "kbo": "KBO League",
 "abl": "Australian Baseball League",
}
API = "https://en.wikipedia.org/w/api.php"
report = {}
for key, title in TITLES.items():
    try:
        r = requests.get(API, params={"action": "query", "titles": title, "prop": "pageimages", "piprop": "original",
                                      "redirects": 1, "format": "json"}, headers=UA, timeout=30).json()
        page = next(iter(r["query"]["pages"].values()))
        src = (page.get("original") or {}).get("source")
        if not src:
            report[key] = f"NO IMAGE ({page.get('title')})"
            continue
        raw = requests.get(src, headers=UA, timeout=60).content
        if src.lower().endswith(".svg"):
            raw = cairosvg.svg2png(bytestring=raw, output_width=600)
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        im.thumbnail((512, 512), Image.LANCZOS)
        im.save(OUT / f"{key}.png")
        report[key] = f"{page.get('title')} -> {src}"
    except Exception as e:
        report[key] = f"ERROR {e}"
(OUT / "sources.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
for k, v in report.items():
    print(k, v)
