"""2026 KBO Defensive Awards carousel: cover + all 10 winners on the field (utility next to home plate)."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import MARGIN, ON_DARK, PETROL_DEEP, PETROL_LINE, RED, ROOT, WHITE, W, H, draw_chevrons, draw_footer, font
from standings import league_tile  # noqa: E402
from tools.potw_post import GOLD, gold_text  # noqa: E402
from tools import npb_gg_post as F  # noqa: E402

A = ROOT / "assets" / "kbo-def-2026"
KBO = {l["key"]: l for l in bot.CFG["standings"]["leagues"]}["kbo"]
WINNERS = [("P", "Kwak Bin", "Doosan"), ("C", "Heo In-seo", "Hanwha"), ("1B", "Austin Dean", "LG"),
           ("2B", "Jung Jun-jae", "SSG"), ("3B", "Kim Do-yeong", "KIA"), ("SS", "Park Seong-han", "SSG"),
           ("LF", "Guillermo Heredia", "SSG"), ("CF", "Park Hae-min", "LG"), ("RF", "Kim Seong-yoon", "Samsung"),
           ("UT", "Koo Bon-hyeok", "LG")]
POS = dict(F.POS, UT=(225, 1080))
WESTERN = {"Austin Dean", "Guillermo Heredia"}


def avatar(canvas, d, cx, cy, pos, name, team, size=112):
    slug = "-".join(name.lower().split())
    im = Image.open(A / f"{slug}.jpg").convert("RGBA")
    im = im.resize((size, int(im.height * size / im.width)), Image.LANCZOS).crop((0, 0, size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    x0, y0 = int(cx - size / 2), int(cy - size / 2 - 30)
    d.ellipse([x0 - 6, y0 - 6, x0 + size + 5, y0 + size + 5], fill=GOLD)
    canvas.paste(im, (x0, y0), mask)
    f_pos = font("oswald-700", 26)
    pw = d.textlength(pos, font=f_pos) + 18
    d.rounded_rectangle([x0 + size - pw + 14, y0 - 4, x0 + size + 14, y0 + 30], radius=8, fill=RED)
    d.text((x0 + size - pw / 2 + 14, y0 + 13), pos, font=f_pos, fill=WHITE, anchor="mm")
    # Korean names: family name first, show the full name; Western names: surname big, first name small
    if name in WESTERN:
        first, big = name.split(" ", 1)
        sub = f"{first.upper()} · {team.upper()}"
    else:
        big, sub = name, team.upper()
    ty = y0 + size + 12
    f_big = font("oswald-700", 30)
    f_sub = font("figtree-800", 17)
    bw = max(d.textlength(big.upper(), font=f_big), d.textlength(sub, font=f_sub)) + 24
    d.rounded_rectangle([cx - bw / 2, ty, cx + bw / 2, ty + 62], radius=10, fill=PETROL_DEEP + (235,))
    d.text((cx, ty + 22), big.upper(), font=f_big, fill=WHITE, anchor="mm")
    d.text((cx, ty + 50), sub, font=f_sub, fill=GOLD, anchor="mm")


def field_slide(out):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    F.field(canvas)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), "2026 KBO DEFENSIVE AWARDS", font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    d.text((MARGIN, 136), "ALL 10 WINNERS", font=font("oswald-700", 84), fill=WHITE)
    league_tile(canvas, d, KBO, W - MARGIN - 110, 70, 110)
    for pos, name, team in WINNERS:
        avatar(canvas, d, *POS[pos], pos, name, team)
    draw_footer(d, H - 132, "FULL STORY · LINK IN BIO")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


def cover(out):
    im = Image.open(A / "cover.jpg").convert("RGB")
    cw = int(im.height * 4 / 5)
    im = im.crop((0, 0, cw, im.height)).resize((W, H), Image.LANCZOS)
    canvas = im.convert("RGBA")
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for y in range(H):
        t = max(0.0, (y - H * 0.35) / (H * 0.65))
        if t:
            gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(255 * min(1, t ** 0.8 * 1.1)),))
    for y in range(0, 260):
        gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(170 * (1 - y / 260) ** 1.4),))
    canvas.alpha_composite(g)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), "KBO · NOVEMBER 18, 2026", font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    league_tile(canvas, d, KBO, W - MARGIN - 110, 70, 110)
    base = 900
    d.text((MARGIN, base - 150), "2026 KBO", font=font("oswald-700", 84), fill=WHITE, anchor="ls")
    size = 150
    while d.textlength("DEFENSIVE AWARDS", font=font("oswald-700", size)) > W - 2 * MARGIN:
        size -= 4
    gold_text(canvas, (MARGIN - 4, base), "DEFENSIVE AWARDS", font("oswald-700", size), anchor="ls")
    d.text((MARGIN, base + 60), "The KBO's best defenders, position by position.", font=font("figtree-700", 34),
           fill=ON_DARK, anchor="ls")
    stats = [("10", "WINNERS"), ("3", "SSG LANDERS"), ("4", "IN A ROW: HEREDIA")]
    cw2 = (W - 2 * MARGIN) / 3
    sy = base + 110
    for i, (v, lab) in enumerate(stats):
        cx = MARGIN + i * cw2
        if i:
            d.line([(cx, sy + 10), (cx, sy + 100)], fill=PETROL_LINE, width=2)
        tx = cx + (24 if i else 0)
        d.text((tx, sy + 76), v, font=font("oswald-700", 80), fill=WHITE, anchor="ls")
        d.text((tx + 2, sy + 110), lab, font=font("figtree-800", 22), fill=GOLD, anchor="ls")
    draw_footer(d, H - 132, "SWIPE FOR ALL WINNERS")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "posts"
    out.mkdir(parents=True, exist_ok=True)
    cover(out / "kbo-def-2026-1.jpg")
    field_slide(out / "kbo-def-2026-2.jpg")
    print("ok")
