"""Probe (Actions): official NPB player photos for a list of players -> probe/npb/<slug>.jpg + report.json"""
import json, re, sys
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "probe" / "npb"; OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (WBN editorial)"}
want = json.loads((ROOT / "probe" / "npb_players.json").read_text())
teams = ["g", "t", "db", "c", "s", "d", "h", "l", "f", "b", "m", "e"]
index = {}
for t in teams:
    for lang in ("eng",):
        u = f"https://npb.jp/bis/{lang}/teams/rst_{t}.html"
        try:
            s = BeautifulSoup(requests.get(u, headers=UA, timeout=30).content, "html.parser")
        except Exception as e:
            print("roster fail", u, e); continue
        for a in s.find_all("a", href=True):
            if "/players/" in a["href"]:
                index.setdefault(re.sub(r"\s+", " ", a.get_text(" ", strip=True)).lower(), []).append((t, urljoin(u, a["href"])))
print("indexed", len(index))
rep = []
for p in want:
    first, last = p["name"].split(" ", 1)
    keys = [f"{last}, {first}".lower(), f"{last} {first}".lower(), p["name"].lower()]
    hit = next((index[k] for k in keys if k in index), None)
    e = {"name": p["name"], "found": bool(hit)}
    if hit:
        url = hit[0][1]; e["page"] = url
        s = BeautifulSoup(requests.get(url, headers=UA, timeout=30).content, "html.parser")
        img = s.select_one("#pc_v_photo img, .player_photo img, img[src*='players'], img[src*='photo']")
        if img:
            src = urljoin(url, img["src"]); e["src"] = src
            b = requests.get(src, headers=UA, timeout=30).content
            fn = re.sub(r"[^a-z]+", "-", p["name"].lower()) + ".jpg"
            (OUT / fn).write_bytes(b); e["file"] = fn
    rep.append(e); print(e)
(OUT / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
