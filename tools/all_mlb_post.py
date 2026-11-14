"""2026 All-MLB Team carousel: cover + per team a field slide (position players + DH) and a pitching-staff slide."""
import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, ROOT, WHITE, W, H,
                 draw_chevrons, draw_footer, font)
from standings import league_tile  # noqa: E402
from tools.potw_post import GOLD, gold_text  # noqa: E402
from tools import npb_gg_post as F  # noqa: E402

A = ROOT / "assets" / "all-mlb-2026"
MLB = {l["key"]: l for l in bot.CFG["standings"]["leagues"]}["mlb"]
TEAMS = {
    "FIRST TEAM": {
        "field": [("C", "Gabriel Moreno", "D-backs"), ("1B", "Pete Alonso", "Orioles"), ("2B", "Brice Turang", "Brewers"),
                  ("3B", "Junior Caminero", "Rays"), ("SS", "Bobby Witt Jr.", "Royals"),
                  ("LF", "Jackson Chourio", "Brewers"), ("CF", "Pete Crow-Armstrong", "Cubs"),
                  ("RF", "Fernando Tatis Jr.", "Padres"), ("DH", "Yordan Alvarez", "Astros")],
        "sp": [("Jacob Misiorowski", "Brewers"), ("Cam Schlittler", "Yankees"), ("Chris Sale", "Braves"),
               ("Dylan Cease", "Blue Jays"), ("Cristopher Sánchez", "Phillies")],
        "rp": [("Mason Miller", "Padres"), ("Louis Varland", "Blue Jays")]},
    "SECOND TEAM": {
        "field": [("C", "William Contreras", "Brewers"), ("1B", "Willson Contreras", "Red Sox"),
                  ("2B", "Brandon Lowe", "Pirates"), ("3B", "Alex Bregman", "Cubs"), ("SS", "Elly De La Cruz", "Reds"),
                  ("LF", "Randy Arozarena", "Mariners"), ("CF", "James Wood", "Nationals"),
                  ("RF", "Jordan Walker", "Cardinals"), ("DH", "Ben Rice", "Yankees")],
        "sp": [("Yoshinobu Yamamoto", "Dodgers"), ("Tarik Skubal", "Tigers/Dodgers"), ("Sonny Gray", "Red Sox"),
               ("Drew Rasmussen", "Rays"), ("Jesús Luzardo", "Phillies")],
        "rp": [("Bryan Baker", "Rays"), ("Cade Smith", "Guardians")]},
}
POS = dict(F.POS, DH=(225, 1080))


def slug(n):
    n = "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]+", "-", n.lower()).strip("-")


def head(name, size):
    im = Image.open(A / f"{slug(name)}.png").convert("RGBA")
    im = im.crop((0, 10, im.width, 10 + im.width))
    bg = Image.new("RGBA", im.size, (232, 232, 232, 255))
    bg.alpha_composite(im)
    return bg.resize((size, size), Image.LANCZOS)


def split_name(name):
    parts = name.split(" ")
    if parts[-1] in ("Jr.", "Sr.", "II", "III"):
        return " ".join(parts[:-2]), " ".join(parts[-2:])
    return parts[0], " ".join(parts[1:])


def avatar(canvas, d, cx, cy, pos, name, team, size=112):
    im = head(name, size)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    x0, y0 = int(cx - size / 2), int(cy - size / 2 - 30)
    d.ellipse([x0 - 6, y0 - 6, x0 + size + 5, y0 + size + 5], fill=GOLD)
    canvas.paste(im, (x0, y0), mask)
    if pos:
        f_pos = font("oswald-700", 26)
        pw = d.textlength(pos, font=f_pos) + 18
        d.rounded_rectangle([x0 + size - pw + 14, y0 - 4, x0 + size + 14, y0 + 30], radius=8, fill=RED)
        d.text((x0 + size - pw / 2 + 14, y0 + 13), pos, font=f_pos, fill=WHITE, anchor="mm")
    first, last = split_name(name)
    ty = y0 + size + 12
    f_last = font("oswald-700", 30 if size < 140 else 34)
    sub = f"{first.upper()} · {team.upper()}"
    f_sub = font("figtree-800", 17 if size < 140 else 19)
    bw = max(d.textlength(last.upper(), font=f_last), d.textlength(sub, font=f_sub)) + 24
    hgt = 62 if size < 140 else 70
    d.rounded_rectangle([cx - bw / 2, ty, cx + bw / 2, ty + hgt], radius=10, fill=PETROL_DEEP + (235,))
    d.text((cx, ty + hgt * 0.36), last.upper(), font=f_last, fill=WHITE, anchor="mm")
    d.text((cx, ty + hgt * 0.8), sub, font=f_sub, fill=GOLD, anchor="mm")


def header(canvas, d, title):
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), "2026 ALL-MLB TEAM", font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    size = 84
    while d.textlength(title, font=font("oswald-700", size)) > W - 2 * MARGIN - 140:
        size -= 2
    d.text((MARGIN, 136 + (84 - size) * 0.8), title, font=font("oswald-700", size), fill=WHITE)
    league_tile(canvas, d, MLB, W - MARGIN - 110, 70, 110)


def field_slide(team, out):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    F.field(canvas)
    d = ImageDraw.Draw(canvas)
    header(canvas, d, team)
    for pos, name, club in TEAMS[team]["field"]:
        avatar(canvas, d, *POS[pos], "OF" if pos in ("LF", "CF", "RF") else pos, name, club)
    draw_footer(d, H - 132, "SWIPE FOR THE PITCHERS")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


def staff_slide(team, out, last=False):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    d = ImageDraw.Draw(canvas)
    # faint mound
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse([W / 2 - 520, 380, W / 2 + 520, 1260], fill=F.GRASS + (255,))
    ImageDraw.Draw(lay).ellipse([W / 2 - 300, 560, W / 2 + 300, 1080], fill=F.DIRT + (160,))
    canvas.alpha_composite(lay)
    d = ImageDraw.Draw(canvas)
    header(canvas, d, f"{team} · PITCHERS")
    d.text((MARGIN, 290), "STARTING PITCHERS", font=font("figtree-800", 24), fill=GOLD)
    sp = TEAMS[team]["sp"]
    for i, (name, club) in enumerate(sp[:3]):
        avatar(canvas, d, 220 + i * 320, 430, "SP", name, club, size=130)
    for i, (name, club) in enumerate(sp[3:]):
        avatar(canvas, d, 380 + i * 320, 690, "SP", name, club, size=130)
    d.line([(MARGIN, 865), (W - MARGIN, 865)], fill=PETROL_LINE, width=2)
    d.text((MARGIN, 885), "RELIEF PITCHERS", font=font("figtree-800", 24), fill=GOLD)
    for i, (name, club) in enumerate(TEAMS[team]["rp"]):
        avatar(canvas, d, 380 + i * 320, 1020, "RP", name, club, size=130)
    draw_footer(d, H - 132, "FULL LIST · LINK IN BIO" if last else "SWIPE FOR THE SECOND TEAM")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


def cover(out):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    names = [n for t in TEAMS.values() for _, n, _ in t["field"]] + \
            [n for t in TEAMS.values() for n, _ in t["sp"] + t["rp"]]
    cols, size = 6, 180
    for i, n in enumerate(names[:36]):
        x, y = (i % cols) * size, (i // cols) * size + 6
        canvas.paste(head(n, size).convert("RGB"), (x, y))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(H):
        t = y / H
        a = int(110 + 145 * max(0.0, (t - 0.25) / 0.45)) if t > 0.25 else 110
        sd.line([(0, y), (W, y)], fill=PETROL_DEEP + (min(255, a),))
    canvas.alpha_composite(shade)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), "MLB · NOVEMBER 2026", font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    league_tile(canvas, d, MLB, W - MARGIN - 110, 70, 110)
    base = 900
    d.text((MARGIN, base - 156), "2026", font=font("oswald-700", 84), fill=WHITE, anchor="ls")
    gold_text(canvas, (MARGIN - 4, base), "ALL-MLB TEAM", font("oswald-700", 158), anchor="ls")
    d.text((MARGIN, base + 60), "The best players in baseball, position by position.", font=font("figtree-700", 34),
           fill=ON_DARK, anchor="ls")
    stats = [("32", "PLAYERS"), ("2", "TEAMS"), ("4", "BREWERS")]
    cw2 = (W - 2 * MARGIN) / 3
    sy = base + 110
    for i, (v, lab) in enumerate(stats):
        cx = MARGIN + i * cw2
        if i:
            d.line([(cx, sy + 10), (cx, sy + 100)], fill=PETROL_LINE, width=2)
        tx = cx + (24 if i else 0)
        d.text((tx, sy + 76), v, font=font("oswald-700", 80), fill=WHITE, anchor="ls")
        d.text((tx + 2, sy + 110), lab, font=font("figtree-800", 22), fill=GOLD, anchor="ls")
    draw_footer(d, H - 132, "SWIPE FOR BOTH TEAMS")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "posts"
    out.mkdir(parents=True, exist_ok=True)
    cover(out / "all-mlb-2026-1.jpg")
    field_slide("FIRST TEAM", out / "all-mlb-2026-2.jpg")
    staff_slide("FIRST TEAM", out / "all-mlb-2026-3.jpg")
    field_slide("SECOND TEAM", out / "all-mlb-2026-4.jpg")
    staff_slide("SECOND TEAM", out / "all-mlb-2026-5.jpg", last=True)
    print("ok")
