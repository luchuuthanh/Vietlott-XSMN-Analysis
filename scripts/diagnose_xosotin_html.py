#!/usr/bin/env python3
"""Capture raw XoSoTin XSMN daily-page structure for parser fixture diagnosis."""
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URLS = [
    "https://xosotin.net/ket-qua/xsmn/02-11-2026.html",
    "https://xosotin.net/ket-qua/xsmn/04-07-2026.html",
]
out = Path("xsmn_html_diagnostics")
out.mkdir(parents=True, exist_ok=True)
s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
})
for i, url in enumerate(URLS, 1):
    r = s.get(url, timeout=30)
    r.raise_for_status()
    (out / f"page_{i}.html").write_text(r.text, encoding="utf-8")
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [
        f"URL: {url}",
        f"FINAL_URL: {r.url}",
        f"STATUS: {r.status_code}",
        f"BYTES: {len(r.content)}",
        f"TITLE: {soup.title.get_text(' ', strip=True) if soup.title else ''}",
        f"TABLES: {len(soup.find_all('table'))}",
        f"TRS: {len(soup.find_all('tr'))}",
        f"DIVS: {len(soup.find_all('div'))}",
    ]
    for j, table in enumerate(soup.find_all("table"), 1):
        lines.append(f"\n--- TABLE {j} ---\n{table.prettify()[:30000]}")
    for j, node in enumerate(soup.find_all(["div", "section"], class_=True)[:80], 1):
        txt = node.get_text(" ", strip=True)
        if any(k in txt.lower() for k in ["đặc biệt", "dac biet", "giải 8", "giai 8", "đồng nai", "cần thơ"]):
            lines.append(f"\n--- MATCH NODE {j} class={node.get('class')} ---\n{node.prettify()[:8000]}")
    (out / f"diagnostic_{i}.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:8]))
