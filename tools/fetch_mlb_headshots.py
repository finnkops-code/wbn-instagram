"""Probe (Actions): official MLB headshots for names in probe/mlb_players.json -> probe/mlb/<slug>.png"""
import json, re, unicodedata
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "probe" / "mlb"; OUT.mkdir(parents=True, exist_ok=True)
API = "https://statsapi.mlb.com/api/v1"
def slug(n):
    n = "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]+", "-", n.lower()).strip("-")
rep = []
for p in json.loads((ROOT / "probe" / "mlb_players.json").read_text()):
    r = requests.get(f"{API}/people/search", params={"names": p["name"], "sportIds": 1, "active": "true"}, timeout=30).json()
    people = r.get("people", [])
    if not people:
        r = requests.get(f"{API}/people/search", params={"names": p["name"]}, timeout=30).json(); people = r.get("people", [])
    e = {"name": p["name"], "matches": [(x["id"], x.get("fullName"), (x.get("currentTeam") or {}).get("id")) for x in people[:3]]}
    if people:
        pid = people[0]["id"]
        url = f"https://img.mlbstatic.com/mlb-photos/image/upload/w_420,q_auto:best,f_png/v1/people/{pid}/headshot/67/current"
        b = requests.get(url, timeout=30).content
        (OUT / f"{slug(p['name'])}.png").write_bytes(b); e["id"] = pid
    rep.append(e); print(e)
(OUT / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
