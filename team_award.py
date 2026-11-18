"""Team-style award / selection posts (Gold Gloves, Golden Gloves, Defensive Awards, All-Star / All-League teams,
Best Nine, All-MLB ...) in the fixed 'field' format:

  slide 1   cover: article photo + gold award title + key figures
  slide 2+  per group (AL/NL, Central/Pacific, First/Second Team, or one group) the winners on a baseball field,
            with official headshots (fallback: team logo); multiple pitchers get an extra 'pitchers' slide.

Used automatically when the bot picks an article whose title is a team-style award (see is_team_award), and
manually via `python bot.py prepare-url <url>`.
"""
from __future__ import annotations

import json
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

import bot
from bot import (CFG, MARGIN, ON_DARK, PETROL_DEEP, PETROL_LINE, RED, ROOT, WHITE, W, H, draw_chevrons, draw_footer,
                 font, log)

SITE = CFG["site_url"].rstrip("/")
LEAGUES = {l["key"]: l for l in CFG["standings"]["leagues"]}
UA = {"User-Agent": "Mozilla/5.0 (compatible; WBN-bot/1.0; +https://worldbaseballnews.org)"}
GOLD = (222, 184, 96)
GOLD_DEEP = (176, 136, 52)
GRASS = (9, 62, 86)
DIRT = (24, 84, 108)

AWARDS = [  # (title regex, display name, emoji)
    (r"golden gloves?", "GOLDEN GLOVES", "🧤"),
    (r"gold gloves?", "GOLD GLOVES", "🧤"),
    (r"defensive awards?|defense awards?|fielding awards?", "DEFENSIVE AWARDS", "🧤"),
    (r"all-?mlb", "ALL-MLB TEAM", "⭐"),
    (r"best nine", "BEST NINE", "⭐"),
    (r"all-?star (team|selections?|rosters?|starters?)", "ALL-STAR TEAM", "⭐"),
    (r"all-?(league|star|tournament|world) teams?", "ALL-STAR TEAM", "⭐"),
    (r"team of the (year|season)", "TEAM OF THE YEAR", "⭐"),
]
POS_RULES = [
    (r"(sp|starting pitchers?|starters?)", "SP"), (r"(rp|relief pitchers?|relievers?|closers?)", "RP"),
    (r"(p|pitchers?)", "P"), (r"(c|catchers?)", "C"), (r"(1b|first base(man)?)", "1B"),
    (r"(2b|second base(man)?)", "2B"), (r"(3b|third base(man)?)", "3B"), (r"(ss|shortstops?)", "SS"),
    (r"(lf|left field(er)?)", "LF"), (r"(cf|cent(er|re) field(er)?)", "CF"), (r"(rf|right field(er)?)", "RF"),
    (r"(of|outfield(ers?)?)", "OF"), (r"(dh|designated hitters?)", "DH"),
    (r"(ut|util|utility( player)?|utility (infielder|outfielder|man))", "UT"),
]
GROUP_WORDS = r"(american league|national league|central league|pacific league|first team|second team|third team|" \
              r"north|south|east|west|eastern league|western league|al|nl)"
FIELD = {"P": (540, 850), "C": (540, 1080), "1B": (860, 840), "2B": (695, 650), "SS": (385, 650), "3B": (220, 840),
         "LF": (200, 470), "CF": (540, 365), "RF": (880, 470), "EXTRA": (225, 1080)}
HOME = (540, 1200)
TWO_WORD_NICKS = ("Red Sox", "White Sox", "Blue Jays", "Golden Eagles", "Sea Dogs", "Wild Things")
NPB_SHORT = {"DeNA": "DeNA", "Seibu": "Seibu", "SoftBank": "SoftBank", "Rakuten": "Rakuten", "Lotte": "Lotte",
             "Orix": "Orix", "Yomiuri": "Giants", "Chunichi": "Chunichi", "Hiroshima": "Hiroshima",
             "Yakult": "Yakult", "Nippon-Ham": "Nippon-Ham", "Hanshin": "Hanshin"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn").lower())
    return re.sub(r"\s+", " ", s).strip()


def slug(s: str) -> str:
    return re.sub(r"\s+", "-", norm(s))


def award_of(title: str):
    t = (title or "").lower()
    for rx, name, emoji in AWARDS:
        if re.search(rx, t):
            return name, emoji
    return None


def is_team_award(title: str) -> bool:
    t = (title or "").lower()
    return bool(award_of(title)) and "platinum" not in t


def pos_code(text: str) -> str | None:
    t = norm(text).replace(" base man", " baseman")
    for rx, code in POS_RULES:
        if re.fullmatch(rx, t):
            return code
    return None


def short_team(team: str, league: str) -> str:
    team = re.sub(r"\s+", " ", team or "").strip()
    if league in ("npb", "npbfarm"):
        for k, v in NPB_SHORT.items():
            if k.lower() in team.lower():
                return v
    if league in ("kbo", "cpbl"):
        return team.split(" ")[0] if " " in team else team
    if team == "Arizona Diamondbacks":
        return "D-backs"
    for nick in TWO_WORD_NICKS:
        if team.endswith(nick):
            return nick
    if league in CFG["potw"]["statsapi_leagues"]:  # North American style: the nickname
        return team.split(" ")[-1]
    return team.split(" ")[-1] if len(team) > 16 else team


# ----------------------------------------------------------------------------- parsing
LINE_RX = re.compile(r"^\s*(?P<pos>[A-Za-z0-9 /.\-]{1,32}?)\s*[:–—]\s*(?P<name>[^,—–(|]+?)\s*(?:[,—–(|]|\bof\b)\s*(?P<team>[^)]+?)\)?\s*$")


def parse_winners(html: str) -> list[dict]:
    """Groups of winners from the article body: headings set the group, tables and 'Pos: Name — Team' lines fill it."""
    soup = BeautifulSoup(html, "html.parser")
    groups, heading = [], ""

    def add(group_name, pos, name, team):
        if not (pos and name):
            return
        g = next((g for g in groups if g["heading"] == group_name), None)
        if not g:
            g = {"heading": group_name, "winners": []}
            groups.append(g)
        g["winners"].append({"pos": pos, "name": re.sub(r"\s+", " ", name).strip(" *"),
                             "team": re.sub(r"\s+", " ", team or "").strip(" *.")})

    for el in soup.find_all(["h2", "h3", "h4", "table", "p", "li"]):
        if el.name in ("h2", "h3", "h4"):
            heading = el.get_text(" ", strip=True)
            continue
        if el.name == "table":
            rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in el.find_all("tr")]
            if not rows:
                continue
            head = [h.lower() for h in rows[0]]
            ip = next((i for i, h in enumerate(head) if "pos" in h), None)
            iname = next((i for i, h in enumerate(head) if any(k in h for k in ("winner", "player", "name"))), None)
            iteam = next((i for i, h in enumerate(head) if any(k in h for k in ("team", "club", "organization"))), None)
            body = rows[1:]
            if ip is None and len(head) >= 2 and pos_code(rows[0][0]):  # no header row
                ip, iname, iteam, body = 0, 1, (2 if len(head) > 2 else None), rows
            if ip is not None and iname is not None:
                for r in body:
                    if len(r) > max(ip, iname):
                        add(heading, pos_code(r[ip]), r[iname], r[iteam] if iteam is not None and len(r) > iteam else "")
            elif ip is not None:  # Position | Group A | Group B with "Name, Team" cells
                for r in body:
                    for ci, h in enumerate(rows[0]):
                        if ci == ip or ci >= len(r):
                            continue
                        name, _, team = r[ci].partition(",")
                        add(h, pos_code(r[ip]), name, team)
            continue
        if el.find_parent("table"):
            continue
        for br in el.find_all("br"):
            br.replace_with("\n")
        for line in re.sub(r"[ \t]+", " ", el.get_text(" ")).split("\n"):
            m = LINE_RX.match(line)
            if m and pos_code(m["pos"]):
                add(heading, pos_code(m["pos"]), m["name"], m["team"])
    return [g for g in groups if len(g["winners"]) >= 6]


def group_title(heading: str, n: int, single: bool = False) -> str:
    m = re.search(r"\b" + GROUP_WORDS + r"\b", heading.lower())
    if m:
        word = m.group(0)
        return {"al": "AMERICAN LEAGUE", "nl": "NATIONAL LEAGUE"}.get(word, word.upper())
    return f"ALL {n} WINNERS"


# ----------------------------------------------------------------------------- photos
_npb_index = None


def npb_index():
    global _npb_index
    if _npb_index is None:
        _npb_index = {}
        for t in ["g", "t", "db", "c", "s", "d", "h", "l", "f", "b", "m", "e"]:
            u = f"https://npb.jp/bis/eng/teams/rst_{t}.html"
            try:
                s = BeautifulSoup(requests.get(u, headers=UA, timeout=30).content, "html.parser")
            except Exception:
                continue
            for a in s.find_all("a", href=True):
                if "/players/" in a["href"]:
                    _npb_index[norm(a.get_text(" ", strip=True))] = urljoin(u, a["href"])
    return _npb_index


def npb_photo(name):
    first, _, last = name.partition(" ")
    idx = npb_index()
    page = idx.get(norm(f"{last}, {first}")) or idx.get(norm(f"{last} {first}")) or idx.get(norm(name))
    if not page and "o" in last.lower():  # Oyama / Ohyama style romanisation
        page = idx.get(norm(f"{last.replace('o', 'oh', 1)} {first}"))
    if not page:
        return None
    s = BeautifulSoup(requests.get(page, headers=UA, timeout=30).content, "html.parser")
    img = s.select_one("#pc_v_photo img, .player_photo img, img[src*='players'], img[src*='photo']")
    return urljoin(page, img["src"]) if img else None


def kbo_photo(name):
    u = "https://eng.koreabaseball.com/Teams/PlayerSearch.aspx"
    sess = requests.Session()
    s = BeautifulSoup(sess.get(u, headers=UA, timeout=30).content, "html.parser")
    form = {i["name"]: i.get("value", "") for i in s.select("input[name]")}
    box = next((k for k in form if k.endswith("txtPlayerSearch")), None)
    btn = s.find("a", href=re.compile("btnPlayerSearch"))
    if not box or not btn:
        return None
    target = re.search(r"__doPostBack\('([^']+)'", btn["href"].replace("&#39;", "'"))
    for q in (name, name.replace("-", ""), name.split(" ")[-1]):
        form[box] = q
        form["__EVENTTARGET"] = target.group(1) if target else ""
        r = sess.post(u, data=form, headers=UA, timeout=30)
        codes = re.findall(r"pcode=(\d+)", r.text)
        if codes:
            from datetime import datetime
            return f"https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/{datetime.now().year}/{codes[0]}.jpg"
    return None


def mlb_photo(name):
    r = requests.get("https://statsapi.mlb.com/api/v1/people/search", params={"names": name}, timeout=30).json()
    people = r.get("people") or []
    if not people:
        return None
    pid = people[0]["id"]
    return f"https://img.mlbstatic.com/mlb-photos/image/upload/w_420,q_auto:best,f_png/v1/people/{pid}/headshot/67/current"


def team_logo(team, league):
    import standings
    try:
        d = standings.fetch_standings(LEAGUES[league])
    except Exception:
        return None
    t = norm(team)
    for g in (d or {}).get("groups", []):
        for row in g["rows"]:
            if row.get("logo") and (t and (t in norm(row["team"]) or norm(row["team"]) in t or norm(row["short"]) == t)):
                return standings.logo(row["logo"], 256)
    return None


def photo_for(w, league):
    """Square headshot (RGBA) or None. Order: official league source by league, fallback team logo."""
    src = None
    try:
        if league in ("npb", "npbfarm"):
            src = npb_photo(w["name"])
        elif league == "kbo":
            src = kbo_photo(w["name"])
        elif league in CFG["potw"]["statsapi_leagues"]:
            src = mlb_photo(w["name"])
    except Exception as e:
        log(f"  photo lookup failed for {w['name']}: {e}")
    if src:
        try:
            im = Image.open(BytesIO(requests.get(src, headers=UA, timeout=30).content)).convert("RGBA")
            if im.width >= 60:
                im = im.crop((0, 0, im.width, im.width)) if im.height > im.width else im
                bg = Image.new("RGBA", im.size, (232, 232, 232, 255))
                bg.alpha_composite(im)
                return bg, "photo"
        except Exception:
            pass
    logo = team_logo(w["team"], league)
    if logo:
        tile = Image.new("RGBA", (256, 256), (255, 255, 255, 255))
        logo.thumbnail((180, 180), Image.LANCZOS)
        tile.alpha_composite(logo, ((256 - logo.width) // 2, (256 - logo.height) // 2))
        return tile, "logo"
    return None, None


# ----------------------------------------------------------------------------- drawing
def gold_text(canvas, xy, text, f, anchor="la"):
    d = ImageDraw.Draw(canvas)
    box = d.textbbox(xy, text, font=f, anchor=anchor)
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255, anchor=anchor)
    grad = Image.new("RGBA", canvas.size, GOLD + (255,))
    gd = ImageDraw.Draw(grad)
    h = max(1, box[3] - box[1])
    for i in range(h):
        c = tuple(int(GOLD[k] + (GOLD_DEEP[k] - GOLD[k]) * i / h) for k in range(3))
        gd.line([(box[0], box[1] + i), (box[2], box[1] + i)], fill=c + (255,))
    canvas.paste(grad, (0, 0), mask)


def draw_field(canvas):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    R, hx, hy = 900, *HOME
    d.pieslice([hx - R, hy - R, hx + R, hy + R], 225, 315, fill=GRASS + (255,))
    d.pieslice([hx - 520, hy - 520, hx + 520, hy + 520], 225, 315, fill=DIRT + (255,))
    s = 235
    b1, b2, b3 = (hx + s, hy - s), (hx, hy - 2 * s), (hx - s, hy - s)
    d.polygon([(hx, hy - 34), (b1[0] - 34, b1[1]), (b2[0], b2[1] + 34), (b3[0] + 34, b3[1])], fill=GRASS + (255,))
    d.ellipse([hx - 70, hy - 70, hx + 70, hy + 70], fill=DIRT + (255,))
    line = (255, 255, 255, 120)
    d.line([HOME, (hx + 760, hy - 760)], fill=line, width=4)
    d.line([HOME, (hx - 760, hy - 760)], fill=line, width=4)
    d.arc([hx - R, hy - R, hx + R, hy + R], 225, 315, fill=(255, 255, 255, 60), width=4)
    for bx, by in (b1, b2, b3):
        d.rectangle([bx - 11, by - 11, bx + 11, by + 11], fill=(255, 255, 255, 230))
    d.polygon([(hx - 11, hy - 6), (hx + 11, hy - 6), (hx + 11, hy + 6), (hx, hy + 14), (hx - 11, hy + 6)],
              fill=(255, 255, 255, 230))
    d.ellipse([hx - 30, hy - s - 30, hx + 30, hy - s + 30], fill=DIRT + (255,), outline=(255, 255, 255, 50))
    canvas.alpha_composite(lay)


FAMILY_FIRST = set("""kim lee park choi jung jeong kang cho yoon jang lim han oh seo shin kwon hwang ahn song yoo hong
jeon ko moon yang son bae baek heo nam noh ha kwak sung cha joo woo koo min ryu na jin ji uhm chae won chun bang gong hyun
ham byun yeom yeo choo do so seok sun seol ma gil wi pyo myung ki ban wang geum ok yook in maeng je mo tak kook eo eun
lin chen huang wu liu tsai hsu cheng hsieh kuo hung tseng chiu liao lai chou yeh su chuang lu chiang ho lo kao chang shih
fan teng chu pan yu tu tsao chung hu hsiao zhang zhao li""".split())


def name_lines(w, league, short):
    parts = w["name"].split(" ")
    if len(parts) == 1 or (league in ("kbo", "cpbl", "cpb") and parts[0].lower() in FAMILY_FIRST):
        return w["name"].upper(), short.upper()
    if parts[-1] in ("Jr.", "Sr.", "II", "III") and len(parts) > 2:
        first, last = " ".join(parts[:-2]), " ".join(parts[-2:])
    else:
        first, last = parts[0], " ".join(parts[1:])
    return last.upper(), f"{first.upper()} · {short.upper()}"


def avatar(canvas, d, cx, cy, label, w, league, size=112):
    img = w.get("_img")
    x0, y0 = int(cx - size / 2), int(cy - size / 2 - 30)
    d.ellipse([x0 - 6, y0 - 6, x0 + size + 5, y0 + size + 5], fill=GOLD)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    if img is not None:
        canvas.paste(img.resize((size, size), Image.LANCZOS), (x0, y0), mask)
    else:
        d.ellipse([x0, y0, x0 + size, y0 + size], fill=PETROL_DEEP)
        ini = "".join(p[0] for p in w["name"].split()[:2]).upper()
        d.text((cx, y0 + size / 2), ini, font=font("oswald-700", 44), fill=WHITE, anchor="mm")
    f_pos = font("oswald-700", 26)
    pw = d.textlength(label, font=f_pos) + 18
    d.rounded_rectangle([x0 + size - pw + 14, y0 - 4, x0 + size + 14, y0 + 30], radius=8, fill=RED)
    d.text((x0 + size - pw / 2 + 14, y0 + 13), label, font=f_pos, fill=WHITE, anchor="mm")
    big, sub = name_lines(w, league, short_team(w["team"], league))
    ty = y0 + size + 12
    f_big, f_sub = font("oswald-700", 30 if size < 140 else 34), font("figtree-800", 17 if size < 140 else 19)
    while d.textlength(big, font=f_big) > 300 and f_big.size > 20:
        f_big = font("oswald-700", f_big.size - 2)
    hgt = 62 if size < 140 else 70
    bw = max(d.textlength(big, font=f_big), d.textlength(sub, font=f_sub)) + 24
    d.rounded_rectangle([cx - bw / 2, ty, cx + bw / 2, ty + hgt], radius=10, fill=PETROL_DEEP + (235,))
    d.text((cx, ty + hgt * 0.36), big, font=f_big, fill=WHITE, anchor="mm")
    d.text((cx, ty + hgt * 0.8), sub, font=f_sub, fill=GOLD, anchor="mm")


def header(canvas, d, kicker, title, league):
    import standings
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), kicker, font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    size = 84
    while d.textlength(title, font=font("oswald-700", size)) > W - 2 * MARGIN - 140:
        size -= 2
    d.text((MARGIN, 136 + (84 - size) * 0.8), title, font=font("oswald-700", size), fill=WHITE)
    standings.league_tile(canvas, d, LEAGUES[league], W - MARGIN - 110, 70, 110)


def layout(winners):
    """Split a group into field slots, pitchers (if more than one) and extras."""
    pitchers = [w for w in winners if w["pos"] in ("P", "SP", "RP")]
    field, extra = {}, []
    if len(pitchers) == 1:
        field["P"] = pitchers[0]
        pitchers = []
    ofs = [w for w in winners if w["pos"] == "OF"]
    for slot, w in zip(("LF", "CF", "RF"), ofs):
        field[slot] = dict(w, _label="OF")
    for w in winners:
        if w in pitchers or w["pos"] in ("P", "OF") or w["pos"] in field and w is field.get(w["pos"]):
            continue
        slot = w["pos"] if w["pos"] in FIELD and w["pos"] not in field and w["pos"] != "EXTRA" else None
        if w["pos"] in ("DH", "UT") and "EXTRA" not in field:
            field["EXTRA"] = w
        elif slot:
            field[slot] = w
        else:
            extra.append(w)
    extra += [w for w in ofs[3:]]
    return field, pitchers, extra


def field_slide(out, kicker, title, league, field, footer):
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    draw_field(canvas)
    d = ImageDraw.Draw(canvas)
    header(canvas, d, kicker, title, league)
    for slot, w in field.items():
        avatar(canvas, d, *FIELD[slot], w.get("_label") or w["pos"], w, league)
    draw_footer(d, H - 132, footer)
    canvas.convert("RGB").save(out, "JPEG", quality=93)


def grid_slide(out, kicker, title, league, sections, footer):
    """Pitchers / extra winners: sections of avatars in rows of 3."""
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse([W / 2 - 520, 380, W / 2 + 520, 1260], fill=GRASS + (255,))
    canvas.alpha_composite(lay)
    d = ImageDraw.Draw(canvas)
    header(canvas, d, kicker, title, league)
    y = 290
    total_rows = sum((len(ws) + 2) // 3 for _, ws in sections)
    size = 130 if total_rows <= 3 else 104
    step = 260 if size == 130 else 215
    for name, ws in sections:
        d.text((MARGIN, y), name, font=font("figtree-800", 24), fill=GOLD)
        y += 140 if size == 130 else 120
        for i in range(0, len(ws), 3):
            row = ws[i:i + 3]
            xs = [220, 540, 860] if len(row) == 3 else ([380, 700] if len(row) == 2 else [540])
            for x, w in zip(xs, row):
                avatar(canvas, d, x, y, w["pos"], w, league, size=size)
            y += step
        y -= (step - (size + 120))
    draw_footer(d, H - 132, footer)
    canvas.convert("RGB").save(out, "JPEG", quality=93)


def cover(out, photo_url, kicker, award_title, league, stats, subtitle):
    from potw_run import face_crop
    canvas = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    try:
        im = Image.open(BytesIO(requests.get(photo_url, headers=UA, timeout=40).content)).convert("RGB")
        box = face_crop(im)
        im = im.crop(tuple(box))
        k = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * k + 1), int(im.height * k + 1)), Image.LANCZOS)
        canvas.paste(im.crop(((im.width - W) // 2, 0, (im.width - W) // 2 + W, H)), (0, 0))
    except Exception as e:
        log(f"  cover photo failed: {e}")
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for y in range(H):
        t = max(0.0, (y - H * 0.35) / (H * 0.65))
        if t:
            gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(255 * min(1, t ** 0.8 * 1.1)),))
    for y in range(260):
        gd.line([(0, y), (W, y)], fill=PETROL_DEEP + (int(170 * (1 - y / 260) ** 1.4),))
    canvas.alpha_composite(g)
    d = ImageDraw.Draw(canvas)
    import standings
    d.rectangle([0, 0, W, 6], fill=GOLD)
    x = draw_chevrons(d, MARGIN, 90, GOLD)
    d.text((x + 10, 100), kicker, font=font("figtree-800", 24), fill=GOLD, anchor="lm")
    standings.league_tile(canvas, d, LEAGUES[league], W - MARGIN - 110, 70, 110)
    base = 900
    d.text((MARGIN, base - 150), f"{award_title[0]}", font=font("oswald-700", 84), fill=WHITE, anchor="ls")
    size = 158
    while d.textlength(award_title[1], font=font("oswald-700", size)) > W - 2 * MARGIN:
        size -= 4
    gold_text(canvas, (MARGIN - 4, base), award_title[1], font("oswald-700", size), anchor="ls")
    d.text((MARGIN, base + 60), subtitle, font=font("figtree-700", 34), fill=ON_DARK, anchor="ls")
    cw = (W - 2 * MARGIN) / len(stats)
    sy = base + 110
    for i, (v, lab) in enumerate(stats):
        cx = MARGIN + i * cw
        if i:
            d.line([(cx, sy + 10), (cx, sy + 100)], fill=PETROL_LINE, width=2)
        tx = cx + (24 if i else 0)
        d.text((tx, sy + 76), v, font=font("oswald-700", 80), fill=WHITE, anchor="ls")
        d.text((tx + 2, sy + 110), lab, font=font("figtree-800", 22), fill=GOLD, anchor="ls")
    draw_footer(d, H - 132, "SWIPE FOR ALL WINNERS")
    canvas.convert("RGB").save(out, "JPEG", quality=93)


# ----------------------------------------------------------------------------- main
def fetch_post(url):
    slug_ = urlparse(url).path.rstrip("/").split("/")[-1]
    r = requests.get(f"{SITE}/wp-json/wp/v2/posts", params={"slug": slug_, "_embed": "wp:featuredmedia"},
                     headers=bot.UA, timeout=30).json()
    return r[0] if r else None


def build(url: str, out_dir: Path, league: str | None = None) -> dict | None:
    """Render the carousel for a team-award article. Returns a custom spec dict (images + captions) or None."""
    import html as htmlmod
    post = fetch_post(url)
    if not post:
        return None
    title = htmlmod.unescape(re.sub("<[^>]+>", "", post["title"]["rendered"]))
    aw = award_of(title)
    if not aw:
        return None
    groups = parse_winners(post["content"]["rendered"])
    if not groups:
        log("  team award: could not parse winners, falling back to the normal post")
        return None
    league = league or bot.league_slug(url)
    league = {"serie-a": "seriea", "czech-extraliga": "extraliga", "french-d1": "d1", "swiss-nla": "nla",
              "swiss-national-league-a": "nla"}.get(league, league)
    if league not in LEAGUES:
        log(f"  team award: unknown league {league}")
        return None
    lab = LEAGUES[league]["label"].upper()
    year = re.search(r"(20\d\d)", title)
    year = year.group(1) if year else post["date"][:4]
    award_name, emoji = aw
    kicker = f"{year} {lab} {award_name}"
    # photos
    n_photo = n_all = 0
    for g in groups:
        for w in g["winners"]:
            w["_img"], kind = photo_for(w, league)
            n_all += 1
            n_photo += kind == "photo"
    log(f"  team award: {n_all} winners in {len(groups)} group(s), {n_photo} headshots")
    slug_ = slug(f"{lab} {award_name} {year}")[:60]
    files = []
    single = len(groups) == 1
    slides = []
    for gi, g in enumerate(groups):
        gtitle = group_title(g["heading"], len(g["winners"]), single)
        field, pitchers, extra = layout(g["winners"])
        slides.append(("field", gtitle, field))
        if pitchers or extra:
            secs = []
            sp = [w for w in pitchers if w["pos"] == "SP"]
            rp = [w for w in pitchers if w["pos"] == "RP"]
            pp = [w for w in pitchers if w["pos"] == "P"]
            if sp:
                secs.append(("STARTING PITCHERS", sp))
            if rp:
                secs.append(("RELIEF PITCHERS", rp))
            if pp:
                secs.append(("PITCHERS", pp))
            if extra:
                secs.append(("ALSO SELECTED", extra))
            slides.append(("grid", f"{gtitle} · {'PITCHERS' if pitchers and not extra else 'MORE'}"
                           if not gtitle.startswith("ALL ") else ("PITCHERS" if pitchers else "MORE WINNERS"), secs))
    slides = slides[:9]
    for i, (kind, t, payload) in enumerate(slides, start=2):
        f = out_dir / f"{slug_}-{i}.jpg"
        last = i == len(slides) + 1
        nxt = slides[i - 1][1] if not last else ""
        footer = "FULL STORY · LINK IN BIO" if last else ("SWIPE FOR THE PITCHERS" if slides[i - 1][0] == "grid"
                                                         else f"SWIPE: {nxt[:22]}")
        if kind == "field":
            field_slide(f, kicker, t, league, payload, footer)
        else:
            grid_slide(f, kicker, t, league, payload, footer)
        files.append(f.name)
    # cover
    teams = {}
    for g in groups:
        for w in g["winners"]:
            k = short_team(w["team"], league)
            teams[k] = teams.get(k, 0) + 1
    top = sorted(teams.items(), key=lambda kv: -kv[1])
    stats = [(str(n_all), "WINNERS")]
    if top and top[0][1] > 1:
        stats.append((str(top[0][1]), top[0][0].upper()))
    if len(groups) > 1:
        stats.append((str(len(groups)), "TEAMS" if "TEAM" in "".join(g["heading"].upper() for g in groups) else "LEAGUES"))
    elif len(top) > 1 and top[1][1] > 1:
        stats.append((str(top[1][1]), top[1][0].upper()))
    media = ((post.get("_embedded") or {}).get("wp:featuredmedia") or [{}])[0].get("source_url")
    words = award_name.split(" ")
    big = award_name if len(award_name) <= 16 else award_name
    subtitle = {"🧤": f"{lab}'s best defenders, position by position.",
                "⭐": f"{lab}'s best players, position by position."}[emoji]
    cover_f = out_dir / f"{slug_}-1.jpg"
    cover(cover_f, media, f"{lab} · {bot.datetime.now(bot.TZ).strftime('%B %-d, %Y').upper()}",
          (f"{year} {lab}", big), league, stats[:3], subtitle)
    files.insert(0, cover_f.name)
    # caption
    lines = []
    for g in groups:
        gt = group_title(g["heading"], len(g["winners"]), single)
        entries = " · ".join(f"{w['pos']} {w['name']} ({short_team(w['team'], league)})" for w in g["winners"])
        lines.append(entries if gt.startswith("ALL ") else f"{gt.title()}\n{entries}")
    excerpt = htmlmod.unescape(re.sub("<[^>]+>", "", post.get("excerpt", {}).get("rendered", ""))).strip()
    excerpt = re.sub(r"\s+", " ", excerpt).replace(" [&hellip;]", "").replace("[…]", "").strip()
    tags = ["#baseball", "#worldbaseballnews"] + CFG["league_hashtags"].get(bot.league_slug(url), [])[:3]
    tags.append("#" + re.sub(r"[^A-Za-z]", "", award_name.title()))
    body = f"{emoji} {year} {LEAGUES[league]['label']} {award_name.title()}\n\n{excerpt}\n\n" + "\n\n".join(lines) + \
           "\n\n➡️ Swipe for every winner on the field.\n"
    cap = body + "👉 Full story via the link in our bio.\n\n" + " ".join(dict.fromkeys(tags))
    cap_fb = body + f"👉 Full story: {url}\n\n" + " ".join(dict.fromkeys(tags))
    return {"url": url, "headline": title, "images": files, "caption": cap, "caption_facebook": cap_fb}


def prepare_pending(url: str, slot: str, collaborators=None) -> bool:
    """Build the carousel into posts/ and queue it as pending.json (used by bot.py)."""
    try:
        spec = build(url, bot.POSTS_DIR)
    except Exception as e:
        print(f"::warning title=Team award format failed::{str(e)[:500]}", flush=True)
        return False
    if not spec:
        return False
    files = spec["images"]
    pending = {"url": url, "slot": slot, "headline": spec["headline"], "title_on_image": spec["headline"],
               "image_file": f"posts/{files[0]}", "image_url": CFG["image_base_url"] + files[0],
               "extra_images": files[1:], "caption": spec["caption"], "caption_facebook": spec["caption_facebook"],
               "tag_context": "", "collaborators": collaborators or []}
    bot.PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"::notice title=Team award carousel::{spec['headline']} ({len(files)} slides)", flush=True)
    bot.gh_output("has_post", "true")
    return True


if __name__ == "__main__":  # python team_award.py <article url> <out dir>   (preview, no posting)
    import sys
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "probe" / "award"
    out.mkdir(parents=True, exist_ok=True)
    spec = build(sys.argv[1], out)
    print(json.dumps({k: v for k, v in (spec or {}).items()}, indent=1, ensure_ascii=False))
