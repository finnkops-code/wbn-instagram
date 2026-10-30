#!/usr/bin/env python3
"""
WBN Instagram bot — posts the biggest WorldBaseballNews headlines to Instagram.

Commands
  python bot.py rank               show how the bot scores the current articles (newsworthiness 0-100)
  python bot.py prepare            pick the next headline (if allowed), render visual + caption -> pending.json
  python bot.py publish            publish pending.json to Instagram, log it in state/posted.json
  python bot.py preview [URL ...]  render visuals + captions to preview/ without posting (default: current hero + featured)
  python bot.py seed               mark everything currently featured as "posted" (no posting) — use once at go-live if wanted
  python bot.py refresh-token      refresh the long-lived Instagram token, writes the new one to new_token.txt
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
STATE_FILE = ROOT / "state" / "posted.json"
PENDING_FILE = ROOT / "pending.json"
POSTS_DIR = ROOT / "posts"
PREVIEW_DIR = ROOT / "preview"
FONTS = ROOT / "fonts"
TZ = ZoneInfo(CFG["timezone"])
UA = {"User-Agent": "WBN-Instagram-Bot/1.0 (+https://worldbaseballnews.org)"}

# Brand colours (from the site's CSS)
PETROL = (3, 53, 76)
PETROL_DEEP = (2, 38, 54)
PETROL_LINE = (27, 77, 99)
RED = (189, 0, 0)
RED_BRIGHT = (226, 59, 59)
ON_DARK = (197, 211, 218)
ON_DARK_2 = (159, 182, 194)
WHITE = (255, 255, 255)


# ----------------------------------------------------------------------------- helpers
def log(*a):
    print(*a, flush=True)


def norm_url(u: str) -> str:
    p = urlparse(urljoin(CFG["site_url"], u))
    path = p.path if p.path.endswith("/") else p.path + "/"
    return f"https://{p.netloc.replace('www.', '')}{path}"


def slug_of(url: str) -> str:
    return [s for s in urlparse(url).path.split("/") if s][-1]


def league_slug(url: str) -> str:
    parts = [s for s in urlparse(url).path.split("/") if s]
    return parts[1] if len(parts) >= 3 and parts[0] == "news" else "baseball"


def get(url: str) -> requests.Response:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            if "charset" not in r.headers.get("content-type", "").lower():
                r.encoding = "utf-8"  # site serves UTF-8 without a charset header
            return r
        except requests.RequestException as e:
            if attempt == 2:
                raise
            log(f"  retry {url}: {e}")
            time.sleep(5)


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"posted": []}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def gh_output(key: str, value: str):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


# ----------------------------------------------------------------------------- 1. candidates
def feed_candidates() -> list[dict]:
    """All articles from the site's RSS feed (newest ~20), with league, date, description and image."""
    soup = BeautifulSoup(get(CFG["site_url"] + "feed/").content, "xml")
    out = []
    for it in soup.find_all("item"):
        enc = it.find("enclosure")
        cats = [c.get_text(strip=True) for c in it.find_all("category")]
        pub = datetime.strptime(it.pubDate.get_text(strip=True), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        out.append({
            "url": norm_url(it.link.get_text(strip=True)),
            "home_title": it.title.get_text(" ", strip=True),
            "feed_description": it.description.get_text(" ", strip=True) if it.description else "",
            "league_label": cats[0] if cats else None,
            "categories": cats,
            "pub_dt": pub,
            "feed_image": enc["url"] if enc and enc.get("url") else None,
        })
    return out


def most_read_urls() -> set[str]:
    """The homepage's 'Most read' list = what readers actually click (a popularity signal)."""
    try:
        soup = BeautifulSoup(get(CFG["site_url"]).text, "html.parser")
    except Exception:
        return set()
    h = soup.find(lambda t: t.name in ("h2", "h3") and "most read" in t.get_text(strip=True).lower())
    lst = h.find_next(["ol", "ul"]) if h else None
    return {norm_url(a["href"]) for a in lst.find_all("a", href=True)} if lst else set()


# ----------------------------------------------------------------------------- 2. editorial scoring
SC = CFG["scoring"]
STOPWORDS = set("""a an the and or of in on at to for with as by from after over into his her their its is are was
were be been has have had win wins won takes take beat beats lead leads 2025 2026 2027 game series season""".split())


def _words(text: str) -> set[str]:
    generic = set(SC.get("generic_words", []))
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 2 and w not in STOPWORDS and w not in generic}


def same_story(a: str, b: str) -> bool:
    """Two headlines about the same event (e.g. 'Brewers win World Series' vs 'Contreras World Series MVP')."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    overlap = len(wa & wb)
    return overlap >= SC["same_story_min_shared_words"] or overlap / min(len(wa), len(wb)) >= 0.5


def score(c: dict, posted_today: list[dict], popular: set[str], recent: list[dict] = ()) -> tuple[int, list[str]]:
    """Newsworthiness 0-100. Returns the score plus the reasons, so every choice is explainable."""
    text = f"{c['home_title']} {c.get('feed_description', '')}"
    lg = league_slug(c["url"])
    pts, why = SC["base_points"], [f"{lg.upper()} base +{SC['base_points']}"]  # every league starts equal

    hits = sorted(((rule["points"], name) for name, rule in SC["topics"].items()
                   if re.search(rule["pattern"], c["home_title"], re.I)), reverse=True)
    if hits:  # strongest topic counts fully, every extra angle adds a little
        extra = SC["extra_topic_points"] * (len(hits) - 1)
        pts += hits[0][0] + extra
        why.append(f"{hits[0][1]} +{hits[0][0]}" + (f" (+{extra} extra: {', '.join(h[1] for h in hits[1:])})" if extra else ""))
    for name, rule in SC["penalties"].items():
        if re.search(rule["pattern"], text, re.I):
            pts += rule["points"]
            why.append(f"{name} {rule['points']}")
    if c["url"] in popular:
        pts += SC["most_read_bonus"]
        why.append(f"most read +{SC['most_read_bonus']}")

    age_h = (datetime.now(timezone.utc) - c["pub_dt"]).total_seconds() / 3600
    decay = int(age_h * SC["decay_per_hour"])
    if decay:
        pts -= decay
        why.append(f"{age_h:.0f}h old -{decay}")
    for p in posted_today:
        if same_story(c["home_title"], p.get("headline", "")):
            pts += SC["same_story_penalty"]
            why.append(f"same story as earlier post {SC['same_story_penalty']}")
            break
    same_lg = sum(1 for p in posted_today if league_slug(p["url"]) == lg)
    if same_lg:
        pts += SC["same_league_penalty"] * same_lg
        why.append(f"{same_lg}x {lg.upper()} already today {SC['same_league_penalty'] * same_lg}")
    earlier = sum(1 for p in recent if league_slug(p["url"]) == lg)  # rotation: leagues take turns over the week
    if earlier:
        pts += SC["rotation_penalty"] * earlier
        why.append(f"{earlier}x {lg.upper()} earlier this week {SC['rotation_penalty'] * earlier}")
    # random tie-breaker, stable per article per day so runs don't flip-flop
    rnd = random.Random(f"{c['url']}|{datetime.now(TZ).date()}").uniform(0, SC["random_jitter"])
    pts += rnd
    why.append(f"random +{rnd:.0f}")
    return max(0, min(100, round(pts))), why


def posted_today(state: dict) -> list[dict]:
    today = datetime.now(TZ).date()
    return [p for p in state["posted"] if p.get("posted_at") and not p.get("seeded")
            and datetime.fromisoformat(p["posted_at"]).astimezone(TZ).date() == today]


def ranked(state: dict) -> list[dict]:
    done = {p["url"] for p in state["posted"]}
    today, popular = posted_today(state), most_read_urls()
    now = datetime.now(TZ)
    recent = [p for p in state["posted"] if p.get("posted_at") and not p.get("seeded") and p not in today
              and now - datetime.fromisoformat(p["posted_at"]) <= timedelta(days=SC["rotation_days"])]
    max_age = timedelta(hours=CFG["max_article_age_hours"])
    out = []
    for c in feed_candidates():
        if c["url"] in done or not c["feed_image"]:
            continue
        if datetime.now(timezone.utc) - c["pub_dt"] > max_age:
            continue
        c["score"], c["why"] = score(c, today, popular, recent)
        out.append(c)
    return sorted(out, key=lambda c: c["score"], reverse=True)


def article_meta(url: str) -> dict:
    soup = BeautifulSoup(get(url).text, "html.parser")

    def meta(prop):
        t = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return t["content"].strip() if t and t.get("content") else None

    headline = None
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except Exception:
            continue
        for node in data.get("@graph", [data]) if isinstance(data, dict) else data:
            if isinstance(node, dict) and node.get("@type") in ("NewsArticle", "Article", "BlogPosting"):
                headline = headline or node.get("headline")
    h1 = soup.find("h1")
    published = meta("article:published_time")
    return {
        "url": url,
        "headline": headline or (h1.get_text(" ", strip=True) if h1 else None) or meta("og:title"),
        "og_title": meta("og:title"),
        "description": meta("og:description") or meta("description") or "",
        "image": meta("og:image"),
        "image_alt": meta("og:image:alt"),
        "published": published,
    }


def can_post_now(state: dict) -> tuple[bool, str]:
    now = datetime.now(TZ)
    today = posted_today(state)
    if len(today) >= CFG["max_posts_per_day"]:
        return False, f"daily limit reached ({len(today)}/{CFG['max_posts_per_day']})"
    real = [p for p in state["posted"] if p.get("posted_at") and not p.get("seeded")]
    if real:
        last = max(datetime.fromisoformat(p["posted_at"]) for p in real)
        gap = (now - last.astimezone(TZ)).total_seconds() / 60
        if gap < CFG["min_minutes_between_posts"]:
            return False, f"last post {gap:.0f} min ago (min {CFG['min_minutes_between_posts']})"
    return True, f"{len(today)}/{CFG['max_posts_per_day']} posted today"


def in_best_of_window() -> bool:
    now = datetime.now(TZ).strftime("%H:%M")
    return CFG["best_of_from"] <= now <= CFG["best_of_until"]


def pick_next(state: dict) -> dict | None:
    """Must-post news goes out right away; otherwise the best remaining story is posted in the evening window."""
    ranking = ranked(state)
    summary = ["| Score | Artikel | Waarom |", "|---:|---|---|"]
    for c in ranking:
        log(f"  {c['score']:>3}  {c['home_title'][:70]}  [{'; '.join(c['why'])}]")
        summary.append(f"| {c['score']} | {c['home_title']} | {'; '.join(c['why'])} |")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("### Ranking\n" + "\n".join(summary) + "\n\n")
    if not ranking:
        return None
    top = ranking[0]
    now_hm = datetime.now(TZ).strftime("%H:%M")
    last_slot = len(posted_today(state)) == CFG["max_posts_per_day"] - 1
    if last_slot and now_hm < CFG["reserve_last_slot_until"] and top["score"] < CFG["breaking_score"]:
        log(f"Last slot of the day is kept free until {CFG['reserve_last_slot_until']} "
            f"(only breaking news >= {CFG['breaking_score']} may use it; best now {top['score']}).")
        return None
    if top["score"] >= CFG["must_post_score"]:
        log(f"Must-post (score {top['score']} >= {CFG['must_post_score']})")
    elif in_best_of_window() and top["score"] >= CFG["min_post_score"]:
        log(f"Best-of window: posting best remaining story (score {top['score']})")
    else:
        log(f"Best is {top['score']}: below must-post {CFG['must_post_score']}; waiting for "
            f"{CFG['best_of_from']}-{CFG['best_of_until']} window (min {CFG['min_post_score']}).")
        return None
    m = article_meta(top["url"])
    m["image"] = m["image"] or top["feed_image"]
    m["description"] = m["description"] or top["feed_description"]
    return {**top, **m, "slot": f"score {top['score']}"}


# ----------------------------------------------------------------------------- 2. title shortening
SPLITTERS = [": ", " — ", " – ", ", ", " as ", " after ", " with ", " while ", " in ", " to ", " for ", " on "]


def short_title(art: dict, max_chars: int) -> str:
    full = (art.get("headline") or art.get("home_title") or art.get("og_title") or "").strip()
    if len(full) <= max_chars:
        return full
    og = (art.get("og_title") or "").strip()
    if 20 <= len(og) <= max_chars:
        return og
    best = ""
    for sp in SPLITTERS:
        idx = 0
        while True:
            idx = full.find(sp, idx + 1)
            if idx == -1:
                break
            cand = full[:idx].rstrip(" ,:—–")
            if len(cand) <= max_chars and len(cand.split()) >= 4 and len(cand) > len(best):
                best = cand
    if best:
        return best
    words, cut = full.split(), ""
    for w in words:
        if len(cut) + len(w) + 2 > max_chars:
            break
        cut = f"{cut} {w}".strip()
    return cut.rstrip(" ,:—–") + "…"


# ----------------------------------------------------------------------------- 3. visual
W, H = 1080, 1350
PHOTO_H = 800
MARGIN = 64


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for w in text.split():
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=fnt) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def fit_title(draw, text, width, max_lines=4):
    for size in range(108, 66, -4):
        f = font("oswald-700", size)
        lines = wrap(draw, text, f, width)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= width for l in lines):
            # balance the lines: narrowest width that keeps the same line count (no lonely word on line 1)
            lo, hi = width * 0.5, width
            while hi - lo > 4:
                mid = (lo + hi) / 2
                if len(wrap(draw, text, f, mid)) == len(lines) and all(
                        draw.textlength(w, font=f) <= mid for w in text.split()):
                    hi = mid
                else:
                    lo = mid
            return f, wrap(draw, text, f, hi), size
    return None, None, None


def cover(img: Image.Image, w: int, h: int, focus_y: float = 0.35) -> Image.Image:
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = (img.width - w) // 2
    top = int((img.height - h) * focus_y)
    return img.crop((left, top, left + w, top + h))


def vertical_gradient(w, h, color, start_alpha, end_alpha, ease=2.0):
    g = Image.new("L", (1, h))
    for y in range(h):
        t = (y / max(h - 1, 1)) ** ease
        g.putpixel((0, y), int(start_alpha + (end_alpha - start_alpha) * t))
    layer = Image.new("RGBA", (w, h), color + (0,))
    layer.putalpha(g.resize((w, h)))
    return layer


def draw_chevrons(draw, x, y, color, n=4, size=16, gap=10, stroke=5):
    for i in range(n):
        x0 = x + i * (size // 2 + gap)
        draw.line([(x0, y), (x0 + size // 2, y + size // 2), (x0, y + size)], fill=color, width=stroke, joint="curve")
    return x + n * (size // 2 + gap)


def render(art: dict, out_path: Path) -> str:
    canvas = Image.new("RGB", (W, H), PETROL_DEEP)
    draw = ImageDraw.Draw(canvas)

    # Title first (decides how much room the text block needs)
    title = short_title(art, CFG["title_max_chars"]).upper()
    f_title, lines, size = fit_title(draw, title, W - 2 * MARGIN)
    max_chars = CFG["title_max_chars"]
    while f_title is None and max_chars > 30:
        max_chars -= 8
        title = short_title(art, max_chars).upper()
        f_title, lines, size = fit_title(draw, title, W - 2 * MARGIN)

    # Layout (bottom-up): footer, title, kicker
    footer_top = H - 132
    line_h = int(size * 1.04)
    title_bottom = footer_top - 54
    title_top = title_bottom - line_h * len(lines)
    ky = title_top - 64

    # Photo, fading into solid petrol right where the kicker starts
    src = Image.open(BytesIO(get(art["image"]).content)).convert("RGB")
    solid_from = ky + 10
    photo_h = max(PHOTO_H, solid_from)
    canvas.paste(cover(src, W, photo_h), (0, 0))
    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(vertical_gradient(W, 220, (0, 0, 0), 150, 0, ease=1.0), (0, 0))
    fade = 380
    canvas.alpha_composite(vertical_gradient(W, fade, PETROL_DEEP, 0, 255, ease=1.4), (0, solid_from - fade))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, solid_from, W, H], fill=PETROL_DEEP)

    # Footer
    draw.line([(MARGIN, footer_top), (W - MARGIN, footer_top)], fill=PETROL_LINE, width=2)
    f_site = font("oswald-600", 34)
    draw.text((MARGIN, footer_top + 66), "WORLDBASEBALLNEWS.ORG", font=f_site, fill=ON_DARK, anchor="lm")
    f_cta = font("figtree-800", 30)
    cta = "READ MORE · LINK IN BIO"
    tw = draw.textlength(cta, font=f_cta)
    pill_w, pill_h = tw + 44 + 40, 64
    px1, py = W - MARGIN, footer_top + 66
    px0 = px1 - pill_w
    draw.rounded_rectangle([px0, py - pill_h / 2, px1, py + pill_h / 2], radius=pill_h / 2, fill=RED)
    draw.text((px0 + 26, py), cta, font=f_cta, fill=WHITE, anchor="lm")
    ax = px0 + 26 + tw + 14
    draw.polygon([(ax, py - 10), (ax + 18, py), (ax, py + 10)], fill=WHITE)  # arrow

    # Title block, anchored above the footer
    for i, line in enumerate(lines):
        draw.text((MARGIN, title_top + i * line_h), line, font=f_title, fill=WHITE)

    # Kicker: chevrons + league chip + date (like the site's kicker)
    x = draw_chevrons(draw, MARGIN, ky + 6, RED_BRIGHT)
    f_chip = font("figtree-800", 28)
    label = (art.get("league_label") or CFG["league_labels"].get(league_slug(art["url"]), "BASEBALL")).upper()
    lw = draw.textlength(label, font=f_chip)
    draw.rounded_rectangle([x + 8, ky - 6, x + 8 + lw + 32, ky + 40], radius=8, fill=RED)
    draw.text((x + 24, ky + 17), label, font=f_chip, fill=WHITE, anchor="lm")
    if art.get("published"):
        d = datetime.fromisoformat(art["published"].replace("Z", "+00:00")).astimezone(TZ)
        date_txt = d.strftime("%b %-d, %Y").upper()
        draw.text((x + 8 + lw + 32 + 18, ky + 17), date_txt, font=font("figtree-700", 26), fill=ON_DARK_2, anchor="lm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "JPEG", quality=90, optimize=True, progressive=False)
    return title


# ----------------------------------------------------------------------------- 4. caption
EMOJI_RULES = [
    (r"\b(wins?|won|champions?|crowned|title|clinch\w*|MVP|sweep\w*)\b", "🏆"),
    (r"\b(no-hitter|perfect game|shutout|one-hit\w*|strikeouts?|K's)\b", "🔥"),
    (r"\b(homers?|home runs?|grand slam|walk-off|slugs?)\b", "💥"),
    (r"\b(signs?|signed|contract|deal|free.agen\w*|trade[ds]?|acquire\w*|re-sign\w*)\b", "✍️"),
    (r"\b(injur\w*|IL|surgery|out for)\b", "🩹"),
    (r"\b(names?|appoint\w*|hires?|manager|coach\w*)\b", "📋"),
    (r"\b(preview|set for|schedule|opener|draft)\b", "📅"),
    (r"\b(qualifier|World Cup|WBC|Classic|national team|U-\d+)\b", "🌍"),
]


def build_caption(art: dict, platform: str = "instagram") -> str:
    headline = (art.get("headline") or art.get("og_title") or "").strip()
    emoji = next((e for rx, e in EMOJI_RULES if re.search(rx, headline, re.I)), "⚾")
    desc = art.get("description", "").strip()
    lg = league_slug(art["url"])
    tags = CFG["league_hashtags"].get(lg, []) + CFG["base_hashtags"]
    tags = list({t.lower(): t for t in reversed(tags)}.values())[::-1]  # de-duplicate, keep order
    parts = [
        f"{emoji} {headline}",
        desc,
        f"👉 Read the full story: {art['url']}" if platform == "facebook"
        else "👉 Read the full story via the link in our bio.",
        "Follow for daily news, scores and standings from 39 baseball leagues around the world 🌍⚾",
        " ".join(tags[:15]),
    ]
    return "\n\n".join(p for p in parts if p)[:2150]


# ----------------------------------------------------------------------------- 5. Instagram API
def ig_route() -> str:
    """'instagram' = Instagram API with Instagram login (default).
    'facebook' = legacy route via the linked Facebook Page (page token never expires, IG_USER_ID required)."""
    return (os.environ.get("IG_API_ROUTE") or "instagram").strip().lower()


def ig_base():
    host = "graph.facebook.com" if ig_route() == "facebook" else "graph.instagram.com"
    return f"https://{host}/{CFG['graph_api_version']}"


def ig_token() -> str:
    t = os.environ.get("IG_ACCESS_TOKEN")
    if not t:
        sys.exit("IG_ACCESS_TOKEN is not set")
    return t


def ig_user_id(token: str) -> str:
    uid = os.environ.get("IG_USER_ID")
    if uid:
        return uid
    if ig_route() == "facebook":
        sys.exit("IG_USER_ID (Instagram business account id) is required for the Facebook route")
    r = requests.get(f"{ig_base()}/me", params={"fields": "user_id,username", "access_token": token}, timeout=30)
    r.raise_for_status()
    return r.json()["user_id"]


def wait_public(url: str, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = requests.head(url, timeout=20, allow_redirects=True)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(10)
    raise RuntimeError(f"image not publicly reachable: {url}")


def ig_publish(image_url: str, caption: str) -> str:
    token = ig_token()
    uid = ig_user_id(token)
    wait_public(image_url)
    r = requests.post(f"{ig_base()}/{uid}/media",
                      data={"image_url": image_url, "caption": caption, "access_token": token}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"create container failed: {r.status_code} {r.text}")
    cid = r.json()["id"]
    for _ in range(10):  # up to ~5 minutes
        s = requests.get(f"{ig_base()}/{cid}", params={"fields": "status_code", "access_token": token}, timeout=30).json()
        status = s.get("status_code")
        log(f"  container {cid}: {status}")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {status}: {s}")
        time.sleep(30)
    r = requests.post(f"{ig_base()}/{uid}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"publish failed: {r.status_code} {r.text}")
    return r.json()["id"]


# ----------------------------------------------------------------------------- commands
def cmd_prepare():
    if not os.environ.get("IG_ACCESS_TOKEN") and os.environ.get("DRY_RUN") != "true":
        log("Instagram is not connected yet (secret IG_ACCESS_TOKEN missing) — skipping this run.")
        gh_output("has_post", "false")
        return
    state = load_state()
    ok, why = can_post_now(state)
    log(f"Status: {why}")
    if not ok:
        gh_output("has_post", "false")
        return
    art = pick_next(state)
    if not art:
        log("No new big headline to post.")
        gh_output("has_post", "false")
        return
    slug = slug_of(art["url"])
    img = POSTS_DIR / f"{slug}.jpg"
    title = render(art, img)
    caption = build_caption(art)
    pending = {
        "url": art["url"], "slot": art["slot"], "title_on_image": title, "headline": art["headline"],
        "image_file": str(img.relative_to(ROOT)), "image_url": CFG["image_base_url"] + img.name, "caption": caption,
        "caption_facebook": build_caption(art, "facebook"),
    }
    PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Prepared: [{art['slot']}] {art['headline']}\n  -> {img}")
    gh_output("has_post", "true")


def fb_publish(image_url: str, caption: str) -> str | None:
    """Photo post on the linked Facebook Page (same visual, caption with clickable article link).
    Needs the Facebook route (page token) with the pages_manage_posts permission."""
    if ig_route() != "facebook" or not CFG.get("post_to_facebook", True):
        return None
    token = ig_token()
    try:
        page = requests.get(f"{ig_base()}/me", params={"fields": "id", "access_token": token}, timeout=30).json()
        r = requests.post(f"{ig_base()}/{page['id']}/photos",
                          data={"url": image_url, "caption": caption, "access_token": token}, timeout=60)
        if r.status_code >= 400:
            log(f"  Facebook post failed (Instagram post is fine): {r.status_code} {r.text[:300]}")
            return None
        fid = r.json().get("post_id") or r.json().get("id")
        log(f"  Facebook post {fid}")
        return fid
    except Exception as e:  # never let Facebook break the Instagram flow
        log(f"  Facebook post failed (Instagram post is fine): {e}")
        return None


def cmd_publish():
    if not PENDING_FILE.exists():
        log("Nothing pending.")
        return
    p = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    media_id = ig_publish(p["image_url"], p["caption"])
    fb_id = fb_publish(p["image_url"], p.get("caption_facebook") or p["caption"])
    state = load_state()
    state["posted"].append({
        "url": p["url"], "headline": p["headline"], "slot": p["slot"], "image": p["image_file"],
        "media_id": media_id, "facebook_post_id": fb_id,
        "posted_at": datetime.now(TZ).isoformat(timespec="seconds"),
    })
    save_state(state)
    PENDING_FILE.unlink()
    log(f"Published {media_id}: {p['headline']}")
    # Instagram keeps its own copy after publishing, so old visuals can go (keeps the repo small)
    cutoff = datetime.now(TZ) - timedelta(days=14)
    for e in state["posted"]:
        f = ROOT / e["image"] if e.get("image") else None
        if f and f.exists() and datetime.fromisoformat(e["posted_at"]) < cutoff:
            f.unlink()


def cmd_preview(urls: list[str]):
    PREVIEW_DIR.mkdir(exist_ok=True)
    if urls:
        cands = [{"url": norm_url(u), "slot": "manual", "league_label": None, "home_title": None} for u in urls]
    else:
        cands = ranked(load_state())[:4]
    report = []
    for c in cands:
        art = {**c, **article_meta(c["url"])}
        img = PREVIEW_DIR / f"{slug_of(art['url'])}.jpg"
        title = render(art, img)
        cap = build_caption(art)
        report.append(f"=== [{art.get('score', art.get('slot'))}] {art['url']}\nIMAGE TITLE: {title}\nFILE: {img.name}\n\n{cap}\n")
        log(f"rendered {img.name}  <-  {title}")
    (PREVIEW_DIR / "captions.txt").write_text("\n".join(report), encoding="utf-8")


def cmd_seed():
    state = load_state()
    done = {p["url"] for p in state["posted"]}
    for c in feed_candidates():
        if c["url"] not in done:
            state["posted"].append({"url": c["url"], "seeded": True,
                                    "posted_at": datetime.now(TZ).isoformat(timespec="seconds")})
            log(f"seeded {c['url']}")
    save_state(state)


def cmd_refresh_token():
    if ig_route() == "facebook":
        log("Facebook route: page tokens don't expire, nothing to refresh.")
        return
    if not os.environ.get("IG_ACCESS_TOKEN"):
        log("Instagram is not connected yet — nothing to refresh.")
        return
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": ig_token()}, timeout=30)
    if r.status_code >= 400:
        sys.exit(f"refresh failed: {r.status_code} {r.text}")
    d = r.json()
    (ROOT / "new_token.txt").write_text(d["access_token"], encoding="utf-8")
    log(f"Token refreshed, valid for {d.get('expires_in', 0) // 86400} more days.")


def cmd_check():
    """Read-only connection check: which page/account the token belongs to and which permissions it has."""
    token = ig_token()
    me = requests.get(f"{ig_base()}/me", params={"fields": "id,name", "access_token": token}, timeout=30).json()
    log(f"Token belongs to: {me.get('name')} ({me.get('id')})  route={ig_route()}")
    if ig_route() == "facebook":
        ig = requests.get(f"{ig_base()}/{ig_user_id(token)}", params={"fields": "username", "access_token": token},
                          timeout=30).json()
        log(f"Instagram account: @{ig.get('username')}")
        dbg = requests.get(f"{ig_base()}/debug_token", params={"input_token": token, "access_token": token},
                           timeout=30).json().get("data", {})
        scopes = dbg.get("scopes", [])
        exp = dbg.get("expires_at")
        log(f"Expires: {'never' if not exp else datetime.fromtimestamp(exp, TZ)}")
        log(f"Permissions: {', '.join(scopes)}")
        for need in ("instagram_content_publish", "pages_manage_posts"):
            log(f"  {need}: {'OK' if need in scopes else 'MISSING'}")


def cmd_rank():
    for c in ranked(load_state()):
        print(f"{c['score']:>3}  {c['home_title'][:72]:72}  {'; '.join(c['why'])}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    {"prepare": cmd_prepare, "publish": cmd_publish, "seed": cmd_seed, "refresh-token": cmd_refresh_token,
     "rank": cmd_rank, "check": cmd_check,
     "preview": lambda: cmd_preview(sys.argv[2:])}.get(cmd, lambda: sys.exit(__doc__))()
