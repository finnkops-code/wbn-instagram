"""World Player of the Week wordmark: the Y in PLAYER is a trophy."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
F = lambda n, s: ImageFont.truetype(str(ROOT / "fonts" / f"{n}.ttf"), s)
GOLD, WHITE = (217, 181, 102, 255), (255, 255, 255, 255)
SS = 4  # supersampling


def trophy(d, x, top, w, h, color):
    """Trophy drawn to the cap height of the type: cup (Y arms) + stem + base."""
    cup_h = h * 0.50
    stem_w = w * 0.16
    cx = x + w / 2
    # cup: flat top, curved sides narrowing into the stem
    pts = []
    import math
    for i in range(41):
        t = i / 40
        # left side from top-left to stem
        yy = top + t * cup_h
        half = (w / 2) * (1 - t ** 1.9) + (stem_w / 2) * t ** 1.9
        pts.append((cx - half, yy))
    right = [(2 * cx - px, py) for px, py in reversed(pts)]
    d.polygon(pts + right, fill=color)
    # handles: solid loops, same weight as the letter strokes
    lw = int(w * 0.075)
    for sgn in (-1, 1):
        ex = cx + sgn * (w / 2)
        box = [ex - w * 0.17, top + h * 0.04, ex + w * 0.17, top + h * 0.36]
        d.arc(box, 270 if sgn > 0 else 90, 90 if sgn > 0 else 270, fill=color, width=lw)
    # stem
    d.rectangle([cx - stem_w / 2, top + cup_h - 2, cx + stem_w / 2, top + h * 0.86], fill=color)
    # base
    d.polygon([(cx - w * 0.22, top + h * 0.86), (cx + w * 0.22, top + h * 0.86), (cx + w * 0.30, top + h),
               (cx - w * 0.30, top + h)], fill=color)


def wordmark(out: Path, size=1080):
    W = H = size * SS
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    big = F("oswald-700", int(240 * SS))
    cap = d.textbbox((0, 0), "E", font=big)
    cap_top, cap_h = cap[1], cap[3] - cap[1]
    left, right = "PLA", "ER"
    tw = cap_h * 0.74  # trophy width
    gap = cap_h * 0.16
    lw = d.textlength(left, font=big)
    rw = d.textlength(right, font=big)
    total = lw + gap + tw + gap + rw
    x0 = (W - total) / 2
    base_y = H * 0.40  # top of caps
    ty = base_y - cap_top
    d.text((x0, ty), left, font=big, fill=WHITE)
    trophy(d, x0 + lw + gap, base_y, tw, cap_h, GOLD)
    d.text((x0 + lw + gap + tw + gap, ty), right, font=big, fill=WHITE)
    # "WORLD" above with rules, "OF THE WEEK" below, sender at the bottom
    small = F("figtree-800", int(40 * SS))
    wtxt = "W O R L D"
    ww = d.textlength(wtxt, font=small)
    y_world = base_y - 80 * SS
    d.text((W / 2, y_world), wtxt, font=small, fill=GOLD, anchor="mm")
    for s in (-1, 1):
        x_in = W / 2 + s * (ww / 2 + 30 * SS)
        x_out = W / 2 + s * (total / 2)
        d.rectangle([min(x_in, x_out), y_world - 2 * SS, max(x_in, x_out), y_world + 2 * SS], fill=GOLD)
    sub = F("oswald-600", int(92 * SS))
    otw = "OF THE WEEK"
    # track it out to the width of PLAYER
    n = len(otw)
    plain = d.textlength(otw, font=sub)
    track = (total - plain) / (n - 1)
    x = x0
    y_sub = base_y + cap_h + 56 * SS
    for ch in otw:
        d.text((x, y_sub), ch, font=sub, fill=WHITE)
        x += d.textlength(ch, font=sub) + track
    tiny = F("figtree-800", int(24 * SS))
    d.text((W / 2, y_sub + 160 * SS), "W O R L D   B A S E B A L L   N E W S", font=tiny, fill=(255, 255, 255, 140),
           anchor="mm")
    im = im.resize((size, size), Image.LANCZOS)
    bbox = im.getbbox()
    im.save(out)
    return im


if __name__ == "__main__":
    wordmark(Path(sys.argv[1]))
