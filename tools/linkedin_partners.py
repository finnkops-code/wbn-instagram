"""LinkedIn image: our partners + call to become one."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT, RED_SOFT, ROOT,
                 WHITE, W, H, draw_chevrons, draw_footer, font)

P = ROOT / "assets" / "partners"
ROWS = [  # each row: (group label, [(file, round logo)]) segments
    [("LEAGUE PARTNER", [("swiss-baseball-softball-federation.webp", False)]),
     ("BRANDED PARTNERS", [("candyball.webp", False), ("katana.png", False)])],
    [("COMMERCIAL PARTNERS", [("bat-king-europe.webp", False), ("forelle.webp", False), ("covee.webp", False)])],
    [("MEDIA PARTNERS", [("baseball-jobs-overseas.png", False), ("merkzicht.webp", False)]),
     ("SOCIAL MEDIA PARTNERS", [("world-baseball-hq.webp", True), ("nachoe-baseball.webp", True)])],
]


def knock_out_black(im: Image.Image) -> Image.Image:
    """Logos delivered on a black square (Bat King): make the black transparent so they sit on white."""
    px = im.getpixel((0, 0))
    if px[3] and max(px[:3]) < 40:
        from PIL import ImageOps
        lum = im.convert("RGB").split()
        mx = Image.merge("RGB", lum).convert("L").point(lambda v: max(0, min(255, int((v - 50) * 2.6))))
        r, g, b, _ = im.split()
        # un-premultiply the edge pixels so the fringe keeps the logo colour instead of turning dark
        im = Image.merge("RGBA", (r, g, b, mx))
        solid = Image.new("RGBA", im.size, (196, 160, 72, 255))
        solid.putalpha(mx)
        im = solid
    return im


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

    gap, th, y = 18, 140, 486
    for row in ROWS:
        n = sum(len(files) for _, files in row)
        tw = (W - 2 * MARGIN - (n - 1) * gap) / n
        x = MARGIN
        for label, files in row:
            seg_w = len(files) * tw + (len(files) - 1) * gap
            d.text((x, y + 20), label, font=font("figtree-800", 22), fill=RED_SOFT, anchor="ls")
            d.line([(x, y + 32), (x + seg_w, y + 32)], fill=PETROL_LINE, width=2)
            for fn, rnd in files:
                ty = y + 46
                d.rounded_rectangle([x, ty, x + tw, ty + th], radius=14, fill=WHITE)
                im = knock_out_black(autocrop(Image.open(P / fn).convert("RGBA")))
                box = (tw * 0.62, th * 0.62) if not rnd else (th - 22, th - 22)
                im.thumbnail((int(box[0]), int(box[1])), Image.LANCZOS)
                if im.height < box[1] * 0.7 and im.width < box[0] * 0.7:
                    k = min(box[0] / im.width, box[1] / im.height) * 0.85
                    im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
                if rnd:
                    m = Image.new("L", im.size, 0)
                    ImageDraw.Draw(m).ellipse([0, 0, im.width - 1, im.height - 1], fill=255)
                    im.putalpha(m)
                canvas.alpha_composite(im, (int(x + (tw - im.width) / 2), int(ty + (th - im.height) / 2)))
                x += tw + gap
        y += 46 + th + 40

    draw_footer(d, H - 132, "BECOME A PARTNER")
    canvas.convert("RGB").save(out, "PNG", optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
