"""LinkedIn image: our partners + call to become one."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT, RED_SOFT, ROOT,
                 WHITE, W, H, draw_chevrons, draw_footer, font)

P = ROOT / "assets" / "partners"
PARTNERS = [  # (file, dark tile, round)
    ("swiss-baseball-softball-federation.webp", False, False), ("bat-king-europe.webp", True, False),
    ("forelle.webp", False, False), ("covee.webp", False, False), ("candyball.webp", False, False),
    ("katana.png", False, False), ("baseball-jobs-overseas.png", False, False), ("merkzicht.webp", False, False),
    ("world-baseball-hq.webp", False, True), ("nachoe-baseball.webp", False, True),
]


def autocrop(im: Image.Image) -> Image.Image:
    """Trim transparent or flat-coloured padding around a logo."""
    from PIL import ImageChops
    bg = Image.new("RGBA", im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 24 else 0)
    box = diff.getbbox()
    if box:
        pad = 6
        im = im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
    return im


def main(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=RED)
    x = draw_chevrons(d, MARGIN, 82, RED_BRIGHT)
    f_chip = font("figtree-800", 26)
    chip = "PARTNER WITH WORLD BASEBALL NEWS"
    lw = d.textlength(chip, font=f_chip)
    d.rounded_rectangle([x + 8, 70, x + 8 + lw + 30, 112], radius=8, fill=RED)
    d.text((x + 23, 91), chip, font=f_chip, fill=WHITE, anchor="lm")
    f = font("oswald-700", 78)
    for i, (t, c) in enumerate([("EXPOSE YOUR BRAND TO", WHITE), ("THOUSANDS OF BASEBALL", WHITE),
                                ("FANS EVERY WEEK", RED_BRIGHT)]):
        d.text((MARGIN, 136 + i * 88), t, font=f, fill=c)
    d.text((MARGIN, 420), "Join the brands, leagues and creators already on board:", font=font("figtree-700", 30),
           fill=ON_DARK)

    cols, gap = 2, 22
    tw = (W - 2 * MARGIN - gap) / cols
    th = 120
    top = 500
    for i, (fn, dark, rnd) in enumerate(PARTNERS):
        tx = MARGIN + (i % cols) * (tw + gap)
        ty = top + (i // cols) * (th + gap)
        d.rounded_rectangle([tx, ty, tx + tw, ty + th], radius=14, fill=(30, 30, 30) if dark else WHITE)
        im = autocrop(Image.open(P / fn).convert("RGBA"))
        box = (tw * 0.55, th * 0.72) if not rnd else (th - 20, th - 20)
        im.thumbnail((int(box[0]), int(box[1])), Image.LANCZOS)
        if im.height < box[1] * 0.7 and im.width < box[0] * 0.7:  # small source logo: scale up a bit
            k = min(box[0] / im.width, box[1] / im.height) * 0.85
            im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
        if rnd:
            m = Image.new("L", im.size, 0)
            ImageDraw.Draw(m).ellipse([0, 0, im.width - 1, im.height - 1], fill=255)
            im.putalpha(m)
        canvas.alpha_composite(im, (int(tx + (tw - im.width) / 2), int(ty + (th - im.height) / 2)))

    draw_footer(d, H - 132, "BECOME A PARTNER")
    canvas.convert("RGB").save(out, "PNG", optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
