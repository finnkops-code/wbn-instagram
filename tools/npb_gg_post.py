"""2026 NPB Golden Glove carousel: cover + one baseball-field slide per league with every winner at his position."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, ROOT, WHITE, W, H,
                 draw_chevrons, draw_footer, font)
from standings import league_tile  # noqa: E402
from tools.potw_post import GOLD, gold_text  # noqa: E402

A = ROOT / "assets" / "npb-gg-2026"
NPB = {l["key"]: l for l in bot.CFG["standings"]["leagues"]}["npb"]
LEAGUES = {
    "CENTRAL LEAGUE": [
        ("P", "Katsuki Azuma", "DeNA"), ("C", "Seishiro Sakamoto", "Hanshin"), ("1B", "Yusuke Oyama", "Hanshin"),
        ("2B", "Takumu Nakano", "Hanshin"), ("3B", "Teruaki Sato", "Hanshin"), ("SS", "Yuta Izuguchi", "Giants"),
        ("LF", "Shota Morishita", "Hanshin"), ("CF", "Go Matsumoto", "Giants"), ("RF", "Ryuki Watarai", "DeNA")],
    "PACIFIC LEAGUE": [
        ("P", "Kaima Taira", "Seibu"), ("C", "Kenya Wakatsuki", "Orix"), ("1B", "Tyler Nevin", "Seibu"),
        ("2B", "Ryusei Ogawa", "Lotte"), ("3B", "Yuma Mune", "Orix"), ("SS", "Kotaro Kurebayashi", "Orix"),
        ("LF", "Ukyo Shuto", "SoftBank"), ("CF", "Ryosuke Tatsumi", "Rakuten"), ("RF", "Kyota Fujiwara", "Lotte")],
}
HOME = (540, 1200)
POS = {"P": (540, 850), "C": (540, 1080), "1B": (860, 840), "2B": (695, 650), "SS": (385, 650), "3B": (220, 840),
       "LF": (200, 470), "CF": (540, 365), "RF": (880, 470)}
GRASS = (9, 62, 86)
DIRT = (24, 84, 108)


def header(canvas, d, kicker, title):
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), kicker, font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    d.text((MARGIN, 136), title, font=font("oswald-700", 84), fill=WHITE)
    league_tile(canvas, d, NPB, W - MARGIN - 110, 70, 110)


def field(canvas):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    R = 900
    hx, hy = HOME
    d.pieslice([hx - R, hy - R, hx + R, hy + R], 225, 315, fill=GRASS + (255,))
    d.pieslice([hx - 520, hy - 520, hx + 520, hy + 520], 225, 315, fill=DIRT + (255,))
    s = 235  # base distance in px
    b1, b2, b3 = (hx + s, hy - s), (hx, hy - 2 * s), (hx - s, hy - s)
    d.polygon([(hx, hy - 34), (b1[0] - 34, b1[1]), (b2[0], b2[1] + 34), (b3[0] + 34, b3[1])], fill=GRASS + (255,))
    d.ellipse([hx - 70, hy - 70, hx + 70, hy + 70], fill=DIRT + (255,))
    line = (255, 255, 255, 120)
    d.line([HOME, (hx + 760, hy - 760)], fill=line, width=4)
    d.line([HOME, (hx - 760, hy - 760)], fill=line, width=4)
    d.arc([hx - R, hy - R, hx + R, hy + R], 225, 315, fill=(255, 255, 255, 60), width=4)
    for bx, by in (b1, b2, b3):
        d.rectangle([bx - 11, by - 11, bx + 11, by + 11], fill=(255, 255, 255, 230))
    d.polygon([(hx - 11, hy - 6), (hx + 11, hy - 6), (hx + 11, hy + 6), (hx, hy + 14), (hx - 11, hy + 6)],
              fill=(255, 255, 255, 230))
    d.ellipse([hx - 30, hy - s - 30, hx + 30, hy - s + 30], fill=DIRT + (255,), outline=(255, 255, 255, 50))
    canvas.alpha_composite(lay)


def avatar(canvas, d, cx, cy, pos, name, team, size=112):
    slug = "-".join(name.lower().split())
    im = Image.open(A / f"{slug}.jpg").convert("RGBA")
    k = size / im.width
    im = im.resize((size, int(im.height * k)), Image.LANCZOS).crop((0, 0, size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    x0, y0 = int(cx - size / 2), int(cy - size / 2 - 30)
    d.ellipse([x0 - 6, y0 - 6, x0 + size + 5, y0 + size + 5], fill=GOLD)
    canvas.paste(im, (x0, y0), mask)
    # position badge
    f_pos = font("oswald-700", 26)
    pw = d.textlength(pos, font=f_pos) + 18
    d.rounded_rectangle([x0 + size - pw + 14, y0 - 4, x0 + size + 14, y0 + 30], radius=8, fill=RED)
    d.text((x0 + size - pw / 2 + 14, y0 + 13), pos, font=f_pos, fill=WHITE, anchor="mm")
    first, last = name.split(" ", 1)
    ty = y0 + size + 12
    f_last = font("oswald-700", 30)
    lw = d.textlength(last.upper(), font=f_last)
    bw = max(lw, d.textlength(f"{first.upper()} · {team.upper()}", font=font("figtree-800", 17))) + 24
    d.rounded_rectangle([cx - bw / 2, ty, cx + bw / 2, ty + 62], radius=10, fill=PETROL_DEEP + (235,))
    d.text((cx, ty + 22), last.upper(), font=f_last, fill=WHITE, anchor="mm")
    d.text((cx, ty + 50), f"{first.upper()} · {team.upper()}", font=font("figtree-800", 17), fill=GOLD, anchor="mm")


def league_slide(title, rows, out):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    field(canvas)
    d = ImageDraw.Draw(canvas)
    header(canvas, d, "2026 NPB GOLDEN GLOVE AWARDS", title)
    for pos, name, team in rows:
        avatar(canvas, d, *POS[pos], "OF" if pos in ("LF", "CF", "RF") else pos, name, team)
    draw_footer(d, H - 132, "FULL LIST · LINK IN BIO")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


def cover(out):
    im = Image.open(A / "cover.jpg").convert("RGB")
    cw = int(im.height * 4 / 5)
    left = max(0, min(im.width - cw, 470 - cw // 2))
    im = im.crop((left, 0, left + cw, im.height)).resize((W, H), Image.LANCZOS)
    canvas = im.convert("RGBA")
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for y in range(int(H * 0.35), H):
        t = max(0.0, (y - H * 0.35) / (H * 0.65))
        gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(255 * min(1, t ** 0.8 * 1.1)),))
    for y in range(0, 260):
        gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(170 * (1 - y / 260) ** 1.4),))
    canvas.alpha_composite(g)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), "NPB · NOVEMBER 11, 2026", font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    league_tile(canvas, d, NPB, W - MARGIN - 110, 70, 110)
    base = 900
    d.text((MARGIN, base - 150), "2026 NPB", font=font("oswald-700", 84), fill=WHITE, anchor="ls")
    gold_text(canvas, (MARGIN - 4, base), "GOLDEN GLOVES", font("oswald-700", 150), anchor="ls")
    d.text((MARGIN, base + 60), "NPB's best defenders, position by position.", font=font("figtree-700", 34),
           fill=ON_DARK, anchor="ls")
    stats = [("18", "WINNERS"), ("5", "HANSHIN"), ("3", "ORIX")]
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
    cover(out / "npb-gg-2026-1.jpg")
    league_slide("CENTRAL LEAGUE", LEAGUES["CENTRAL LEAGUE"], out / "npb-gg-2026-2.jpg")
    league_slide("PACIFIC LEAGUE", LEAGUES["PACIFIC LEAGUE"], out / "npb-gg-2026-3.jpg")
    print("ok")
