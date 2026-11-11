"""World Player of the Week: weekly pipeline.

Monday (after 12:00 NL)  snapshot season stats of every non-MLB-Stats-API league from the public stats pages.
Thursday (after 17:00 NL) rank last week's (Mon-Sun) performances, find a verified photo, render and queue the post.

Weekly lines:
- leagues on the MLB Stats API (MLB, MiLB, AFL, winter leagues): exact, from every box score of the week.
- other leagues: difference between two Monday snapshots of the site's public stats pages.
Photo: from news articles about the player (Bing News RSS); only an image whose caption/alt names the player,
not an archive photo, and big enough. If none is found, the next player in the ranking wins.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

import bot
import potw
from bot import CFG, ROOT, TZ, log

PCFG = CFG["potw"]
SITE = CFG["site_url"].rstrip("/")
LEAGUES = {l["key"]: l for l in CFG["standings"]["leagues"]}
STATE = ROOT / "state" / "potw"
API = "https://statsapi.mlb.com/api/v1"
UA = {"User-Agent": "Mozilla/5.0 (compatible; WBN-bot/1.0; +https://worldbaseballnews.org)"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def week_of(now: datetime) -> tuple[date, date]:
    """Previous full week Mon..Sun."""
    this_monday = now.date() - timedelta(days=now.weekday())
    return this_monday - timedelta(days=7), this_monday - timedelta(days=1)


# ----------------------------------------------------------------------------- snapshots (non-statsapi leagues)
def parse_stats_page(slug: str) -> dict | None:
    r = requests.get(f"{SITE}/leagues/{slug}/stats/", headers=bot.UA, timeout=40)
    if r.status_code != 200:
        return None
    s = BeautifulSoup(r.content, "html.parser")
    out = {"hitting": [], "pitching": []}
    for t in s.find_all("table"):
        keys = [b.get("data-sort") for b in t.thead.find_all("button")] if t.thead else []
        if not keys:
            continue
        kind = "pitching" if "ip" in keys else "hitting"
        for tr in t.tbody.find_all("tr"):
            th = tr.find("th")
            if not th or not th.find("b"):
                continue
            small = th.find("small").get_text(" ", strip=True) if th.find("small") else ""
            abbr, _, pos = small.partition(" · ")
            row = {"name": th.find("b").get_text(strip=True), "team": abbr.strip(), "pos": pos.strip()}
            for k, td in zip(keys, tr.find_all("td")):
                row[k] = td.get_text(strip=True)
                if k == "ip" and td.get("data-v"):
                    row["outs"] = td["data-v"]
            out[kind].append(row)
    return out


def snapshot_due(now: datetime) -> bool:
    if now.weekday() != 0 or now.strftime("%H:%M") < PCFG["snapshot_after"]:
        return False
    return not (STATE / f"snap-{now.date()}.json").exists()


def take_snapshot(now: datetime) -> Path:
    snap = {"taken": now.isoformat(timespec="seconds"), "leagues": {}}
    for key, lg in LEAGUES.items():
        if key in PCFG["statsapi_leagues"]:
            continue
        try:
            data = parse_stats_page(lg["slug"])
        except Exception as e:
            log(f"  snapshot {key}: {e}")
            continue
        if data and (data["hitting"] or data["pitching"]):
            snap["leagues"][key] = data
    STATE.mkdir(parents=True, exist_ok=True)
    f = STATE / f"snap-{now.date()}.json"
    f.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    log(f"Snapshot {f.name}: {len(snap['leagues'])} leagues")
    return f


def snapshot_candidates(start: date, end: date) -> list[dict]:
    old_f, new_f = STATE / f"snap-{start}.json", STATE / f"snap-{end + timedelta(days=1)}.json"
    if not (old_f.exists() and new_f.exists()):
        log(f"  snapshot pair missing ({old_f.name}, {new_f.name}): non-statsapi leagues skipped")
        return []
    old, new = (json.loads(f.read_text(encoding="utf-8"))["leagues"] for f in (old_f, new_f))
    import standings
    out = []
    for key, data in new.items():
        prev = old.get(key)
        if prev is None:
            continue
        cands = potw.candidates(key, prev, data)
        names = {}
        if cands:
            try:
                for g in (standings.fetch_standings(LEAGUES[key]) or {}).get("groups", []):
                    for row in g["rows"]:
                        names[row["short"].upper()] = row["team"]
            except Exception:
                pass
        for c in cands:
            c["source"] = "snapshot"
            c["team_full"] = names.get((c["team"] or "").upper(), c["team"])
            out.append(c)
    return out


# ----------------------------------------------------------------------------- MLB Stats API leagues
def team_league_map() -> dict[str, str]:
    import standings
    m = {}
    for key in PCFG["statsapi_leagues"]:
        try:
            d = standings.fetch_standings(LEAGUES[key])
        except Exception:
            d = None
        for g in (d or {}).get("groups", []):
            for row in g["rows"]:
                m[norm(row["team"])] = key
    return m


def statsapi_candidates(start: date, end: date) -> list[dict]:
    tmap = team_league_map()
    players: dict[int, dict] = {}
    for sport in PCFG["statsapi_sports"]:
        try:
            sched = requests.get(f"{API}/schedule", params={"sportId": sport, "startDate": str(start),
                                                            "endDate": str(end)}, timeout=40).json()
        except Exception as e:
            log(f"  schedule sport {sport}: {e}")
            continue
        for d in sched.get("dates", []):
            for g in d.get("games", []):
                if g.get("status", {}).get("abstractGameState") != "Final" or g.get("gameType") in ("E", "S", "A"):
                    continue
                names = {side: g["teams"][side]["team"]["name"] for side in ("home", "away")}
                if not any(norm(n) in tmap for n in names.values()):
                    continue
                try:
                    box = requests.get(f"{API}/game/{g['gamePk']}/boxscore", timeout=40).json()
                except Exception:
                    continue
                for side in ("home", "away"):
                    team = names[side]
                    league = tmap.get(norm(team))
                    if not league:
                        continue
                    opp = names["away" if side == "home" else "home"]
                    for p in box["teams"][side]["players"].values():
                        pid = p["person"]["id"]
                        st = p.get("stats", {})
                        bat, pit = st.get("batting") or {}, st.get("pitching") or {}
                        if not bat.get("plateAppearances") and not pit.get("outs"):
                            continue
                        rec = players.setdefault(pid, {"id": pid, "name": p["person"]["fullName"], "team": team,
                                                       "league": league, "games": []})
                        rec["team"], rec["league"] = team, league
                        rec["games"].append({"date": d["date"], "opp": opp, "home": side == "home", "bat": bat,
                                             "pit": pit, "pos": (p.get("position") or {}).get("abbreviation")})
    out = []
    for rec in players.values():
        out += statsapi_lines(rec)
    return out


def statsapi_lines(rec: dict) -> list[dict]:
    games = sorted(rec["games"], key=lambda g: g["date"])
    res = []
    bats = [g for g in games if g["bat"].get("plateAppearances")]
    if bats:
        s = lambda k: sum(int(g["bat"].get(k) or 0) for g in bats)  # noqa: E731
        w = {"g": len(bats), "pa": s("plateAppearances"), "ab": s("atBats"), "r": s("runs"), "h": s("hits"),
             "d": s("doubles"), "t": s("triples"), "hr": s("homeRuns"), "rbi": s("rbi"), "bb": s("baseOnBalls"),
             "so": s("strikeOuts"), "sb": s("stolenBases"), "hbp": s("hitByPitch"), "sf": s("sacFlies")}
        sc = potw.hitter_score(w)
        if sc:
            res.append({**w, "role": "hitter", "raw": sc[0], "notes": sc[1], "games": bats})
    pits = [g for g in games if g["pit"].get("outs")]
    if pits:
        s = lambda k: sum(int(g["pit"].get(k) or 0) for g in pits)  # noqa: E731
        w = {"g": len(pits), "gs": s("gamesStarted"), "w": s("wins"), "l": s("losses"), "sv": s("saves"),
             "outs": s("outs"), "h": s("hits"), "er": s("earnedRuns"), "bb": s("baseOnBalls"),
             "so": s("strikeOuts"), "hr": s("homeRuns")}
        sc = potw.pitcher_score(w, starts=[g["pit"] for g in pits if g["pit"].get("gamesStarted")])
        if sc:
            res.append({**w, "role": "pitcher", "raw": sc[0], "notes": sc[1], "games": pits})
    lvl = 0.5 + 0.5 * potw.LEVEL.get(rec["league"], 0.3)
    for r in res:
        r.update({"id": rec["id"], "name": rec["name"], "team": rec["team"], "team_full": rec["team"],
                  "league": rec["league"], "score": r["raw"] * lvl, "source": "statsapi"})
    return res


# ----------------------------------------------------------------------------- photo search
BAD_CAPTION = re.compile(r"\b(archivo|archive|file photo|foto de archivo|archival)\b", re.I)


def news_links(query: str, limit=12) -> list[tuple[str, str]]:
    url = f"https://www.bing.com/news/search?q={quote_plus(query)}&format=rss&qft=interval%3d%228%22"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        s = BeautifulSoup(r.content, "xml")
    except Exception as e:
        log(f"  news search failed: {e}")
        return []
    out = []
    for it in s.find_all("item")[:limit]:
        link = it.link.get_text(strip=True) if it.link else ""
        q = parse_qs(urlparse(link).query)
        if "url" in q:
            link = q["url"][0]
        out.append((link, it.pubDate.get_text(strip=True) if it.pubDate else ""))
    return out


def image_text(img) -> str:
    parts = [img.get("alt") or "", img.get("title") or ""]
    fig = img.find_parent("figure")
    if fig and fig.find("figcaption"):
        parts.append(fig.find("figcaption").get_text(" ", strip=True))
    return " ".join(parts)


def find_photo(c: dict, since: date) -> dict | None:
    full = norm(c["name"])
    team_word = c["team_full"].split()[-1] if c.get("team_full") else ""
    seen = set()
    for q in (f"\"{c['name']}\" {team_word}", f"\"{c['name']}\" baseball", f"\"{c['name']}\""):
        for link, pub in news_links(q):
            if link in seen or not link.startswith("http"):
                continue
            seen.add(link)
            try:
                r = requests.get(link, headers=UA, timeout=30)
                s = BeautifulSoup(r.content, "html.parser")
            except Exception:
                continue
            pt = s.find("meta", property="article:published_time")
            if pt and pt.get("content", "")[:10] < str(since - timedelta(days=1)):
                continue
            for img in s.find_all("img"):
                txt = image_text(img)
                if full not in norm(txt) or BAD_CAPTION.search(txt):
                    continue
                src = img.get("data-src") or img.get("src") or ""
                if img.get("srcset"):
                    src = img["srcset"].split(",")[-1].strip().split(" ")[0]
                if not src or src.startswith("data:"):
                    continue
                src = requests.compat.urljoin(link, src)
                try:
                    im = Image.open(BytesIO(requests.get(src, headers=UA, timeout=40).content)).convert("RGB")
                except Exception:
                    continue
                if min(im.size) < 650 or im.width < 900:
                    continue
                credit = re.findall(r"\(([^()]{3,60})\)\s*$", txt.strip())
                return {"image": im, "src": src, "page": link, "caption": txt.strip(),
                        "credit": credit[0] if credit else ""}
    return None


def face_crop(im: Image.Image) -> list[int]:
    """4:5 crop centred on the largest face (falls back to the centre)."""
    tw = int(im.height * 4 / 5)
    cx = im.width / 2
    try:
        import cv2
        import numpy as np
        g = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2GRAY)
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = casc.detectMultiScale(g, 1.1, 5, minSize=(int(im.width * 0.03),) * 2)
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            cx = x + w / 2
    except Exception as e:
        log(f"  face detection unavailable: {e}")
    if tw >= im.width:
        return [0, 0, im.width, im.height]
    left = int(min(max(0, cx - tw / 2), im.width - tw))
    return [left, 0, left + tw, im.height]


# ----------------------------------------------------------------------------- copy
def date_label(d: str) -> str:
    return datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %-d")


def bat_line(b: dict) -> str:
    parts = [f"{b.get('hits', 0)}-{b.get('atBats', 0)}"]
    for k, lab in (("homeRuns", "HR"), ("triples", "3B"), ("doubles", "2B"), ("rbi", "RBI"), ("baseOnBalls", "BB"),
                   ("stolenBases", "SB")):
        v = int(b.get(k) or 0)
        if v:
            parts.append(f"{v} {lab}" if v > 1 else lab)
    return " · ".join(parts)


def pit_line(p: dict) -> str:
    return f"{p.get('inningsPitched')} IP · {p.get('hits', 0)} H · {p.get('earnedRuns', 0)} ER · {p.get('strikeOuts', 0)} K"


def fmt3(x: float) -> str:
    s = f"{x:.3f}"
    return s[1:] if s.startswith("0") else s


def rates(c: dict) -> dict:
    if c["role"] == "hitter":
        ab, h = c["ab"], c["h"]
        tb = h + c["d"] + 2 * c["t"] + 3 * c["hr"]
        den = ab + c["bb"] + c.get("hbp", 0) + c.get("sf", 0)
        obp = (h + c["bb"] + c.get("hbp", 0)) / den if den else 0
        slg = tb / ab if ab else 0
        return {"avg": h / ab if ab else 0, "obp": obp, "slg": slg, "ops": obp + slg}
    ip = c["outs"] / 3
    return {"era": 9 * c["er"] / ip if ip else 0, "whip": (c["h"] + c["bb"]) / ip if ip else 0,
            "ip": f"{c['outs'] // 3}.{c['outs'] % 3}"}


def stat_boxes(c: dict):
    r = rates(c)
    if c["role"] == "hitter":
        mid = [str(c["hr"]), "HR"] if c["hr"] else [str(c["h"]), "HITS"]
        return [[fmt3(r["avg"]), "AVG"], mid, [str(c["rbi"]), "RBI"], [fmt3(r["ops"]), "OPS"]]
    return [[r["ip"], "IP"], [str(c["so"]), "K"], [f"{r['era']:.2f}", "ERA"], [f"{r['whip']:.2f}", "WHIP"]]


def short_line(c: dict) -> str:
    if c["role"] == "hitter":
        bits = [f"{c['h']}-for-{c['ab']}"]
        if c["hr"]:
            bits.append(f"{c['hr']} HR" if c["hr"] > 1 else "HR")
        if c["t"]:
            bits.append(f"{c['t']} 3B" if c["t"] > 1 else "3B")
        if c["sb"] >= 3:
            bits.append(f"{c['sb']} SB")
        if c["rbi"] >= 5:
            bits.append(f"{c['rbi']} RBI")
        return " · ".join(bits[:4])
    r = rates(c)
    return f"{r['ip']} IP · {c['so']} K · {r['era']:.2f} ERA"


def flag_emoji(key: str) -> str:
    codes = LEAGUES[key].get("flags") or []
    return "".join(chr(0x1F1E6 + ord(ch) - 97) for ch in codes[0]) if codes else ""


def build(winner: dict, photo: dict, ranked: list[dict], start: date, end: date, n_players: int, n_leagues: int):
    lg = LEAGUES[winner["league"]]
    rng = f"{start.strftime('%b %-d')}–{end.strftime('%-d, %Y')}" if start.month == end.month else \
        f"{start.strftime('%b %-d')}–{end.strftime('%b %-d, %Y')}"
    parts = winner["name"].split()
    first, last = parts[0], " ".join(parts[1:]) or parts[0]
    games, highlight = [], ""
    if winner.get("games"):
        for g in winner["games"]:
            opp = ("vs " if g["home"] else "at ") + g["opp"]
            line = bat_line(g["bat"]) if winner["role"] == "hitter" else pit_line(g["pit"])
            games.append({"date": date_label(g["date"]), "opp": opp, "line": line})
        if winner["role"] == "hitter":
            best = max(winner["games"], key=lambda g: potw.hitter_game_value(g["bat"]))
            highlight = (f"Best game: {bat_line(best['bat']).replace(' · ', ', ')} "
                         f"{'vs' if best['home'] else 'at'} {best['opp']} on {date_label(best['date'])}.")
        else:
            best = max(winner["games"], key=lambda g: int(g["pit"].get("outs") or 0))
            highlight = (f"Best outing: {pit_line(best['pit']).replace(' · ', ', ')} "
                         f"{'vs' if best['home'] else 'at'} {best['opp']} on {date_label(best['date'])}.")
        if winner.get("notes"):
            highlight = winner["notes"][0][0].upper() + winner["notes"][0][1:] + ". " + highlight
    else:
        games.append({"date": "WEEK", "opp": f"{winner['g']} games", "line": potw.line(winner)})
    # shortlist: winner + best of other leagues first, then the rest
    others, used = [], {winner["league"]}
    for c in ranked:
        if c is winner or c["name"] == winner["name"]:
            continue
        if c["league"] not in used:
            others.append(c)
            used.add(c["league"])
        if len(others) == 5:
            break
    for c in ranked:
        if len(others) >= 5:
            break
        if c is not winner and c not in others and c["name"] != winner["name"]:
            others.append(c)
    race = [{"name": winner["name"], "league": winner["league"], "line": short_line(winner), "winner": True}]
    race += [{"name": c["name"], "league": c["league"], "line": short_line(c)} for c in others]
    slug = f"potw-{start.isocalendar()[0]}-w{start.isocalendar()[1]:02d}"
    photo_rel = f"assets/potw/{slug}.jpg"
    (ROOT / "assets" / "potw").mkdir(parents=True, exist_ok=True)
    photo["image"].save(ROOT / photo_rel, quality=94)
    spec = {"slug": slug, "week_label": rng.upper(), "first": first, "last": last, "team": winner["team_full"],
            "league": winner["league"], "photo": photo_rel, "crop": face_crop(photo["image"]), "v_align": 0.0,
            "credit": None, "stats": stat_boxes(winner), "games": games, "highlight": highlight,
            "evaluated": f"{n_players:,} players · {n_leagues} leagues", "race": race}
    r = rates(winner)
    if winner["role"] == "hitter":
        rate_line = f"{fmt3(r['avg'])} AVG · {fmt3(r['obp'])} OBP · {fmt3(r['slg'])} SLG"
        summary = (f"{winner['h']}-for-{winner['ab']} with {winner['hr']} HR, {winner['rbi']} RBI and "
                   f"{winner['bb']} walks in {winner['g']} games.")
    else:
        rate_line = f"{r['ip']} IP · {winner['so']} K · {r['era']:.2f} ERA · {r['whip']:.2f} WHIP"
        summary = f"{winner['g']} {'starts' if winner['gs'] > 1 else 'appearance' if winner['g'] == 1 else 'appearances'}: {potw.line(winner)}."
    sl = "\n".join(f"{flag_emoji(c['league'])} {c['name']} ({LEAGUES[c['league']]['label']}): {short_line(c)}"
                   for c in others)
    tags = ["#WorldPlayerOfTheWeek", "#baseball", "#worldbaseballnews"]
    tags += CFG["league_hashtags"].get(winner["league"], [])[:2]
    tags += [t for c in others for t in CFG["league_hashtags"].get(c["league"], [])[:1]]
    tags = list(dict.fromkeys(tags))[:12]
    credit = f"\n\n📸 {photo['credit']}" if photo.get("credit") else ""
    body = (f"🏆 World Player of the Week | {rng}\n\n{winner['name']}, {winner['team_full']} ({lg['label']}) "
            f"{flag_emoji(winner['league'])}\n\n{summary}\n\n{rate_line}\n\n"
            f"Every week we look at every player in every league we cover and pick the best in the world. "
            f"This week: {n_players:,} players in {n_leagues} leagues.\n\nThe shortlist:\n{sl}{credit}\n\n")
    caption = body + " ".join(tags)
    caption_fb = body + f"👉 Every league, every week: {SITE}/\n\n" + " ".join(tags)
    return spec, caption, caption_fb


# ----------------------------------------------------------------------------- main entry points
def rank_week(start: date, end: date):
    cands = statsapi_candidates(start, end) + snapshot_candidates(start, end)
    cands.sort(key=lambda c: -c["score"])
    played = {(c["name"], c["league"]) for c in cands}
    leagues = {c["league"] for c in cands}
    return cands, len(played), len(leagues)


def due(now: datetime) -> bool:
    if now.weekday() != PCFG["post_weekday"] or now.strftime("%H:%M") < PCFG["post_after"]:
        return False
    if str(now.date()) < PCFG.get("start_date", "2000-01-01"):
        return False
    start, _ = week_of(now)
    done = json.loads((STATE / "posted.json").read_text()) if (STATE / "posted.json").exists() else {}
    return str(start) not in done


def cmd_prepare(force: bool = False, dry: bool = False) -> bool:
    now = datetime.now(TZ)
    if not force and not due(now):
        return False
    start, end = week_of(now)
    log(f"World Player of the Week: {start}..{end}")
    cands, n_players, n_leagues = rank_week(start, end)
    log(f"  {len(cands)} qualified lines from {n_players} players in {n_leagues} leagues")
    top = "\n".join(f"{c['score']:.1f} {c['league']} {c['name']} ({c['team_full']}): {potw.line(c)}" for c in cands[:12])
    log(top)
    if dry:
        print(f"::notice title=POTW ranking {start}..{end} ({n_players} players, {n_leagues} leagues)::" +
              top.replace("\n", " | "), flush=True)
    tried = []
    for c in cands[:PCFG["max_candidates"]]:
        photo = find_photo(c, start)
        tried.append(c["name"])
        if not photo:
            log(f"  no verified photo for {c['name']}")
            if dry:
                print(f"::notice title=POTW photo::none verified for {c['name']}", flush=True)
            continue
        spec, caption, caption_fb = build(c, photo, cands, start, end, n_players, n_leagues)
        spec_f = ROOT / "slides" / f"{spec['slug']}.json"
        spec_f.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
        post = {"url": f"potw:{spec['slug']}", "headline": f"World Player of the Week {spec['week_label']}: {c['name']}",
                "generator": ["tools/potw_post.py", f"slides/{spec['slug']}.json"],
                "images": [f"{spec['slug']}-1.jpg", f"{spec['slug']}-2.jpg"], "caption": caption,
                "caption_facebook": caption_fb, "collaborators": [], "potw_week": str(start),
                "photo_source": photo["page"]}
        post_f = ROOT / "slides" / f"{spec['slug']}-post.json"
        post_f.write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"::notice title=World Player of the Week::{c['name']} ({c['league']}) — photo from {photo['page']}",
              flush=True)
        if dry:
            import subprocess
            subprocess.run([sys.executable, str(ROOT / "tools/potw_post.py"), str(spec_f), str(ROOT / "probe" / "potw")],
                           check=True)
            return True
        bot.cmd_prepare_custom(str(post_f.relative_to(ROOT)))
        return True
    print(f"::warning title=World Player of the Week::no verified photo for {', '.join(tried)}; nothing posted",
          flush=True)
    return False


def mark_posted(week: str, media_id: str):
    STATE.mkdir(parents=True, exist_ok=True)
    f = STATE / "posted.json"
    done = json.loads(f.read_text()) if f.exists() else {}
    done[week] = media_id
    f.write_text(json.dumps(done, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        take_snapshot(datetime.now(TZ))
    elif cmd == "dry":  # python potw_run.py dry 2026-11-12  (simulate the Thursday run of that date)
        when = datetime.fromisoformat(sys.argv[2]).replace(hour=18, tzinfo=TZ) if len(sys.argv) > 2 else datetime.now(TZ)
        _now = datetime.now
        import potw_run as me
        me.datetime = type("D", (datetime,), {"now": staticmethod(lambda tz=None: when)})
        cmd_prepare(force=True, dry=True)
