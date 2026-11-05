#!/usr/bin/env python3
"""Probe public 383.im XSMN endpoints; never merges unverified data."""
from __future__ import annotations
import json
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://api.383.im/lottery"
CANDIDATES = [
    f"{BASE}/region/mn.json",
    f"{BASE}/region/mien-nam.json",
    f"{BASE}/live.json",
]
OUT = Path("xsmn_383_probe")
OUT.mkdir(exist_ok=True)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "XSMN-Archive-Audit/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return r.status, r.headers.get("Content-Type", ""), raw

def describe(value):
    info = {"root_type": type(value).__name__}
    if isinstance(value, dict):
        info["root_keys"] = sorted(value.keys())
        for key, item in value.items():
            if isinstance(item, list):
                info["list_field"] = key
                info["list_length"] = len(item)
                if item:
                    info["first_item_type"] = type(item[0]).__name__
                    if isinstance(item[0], dict):
                        info["first_item_keys"] = sorted(item[0].keys())
                break
    elif isinstance(value, list):
        info["list_length"] = len(value)
        if value and isinstance(value[0], dict):
            info["first_item_keys"] = sorted(value[0].keys())
    return info

results = []
for url in CANDIDATES:
    row = {"url": url}
    try:
        status, content_type, raw = fetch(url)
        row.update(http_status=status, content_type=content_type, bytes=len(raw))
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
            row["json"] = describe(parsed)
            if "live.json" in url:
                (OUT / "live_sample.json").write_bytes(raw)
            else:
                (OUT / ("region_sample.json" if "region/" in url else "alternate_sample.json")).write_bytes(raw)
        except Exception as exc:
            row["json_error"] = str(exc)
            row["body_preview"] = raw[:300].decode("utf-8", "replace")
    except Exception as exc:
        row["error"] = str(exc)
    results.append(row)

(OUT / "probe_report.json").write_text(json.dumps({
    "checked_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    "window_needed": ["2026-07-01", date.today().isoformat()],
    "results": results,
    "note": "Probe only. No records are merged until a dated historical schema is verified."
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2))
