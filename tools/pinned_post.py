"""One-off pinned 'about' carousel: world map with every league we cover + an overview of all leagues."""
import json
import sys
from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT, RED_SOFT, ROOT,
                 WHITE, W, H, draw_chevrons, draw_footer, font)
from standings import draw_flags, fit_text  # noqa: E402

LEAGUES = json.loads((ROOT / "assets" / "leagues_geo.json").read_text(encoding="utf-8"))
FLAGS = {lg["key"]: lg.get("flags") for lg in bot.CFG["standings"]["leagues"]}
LAT_MAX, LAT_MIN = 74, -56  # same projection as the homepage map (1800 x 650)
LON_MIN, LON_MAX = -128, 160  # crop the empty Pacific edges so the map is bigger
LAT_TOP, LAT_BOTTOM = 66, -46
LABELS = {"mlb": "MLB", "npb": "NPB", "kbo": "KBO", "cpbl": "CPBL", "abl": "ABL", "lidom": "LIDOM", "lmb": "LMB",
          "lvbp": "LVBP", "hoofdklasse": "HOOFDKLASSE", "cpb": "CPB", "seriea": "SERIE A"}
LABEL_SIDE = {"cpb": "left", "kbo": "up", "npb": "right", "cpbl": "right", "abl": "right", "hoofdklasse": "left",
              "seriea": "down", "lidom": "right", "lvbp": "right", "lmb": "left", "lpb": "left", "apbn": "left",
              "mlb": "up"}


def kicker(draw, y, chip, eyebrow):
    x = draw_chevrons(draw, MARGIN, y + 6, RED_BRIGHT)
    f_chip = font("figtree-800", 28)
    lw = draw.textlength(chip, font=f_chip)
    draw.rounded_rectangle([x + 8, y - 6, x + 8 + lw + 32, y + 40], radius=8, fill=RED)
    draw.text((x + 24, y + 17), chip, font=f_chip, fill=WHITE, anchor="lm")
    if eyebrow:
        draw.text((x + 8 + lw + 32 + 18, y + 17), eyebrow, font=font("figtree-700", 26), fill=ON_DARK_2, anchor="lm")


def map_slide(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 6], fill=RED)
    kicker(draw, 84, "WORLD BASEBALL NEWS", "")
    f_big = font("oswald-700", 128)
    draw.text((MARGIN, 140), "EVERY LEAGUE.", font=f_big, fill=WHITE)
    draw.text((MARGIN, 284), "ONE HOME.", font=f_big, fill=RED_BRIGHT)
    draw.text((MARGIN, 462), "Daily news, standings and stats from pro baseball", font=font("figtree-500", 32),
              fill=ON_DARK)
    draw.text((MARGIN, 504), "on five continents — not just MLB.", font=font("figtree-500", 32), fill=ON_DARK)

    # map: render the homepage dot-map at high resolution, then crop to the inhabited part
    scale = 2.2
    svg = (ROOT / "assets" / "world.svg").read_bytes()
    full = Image.open(BytesIO(cairosvg.svg2png(bytestring=svg, output_width=int(1800 * scale)))).convert("RGBA")

    def px(lat, lon):  # homepage projection, in full-res pixels
        return ((lon + 180) / 360 * 1800 * scale, (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * 650 * scale)

    x0, y0 = px(LAT_TOP, LON_MIN)
    x1, y1 = px(LAT_BOTTOM, LON_MAX)
    crop = full.crop((int(x0), int(y0), int(x1), int(y1)))
    mw = W
    k = mw / crop.width
    mh = int(crop.height * k)
    crop = crop.resize((mw, mh), Image.LANCZOS)
    my = 590
    canvas.alpha_composite(crop, (0, my))

    def pos(lat, lon):
        x, y = px(lat, lon)
        return (x - x0) * k, my + (y - y0) * k

    # glow layer + dots
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for lg in LEAGUES:
        x, y = pos(*lg["geo"])
        gd.ellipse([x - 16, y - 16, x + 16, y + 16], fill=RED_BRIGHT + (110,))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))
    for lg in LEAGUES:
        x, y = pos(*lg["geo"])
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=RED_BRIGHT, outline=WHITE, width=2)

    # labels for the headline leagues
    f_lbl = font("oswald-600", 24)
    for key, text in LABELS.items():
        lg = next(l for l in LEAGUES if l["key"] == key)
        x, y = pos(*lg["geo"])
        tw = draw.textlength(text, font=f_lbl)
        bw, bh = tw + 18, 34
        side = LABEL_SIDE.get(key, "up")
        if side == "up":
            bx, by = x - bw / 2, y - 14 - bh
        elif side == "down":
            bx, by = x - bw / 2, y + 14
        elif side == "left":
            bx, by = x - 14 - bw, y - bh / 2
        else:
            bx, by = x + 14, y - bh / 2
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=4, fill=RED)
        draw.text((bx + bw / 2, by + bh / 2), text, font=f_lbl, fill=WHITE, anchor="mm")

    # key figures
    countries = set()
    for lg in bot.CFG["standings"]["leagues"]:
        countries.update(lg.get("flags") or [])
    stats = [(str(len(LEAGUES)), "LEAGUES"), (str(len(countries)), "COUNTRIES"), ("5", "CONTINENTS")]
    sy = my + mh + 34
    cw = (W - 2 * MARGIN) / 3
    for i, (num, lab) in enumerate(stats):
        cx = MARGIN + i * cw
        if i:
            draw.line([(cx, sy + 8), (cx, sy + 104)], fill=PETROL_LINE, width=2)
        tx = cx + (28 if i else 0)
        draw.text((tx, sy), num, font=font("oswald-700", 84), fill=WHITE)
        draw.text((tx + draw.textlength(num, font=font("oswald-700", 84)) + 14, sy + 74), lab,
                  font=font("figtree-800", 26), fill=RED_SOFT, anchor="ls")
    draw_footer(draw, H - 132, "SWIPE FOR ALL LEAGUES")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, "JPEG", quality=93)


GROUPS = [
    ("USA & CANADA", ["mlb", "afl", "il", "pcl", "eastern", "southern", "texas", "sally", "midwest", "northwest",
                      "carolina", "fsl", "california", "atlantic", "aapb", "frontier", "cbl"]),
    ("LATIN AMERICA", ["lmb", "lmp", "lidom", "lvbp", "lbprc", "lpb", "apbn"]),
    ("ASIA & OCEANIA", ["npb", "npbfarm", "kbo", "cpbl", "cpb", "abl"]),
    ("EUROPE", ["hoofdklasse", "dbl", "seriea", "extraliga", "d1", "dhb", "belgium", "austria", "nla", "elitserien",
                "nbl"]),
]
COLUMNS = [[0], [1, 2], [3]]
NICE = {"lpb": "Colombian League", "aapb": "American Association", "atlantic": "Atlantic League",
        "lvbp": "Venezuelan League", "lbprc": "Puerto Rico League",
        "lidom": "Dominican League", "lmp": "Mexican Pacific League", "lmb": "Mexican League",
        "apbn": "Nicaraguan League", "nbl": "British NBL", "cpbl": "CPBL Taiwan",
        "cpb": "Chinese Pro Baseball", "kbo": "KBO League", "npb": "Nippon Pro Baseball", "npbfarm": "NPB Farm League",
        "abl": "Australian League", "mlb": "Major League Baseball", "afl": "Arizona Fall League",
        "il": "International League", "pcl": "Pacific Coast League", "cbl": "Canadian League",
        "hoofdklasse": "Hoofdklasse Honkbal", "dbl": "German Bundesliga", "seriea": "Italian Serie A",
        "extraliga": "Czech Extraliga", "d1": "French Division 1", "dhb": "Spanish League",
        "belgium": "Belgian D1", "austria": "Austrian Bundesliga", "nla": "Swiss NLA", "elitserien": "Swedish Elitserien"}


def list_slide(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 6], fill=RED)
    kicker(draw, 84, "OUR LEAGUES", f"{len(LEAGUES)} LEAGUE HUBS")
    draw.text((MARGIN, 140), "WHERE WE COVER", font=font("oswald-700", 92), fill=WHITE)
    by_key = {l["key"]: l for l in LEAGUES}
    gap = 26
    cw = (W - 2 * MARGIN - 2 * gap) / 3
    top, bottom = 290, H - 132 - 26
    names = [NICE.get(k, by_key[k]["name"]).upper() for _, ks in GROUPS for k in ks]
    size = 27
    while size > 18 and any(draw.textlength(n, font=font("oswald-600", size)) > cw - 40 for n in names):
        size -= 1
    f_name = font("oswald-600", size)
    units = max(sum(len(GROUPS[g][1]) + 1.3 for g in col) for col in COLUMNS)
    row_h = (bottom - top) / units
    for ci, col in enumerate(COLUMNS):
        x = MARGIN + ci * (cw + gap)
        y = top
        for g in col:
            name, keys = GROUPS[g]
            draw.text((x, y + row_h * 0.75), name, font=font("figtree-800", 22), fill=RED_SOFT, anchor="ls")
            draw.line([(x, y + row_h * 1.0), (x + cw, y + row_h * 1.0)], fill=PETROL_LINE, width=2)
            y += row_h * 1.3
            for key in keys:
                lg = by_key[key]
                cy = y + row_h / 2
                codes = FLAGS.get(key) or []
                if len(codes) == 2:  # US & Canada: two small flags stacked
                    draw_flags(canvas, draw, x + 4, cy - 9, codes[:1], h=16)
                    draw_flags(canvas, draw, x + 4, cy + 9, codes[1:], h=16)
                else:
                    draw_flags(canvas, draw, x, cy, codes, h=22)
                fx = x + 40
                text = NICE.get(key, lg["name"]).upper()
                draw.text((fx, cy), text, font=f_name, fill=WHITE, anchor="lm")
                y += row_h
    draw_footer(draw, H - 132, "FOLLOW FOR DAILY NEWS")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "posts"
    map_slide(out / "wbn-every-league-1.jpg")
    list_slide(out / "wbn-every-league-2.jpg")
    print("ok")
