"""'Get to know' carousel: Teruaki Sato (6 slides).

Facts: worldbaseballnews.org articles (Oct 20, Nov 12, Nov 24, Nov 25 2026) and Wikipedia (early life, draft).
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT, ROOT, WHITE, W, H,
                 draw_chevrons, draw_footer, font, wrap)
import standings  # noqa: E402
from tools.potw_post import GOLD, gold_text  # noqa: E402

A = ROOT / "assets" / "sato-gtk"
N = 6
CUBS = "https://worldbaseballnews.org/team-logos/112.svg"
TIGERS = "https://worldbaseballnews.org/team-logos/npb-t.png"


def fit(im, w, h, fx=0.5, fy=0.35):
    k = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * k + 1), int(im.height * k + 1)), Image.LANCZOS)
    x, y = int((im.width - w) * fx), int((im.height - h) * fy)
    return im.crop((x, y, x + w, y + h))


def base():
    c = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([600, -300, 1500, 600], fill=PETROL_MID + (200,))
    c.alpha_composite(g.filter(ImageFilter.GaussianBlur(120)))
    return c


def fade(canvas, y0, y1, a0=0, a1=255):
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for y in range(int(y0), int(y1)):
        t = (y - y0) / (y1 - y0)
        gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(a0 + (a1 - a0) * t ** 1.2),))
    gd.rectangle([0, y1, W, H], fill=PETROL_DEEP + (a1,))
    canvas.alpha_composite(g)


def header(canvas, d, i, title):
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 82, GOLD)
    d.text((x + 10, 83), "GET TO KNOW · TERUAKI SATO", font=font("figtree-800", 22), fill=GOLD, anchor="lm")
    d.text((W - MARGIN, 83), f"{i:02d} / {N:02d}", font=font("oswald-600", 26), fill=ON_DARK_2, anchor="rm")
    d.text((MARGIN, 118), title, font=font("oswald-700", 82), fill=WHITE)


def team_chip(canvas, d, x, y, url, label, size=58):
    d.ellipse([x, y, x + size, y + size], fill=WHITE)
    lg = standings.logo(url, size - 14)
    if lg is not None:
        canvas.alpha_composite(lg, (int(x + size / 2 - lg.width / 2), int(y + size / 2 - lg.height / 2)))
    d.text((x + size + 14, y + size / 2), label, font=font("figtree-800", 24), fill=WHITE, anchor="lm")
    return x + size + 14 + d.textlength(label, font=font("figtree-800", 24))


# --------------------------------------------------------------------------- 1. cover
def s1(out):
    im = Image.open(A / "japan.jpg").convert("RGB")
    canvas = fit(im, W, H, fx=0.62, fy=0.2).convert("RGBA")
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    for y in range(240):
        td.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(180 * (1 - y / 240) ** 1.4),))
    canvas.alpha_composite(top)
    fade(canvas, H * 0.46, H * 0.80)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 82, GOLD)
    d.text((x + 10, 83), "PLAYER PROFILE", font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    f_k = font("figtree-800", 30)
    lab = "GET TO KNOW"
    lw = d.textlength(lab, font=f_k)
    d.rounded_rectangle([MARGIN, 742, MARGIN + lw + 36, 794], radius=10, fill=RED)
    d.text((MARGIN + 18, 768), lab, font=f_k, fill=WHITE, anchor="lm")
    d.text((MARGIN - 4, 930), "TERUAKI", font=font("oswald-700", 130), fill=WHITE, anchor="ls")
    gold_text(canvas, (MARGIN - 6, 1080), "SATO", font("oswald-700", 172), anchor="ls")
    d = ImageDraw.Draw(canvas)
    d.text((MARGIN, 1130), "Japan's Triple Crown slugger is heading to Chicago.",
           font=font("figtree-700", 32), fill=ON_DARK, anchor="ls")
    draw_footer(d, H - 132, "SWIPE TO MEET HIM")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


# --------------------------------------------------------------------------- 2. the basics
def s2(out):
    canvas = base()
    ph = fit(Image.open(A / "portrait.jpg").convert("RGB"), 420, 560, fy=0.15)
    m = Image.new("L", ph.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, ph.width - 1, ph.height - 1], radius=22, fill=255)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([W - MARGIN - 426, 238, W - MARGIN + 6, 238 + 566], radius=25, fill=GOLD)
    canvas.paste(ph, (W - MARGIN - 423, 241), m)
    header(canvas, d, 2, "THE BASICS")
    rows = [("BORN", "March 13, 1999"), ("HOMETOWN", "Nishinomiya, Hyōgo"), ("AGE", "27"),
            ("BATS / THROWS", "Left / Right"), ("POSITION", "3B · Corner OF"), ("JERSEY", "No. 8 (Hanshin)")]
    y = 250
    for k, v in rows:
        d.text((MARGIN, y), k, font=font("figtree-800", 20), fill=GOLD)
        d.text((MARGIN, y + 28), v, font=font("oswald-700", 42), fill=WHITE)
        y += 92
    # career path strip
    y = 860
    d.line([(MARGIN, y), (W - MARGIN, y)], fill=PETROL_LINE, width=2)
    d.text((MARGIN, y + 34), "2021–2026", font=font("figtree-800", 20), fill=GOLD)
    team_chip(canvas, d, MARGIN, y + 66, TIGERS, "HANSHIN TIGERS")
    d.text((W / 2 + 40, y + 34), "FROM 2027", font=font("figtree-800", 20), fill=GOLD)
    team_chip(canvas, d, W / 2 + 40, y + 66, CUBS, "CHICAGO CUBS")
    d.polygon([(W / 2 - 20, y + 82), (W / 2 + 4, y + 95), (W / 2 - 20, y + 108)], fill=GOLD)
    d.rounded_rectangle([MARGIN, y + 162, W - MARGIN, y + 244], radius=14, fill=PETROL_MID)
    d.text((W / 2, y + 203), "6 YEARS · $120 MILLION", font=font("oswald-700", 46), fill=GOLD, anchor="mm")
    draw_footer(d, H - 132, "KEEP SWIPING")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


# --------------------------------------------------------------------------- 3. 2026 in numbers
def s3(out):
    canvas = base()
    ph = fit(Image.open(A / "swing.jpg").convert("RGB"), W, 520, fx=0.55, fy=0.25).convert("RGBA")
    canvas.alpha_composite(ph, (0, 0))
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for y in range(0, 230):
        gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(200 * (1 - y / 230) ** 1.3),))
    for y in range(300, 520):
        gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(255 * ((y - 300) / 220) ** 1.2),))
    canvas.alpha_composite(g)
    d = ImageDraw.Draw(canvas)
    header(canvas, d, 3, "2026 BY THE NUMBERS")
    d.text((MARGIN, 520), "THE TRIPLE CROWN", font=font("figtree-800", 24), fill=GOLD)
    big = [(".306", "AVG"), ("39", "HOME RUNS"), ("106", "RBI")]
    cw = (W - 2 * MARGIN) / 3
    for i, (v, lab) in enumerate(big):
        cx = MARGIN + i * cw
        if i:
            d.line([(cx, 580), (cx, 730)], fill=PETROL_LINE, width=2)
        tx = cx + (28 if i else 0)
        gold_text(canvas, (tx, 700), v, font("oswald-700", 120), anchor="ls")
        d = ImageDraw.Draw(canvas)
        d.text((tx + 2, 736), lab, font=font("figtree-800", 22), fill=WHITE, anchor="ls")
    d.text((MARGIN, 790), "Led the Central League in all three. Only the 9th Triple Crown in NPB history.",
           font=font("figtree-700", 24), fill=ON_DARK)
    small = [("165", "HITS"), ("100", "RUNS"), ("40", "DOUBLES"), (".383", "OBP"), (".609", "SLG"), ("143", "GAMES")]
    tw_ = (W - 2 * MARGIN - 2 * 16) / 3
    for i, (v, lab) in enumerate(small):
        x0 = MARGIN + (i % 3) * (tw_ + 16)
        y0 = 860 + (i // 3) * 150
        d.rounded_rectangle([x0, y0, x0 + tw_, y0 + 134], radius=14, fill=PETROL_MID)
        d.text((x0 + 24, y0 + 74), v, font=font("oswald-700", 58), fill=WHITE, anchor="ls")
        d.text((x0 + 26, y0 + 110), lab, font=font("figtree-800", 19), fill=GOLD, anchor="ls")
    draw_footer(d, H - 132, "KEEP SWIPING")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


# --------------------------------------------------------------------------- 4. trophy cabinet
def s4(out):
    canvas = base()
    d = ImageDraw.Draw(canvas)
    header(canvas, d, 4, "TROPHY CABINET")
    items = [("2×", "CENTRAL LEAGUE MVP", "2025 and 2026, back to back"),
             ("1ST", "SHIGEO NAGASHIMA AWARD", "The inaugural winner, picked by a panel led by Sadaharu Oh"),
             ("9TH", "NPB TRIPLE CROWN", "Ninth in NPB history, a first for a Japanese Tiger"),
             ("2×", "GOLDEN GLOVE AT 3B", "2025 and 2026"),
             ("2023", "JAPAN SERIES CHAMPION", "With the Hanshin Tigers"),
             ("5×", "NPB ALL-STAR", "2021–23, 2025, 2026")]
    y = 250
    for big, title, sub in items:
        d.rounded_rectangle([MARGIN, y, W - MARGIN, y + 124], radius=16, fill=PETROL_MID)
        d.rounded_rectangle([MARGIN, y, MARGIN + 170, y + 124], radius=16, fill=GOLD)
        d.rectangle([MARGIN + 150, y, MARGIN + 170, y + 124], fill=GOLD)
        size = 62 if len(big) <= 3 else 50
        d.text((MARGIN + 85, y + 62), big, font=font("oswald-700", size), fill=PETROL_DEEP, anchor="mm")
        d.text((MARGIN + 200, y + 46), title, font=font("oswald-700", 38), fill=WHITE, anchor="lm")
        d.text((MARGIN + 202, y + 90), sub, font=font("figtree-700", 21), fill=ON_DARK, anchor="lm")
        y += 140
    draw_footer(d, H - 132, "KEEP SWIPING")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


# --------------------------------------------------------------------------- 5. fun facts
def s5(out):
    canvas = base()
    d = ImageDraw.Draw(canvas)
    header(canvas, d, 5, "5 THINGS YOU DIDN'T KNOW")
    facts = [
        "Four teams took him in the first round of the 2020 draft. Hanshin won him in a lottery.",
        "His father was a national judo champion.",
        "He nearly joined his junior high soccer club, until a friend talked him into baseball.",
        "He grew up in Nishinomiya, home of Koshien, and played for the Hanshin Tigers Juniors as a sixth grader.",
        "In 2021 he became the first NPB rookie in 63 years to hit three home runs in one game.",
    ]
    f = font("figtree-800", 34)
    y = 260
    for i, t in enumerate(facts, 1):
        lines = wrap(d, t, f, W - 2 * MARGIN - 130)
        h = 44 + len(lines) * 46 + 26
        d.rounded_rectangle([MARGIN, y, W - MARGIN, y + h], radius=16, fill=PETROL_MID)
        d.text((MARGIN + 30, y + 30), f"{i:02d}", font=font("oswald-700", 60), fill=GOLD)
        for j, ln in enumerate(lines):
            d.text((MARGIN + 124, y + 36 + j * 46), ln, font=f, fill=WHITE)
        y += h + 20
    draw_footer(d, H - 132, "KEEP SWIPING")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


# --------------------------------------------------------------------------- 6. scouting report
def s6(out):
    canvas = base()
    ph = fit(Image.open(A / "bases.jpg").convert("RGB"), W, H, fx=0.5, fy=0.2).convert("RGBA")
    canvas.alpha_composite(ph)
    g = Image.new("RGBA", (W, H), PETROL_DEEP + (150,))
    canvas.alpha_composite(g)
    fade(canvas, 300, 640, 0, 245)
    d = ImageDraw.Draw(canvas)
    header(canvas, d, 6, "WHAT CUBS FANS GET")
    rows = [("+", "ELITE LEFT-HANDED POWER", "163 home runs in six NPB seasons, 79 in the last two"),
            ("+", "BUILT TO PLAY EVERY DAY", "120+ games in every season; all 143 in 2026"),
            ("+", "BIG-GAME EXPERIENCE", "Japan Series champion, 2026 WBC with Samurai Japan"),
            ("–", "THE QUESTION MARK", "Swing-and-miss: about a 27% strikeout rate in 2025–26")]
    y = 560
    for sign, t, sub in rows:
        good = sign == "+"
        d.ellipse([MARGIN, y, MARGIN + 64, y + 64], fill=GOLD if good else RED)
        d.text((MARGIN + 32, y + 30), sign, font=font("oswald-700", 50), fill=PETROL_DEEP if good else WHITE,
               anchor="mm")
        d.text((MARGIN + 92, y + 4), t, font=font("oswald-700", 40), fill=WHITE)
        d.text((MARGIN + 94, y + 58), sub, font=font("figtree-700", 24), fill=ON_DARK)
        y += 128
    draw_footer(d, H - 132, "FOLLOW FOR MORE")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "posts"
    out.mkdir(parents=True, exist_ok=True)
    for i, fn in enumerate([s1, s2, s3, s4, s5, s6], 1):
        fn(out / f"sato-gtk-{i}.jpg")
    print("ok")
