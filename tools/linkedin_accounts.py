"""LinkedIn visual: reader accounts and personalisation, shown as the actual personal feed on a phone."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
import standings  # noqa: E402
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT, RED_SOFT, ROOT,
                 WHITE, W, H, draw_chevrons, font)

A = ROOT / "assets" / "linkedin-feed"
SITE = "https://worldbaseballnews.org/team-logos/"
LG = {l["key"]: l for l in bot.CFG["standings"]["leagues"]}
INK = (3, 43, 61)
MUTED = (96, 116, 128)
PAPER = (244, 247, 248)

FOLLOW_LEAGUES = ["mlb", "npb", "lidom", "hoofdklasse"]
FOLLOW_TEAMS = [("Cubs", "112.svg"), ("Tigers", "npb-t.png"), ("Escogido", "671.svg"), ("Neptunus", "w39587.png")]
FEED = [
    ("Pete-Crow-Armstrong-2026-NL-MVP-season.jpg", "MLB", "Cubs", "Pete Crow-Armstrong Wins 2026 NL MVP Unanimously"),
    ("Teruaki-Sato-after-winning-the-inaugural-Shigeo-Nagashima-Award.jpg", "NPB", "Tigers",
     "Teruaki Sato Becomes First Shigeo Nagashima Award Winner"),
    ("escogido.jpg", "LIDOM", "Escogido", "Escogido Beats Licey 5-3, Opens Two-Game Lead Atop LIDOM"),
    ("hoofdklasse.png", "HOOFDKLASSE", "", "Hoofdklasse Transfers 2027: UVV Leads Headlines"),
]


def logo_img(kind, ref, size):
    if kind == "league":
        im = Image.open(ROOT / "league-logos" / f"{ref}.png").convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        return im
    return standings.logo(SITE + ref, size)


def cover_fit(im, w, h):
    k = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * k + 1), int(im.height * k + 1)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 3
    return im.crop((x, y, x + w, y + h))


def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=r, fill=255)
    out = im.convert("RGBA")
    out.putalpha(m)
    return out


def chip(screen, d, x, y, label, icon=None, on=True, h=46):
    f = font("figtree-800", 20)
    tw = d.textlength(label, font=f)
    w = tw + 28 + (h - 8 if icon else 0)
    d.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=INK if on else WHITE,
                        outline=None if on else (210, 218, 222), width=2)
    tx = x + 14
    if icon is not None:
        d.ellipse([x + 4, y + 4, x + h - 4, y + h - 4], fill=WHITE)
        ic = icon.copy()
        ic.thumbnail((h - 16, h - 16), Image.LANCZOS)
        screen.alpha_composite(ic, (int(x + h / 2 - ic.width / 2), int(y + h / 2 - ic.height / 2)))
        tx = x + h + 4
    d.text((tx, y + h / 2), label, font=f, fill=WHITE if on else INK, anchor="lm")
    return w


def phone(width=600, height=1180):
    """Render the account page as it looks on a phone."""
    pad = 22
    sw, sh = width - 2 * pad, height - 2 * pad
    screen = Image.new("RGBA", (sw, sh), PAPER + (255,))
    d = ImageDraw.Draw(screen)
    # site header
    d.rectangle([0, 0, sw, 96], fill=PETROL_DEEP)
    wbn = Image.open(ROOT / "assets" / "wbn-logo.png").convert("RGBA").resize((54, 54), Image.LANCZOS)
    screen.alpha_composite(wbn, (22, 30))
    d.text((88, 57), "WORLD BASEBALL NEWS", font=font("oswald-700", 26), fill=WHITE, anchor="lm")
    d.ellipse([sw - 66, 33, sw - 22, 77], fill=RED)
    d.text((sw - 44, 56), "A", font=font("figtree-800", 22), fill=WHITE, anchor="mm")
    y = 122
    d.text((24, y), "Hi, Alex", font=font("oswald-700", 40), fill=INK)
    y += 66
    d.text((24, y), "LEAGUES YOU FOLLOW", font=font("figtree-800", 17), fill=MUTED)
    y += 30
    x = 24
    f_c = font("figtree-800", 20)
    for k in FOLLOW_LEAGUES:
        lab = LG[k]["label"].upper()
        if x + d.textlength(lab, font=f_c) + 66 > sw - 16:
            x, y = 24, y + 56
        w = chip(screen, d, x, y, lab, logo_img("league", k, 40))
        x += w + 10
    y += 72
    d.text((24, y), "TEAMS YOU FOLLOW", font=font("figtree-800", 17), fill=MUTED)
    y += 30
    x = 24
    for lab, ref in FOLLOW_TEAMS:
        if x + d.textlength(lab.upper(), font=f_c) + 66 > sw - 16:
            x, y = 24, y + 56
        w = chip(screen, d, x, y, lab.upper(), logo_img("team", ref, 40), on=False)
        x += w + 10
    y += 76
    d.text((24, y), "YOUR FEED", font=font("oswald-700", 32), fill=INK)
    y += 54
    for img, lg, team, title in FEED:
        ch = 150
        d.rounded_rectangle([16, y, sw - 16, y + ch], radius=14, fill=WHITE)
        th = rounded(cover_fit(Image.open(A / img).convert("RGB"), 170, ch - 24), 10)
        screen.alpha_composite(th, (28, y + 12))
        tx = 28 + 170 + 18
        f_tag = font("figtree-800", 15)
        tags = [lg] + ([team.upper()] if team else [])
        cx = tx
        for i, t in enumerate(tags):
            tw = d.textlength(t, font=f_tag) + 16
            d.rounded_rectangle([cx, y + 16, cx + tw, y + 40], radius=6, fill=RED if i == 0 else (226, 232, 235))
            d.text((cx + tw / 2, y + 28), t, font=f_tag, fill=WHITE if i == 0 else INK, anchor="mm")
            cx += tw + 8
        lines = bot.wrap(d, title, font("figtree-800", 21), sw - 30 - tx)
        for j, ln in enumerate(lines[:3]):
            d.text((tx, y + 52 + j * 27), ln, font=font("figtree-800", 21), fill=INK)
        y += ch + 14
    body = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.rounded_rectangle([0, 0, width - 1, height - 1], radius=70, fill=(12, 18, 22, 255))
    bd.rounded_rectangle([3, 3, width - 4, height - 4], radius=68, outline=(70, 82, 90, 255), width=3)
    body.alpha_composite(rounded(screen, 50), (pad, pad))
    bd.rounded_rectangle([width / 2 - 80, pad + 2, width / 2 + 80, pad + 30], radius=14, fill=(12, 18, 22, 255))
    return body


def callout(canvas, d, x, y, num, title, icons, round_icons=False):
    d.text((x, y), num, font=font("oswald-700", 64), fill=RED_BRIGHT)
    d.text((x, y + 82), title, font=font("oswald-700", 40), fill=WHITE)
    ix = x
    for ic in icons:
        s = 64
        if round_icons:
            d.ellipse([ix, y + 140, ix + s, y + 140 + s], fill=WHITE)
        else:
            d.rounded_rectangle([ix, y + 140, ix + s, y + 140 + s], radius=12, fill=WHITE)
        im = ic.copy()
        im.thumbnail((s - 16, s - 16), Image.LANCZOS)
        canvas.alpha_composite(im, (int(ix + s / 2 - im.width / 2), int(y + 140 + s / 2 - im.height / 2)))
        ix += s + 10


def main(out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    # soft glow behind the phone
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([380, 380, 1240, 1400], fill=RED + (70,))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=RED)
    x = draw_chevrons(d, MARGIN, 82, RED_BRIGHT)
    f_chip = font("figtree-800", 24)
    lab = "NEW: READER ACCOUNTS"
    lw = d.textlength(lab, font=f_chip)
    d.rounded_rectangle([x + 8, 70, x + 8 + lw + 30, 110], radius=8, fill=RED)
    d.text((x + 23, 90), lab, font=f_chip, fill=WHITE, anchor="lm")
    f = font("oswald-700", 92)
    d.text((MARGIN, 130), "YOUR LEAGUES.", font=f, fill=WHITE)
    d.text((MARGIN, 232), "YOUR TEAMS.", font=f, fill=WHITE)
    d.text((MARGIN, 334), "ONE FEED.", font=f, fill=RED_BRIGHT)

    ph = phone()
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([470, 500, 470 + ph.width, 500 + ph.height], radius=70, fill=(0, 0, 0, 150))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(30)))
    canvas.alpha_composite(ph, (450, 470))

    d = ImageDraw.Draw(canvas)
    callout(canvas, d, MARGIN, 520, "40+", "LEAGUES",
            [logo_img("league", k, 60) for k in ("mlb", "npb", "kbo", "lidom")])
    callout(canvas, d, MARGIN, 800, "ANY", "TEAM",
            [logo_img("team", r, 60) for r in ("119.svg", "npb-g.png", "672.svg", "kbo-LG.png")], round_icons=True)
    d.text((MARGIN, 1084), "FOR YOU", font=font("oswald-700", 64), fill=RED_BRIGHT)
    d.text((MARGIN, 1166), "ON THE HOMEPAGE", font=font("oswald-700", 40), fill=WHITE)
    d.text((MARGIN, 1268), "worldbaseballnews.org/account", font=font("figtree-700", 24), fill=ON_DARK)
    canvas.convert("RGB").save(out, "PNG", optimize=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
