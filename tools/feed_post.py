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


def slide1(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 6], fill=RED)
    kicker(draw, 84, "NEW ON WORLDBASEBALLNEWS.ORG")
    f = font("oswald-700", 116)
    draw.text((MARGIN, 146), "YOUR LEAGUES.", font=f, fill=WHITE)
    draw.text((MARGIN, 276), "YOUR TEAMS.", font=f, fill=WHITE)
    draw.text((MARGIN, 406), "ONE FEED.", font=f, fill=RED_BRIGHT)

    # league picker mock-up: 4 x 3 tiles, followed ones get a red ring + check
    cols, gap = 4, 30
    top, bottom = 590, H - 132 - 44
    size = int((bottom - top - 2 * gap) / 3)
    left = (W - (cols * size + (cols - 1) * gap)) / 2
    for i, key in enumerate(GRID):
        x = left + (i % cols) * (size + gap)
        y = top + (i // cols) * (size + gap)
        league_tile(canvas, draw, LG[key], x, y, size)
        if key in FOLLOWED:
            draw.rounded_rectangle([x - 5, y - 5, x + size + 5, y + size + 5], radius=size // 7 + 5,
                                   outline=RED_BRIGHT, width=6)
            check_badge(draw, x + size - 4, y + 4)
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
