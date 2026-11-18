"""Probe (Actions): save raw HTML of URLs in probe/html_urls.json to probe/html/<i>.html"""
import json
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "probe" / "html"; OUT.mkdir(parents=True, exist_ok=True)
for i, u in enumerate(json.loads((ROOT / "probe" / "html_urls.json").read_text())):
    try:
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        (OUT / f"{i}.html").write_text(f"<!-- {r.status_code} {r.url} -->\n" + r.text, encoding="utf-8")
    except Exception as e:
        (OUT / f"{i}.html").write_text(f"<!-- ERROR {e} -->", encoding="utf-8")
