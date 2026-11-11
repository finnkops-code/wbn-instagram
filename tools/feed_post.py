"""One-off carousel announcing reader accounts + personal feed."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT, RED_SOFT, ROOT,
                 WHITE, W, H, draw_chevrons, draw_footer, font)
from standings import league_tile  # noqa: E402

LG = {l["key"]: l for l in bot.CFG["standings"]["leagues"]}
GRID = ["mlb", "npb", "kbo", "lidom", "hoofdklasse", "cpbl", "lvbp", "abl", "lmp", "seriea", "lbprc", "dbl"]
FOLLOWED = {"mlb", "npb", "hoofdklasse", "lidom", "abl"}


def kicker(draw, y, chip):
    x = draw_chevrons(draw, MARGIN, y + 6, RED_BRIGHT)
    f_chip = font("figtree-800", 28)
    lw = draw.textlength(chip, font=f_chip)
    draw.rounded_rectangle([x + 8, y - 6, x + 8 + lw + 32, y + 40], radius=8, fill=RED)
    draw.text((x + 24, y + 17), chip, font=f_chip, fill=WHITE, anchor="lm")


def check_badge(draw, cx, cy, r=22):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED_BRIGHT, outline=PETROL_DEEP, width=4)
    draw.line([(cx - 10, cy + 1), (cx - 3, cy + 8), (cx + 11, cy - 8)], fill=WHITE, width=5, joint="curve")


SITE = "https://worldbaseballnews.org"
# (kind, key or logo path, name, followed) — leagues and teams mixed, like the follow screen on the site
ROWS = [
    [("team", "/team-logos/119.svg", "Los Angeles Dodgers", True), ("league", "npb", "NPB", True),
     ("team", "/team-logos/npb-t.png", "Hanshin Tigers", False), ("league", "kbo", "KBO", False)],
    [("league", "lidom", "LIDOM", True), ("team", "/team-logos/kbo-LG.png", "LG Twins", False),
     ("team", "/team-logos/w39587.png", "Curaçao Neptunus", True), ("league", "cpbl", "CPBL", False)],
    [("team", "/team-logos/147.svg", "New York Yankees", False), ("league", "hoofdklasse", "Hoofdklasse", True),
     ("team", "/team-logos/672.svg", "Tigres del Licey", True)],
    [("league", "abl", "ABL", True), ("team", "/team-logos/cpbl-rakuten.png", "Rakuten Monkeys", True),
     ("team", "/team-logos/695.svg", "Leones del Caracas", False), ("league", "mlb", "MLB", False)],
    [("team", "/team-logos/npb-g.png", "Yomiuri Giants", False), ("league", "lvbp", "LVBP", True),
     ("team", "/team-logos/4068.png", "Perth Heat", True), ("league", "seriea", "Serie A", False)],
]
ROW_OFFSETS = [-70, -190, 40, -120, -30]


def pill_logo(kind, ref, size):
    if kind == "league":
        f = ROOT / "league-logos" / f"{ref}.png"
        im = Image.open(f).convert("RGBA") if f.exists() else None
        if im:
            im.thumbnail((size, size), Image.LANCZOS)
        return im
    import standings
    return standings.logo(SITE + ref, size)


def pill(canvas, x, cy, item, h=96):
    """One follow pill: logo in a white circle, name, and Following (red) / Follow (+) state."""
    kind, ref, name, on = item
    draw = ImageDraw.Draw(canvas)
    f_name = font("oswald-600", 36)
    tw = draw.textlength(name.upper(), font=f_name)
    w = h + 14 + tw + 26 + 52 + 22
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    if on:
        ld.rounded_rectangle([x, cy - h / 2, x + w, cy + h / 2], radius=h / 2, fill=RED + (255,))
    else:
        ld.rounded_rectangle([x, cy - h / 2, x + w, cy + h / 2], radius=h / 2, fill=PETROL_MID + (255,),
                             outline=PETROL_LINE + (255,), width=3)
    canvas.alpha_composite(layer)
    pad = 8
    d = h - 2 * pad
    draw.ellipse([x + pad, cy - d / 2, x + pad + d, cy + d / 2], fill=WHITE)
    im = pill_logo(kind, ref, int(d * 0.68))
    if im:
        canvas.alpha_composite(im, (int(x + pad + (d - im.width) / 2), int(cy - im.height / 2)))
    draw.text((x + h + 14, cy), name.upper(), font=f_name, fill=WHITE, anchor="lm")
    bx = x + w - 22 - 52
    if on:
        draw.ellipse([bx, cy - 26, bx + 52, cy + 26], fill=WHITE)
        draw.line([(bx + 14, cy + 1), (bx + 23, cy + 10), (bx + 39, cy - 9)], fill=RED, width=6, joint="curve")
    else:
        draw.ellipse([bx, cy - 26, bx + 52, cy + 26], outline=ON_DARK, width=3)
        draw.line([(bx + 26, cy - 12), (bx + 26, cy + 12)], fill=ON_DARK, width=4)
        draw.line([(bx + 14, cy), (bx + 38, cy)], fill=ON_DARK, width=4)
    return w


def slide1(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 6], fill=RED)
    kicker(draw, 84, "NEW ON WORLDBASEBALLNEWS.ORG")
    f = font("oswald-700", 116)
    draw.text((MARGIN, 146), "YOUR LEAGUES.", font=f, fill=WHITE)
    draw.text((MARGIN, 276), "YOUR TEAMS.", font=f, fill=WHITE)
    draw.text((MARGIN, 406), "ONE FEED.", font=f, fill=RED_BRIGHT)
    top, row_gap, h = 612, 22, 96
    for r, row in enumerate(ROWS):
        cy = top + r * (h + row_gap) + h / 2
        x = ROW_OFFSETS[r]
        for item in row:
            x += pill(canvas, x, cy, item, h) + 20
    # soft fade at both edges so cut-off pills read as "and many more"
    fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i in range(110):
        a = int(255 * (1 - i / 110) ** 1.6)
        ImageDraw.Draw(fade).line([(i, top - 10), (i, H - 150)], fill=PETROL_DEEP + (a,))
        ImageDraw.Draw(fade).line([(W - 1 - i, top - 10), (W - 1 - i, H - 150)], fill=PETROL_DEEP + (a,))
    canvas.alpha_composite(fade)
    draw = ImageDraw.Draw(canvas)
    draw_footer(draw, H - 132, "FREE ACCOUNT · LINK IN BIO")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


STEPS = [
    ("CREATE YOUR FREE ACCOUNT", "Username, email and a password. Done in 30 seconds."),
    ("FOLLOW LEAGUES AND TEAMS", "Pick from 40+ leagues on five continents and add your favourite clubs."),
    ("GET YOUR PERSONAL FEED", "The latest stories from everything you follow, together on one page."),
]


def slide2(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 6], fill=RED)
    kicker(draw, 84, "MY WORLD BASEBALL NEWS")
    draw.text((MARGIN, 146), "HOW IT WORKS", font=font("oswald-700", 116), fill=WHITE)
    top, step_h = 330, 268
    f_num = font("oswald-700", 150)
    f_t = font("oswald-700", 50)
    f_b = font("figtree-500", 32)
    for i, (title, body) in enumerate(STEPS):
        y = top + i * step_h
        draw.rounded_rectangle([MARGIN - 16, y, W - MARGIN + 16, y + step_h - 30], radius=16, fill=PETROL_MID)
        draw.text((MARGIN + 30, y + (step_h - 30) / 2), str(i + 1), font=f_num, fill=RED_BRIGHT, anchor="lm")
        tx = MARGIN + 160
        draw.text((tx, y + 42), title, font=f_t, fill=WHITE)
        lines = bot.wrap(draw, body, f_b, W - MARGIN - tx)
        for j, line in enumerate(lines[:2]):
            draw.text((tx, y + 116 + j * 42), line, font=f_b, fill=ON_DARK)
    draw.text((MARGIN, top + 3 * step_h + 6), "Signed in? Your feed also shows up on the homepage under For you.",
              font=font("figtree-700", 28), fill=RED_SOFT)
    draw_footer(draw, H - 132, "SIGN UP · LINK IN BIO")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "posts"
    out.mkdir(parents=True, exist_ok=True)
    slide1(out / "wbn-my-feed-1.jpg")
    slide2(out / "wbn-my-feed-2.jpg")
    print("ok")
