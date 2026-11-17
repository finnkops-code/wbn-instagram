"""LinkedIn image: reader accounts + personalisation, for a business audience."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import (MARGIN, ON_DARK, PETROL_DEEP, PETROL_MID, RED, RED_BRIGHT, RED_SOFT, WHITE, W, H, draw_chevrons,
                 draw_footer, font)

PILLARS = [
    ("01", "LEAGUES", "Readers follow any of our 40+ leagues, from MLB and NPB to the Hoofdklasse."),
    ("02", "TEAMS", "They add their own clubs and get every story that mentions them, in any league."),
    ("03", "ONE FEED", "Everything they follow comes together in a personal feed, also on the homepage."),
    ("04", "IN CONTEXT", "Sign-up prompts follow the league of the article a reader is on."),
]


def main(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=RED)
    x = draw_chevrons(d, MARGIN, 82, RED_BRIGHT)
    f_chip = font("figtree-800", 26)
    chip = "NEW: READER ACCOUNTS"
    lw = d.textlength(chip, font=f_chip)
    d.rounded_rectangle([x + 8, 70, x + 8 + lw + 30, 112], radius=8, fill=RED)
    d.text((x + 23, 91), chip, font=f_chip, fill=WHITE, anchor="lm")
    f = font("oswald-700", 88)
    for i, (t, c) in enumerate([("EVERY FAN GETS", WHITE), ("THEIR OWN", WHITE), ("BASEBALL FEED", RED_BRIGHT)]):
        d.text((MARGIN, 134 + i * 98), t, font=f, fill=c)
    d.text((MARGIN, 462), "Personalisation that brings readers back.", font=font("figtree-700", 32), fill=ON_DARK)
    y, bh = 528, 148
    for num, title, body in PILLARS:
        d.rounded_rectangle([MARGIN - 16, y, W - MARGIN + 16, y + bh], radius=16, fill=PETROL_MID)
        d.text((MARGIN + 14, y + bh / 2), num, font=font("oswald-700", 72), fill=RED_BRIGHT, anchor="lm")
        tx = MARGIN + 130
        d.text((tx, y + 26), title, font=font("oswald-700", 40), fill=WHITE)
        lines = bot.wrap(d, body, font("figtree-500", 27), W - MARGIN - tx)
        for j, ln in enumerate(lines[:2]):
            d.text((tx, y + 78 + j * 34), ln, font=font("figtree-500", 27), fill=ON_DARK)
        y += bh + 14
    draw_footer(d, H - 132, "CREATE A FREE ACCOUNT")
    canvas.convert("RGB").save(out, "PNG", optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
