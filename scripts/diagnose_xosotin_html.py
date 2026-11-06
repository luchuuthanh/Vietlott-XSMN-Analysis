#!/usr/bin/env python3
"""Capture XSMN source HTML to diagnose independent result-table parsing."""
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URLS = {
    "xskt_net": "https://xskt.net/xsmn/23-10-2026",
    "xskt_com_vn_vinhlong": "https://xskt.com.vn/xsvl/ngay-23-10-2026",
    "xskt_com_vn_longan": "https://xskt.com.vn/xsla/ngay-29-8-2026",
    "xosotin": "https://xosotin.net/ket-qua/xsmn/23-10-2026.html",
}
out = Path("xsmn_html_diagnostics")
out.mkdir(parents=True, exist_ok=True)
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36", "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"})
summary = []
for name, url in URLS.items():
    try:
        r = s.get(url, timeout=35)
        r.raise_for_status()
        (out / f"{name}.html").write_bytes(r.content)
        soup = BeautifulSoup(r.content, "html.parser")
        lines = [f"URL: {url}", f"FINAL_URL: {r.url}", f"STATUS: {r.status_code}", f"BYTES: {len(r.content)}", f"TITLE: {soup.title.get_text(' ', strip=True) if soup.title else ''}", f"TABLES: {len(soup.find_all('table'))}", f"TRS: {len(soup.find_all('tr'))}", f"DIVS: {len(soup.find_all('div'))}"]
        for i, table in enumerate(soup.find_all("table"), 1):
            lines.append(f"\\n--- TABLE {i} ---\\n{table.prettify()[:20000]}")
        for i, node in enumerate(soup.find_all(["div", "section"], class_=True)[:100], 1):
            txt = node.get_text(" ", strip=True)
            if any(k in txt.lower() for k in ["đặc biệt", "dac biet", "giải 8", "giai 8", "vĩnh long", "long an"]):
                lines.append(f"\\n--- NODE {i} class={node.get('class')} ---\\n{node.prettify()[:5000]}")
        (out / f"{name}.txt").write_text("\\n".join(lines), encoding="utf-8")
        summary.append(f"{name}: HTTP {r.status_code}; {len(r.content)} bytes; {len(soup.find_all('table'))} tables; {len(soup.find_all('tr'))} rows")
    except Exception as e:
        summary.append(f"{name}: ERROR {e}")
print("\\n".join(summary))
