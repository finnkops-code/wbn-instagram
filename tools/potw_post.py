"""World Player of the Week carousel (2 slides) from a spec JSON (slides/potw-*.json)."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from bot import (MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT, ROOT, WHITE, W, H,
                 draw_chevrons, draw_footer, font)
from standings import draw_flags, league_tile  # noqa: E402

GOLD = (222, 184, 96)
GOLD_DEEP = (176, 136, 52)
LG = {l["key"]: l for l in bot.CFG["standings"]["leagues"]}


def gold_text(canvas, xy, text, f, anchor="la"):
    """Text with a vertical gold gradient."""
    d = ImageDraw.Draw(canvas)
    box = d.textbbox(xy, text, font=f, anchor=anchor)
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255, anchor=anchor)
    grad = Image.new("RGBA", canvas.size, GOLD + (255,))
    gd = ImageDraw.Draw(grad)
    h = max(1, box[3] - box[1])
    for i in range(h):
        t = i / h
        c = tuple(int(GOLD[k] + (GOLD_DEEP[k] - GOLD[k]) * t) for k in range(3))
        gd.line([(box[0], box[1] + i), (box[2], box[1] + i)], fill=c + (255,))
    canvas.paste(grad, (0, 0), mask)
    return box


def award_badge(canvas, x, y, week_label):
    d = ImageDraw.Draw(canvas)
    f1 = font("figtree-800", 24)
    f2 = font("oswald-700", 44)
    w = 104 + ImageDraw.Draw(canvas).textlength("PLAYER OF THE WEEK", font=f2) + 34
    d.rounded_rectangle([x, y, x + w, y + 132], radius=14, fill=PETROL_DEEP + (235,), outline=GOLD, width=3)
    # star
    cx, cy, r = x + 58, y + 66, 30
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=GOLD)
    d.text((x + 104, y + 36), "WORLD", font=f1, fill=GOLD, anchor="lm")
    d.text((x + 104, y + 74), "PLAYER OF THE WEEK", font=f2, fill=WHITE, anchor="lm")
    d.text((x + 104, y + 110), week_label, font=font("figtree-700", 20), fill=ON_DARK_2, anchor="lm")


def slide1(spec, out: Path):
    photo = Image.open(ROOT / spec["photo"]).convert("RGB")
    crop = spec.get("crop")
    if crop:
        photo = photo.crop(tuple(crop))
    # cover 1080x1350
    k = max(W / photo.width, H / photo.height)
    photo = photo.resize((int(photo.width * k + 0.5), int(photo.height * k + 0.5)), Image.LANCZOS)
    ox, oy = (photo.width - W) // 2, int((photo.height - H) * spec.get("v_align", 0.3))
    canvas = photo.crop((ox, oy, ox + W, oy + H)).convert("RGBA")
    # gradient to deep petrol at the bottom, light vignette at the top
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    start = int(H * 0.40)
    for yy in range(start, H):
        t = (yy - start) / (H - start)
        gd.line([(0, yy), (W, yy)], fill=PETROL_DEEP + (int(255 * min(1, t ** 0.75 * 1.08)),))
    for yy in range(0, 240):
        gd.line([(0, yy), (W, yy)], fill=PETROL_DEEP + (int(150 * (1 - yy / 240) ** 1.4),))
    canvas.alpha_composite(grad)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=GOLD)
    award_badge(canvas, MARGIN, 56, spec["week_label"])
    league_tile(canvas, d, LG[spec["league"]], W - MARGIN - 132, 56, 132)

    # name block, laid out from the footer upwards
    sy = H - 132 - 150                       # stat row top
    ty = sy - 34                             # team line (centre)
    base = ty - 42                           # baseline of the last name
    gold_text(canvas, (MARGIN - 6, base), spec["last"].upper(), font("oswald-700", 190), anchor="ls")
    d.text((MARGIN, base - 168), spec["first"].upper(), font=font("oswald-700", 80), fill=WHITE, anchor="ls")
    lg = LG[spec["league"]]
    fx = draw_flags(canvas, d, MARGIN, ty, lg.get("flags"), h=30)
    d.text((fx + 4, ty), f"{spec['team'].upper()}  ·  {lg['label'].upper()}", font=font("figtree-800", 30),
           fill=ON_DARK, anchor="lm")
    n = len(spec["stats"])
    cw = (W - 2 * MARGIN) / n
    for i, (val, lab) in enumerate(spec["stats"]):
        cx = MARGIN + i * cw
        if i:
            d.line([(cx, sy + 16), (cx, sy + 118)], fill=PETROL_LINE, width=2)
        tx = cx + (24 if i else 0)
        d.text((tx, sy + 84), val, font=font("oswald-700", 76), fill=WHITE, anchor="ls")
        d.text((tx + 2, sy + 120), lab, font=font("figtree-800", 22), fill=GOLD, anchor="ls")
    if spec.get("credit"):
        d.text((W - MARGIN, 56 + 132 + 30), f"Photo: {spec['credit']}", font=font("figtree-500", 18),
               fill=ON_DARK_2, anchor="rs")
    draw_footer(d, H - 132, "SWIPE FOR HIS WEEK")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


def slide2(spec, out: Path):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), f"WORLD PLAYER OF THE WEEK · {spec['week_label']}", font=font("figtree-800", 24),
           fill=GOLD, anchor="lm")
    d.text((MARGIN, 140), "HIS WEEK", font=font("oswald-700", 96), fill=WHITE)
    # game log
    y = 270
    f_d = font("figtree-800", 26)
    f_l = font("oswald-600", 34)
    for g in spec["games"]:
        d.rounded_rectangle([MARGIN - 16, y, W - MARGIN + 16, y + 82], radius=12, fill=PETROL_MID)
        d.text((MARGIN + 4, y + 41), g["date"].upper(), font=f_d, fill=GOLD, anchor="lm")
        d.text((MARGIN + 176, y + 41), g["opp"].upper(), font=font("figtree-700", 26), fill=ON_DARK, anchor="lm")
        d.text((W - MARGIN, y + 41), g["line"], font=f_l, fill=WHITE, anchor="rm")
        y += 96
    if spec.get("highlight"):
        y += 10
        d.rectangle([MARGIN, y, MARGIN + 6, y + 92], fill=GOLD)
        lines = bot.wrap(d, spec["highlight"], font("figtree-700", 30), W - 2 * MARGIN - 30)
        for i, ln in enumerate(lines[:3]):
            d.text((MARGIN + 28, y + 6 + i * 40), ln, font=font("figtree-700", 30), fill=WHITE)
        y += 40 * min(3, len(lines)) + 34
    # the race
    y = max(y + 40, 640)
    d.text((MARGIN, y), "THE SHORTLIST", font=font("oswald-700", 52), fill=WHITE)
    d.text((W - MARGIN, y + 34), spec["evaluated"].upper(), font=font("figtree-800", 22), fill=ON_DARK_2, anchor="rs")
    y += 80
    rows = spec["race"]
    row_h = min(70, (H - 132 - 30 - y) / len(rows))
    for i, r in enumerate(rows):
        cy = y + row_h / 2
        win = r.get("winner")
        if win:
            d.rounded_rectangle([MARGIN - 16, y + 3, W - MARGIN + 16, y + row_h - 3], radius=10, outline=GOLD, width=3)
        fx = draw_flags(canvas, d, MARGIN + 6, cy, LG[r["league"]].get("flags"), h=24)
        d.text((fx + 2, cy), r["name"].upper(), font=font("oswald-600", 32), fill=WHITE, anchor="lm")
        nx = fx + 2 + d.textlength(r["name"].upper(), font=font("oswald-600", 32)) + 14
        d.text((nx, cy + 2), LG[r["league"]]["label"].upper(), font=font("figtree-800", 20), fill=ON_DARK_2, anchor="lm")
        d.text((W - MARGIN, cy), r["line"], font=font("figtree-700", 24), fill=GOLD if win else ON_DARK, anchor="rm")
        y += row_h
    draw_footer(d, H - 132, "FOLLOW FOR NEXT WEEK")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "posts"
    out.mkdir(parents=True, exist_ok=True)
    slide1(spec, out / f"{spec['slug']}-1.jpg")
    slide2(spec, out / f"{spec['slug']}-2.jpg")
    print("ok")
