"""Probe (Actions): for each page URL, save og:image and images whose alt/title/filename mention a keyword."""
import json, re, sys, hashlib
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "probe" / "pages"; OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (WBN editorial research)"}
spec = json.loads((ROOT / "probe" / "pages.json").read_text())
kw = [k.lower() for k in spec["keywords"]]
rep = []
for url in spec["urls"]:
    e = {"url": url, "imgs": [], "text": ""}
    try:
        r = requests.get(url, headers=UA, timeout=40)
        s = BeautifulSoup(r.content, "html.parser")
        art = s.find("article") or s
        e["text"] = re.sub(r"\s+", " ", art.get_text(" "))[:2500]
        cands = []
        og = s.find("meta", property="og:image")
        if og: cands.append((og.get("content"), "og:image"))
        for im in s.find_all("img"):
            src = im.get("data-src") or im.get("src") or ""
            meta = " ".join([im.get("alt") or "", im.get("title") or "", src]).lower()
            if src and any(k in meta for k in kw): cands.append((src, im.get("alt") or ""))
        for src, alt in cands[:6]:
            src = urljoin(url, src)
            b = requests.get(src, headers=UA, timeout=40).content
            if len(b) < 15000: continue
            fn = hashlib.md5(src.encode()).hexdigest()[:10] + ".jpg"
            (OUT / fn).write_bytes(b)
            e["imgs"].append({"file": fn, "src": src, "alt": alt})
    except Exception as ex:
        e["error"] = str(ex)[:200]
    rep.append(e); print(url, len(e["imgs"]))
(OUT / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
