"""LinkedIn visual: advertise in the World Baseball News newsletter.

The email shown is the real edition as sent (assets/linkedin-newsletter/edition.html, rendered with
tools/render_html.js), with the partner slot added in the newsletter's own styling.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot import MARGIN, ON_DARK, PETROL_DEEP, RED, RED_BRIGHT, ROOT, WHITE, W, H, draw_chevrons, font
from tools.potw_post import GOLD  # noqa: E402

A = ROOT / "assets" / "linkedin-newsletter"
INK = (3, 53, 76)


def email_image():
    out = subprocess.run(["node", str(ROOT / "tools" / "render_html.js"), str(A / "edition.html"), str(A / "edition.png"),
                          "#mail"], capture_output=True, text=True, check=True).stdout
    top, h = json.loads(out.strip().splitlines()[-1])["adslot"]
    return Image.open(A / "edition.png").convert("RGBA"), (top * 2, h * 2)


def calendar_tile(canvas, x, y, day, size=118):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x + 6, y + 10, x + size + 6, y + size + 10], radius=16, fill=(0, 0, 0, 110))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([x, y, x + size, y + size], radius=16, fill=WHITE)
    d.rounded_rectangle([x, y, x + size, y + 34], radius=16, fill=RED)
    d.rectangle([x, y + 18, x + size, y + 34], fill=RED)
    d.text((x + size / 2, y + 18), "EVERY", font=font("figtree-800", 15), fill=WHITE, anchor="mm")
    d.text((x + size / 2, y + 76), day, font=font("oswald-700", 50), fill=INK, anchor="mm")


def main(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([520, -200, 1400, 700], fill=RED + (90,))
    ImageDraw.Draw(glow).ellipse([-300, 900, 500, 1600], fill=(11, 69, 96, 160))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for gx in range(30, W, 36):
        for gy in range(30, H, 36):
            dd.ellipse([gx - 1.4, gy - 1.4, gx + 1.4, gy + 1.4], fill=(255, 255, 255, 22))
    canvas.alpha_composite(dots)

    # the real email, slightly tilted, with a gold glow around the partner slot
    mail, (ad_top, ad_h) = email_image()
    target_w = 520
    k = target_w / mail.width
    mail = mail.resize((target_w, int(mail.height * k)), Image.LANCZOS)
    ad_top, ad_h = ad_top * k, ad_h * k
    pad = 80
    layer = Image.new("RGBA", (mail.width + 2 * pad, mail.height + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([pad + 10, pad + 24, pad + mail.width + 10, pad + mail.height + 24],
                                             radius=14, fill=(0, 0, 0, 170))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(26)))
    gl = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle([pad - 6, pad + ad_top - 8, pad + mail.width + 6, pad + ad_top + ad_h + 12],
                                         radius=18, fill=GOLD + (235,))
    layer.alpha_composite(gl.filter(ImageFilter.GaussianBlur(22)))
    layer.alpha_composite(mail, (pad, pad))
    angle = 4
    rot = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    ox, oy = 470, 60
    canvas.alpha_composite(rot, (ox, oy))

    # where the partner slot ended up after rotation (for the sticker)
    cx0, cy0 = layer.width / 2, layer.height / 2
    px, py = pad, pad + ad_top + ad_h / 2
    a = math.radians(angle)
    rx = (px - cx0) * math.cos(a) + (py - cy0) * math.sin(a) + rot.width / 2 + ox
    ry = -(px - cx0) * math.sin(a) + (py - cy0) * math.cos(a) + rot.height / 2 + oy

    d = ImageDraw.Draw(canvas)
    x = draw_chevrons(d, MARGIN, 82, RED_BRIGHT)
    f_chip = font("figtree-800", 22)
    lab = "ADVERTISE WITH US"
    lw = d.textlength(lab, font=f_chip)
    d.rounded_rectangle([x + 8, 70, x + 8 + lw + 28, 108], radius=8, fill=RED)
    d.text((x + 22, 89), lab, font=f_chip, fill=WHITE, anchor="lm")
    f = font("oswald-700", 96)
    for i, (t, c) in enumerate([("YOUR", WHITE), ("BRAND", WHITE), ("IN EVERY", WHITE), ("EDITION.", RED_BRIGHT)]):
        d.text((MARGIN, 128 + i * 100), t, font=f, fill=c)
    d.text((MARGIN, 568), "The World Baseball News newsletter,", font=font("figtree-700", 24), fill=ON_DARK)
    d.text((MARGIN, 600), "straight to fans' inboxes.", font=font("figtree-700", 24), fill=ON_DARK)
    calendar_tile(canvas, MARGIN, 664, "MON")
    calendar_tile(canvas, MARGIN + 140, 664, "THU")
    d = ImageDraw.Draw(canvas)
    y = 830
    for big, small in [("100%", "opted-in baseball fans"), ("40+", "leagues, five continents"),
                       ("DAILY", "new subscribers")]:
        d.text((MARGIN, y), big, font=font("oswald-700", 54), fill=GOLD)
        d.text((MARGIN, y + 66), small, font=font("figtree-700", 23), fill=WHITE)
        y += 124

    # sticker pointing at the partner slot
    sx, sy = rx - 250, ry - 34
    d.rounded_rectangle([sx, sy, sx + 210, sy + 68], radius=34, fill=GOLD)
    d.text((sx + 105, sy + 35), "YOU, HERE", font=font("oswald-700", 32), fill=INK, anchor="mm")
    d.polygon([(sx + 204, sy + 20), (sx + 238, sy + 34), (sx + 204, sy + 48)], fill=GOLD)
    d.text((MARGIN, H - 54), "worldbaseballnews.org/partners", font=font("figtree-700", 22), fill=ON_DARK, anchor="ls")
    d.rectangle([0, 0, W, 6], fill=RED)
    canvas.convert("RGB").save(out, "PNG", optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
