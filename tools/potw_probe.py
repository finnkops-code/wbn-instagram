"""Probe (runs in Actions): verify weekly lines via MLB Stats API game logs and look for highlight images
of the player from those games. Writes probe/report.json and probe/img/<id>-*.jpg."""
import json, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "probe"
(OUT / "img").mkdir(parents=True, exist_ok=True)
START, END = sys.argv[1], sys.argv[2]  # YYYY-MM-DD inclusive
top = json.loads((OUT / "potw_top.json").read_text())[:int(sys.argv[3]) if len(sys.argv) > 3 else 8]
API = "https://statsapi.mlb.com/api/v1"
report = []
for c in top:
    pid = c["id"]
    entry = {"name": c["name"], "id": pid, "team": c["team"], "league": c["league"], "games": [], "images": []}
    group = "hitting" if c["role"] == "hitter" else "pitching"
    for sport in (17, 22, 23, 1, 11, 12, 13, 14, 16):
        r = requests.get(f"{API}/people/{pid}/stats", params={"stats": "gameLog", "group": group, "season": 2026,
                                                               "sportId": sport}, timeout=30).json()
        splits = [s for st in r.get("stats", []) for s in st.get("splits", []) if START <= s.get("date", "") <= END]
        if splits:
            entry["sport"] = sport
            for s in splits:
                st = s["stat"]
                entry["games"].append({"date": s["date"], "gamePk": s["game"]["gamePk"], "opp": s.get("opponent", {}).get("name"),
                                       "team": s.get("team", {}).get("name"),
                                       "line": {k: st.get(k) for k in ("atBats", "hits", "doubles", "triples", "homeRuns", "rbi", "runs", "baseOnBalls", "stolenBases", "inningsPitched", "earnedRuns", "strikeOuts")}})
            break
    for g in entry["games"]:
        try:
            ct = requests.get(f"{API}/game/{g['gamePk']}/content", timeout=30).json()
        except Exception as e:
            continue
        items = (((ct.get("highlights") or {}).get("highlights") or {}).get("items") or [])
        for it in items:
            kws = it.get("keywordsAll") or []
            if not any(k.get("type") == "player_id" and str(k.get("value")) == str(pid) for k in kws):
                continue
            cuts = (it.get("image") or {}).get("cuts") or []
            best = max(cuts, key=lambda x: x.get("width", 0) * x.get("height", 0), default=None)
            if not best:
                continue
            fn = f"{pid}-{g['gamePk']}-{len(entry['images'])}.jpg"
            try:
                (OUT / "img" / fn).write_bytes(requests.get(best["src"], timeout=60).content)
            except Exception:
                continue
            entry["images"].append({"file": fn, "title": it.get("title"), "date": g["date"], "w": best.get("width"),
                                    "h": best.get("height"), "src": best["src"]})
    report.append(entry)
    print(c["name"], len(entry["games"]), "games,", len(entry["images"]), "images")
(OUT / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
