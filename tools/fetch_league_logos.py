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
LOCAL = {"lmb": "es", "lidom": "es", "lmp": "es", "lvbp": "es", "lbprc": "es", "lpb": "es", "apbn": "es", "dhb": "es",
         "hoofdklasse": "nl", "dbl": "de", "austria": "de", "seriea": "it", "extraliga": "cs", "d1": "fr", "belgium": "nl",
         "nla": "de", "elitserien": "sv", "npb": "ja", "npbfarm": "ja", "cpbl": "zh", "cpb": "zh", "kbo": "ko"}
from bs4 import BeautifulSoup


def api(lang, **params):
    return requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={**params, "format": "json"},
                        headers=UA, timeout=30).json()


def infobox_logo(lang, title):
    d = api(lang, action="parse", page=title, prop="text", section=0, redirects=1)
    html = (d.get("parse") or {}).get("text", {}).get("*")
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("table.infobox, table.infobox_v2, table.infobox_v3, table[class*=infobox], table.toccolours")
    imgs = (box or soup).find_all("img")
    imgs = [i for i in imgs if int(i.get("width") or 0) >= 60]
    pick = next((i for i in imgs if "logo" in (i.get("src", "") + i.get("alt", "")).lower()), None)
    pick = pick or (imgs[0] if box and imgs else None)
    if not pick:
        return None
    src = pick.get("src")
    if pick.get("srcset"):
        src = pick["srcset"].split(",")[-1].strip().split(" ")[0]
    return "https:" + src if src.startswith("//") else src


report = {}
for key, title in TITLES.items():
    tried = []
    try:
        src = infobox_logo("en", title)
        tried.append(("en", title))
        if not src and key in LOCAL:
            ll = api("en", action="query", titles=title, prop="langlinks", lllang=LOCAL[key], redirects=1)
            page = next(iter(ll["query"]["pages"].values()))
            links = page.get("langlinks") or []
            if links:
                lt = links[0]["*"]
                tried.append((LOCAL[key], lt))
                src = infobox_logo(LOCAL[key], lt)
        if not src:
            report[key] = f"NOT FOUND {tried}"
            continue
        raw = requests.get(src, headers=UA, timeout=60).content
        if src.split("?")[0].lower().endswith(".svg"):
            raw = cairosvg.svg2png(bytestring=raw, output_width=600)
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        im.thumbnail((512, 512), Image.LANCZOS)
        im.save(OUT / f"{key}.png")
        report[key] = f"{tried[-1]} -> {src}"
    except Exception as e:
        report[key] = f"ERROR {e} {tried}"
(OUT / "sources.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
for k, v in report.items():
    print(k, v)
