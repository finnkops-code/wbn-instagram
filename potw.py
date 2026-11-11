"""World Player of the Week: the best weekly performance anywhere in pro baseball.

Weekly lines are the difference between two season-stat snapshots (Monday 09:00 NL to the next Monday).
Scoring is rate-based (with shrinkage, so a 2-game week doesn't beat a 6-game week by luck), adjusted for
league level, and rewards rare feats (no-hitters, complete-game shutouts, multi-homer weeks).
"""
from __future__ import annotations

# Rough league strength, MLB = 1.0. Used as factor 0.5 + 0.5 * level, so a historic feat in a smaller league
# can still beat a very good week in a stronger league.
LEVEL = {
    "mlb": 1.00, "npb": 0.86, "kbo": 0.76, "il": 0.76, "pcl": 0.74, "cpbl": 0.62, "afl": 0.66, "eastern": 0.66,
    "southern": 0.65, "texas": 0.66, "lidom": 0.64, "lmb": 0.60, "lvbp": 0.60, "lmp": 0.60, "npbfarm": 0.60,
    "lbprc": 0.52, "sally": 0.55, "midwest": 0.55, "northwest": 0.55, "carolina": 0.50, "fsl": 0.50,
    "california": 0.50, "abl": 0.50, "atlantic": 0.52, "aapb": 0.46, "frontier": 0.42, "apbn": 0.44, "lpb": 0.44,
    "cpb": 0.40, "cbl": 0.34, "hoofdklasse": 0.40, "seriea": 0.38, "dbl": 0.36, "extraliga": 0.32, "d1": 0.30,
    "dhb": 0.30, "elitserien": 0.22, "nla": 0.22, "austria": 0.22, "belgium": 0.20, "nbl": 0.16,
}
MIN_PA = 8
MIN_OUTS = 15  # 5 innings


def ip_outs(ip) -> int:
    s = str(ip or "0")
    whole, _, frac = s.partition(".")
    return int(whole or 0) * 3 + int(frac or 0)


def _num(row, k):
    try:
        return int(row.get(k) or 0)
    except (TypeError, ValueError):
        return 0


def diff_rows(old: list[dict], new: list[dict], keys: list[str]) -> list[dict]:
    before = {(r.get("id") or r["name"], r.get("team")): r for r in old}
    out = []
    for r in new:
        o = before.get((r.get("id") or r["name"], r.get("team")), {})
        d = {k: _num(r, k) - _num(o, k) for k in keys}
        if r.get("outs") is not None or "ip" in r:
            d["outs"] = (_num(r, "outs") or ip_outs(r.get("ip"))) - (_num(o, "outs") or ip_outs(o.get("ip")))
        if any(v < 0 for v in d.values()):  # data correction / player moved: skip, can't trust the delta
            continue
        d.update({"id": r.get("id"), "name": r["name"], "team": r.get("team"), "teamId": r.get("teamId"),
                  "pos": r.get("pos")})
        out.append(d)
    return out


HIT_KEYS = ["g", "pa", "ab", "r", "h", "d", "t", "hr", "rbi", "bb", "so", "sb"]
PIT_KEYS = ["g", "gs", "w", "l", "sv", "h", "er", "bb", "so", "hr"]


def hitter_score(w: dict) -> tuple[float, list[str]] | None:
    pa = w["pa"] or (w["ab"] + w["bb"])
    if pa < MIN_PA:
        return None
    singles = w["h"] - w["d"] - w["t"] - w["hr"]
    woba = (0.70 * w["bb"] + 0.90 * singles + 1.25 * w["d"] + 1.60 * w["t"] + 2.00 * w["hr"]) / pa
    shrunk = (woba * pa + 0.320 * 15) / (pa + 15)  # regress small samples toward average
    score = (shrunk - 0.320) * 250 + 0.6 * w["sb"]
    notes = []
    if w["hr"] >= 3:
        score += 4 * (w["hr"] - 2)
        notes.append(f"{w['hr']} home runs")
    return score, notes


def game_score(outs, h, er, bb, so) -> float:
    """Bill James-style game score from one start's line (runs = earned runs; unearned runs aren't in the data)."""
    full_inn_after_4 = max(0, outs // 3 - 4)
    return 50 + outs + 2 * full_inn_after_4 + so - 2 * h - 4 * er - bb


def hitter_game_value(b: dict) -> float:
    h, d, t, hr = (int(b.get(k) or 0) for k in ("hits", "doubles", "triples", "homeRuns"))
    return (h - d - t - hr) + 2 * d + 3 * t + 4 * hr + 0.7 * int(b.get("baseOnBalls") or 0) + 0.5 * int(b.get("rbi") or 0)


def pitcher_score(w: dict, starts: list[dict] | None = None) -> tuple[float, list[str]] | None:
    outs = w["outs"]
    if outs < MIN_OUTS:
        return None
    notes = []
    gs = max(w["gs"], 0)
    if starts:  # exact per-start lines from box scores
        scores = []
        for p in starts:
            o = int(p.get("outs") or 0)
            g_s = game_score(o, int(p.get("hits") or 0), int(p.get("earnedRuns") or 0), int(p.get("baseOnBalls") or 0),
                             int(p.get("strikeOuts") or 0))
            if o >= 27 and int(p.get("hits") or 0) == 0:
                perfect = int(p.get("battersFaced") or 0) == 27
                g_s += 35 if perfect else 25
                notes.append("threw a perfect game" if perfect else "threw a no-hitter")
            elif o >= 27 and int(p.get("runs") or 0) == 0:
                g_s += 8
                notes.append("threw a complete-game shutout")
            scores.append(g_s)
        score = (sum(scores) / len(scores) - 50) * 1.2 + 6 * (len(scores) - 1)
        return score, notes
    if gs >= 1:
        avg = game_score(outs / gs, w["h"] / gs, w["er"] / gs, w["bb"] / gs, w["so"] / gs)
        score = (avg - 50) * 1.2 + 6 * (gs - 1)
    else:  # long relief week
        score = (outs * 0.8 + w["so"] - 3 * w["er"] - w["h"] - w["bb"]) * 0.6
    if gs == 1 and w["g"] == 1 and outs >= 27 and w["h"] == 0:
        score += 25 if w["bb"] else 35
        notes.append("no-hitter" if w["bb"] else "no hits, no walks over 9+ innings")
    elif gs == 1 and w["g"] == 1 and outs >= 27 and w["er"] == 0:
        score += 8
        notes.append("complete-game shutout")
    return score, notes


def candidates(league: str, old: dict, new: dict) -> list[dict]:
    lvl = LEVEL.get(league, 0.3)
    factor = 0.5 + 0.5 * lvl
    out = []
    for w in diff_rows(old.get("hitting", []), new.get("hitting", []), HIT_KEYS):
        s = hitter_score(w)
        if s:
            out.append({**w, "role": "hitter", "raw": s[0], "score": s[0] * factor, "notes": s[1], "league": league})
    for w in diff_rows(old.get("pitching", []), new.get("pitching", []), PIT_KEYS):
        s = pitcher_score(w)
        if s:
            out.append({**w, "role": "pitcher", "raw": s[0], "score": s[0] * factor, "notes": s[1], "league": league})
    return out


def line(c: dict) -> str:
    if c["role"] == "hitter":
        s = f"{c['h']}-for-{c['ab']}"
        extras = []
        if c["hr"]:
            extras.append(f"{c['hr']} HR")
        if c["d"]:
            extras.append(f"{c['d']} 2B")
        if c["t"]:
            extras.append(f"{c['t']} 3B")
        extras += [f"{c['rbi']} RBI", f"{c['r']} R"]
        if c["bb"]:
            extras.append(f"{c['bb']} BB")
        if c["sb"]:
            extras.append(f"{c['sb']} SB")
        return f"{s}, " + ", ".join(extras) + f" in {c['g']} G"
    ip = f"{c['outs'] // 3}.{c['outs'] % 3}"
    rec = f"{c['w']}-{c['l']}, " if (c["w"] or c["l"]) else ""
    return f"{rec}{ip} IP, {c['h']} H, {c['er']} ER, {c['bb']} BB, {c['so']} K in {c['gs'] or c['g']} {'GS' if c['gs'] else 'G'}"
