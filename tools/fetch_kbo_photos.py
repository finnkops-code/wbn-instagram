"""Probe (Actions): official KBO player photos via koreabaseball.com search -> probe/kbo/<slug>.jpg"""
import json, re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "probe" / "kbo"; OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (WBN editorial)"}
rep = []
for p in json.loads((ROOT / "probe" / "kbo_players.json").read_text()):
    e = {"name": p["name"], "ko": p["ko"], "team": p["team"]}
    try:
        u = "https://www.koreabaseball.com/Player/Search.aspx"
        s = BeautifulSoup(requests.get(u, params={"searchWord": p["ko"]}, headers=UA, timeout=30).content, "html.parser")
        rows = []
        for tr in s.select("table tr"):
            a = tr.find("a", href=re.compile("playerId", re.I))
            if a:
                rows.append((tr.get_text(" ", strip=True), urljoin(u, a["href"])))
        e["rows"] = [r[0][:80] for r in rows[:5]]
        hit = next((r for r in rows if p["team_ko"] in r[0]), rows[0] if rows else None)
        if hit:
            e["page"] = hit[1]
            ps = BeautifulSoup(requests.get(hit[1], headers=UA, timeout=30).content, "html.parser")
            img = ps.select_one(".player_basic .photo img, .photo img, img[src*='person']")
            if img:
                src = urljoin(hit[1], img["src"]); e["src"] = src
                (OUT / f"{p['slug']}.jpg").write_bytes(requests.get(src, headers=UA, timeout=30).content)
    except Exception as ex:
        e["error"] = str(ex)[:200]
    rep.append(e); print(e)
(OUT / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
