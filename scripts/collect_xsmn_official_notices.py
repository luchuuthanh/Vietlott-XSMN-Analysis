#!/usr/bin/env python3
"""Discover and preserve XSMN result notices published by the Southern Lottery Council portal.

This is a source-discovery/evidence collector. It deliberately does NOT turn
unverified article text or images into canonical prize rows. Each captured
notice is stored with its URL, company label, date hints, media URLs and hashes.
"""
from __future__ import annotations
import hashlib, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE = "https://xsktmiennam.vn/"
OUT = Path("xsmn_official_source_probe")
COMPANIES = [
    "An Giang","Bạc Liêu","Bến Tre","Bình Dương","Bình Phước","Bình Thuận",
    "Cà Mau","Cần Thơ","Đồng Nai","Đồng Tháp","Hậu Giang","Kiên Giang",
    "Lâm Đồng","Long An","Sóc Trăng","Tây Ninh","Tiền Giang","TP.HCM",
    "Trà Vinh","Vĩnh Long","Bà Rịa - Vũng Tàu",
]
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; XSMNResearchBot/1.0; +https://github.com/luchuuthanh/Vietlott-XSMN-Analysis)"}
KEYWORDS = ("kqxskt", "công bố thông tin kq", "kết quả xổ số", "thông tin kqxskt")

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    response = session.get(BASE, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    candidates = {}
    for a in soup.select("a[href]"):
        title = " ".join(a.get_text(" ", strip=True).split())
        url = urljoin(BASE, a.get("href", ""))
        low = (title + " " + url).lower()
        if any(k in low for k in KEYWORDS) and urlparse(url).netloc == urlparse(BASE).netloc:
            candidates[url] = title or url
    # Search the site's result-news section links exposed on the home page.
    for a in soup.select("a[href]"):
        title = " ".join(a.get_text(" ", strip=True).split())
        if re.search(r"\b(xsk|xổ số|kết quả|kq)\b", title, re.I):
            url = urljoin(BASE, a["href"])
            if urlparse(url).netloc == urlparse(BASE).netloc:
                candidates.setdefault(url, title or url)

    notices, failures, media_manifest = [], [], []
    for idx, (url, title) in enumerate(sorted(candidates.items())):
        try:
            r = session.get(url, timeout=25)
            r.raise_for_status()
            page = BeautifulSoup(r.content, "html.parser")
            text = " ".join(page.get_text(" ", strip=True).split())
            matched = [name for name in COMPANIES if name.casefold() in (title + " " + text[:2500]).casefold()]
            date_hints = sorted(set(re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b", title + " " + text[:4000])))
            images = []
            for im in page.select("img[src]"):
                src = urljoin(url, im.get("src", ""))
                if urlparse(src).scheme in ("http", "https"):
                    images.append(src)
            saved_media = []
            for j, media_url in enumerate(images[:8]):
                try:
                    mr = session.get(media_url, timeout=25)
                    mr.raise_for_status()
                    suffix = Path(urlparse(media_url).path).suffix.lower()
                    if suffix not in (".jpg",".jpeg",".png",".webp",".gif"): suffix = ".bin"
                    name = f"notice_{idx:03d}_media_{j:02d}{suffix}"
                    (OUT / name).write_bytes(mr.content)
                    item = {"file":name,"url":media_url,"sha256":sha(mr.content),"bytes":len(mr.content)}
                    saved_media.append(item); media_manifest.append(item)
                except Exception as exc:
                    failures.append({"url":media_url,"error":str(exc)})
            html_name = f"notice_{idx:03d}.html"
            (OUT / html_name).write_bytes(r.content)
            notices.append({
                "title":title,"url":url,"http_status":r.status_code,
                "company_name_hints":matched,"date_hints":date_hints,
                "html_file":html_name,"html_sha256":sha(r.content),
                "media":saved_media,"text_excerpt":text[:1600]
            })
            time.sleep(0.2)
        except Exception as exc:
            failures.append({"url":url,"error":str(exc)})
    manifest = {
        "collector":"Southern Lottery Council portal notice discovery",
        "portal":BASE,"captured_at_utc":datetime.now(timezone.utc).isoformat(),
        "candidate_notice_count":len(candidates),"notice_count":len(notices),
        "media_count":len(media_manifest),"failures":failures,
        "notices":notices,
        "companies_expected":COMPANIES,
        "companies_with_notice_hints":sorted({n for x in notices for n in x["company_name_hints"]}),
        "important":"This portal is a Council information site, not the issuing company website itself. Captures are source evidence only; no prize numbers are promoted into the canonical dataset without an issuer-level parser and independent validation."
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k not in ("notices","failures")},ensure_ascii=False,indent=2))
    if not notices:
        raise SystemExit("No result notices discovered; refusing a successful empty run.")

if __name__ == "__main__":
    main()
