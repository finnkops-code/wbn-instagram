"""LinkedIn visual: advertise in the World Baseball News newsletter (Mon + Thu), shown as the email on a phone."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import MARGIN, ON_DARK, PETROL_DEEP, RED, RED_BRIGHT, ROOT, WHITE, W, H, draw_chevrons, font
from tools.linkedin_accounts import INK, MUTED, PAPER, cover_fit, rounded  # noqa: E402
from tools.potw_post import GOLD  # noqa: E402

A = ROOT / "assets" / "linkedin-newsletter"
LEAD = ("Navegantes-del-Magallanes-celebrate-LVBP-extra-inning-victory.jpg", "LVBP",
        "Magallanes Beats Leones Before Record 39,031 Fans in Caracas")
MORE = [("Sonny-Gray-returns-to-Minnesota-Twins.jpg", "MLB", "Sonny Gray Returns to Twins on Two-Year, $55M Deal"),
        ("Perth-Heat-Dugout-Celebration.jpg", "ABL", "Perth Heat Blank Sydney With One-Hit Opening Night Shutout"),
        ("Rowdy-Tellez-Atlanta-Braves-2026.jpg", "NPB", "Rakuten Sign 123-Homer MLB Veteran Rowdy Tellez")]


def tag(d, x, y, text, fill=RED, color=WHITE, size=15):
    f = font("figtree-800", size)
    tw = d.textlength(text, font=f) + 16
    d.rounded_rectangle([x, y, x + tw, y + size + 10], radius=6, fill=fill)
    d.text((x + tw / 2, y + (size + 10) / 2), text, font=f, fill=color, anchor="mm")


def phone(width=600, height=1180):
    pad = 22
    sw, sh = width - 2 * pad, height - 2 * pad
    sc = Image.new("RGBA", (sw, sh), WHITE + (255,))
    d = ImageDraw.Draw(sc)
    # mail app header
    d.rectangle([0, 0, sw, 150], fill=PAPER)
    d.text((24, 52), "‹ Inbox", font=font("figtree-700", 22), fill=(0, 122, 255))
    logo = Image.open(ROOT / "assets" / "wbn-logo.png").convert("RGBA").resize((52, 52), Image.LANCZOS)
    sc.alpha_composite(logo, (24, 86))
    d.text((88, 96), "World Baseball News", font=font("figtree-800", 22), fill=INK)
    d.text((88, 124), "Thursday edition · The week in world baseball", font=font("figtree-500", 17), fill=MUTED)
    # newsletter masthead
    y = 150
    d.rectangle([0, y, sw, y + 92], fill=PETROL_DEEP)
    d.text((24, y + 46), "WORLD BASEBALL NEWS", font=font("oswald-700", 32), fill=WHITE, anchor="lm")
    d.text((sw - 24, y + 46), "MON + THU", font=font("figtree-800", 17), fill=GOLD, anchor="rm")
    y += 110
    # the ad slot, right under the masthead ("presented by")
    ad_y, ad_h = y, 170
    d.rounded_rectangle([20, y, sw - 20, y + ad_h], radius=16, fill=(255, 248, 232), outline=GOLD, width=4)
    tag(d, 36, y + 16, "PRESENTED BY", fill=GOLD, color=INK)
    d.text((sw / 2, y + 86), "YOUR BRAND HERE", font=font("oswald-700", 44), fill=INK, anchor="mm")
    d.text((sw / 2, y + 130), "Logo · message · link to your offer", font=font("figtree-700", 19), fill=MUTED,
           anchor="mm")
    y += ad_h + 24
    # lead story
    img = rounded(cover_fit(Image.open(A / LEAD[0]).convert("RGB"), sw - 48, 230), 14)
    sc.alpha_composite(img, (24, y))
    tag(d, 36, y + 14, LEAD[1])
    y += 246
    for i, ln in enumerate(bot.wrap(d, LEAD[2], font("oswald-700", 32), sw - 48)[:2]):
        d.text((24, y + i * 38), ln, font=font("oswald-700", 32), fill=INK)
    y += 100
    # more stories
    for fn, lg, title in MORE:
        th = rounded(cover_fit(Image.open(A / fn).convert("RGB"), 150, 100), 10)
        sc.alpha_composite(th, (24, y))
        tag(d, 190, y + 2, lg, size=14)
        for i, ln in enumerate(bot.wrap(d, title, font("figtree-800", 20), sw - 214)[:2]):
            d.text((190, y + 34 + i * 25), ln, font=font("figtree-800", 20), fill=INK)
        y += 118
    body = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.rounded_rectangle([0, 0, width - 1, height - 1], radius=70, fill=(12, 18, 22, 255))
    bd.rounded_rectangle([3, 3, width - 4, height - 4], radius=68, outline=(70, 82, 90, 255), width=3)
    body.alpha_composite(rounded(sc, 50), (pad, pad))
    bd.rounded_rectangle([width / 2 - 80, pad + 2, width / 2 + 80, pad + 30], radius=14, fill=(12, 18, 22, 255))
    return body, pad + ad_y  # y of the ad slot inside the phone


def main(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([380, 380, 1240, 1400], fill=RED + (70,))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=RED)
    x = draw_chevrons(d, MARGIN, 82, RED_BRIGHT)
    f_chip = font("figtree-800", 24)
    lab = "ADVERTISE IN OUR NEWSLETTER"
    lw = d.textlength(lab, font=f_chip)
    d.rounded_rectangle([x + 8, 70, x + 8 + lw + 30, 110], radius=8, fill=RED)
    d.text((x + 23, 90), lab, font=f_chip, fill=WHITE, anchor="lm")
    f = font("oswald-700", 92)
    d.text((MARGIN, 130), "YOUR BRAND.", font=f, fill=WHITE)
    d.text((MARGIN, 232), "THEIR INBOX.", font=f, fill=WHITE)
    d.text((MARGIN, 334), "TWICE A WEEK.", font=f, fill=RED_BRIGHT)

    ph, ad_y = phone()
    px, py = 450, 470
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([px + 20, py + 30, px + 20 + ph.width, py + 30 + ph.height], radius=70,
                                             fill=(0, 0, 0, 150))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(30)))
    canvas.alpha_composite(ph, (px, py))
    d = ImageDraw.Draw(canvas)
    # arrow pointing at the ad slot
    ay = py + ad_y + 85
    d.line([(MARGIN + 300, ay), (px + 10, ay)], fill=GOLD, width=5)
    d.polygon([(px + 26, ay), (px + 4, ay - 14), (px + 4, ay + 14)], fill=GOLD)

    def callout(y, big, small, color=RED_BRIGHT):
        d.text((MARGIN, y), big, font=font("oswald-700", 62), fill=color)
        d.text((MARGIN, y + 78), small, font=font("oswald-700", 34), fill=WHITE)

    callout(ay - 70, "YOU", "ARE HERE", color=GOLD)
    callout(950, "2X", "EVERY WEEK")
    d.text((MARGIN, 1084), "Monday + Thursday", font=font("figtree-700", 24), fill=ON_DARK)
    callout(1120, "100%", "OPT-IN FANS")
    d.text((MARGIN, 1254), "Growing every day", font=font("figtree-700", 24), fill=ON_DARK)
    canvas.convert("RGB").save(out, "PNG", optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
