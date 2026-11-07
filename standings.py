"""Weekly standings carousel: one slide per league that is actually playing.

Data is read live from the public standings pages on worldbaseballnews.org at the moment of posting.
A league counts as "active" when its standings changed since the previous weekly post (more games
played than in the stored snapshot). Finished seasons and postseason-only weeks therefore drop out.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

import bot
from bot import (CFG, MARGIN, ON_DARK, ON_DARK_2, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED, RED_BRIGHT,
                 RED_SOFT, ROOT, TZ, WHITE, W, H, draw_chevrons, draw_footer, font, log)

SCFG = CFG["standings"]
SNAP_FILE = ROOT / "state" / "standings.json"
SITE = CFG["site_url"].rstrip("/")


# ----------------------------------------------------------------------------- data
def page_url(slug: str) -> str:
    return f"{SITE}/leagues/{slug}/standings/"


def fetch_standings(lg: dict) -> dict | None:
    r = requests.get(page_url(lg["slug"]), headers=bot.UA, timeout=30)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.content, "html.parser")
    groups = []
    for t in soup.find_all("table"):
        if not t.tbody:
            continue
        head = t.find_previous(["h2", "h3"])
        gname = head.get_text(" ", strip=True) if head and head.name == "h3" else ""
        cols = [th.get_text(strip=True).upper() for th in t.thead.find_all("th")] if t.thead else []
        rows = []
        for tr in t.tbody.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            vals = [c.get_text(" ", strip=True) for c in cells]
            team = tr.find("th", class_="tm") or (cells[1] if len(cells) > 1 else None)
            if team is None:
                continue
            full = team.find(class_="full")
            short = team.find(class_="abbr")
            img = team.find("img")
            row = dict(zip(cols, vals))
            row["team"] = full.get_text(strip=True) if full else team.get_text(" ", strip=True)
            row["short"] = short.get_text(strip=True) if short else row["team"]
            row["logo"] = (SITE + img["src"]) if img and img.get("src", "").startswith("/") else None
            rows.append(row)
        if rows:
            groups.append({"name": gname, "rows": rows})
    if not groups:
        return None
    games = 0
    for g in groups:
        for row in g["rows"]:
            games += sum(int(row.get(k) or 0) for k in ("W", "L", "T") if (row.get(k) or "").isdigit())
    h1 = soup.find("h1")
    season = re.search(r"(20\d\d)", h1.get_text()) if h1 else None
    return {"groups": groups, "games": games, "season": season.group(1) if season else ""}


def load_snap() -> dict:
    if SNAP_FILE.exists():
        return json.loads(SNAP_FILE.read_text(encoding="utf-8"))
    return {"leagues": {}, "posts": []}


def active_leagues(snap: dict) -> tuple[list[tuple[dict, dict]], dict]:
    """Leagues whose standings moved since the last weekly snapshot (and that have games at all).
    Also returns the new snapshot of every league."""
    out, new_snap = [], {}
    for lg in SCFG["leagues"]:
        try:
            data = fetch_standings(lg)
        except Exception as e:
            log(f"  {lg['key']}: fetch failed ({e})")
            continue
        if not data:
            log(f"  {lg['key']}: no standings")
            continue
        new_snap[lg["key"]] = {"games": data["games"], "season": data["season"]}
        if data["games"] == 0:
            log(f"  {lg['key']}: no games")
            continue
        prev = snap["leagues"].get(lg["key"], {})
        moved = data["games"] != prev.get("games") or data["season"] != prev.get("season")
        log(f"  {lg['key']}: {data['games']} team-games (last week {prev.get('games')}) -> "
            f"{'ACTIVE' if moved else 'not active'}")
        if moved:
            out.append((lg, data))
    return out, new_snap


# ----------------------------------------------------------------------------- visuals
_logo_cache: dict[str, Image.Image | None] = {}


def logo(url: str | None, size: int) -> Image.Image | None:
    if not url:
        return None
    if url not in _logo_cache:
        try:
            raw = requests.get(url, headers=bot.UA, timeout=20).content
            if url.endswith(".svg"):
                import cairosvg
                raw = cairosvg.svg2png(bytestring=raw, output_width=256, output_height=256)
            im = Image.open(BytesIO(raw)).convert("RGBA")
            im.thumbnail((256, 256), Image.LANCZOS)
            _logo_cache[url] = im
        except Exception as e:
            log(f"  logo failed {url}: {e}")
            _logo_cache[url] = None
    im = _logo_cache[url]
    if im is None:
        return None
    im = im.copy()
    im.thumbnail((size, size), Image.LANCZOS)
    return im


def draw_kicker(draw, y, chip, eyebrow):
    x = draw_chevrons(draw, MARGIN, y + 6, RED_BRIGHT)
    f_chip = font("figtree-800", 28)
    lw = draw.textlength(chip, font=f_chip)
    draw.rounded_rectangle([x + 8, y - 6, x + 8 + lw + 32, y + 40], radius=8, fill=RED)
    draw.text((x + 24, y + 17), chip, font=f_chip, fill=WHITE, anchor="lm")
    draw.text((x + 8 + lw + 32 + 18, y + 17), eyebrow, font=font("figtree-700", 26), fill=ON_DARK_2, anchor="lm")


def fit_text(draw, text, fname, start, minimum, width):
    for s in range(start, minimum - 1, -2):
        f = font(fname, s)
        if draw.textlength(text, font=f) <= width:
            return f
    return font(fname, minimum)


def week_label(now: datetime) -> str:
    return now.strftime("%b %-d, %Y").upper()


FLAGS = ROOT / "flags"
LEAGUE_LOGOS = ROOT / "league-logos"


def flag_img(code: str, h: int) -> Image.Image | None:
    f = FLAGS / f"{code}.png"
    if not f.exists():
        return None
    im = Image.open(f).convert("RGBA").resize((round(h * 4 / 3), h), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=max(3, h // 8), fill=255)
    im.putalpha(mask)
    return im


def draw_flags(canvas, draw, x, cy, codes, h=34) -> int:
    for c in codes or []:
        im = flag_img(c, h)
        if im:
            draw.rounded_rectangle([x - 2, cy - h / 2 - 2, x + im.width + 1, cy + h / 2 + 1], radius=max(3, h // 8) + 1,
                                   fill=PETROL_LINE)
            canvas.alpha_composite(im, (int(x), int(cy - h / 2)))
            x += im.width + 10
    return x


def league_tile(canvas, draw, lg, x, y, size):
    """League logo on a white rounded tile (logos are made for light backgrounds)."""
    tile = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([x, y, x + size, y + size], radius=size // 7, fill=WHITE + (128,))
    canvas.alpha_composite(tile)
    f = LEAGUE_LOGOS / f"{lg['key']}.png"
    if f.exists():
        im = Image.open(f).convert("RGBA")
        pad = int(size * 0.12)
        im.thumbnail((size - 2 * pad, size - 2 * pad), Image.LANCZOS)
        canvas.alpha_composite(im, (int(x + (size - im.width) / 2), int(y + (size - im.height) / 2)))
    else:
        fl = fit_text(draw, lg["label"].upper(), "oswald-700", int(size * 0.34), 14, size - 16)
        draw.text((x + size / 2, y + size / 2), lg["label"].upper(), font=fl, fill=PETROL_DEEP, anchor="mm")


def fit_title_block(draw, text, width):
    """League name: one line if it fits at a decent size, otherwise two balanced lines."""
    for size in range(76, 55, -2):
        f = font("oswald-700", size)
        if draw.textlength(text, font=f) <= width:
            return f, [text]
    for size in range(60, 37, -2):
        f = font("oswald-700", size)
        lines = bot.wrap(draw, text, f, width)
        if len(lines) <= 2 and all(draw.textlength(l, font=f) <= width for l in lines):
            return f, lines
    return font("oswald-700", 38), [text]


def draw_league_header(canvas, draw, lg, now, part=""):
    tile = 176
    x0 = MARGIN + tile + 34
    x = draw_chevrons(draw, x0, 76, RED_BRIGHT, n=3)
    f_chip = font("figtree-800", 26)
    label = lg["label"].upper()
    lw = draw.textlength(label, font=f_chip)
    draw.rounded_rectangle([x + 6, 64, x + 6 + lw + 28, 106], radius=8, fill=RED)
    draw.text((x + 20, 85), label, font=f_chip, fill=WHITE, anchor="lm")
    draw.text((x + 6 + lw + 28 + 16, 85), f"STANDINGS · {week_label(now)}", font=font("figtree-700", 24),
              fill=ON_DARK_2, anchor="lm")
    title = (lg["name"] + (f" · {part}" if part else "")).upper()
    f_title, lines = fit_title_block(draw, title, W - MARGIN - x0)
    lh = int(f_title.size * 1.06)
    ty = 120
    bottom = ty
    for i, l in enumerate(lines):
        draw.text((x0, ty + i * lh), l, font=f_title, fill=WHITE)
        bottom = draw.textbbox((x0, ty + i * lh), l, font=f_title)[3]
    cy = max(bottom + 38, 212)
    fx = draw_flags(canvas, draw, x0, cy, lg.get("flags"))
    draw.text((fx + 4, cy), (lg.get("country") or "").upper(), font=font("figtree-800", 26), fill=ON_DARK, anchor="lm")
    # logo tile centred on the text block (chip line top -> country line bottom)
    block_top, block_bottom = 64, cy + 18
    tile_y = int((block_top + block_bottom) / 2 - tile / 2)
    league_tile(canvas, draw, lg, MARGIN, tile_y, tile)
    return max(tile_y + tile, block_bottom) + 34


COLS = [("W", 70), ("L", 70), ("PCT", 108), ("GB", 86), ("L10", 96), ("STRK", 96)]


def render_league_slide(lg: dict, data: dict, out: Path, now: datetime, groups: list[dict] | None = None,
                        part: str = ""):
    groups = groups or data["groups"]
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 6], fill=RED)
    top = draw_league_header(canvas, draw, lg, now, part)

    n_rows = sum(len(g["rows"]) for g in groups)
    n_heads = sum(1 for g in groups if g["name"])
    bottom = H - 132 - 30
    head_h = 46
    row_h = min(118, (bottom - top - 50 - n_heads * head_h) / n_rows)
    # column header
    right = W - MARGIN
    xs = []
    for name, w in reversed(COLS):
        xs.insert(0, (name, right - w / 2))
        right -= w
    team_right = right - 10
    f_hdr = font("figtree-800", 22)
    draw.text((MARGIN + 6, top + 18), "#", font=f_hdr, fill=ON_DARK_2, anchor="lm")
    draw.text((MARGIN + 60, top + 18), "TEAM", font=f_hdr, fill=ON_DARK_2, anchor="lm")
    for name, cx in xs:
        draw.text((cx, top + 18), name, font=f_hdr, fill=ON_DARK_2, anchor="mm")
    draw.line([(MARGIN - 16, top + 42), (W - MARGIN + 16, top + 42)], fill=PETROL_LINE, width=2)

    y = top + 50
    num_size = int(min(40, row_h * 0.44))
    f_num = font("oswald-600", num_size)
    f_rank = font("oswald-600", num_size)
    logo_px = int(min(64, row_h * 0.62))
    # one team-name size for the whole table (consistent look); names that still don't fit use the short name
    name_w = team_right - (MARGIN + 60 + logo_px + 18)
    names = [r["team"].upper() for g in groups for r in g["rows"]]
    team_size = num_size
    while team_size > int(num_size * 0.72) and sum(
            draw.textlength(n, font=font("oswald-600", team_size)) > name_w for n in names) > len(names) // 4:
        team_size -= 2
    f_team = font("oswald-600", team_size)
    for g in groups:
        if g["name"]:
            draw.text((MARGIN, y + head_h / 2 + 2), g["name"].upper(), font=font("figtree-800", 24), fill=RED_SOFT,
                      anchor="lm")
            y += head_h
        for i, row in enumerate(g["rows"]):
            cy = y + row_h / 2
            if i % 2 == 0:
                draw.rounded_rectangle([MARGIN - 16, y + 3, W - MARGIN + 16, y + row_h - 3], radius=10, fill=PETROL_MID)
            if i == 0:
                draw.rounded_rectangle([MARGIN - 16, y + 3, MARGIN - 8, y + row_h - 3], radius=3, fill=RED_BRIGHT)
            draw.text((MARGIN + 6, cy), row.get("#") or str(i + 1), font=f_rank, fill=ON_DARK_2, anchor="lm")
            tx = MARGIN + 60
            lg_img = logo(row.get("logo"), logo_px)
            if lg_img:
                canvas.alpha_composite(lg_img, (int(tx + (logo_px - lg_img.width) / 2), int(cy - lg_img.height / 2)))
                tx += logo_px + 18
            name = row["team"].upper()
            if draw.textlength(name, font=f_team) > team_right - tx:
                name = row["short"].upper()
            draw.text((tx, cy), name, font=f_team, fill=WHITE, anchor="lm")
            for col, cx in xs:
                v = row.get(col, "")
                color = WHITE if col in ("W", "L") else ON_DARK
                if col == "STRK" and v.startswith("W"):
                    color = WHITE
                if col == "STRK" and v.startswith("L"):
                    color = RED_SOFT
                draw.text((cx, cy), v, font=f_num if col in ("W", "L") else font("figtree-700", int(num_size * 0.72)),
                          fill=color, anchor="mm")
            y += row_h
    draw_footer(draw, H - 132, SCFG["cover_cta"])
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, "JPEG", quality=92, optimize=True, progressive=False)


def render_cover(items: list[tuple[dict, dict]], out: Path, now: datetime):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, W, 6], fill=RED)
    draw_kicker(draw, 84, "STANDINGS", week_label(now))
    draw.text((MARGIN, 150), "WEEKLY", font=font("oswald-700", 150), fill=WHITE)
    draw.text((MARGIN, 318), "STANDINGS", font=font("oswald-700", 150), fill=WHITE)
    draw.text((MARGIN, 520), f"WHO LEADS IN THE {len(items)} LEAGUES IN ACTION", font=font("figtree-800", 30),
              fill=RED_SOFT)
    top, bottom = 590, H - 132 - 40
    row_h = min(110, (bottom - top) / max(len(items), 1))
    for i, (lg, data) in enumerate(items):
        y = top + i * row_h
        cy = y + row_h / 2
        if i % 2 == 0:
            draw.rounded_rectangle([MARGIN - 16, y + 4, W - MARGIN + 16, y + row_h - 4], radius=10, fill=PETROL_MID)
        leader = data["groups"][0]["rows"][0]
        ts = int(row_h * 0.72)
        league_tile(canvas, draw, lg, MARGIN - 4, cy - ts / 2, ts)
        fx = draw_flags(canvas, draw, MARGIN + ts + 14, cy - 17, lg.get("flags"), h=24)
        draw.text((MARGIN + ts + 14, cy + 17), lg["label"].upper(), font=font("figtree-800", 24), fill=RED_SOFT,
                  anchor="lm")
        tx = MARGIN + 300
        im = logo(leader.get("logo"), int(row_h * 0.6))
        if im:
            canvas.alpha_composite(im, (int(tx), int(cy - im.height / 2)))
            tx += int(row_h * 0.6) + 18
        rec = f"{leader.get('W')}-{leader.get('L')}"
        f_rec = font("oswald-600", 40)
        rw = draw.textlength(rec, font=f_rec)
        name = leader["team"].upper()
        f_team = fit_text(draw, name, "oswald-600", 42, 32, W - MARGIN - rw - 30 - tx)
        if draw.textlength(name, font=f_team) > W - MARGIN - rw - 30 - tx:
            name = leader["short"].upper()
        draw.text((tx, cy), name, font=f_team, fill=WHITE, anchor="lm")
        draw.text((W - MARGIN, cy), rec, font=f_rec, fill=ON_DARK, anchor="rm")
    draw_footer(draw, H - 132, "SWIPE FOR ALL TABLES")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, "JPEG", quality=92, optimize=True, progressive=False)


MAX_ROWS_PER_SLIDE = 16


def split_groups(data: dict) -> list[list[dict]]:
    """Big multi-division leagues (MLB, MiLB) don't fit on one slide: split by division groups."""
    chunks, cur, n = [], [], 0
    for g in data["groups"]:
        if cur and n + len(g["rows"]) > MAX_ROWS_PER_SLIDE:
            chunks.append(cur)
            cur, n = [], 0
        cur.append(g)
        n += len(g["rows"])
    if cur:
        chunks.append(cur)
    return chunks


def build_caption(items: list[tuple[dict, dict]], now: datetime, platform: str = "instagram") -> str:
    lines = [f"📊 Weekly standings — {now.strftime('%B %-d, %Y')}",
             "Where every league in action stands this week:"]
    for lg, data in items:
        leader = data["groups"][0]["rows"][0]
        lines.append(f"• {lg['label']}: {leader['team']} lead at {leader.get('W')}-{leader.get('L')}")
    body = "\n".join(lines)
    swipe = "➡️ Swipe for the full tables."
    more = (f"👉 All standings: {SITE}/leagues/" if platform == "facebook"
            else "👉 Live standings for every league via the link in our bio.")
    tags = ["#baseball", "#standings", "#worldbaseballnews"]
    for lg, _ in items:
        tags += CFG["league_hashtags"].get(lg["key"], [f"#{lg['label'].replace(' ', '')}"])[:1]
    tags = list(dict.fromkeys(tags))
    return "\n\n".join([body, swipe, more, " ".join(tags[:15])])


def prepare(out_dir: Path, now: datetime | None = None) -> dict | None:
    now = now or datetime.now(TZ)
    snap = load_snap()
    items, new_snap = active_leagues(snap)
    if not items:
        log("No active leagues this week.")
        return None
    stamp = now.strftime("%Y-%m-%d")
    files = [out_dir / f"standings-{stamp}-1.jpg"]
    render_cover(items, files[0], now)
    for lg, data in items:
        chunks = split_groups(data)
        for j, groups in enumerate(chunks, start=1):
            f = out_dir / f"standings-{stamp}-{lg['key']}{'-' + str(j) if len(chunks) > 1 else ''}.jpg"
            render_league_slide(lg, data, f, now, groups, f"{j}/{len(chunks)}" if len(chunks) > 1 else "")
            files.append(f)
    files = files[:10]  # Instagram carousel limit
    return {"files": files, "items": items, "caption": build_caption(items, now),
            "caption_facebook": build_caption(items, now, "facebook"),
            "snapshot": new_snap}


# ----------------------------------------------------------------------------- posting
def due(now: datetime | None = None) -> bool:
    """Monday after post_after (NL time) and no standings carousel posted yet this ISO week."""
    now = now or datetime.now(TZ)
    if now.weekday() != SCFG["post_weekday"] or now.strftime("%H:%M") < SCFG["post_after"]:
        return False
    week = now.isocalendar()[:2]
    for p in load_snap().get("posts", []):
        if tuple(datetime.fromisoformat(p["posted_at"]).astimezone(TZ).isocalendar()[:2]) == tuple(week):
            return False
    return True


def cmd_prepare(force: bool = False) -> bool:
    import os
    if not force and not due():
        return False
    now = datetime.now(TZ)
    res = prepare(bot.POSTS_DIR, now)
    if not res:
        bot.gh_output("has_post", "false")
        return False
    collabs = [c.strip().lstrip("@") for c in os.environ.get("COLLABORATORS", "").split(",") if c.strip()]
    collabs = collabs or SCFG.get("collaborators", [])
    first, extra = res["files"][0], res["files"][1:]
    pending = {
        "url": f"standings:{now.strftime('%Y-%m-%d')}", "slot": "standings",
        "headline": f"Weekly standings {now.strftime('%b %-d, %Y')}: " + ", ".join(lg["label"] for lg, _ in res["items"]),
        "title_on_image": "WEEKLY STANDINGS", "image_file": str(first.relative_to(ROOT)),
        "image_url": CFG["image_base_url"] + first.name, "extra_images": [f.name for f in extra],
        "caption": res["caption"], "caption_facebook": res["caption_facebook"], "tag_context": "",
        "collaborators": collabs, "standings_snapshot": res["snapshot"],
    }
    bot.PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Prepared standings carousel: {len(res['files'])} slides, collaborators={collabs}")
    print(f"::notice title=Standings::{pending['headline']}", flush=True)
    bot.gh_output("has_post", "true")
    return True


def save_after_post(snapshot: dict, media_id: str):
    snap = load_snap()
    snap["leagues"].update(snapshot)
    snap.setdefault("posts", []).append({"posted_at": datetime.now(TZ).isoformat(timespec="seconds"),
                                         "media_id": media_id, "leagues": sorted(snapshot)})
    snap.pop("note", None)
    SNAP_FILE.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")
