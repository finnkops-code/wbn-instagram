"""Instagram visual: sign up for the World Baseball News newsletter (B2C). Shows the real edition as sent."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot import MARGIN, ON_DARK, PETROL_DEEP, RED, RED_BRIGHT, ROOT, WHITE, W, H, draw_chevrons, draw_footer, font
from tools.potw_post import GOLD  # noqa: E402
from tools.linkedin_newsletter import A, INK, calendar_tile  # noqa: E402


def main(out: Path):
    subprocess.run(["node", str(ROOT / "tools" / "render_html.js"), str(A / "edition-fans.html"),
                    str(A / "edition-fans.png"), "#mail"], capture_output=True, check=True)
    mail = Image.open(A / "edition-fans.png").convert("RGBA")
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

    target_w = 520
    mail = mail.resize((target_w, int(mail.height * target_w / mail.width)), Image.LANCZOS)
    # drop the dark footer band so the email ends cleanly above the sign-up pill
    mail = mail.crop((0, 0, mail.width, mail.height - 118))
    m = Image.new("L", mail.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, mail.width - 1, mail.height - 1], radius=10, fill=255)
    mail.putalpha(Image.composite(mail.getchannel("A"), m, m))
    pad = 80
    layer = Image.new("RGBA", (mail.width + 2 * pad, mail.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad + 10, pad + 24, pad + mail.width + 10, pad + mail.height + 24],
                                         radius=14, fill=(0, 0, 0, 170))
    layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(26)))
    layer.alpha_composite(mail, (pad, pad))
    rot = layer.rotate(4, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(rot, (470, 60))

    d = ImageDraw.Draw(canvas)
    x = draw_chevrons(d, MARGIN, 82, RED_BRIGHT)
    f_chip = font("figtree-800", 22)
    lab = "FREE NEWSLETTER"
    lw = d.textlength(lab, font=f_chip)
    d.rounded_rectangle([x + 8, 70, x + 8 + lw + 28, 108], radius=8, fill=RED)
    d.text((x + 22, 89), lab, font=f_chip, fill=WHITE, anchor="lm")
    f = font("oswald-700", 96)
    for i, (t, c) in enumerate([("NEVER", WHITE), ("MISS A", WHITE), ("PITCH.", RED_BRIGHT)]):
        d.text((MARGIN, 128 + i * 100), t, font=f, fill=c)
    d.text((MARGIN, 458), "World baseball's biggest stories,", font=font("figtree-700", 24), fill=ON_DARK)
    d.text((MARGIN, 490), "straight to your inbox.", font=font("figtree-700", 24), fill=ON_DARK)
    calendar_tile(canvas, MARGIN, 560, "MON")
    calendar_tile(canvas, MARGIN + 140, 560, "THU")
    d = ImageDraw.Draw(canvas)
    y = 730
    for big, small in [("FREE", "no cost, unsubscribe anytime"), ("2 MIN", "and you're up to date"),
                       ("40+", "leagues, five continents")]:
        d.text((MARGIN, y), big, font=font("oswald-700", 54), fill=GOLD)
        d.text((MARGIN, y + 66), small, font=font("figtree-700", 23), fill=WHITE)
        y += 124
    draw_footer(d, H - 132, "SIGN UP · LINK IN BIO")
    d.rectangle([0, 0, W, 6], fill=RED)
    canvas.convert("RGB").save(out, "JPEG", quality=93)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
