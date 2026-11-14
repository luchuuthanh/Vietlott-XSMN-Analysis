#!/usr/bin/env python3
"""Build today's XSMN draw in parallel from 383 and XoSoTin, filling only incomplete stations."""
from __future__ import annotations
import csv, json, sys, time
from collections import defaultdict
from datetime import date
from pathlib import Path
import requests

from validate_383_xsmn_supplement import PROVINCES, SCHEDULE, PRIZES
from verify_xsmn_supplement_sources_v2 import parse_daily
from xsmn_live import fetch_live_xsmn_partial, normalize_station_key

RAW = Path("xsmn_383_probe/region_sample.json")
OUT = Path("xsmn_daily_verified.csv")
REPORT = Path("xsmn_383_supplement/validation_report.json")
AUDIT = Path("xsmn_383_supplement/station_fallback_audit.json")
COLUMNS = ["date", "province", "prize", "prize_order", "number", "source"]

def chosen_for_station(rows, station, day, prize):
    return [str(r[4]) for r in rows if r[0] == day and r[1] == station and r[2] == prize.upper()]

def main():
    today = date.today()
    day = today.isoformat()
    weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[today.weekday()]
    expected_slugs = SCHEDULE[weekday]
    expected_stations = {PROVINCES[s] for s in expected_slugs}
    if not RAW.exists():
        raise SystemExit("Missing 383 API response; refusing to prepare daily draw.")
    root = json.loads(RAW.read_text(encoding="utf-8"))
    if root.get("schema") != "lottery_region_v1" or not isinstance(root.get("items"), list):
        raise SystemExit("Unexpected 383 API schema; refusing to prepare daily draw.")
    today_items = [x for x in root["items"] if x.get("d") == day]
    if not today_items:
        latest = sorted(str(x.get("d", "")) for x in root["items"])[-1:] or ["none"]
        raise SystemExit(f"383 feed has no draw for {day}; latest feed date={latest[0]}. No stale-date substitution.")
    if len(today_items) != 1:
        raise SystemExit(f"383 feed contains {len(today_items)} records for {day}; refusing ambiguous data.")
    item = today_items[0]
    if item.get("w") != weekday:
        raise SystemExit(f"383 weekday mismatch for {day}: {item.get('w')} != {weekday}")
    available = {}
    raw_stations = item.get("ps")
    if not isinstance(raw_stations, list):
        raise SystemExit("383 station list is invalid.")
    for station in raw_stations:
        slug = station.get("i")
        if slug not in PROVINCES:
            continue
        name = PROVINCES[slug]
        prizes = station.get("g")
        if not isinstance(prizes, dict):
            continue
        normalized = {}
        for prize, (count, length) in PRIZES.items():
            vals = prizes.get(prize, [])
            if not isinstance(vals, list):
                vals = []
            vals = [str(v).strip() for v in vals]
            normalized[prize.upper()] = vals
        if name in available:
            raise SystemExit(f"Duplicate 383 station record: {name}")
        available[name] = normalized

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
                            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"})
    secondary = None
    rows, fallback, errors = [], [], []
    for station in sorted(expected_stations):
        primary = available.get(station, {})
        complete = all(len(primary.get(p.upper(), [])) == count and
                       all(v.isdigit() and len(v) == length for v in primary.get(p.upper(), []))
                       for p, (count, length) in PRIZES.items())
        if complete:
            chosen = primary
            source = "383_supplement"
        else:
            if secondary is None:
                url = f"https://xosotin.net/ket-qua/xsmn/{today:%d-%m-%Y}.html"
                try:
                    response = session.get(url, timeout=25)
                    response.raise_for_status()
                    secondary = parse_daily(response.content)
                except Exception as exc:
                    raise SystemExit(f"Cannot fetch independent fallback {url}: {exc}")
                if not secondary:
                    raise SystemExit(f"XoSoTin has no complete result grid for {day}; no history write.")
            observed = secondary.get(station)
            if not observed:
                raise SystemExit(f"{station}: 383 incomplete and XoSoTin has no complete station result.")
            chosen = {p.upper(): list(observed.get(p, [])) for p in PRIZES}
            # If 383 already has a complete prize row, it must agree with the fallback.
            for prize, (count, length) in PRIZES.items():
                p = prize.upper()
                vals = primary.get(p, [])
                if len(vals) == count and vals != chosen.get(p, []):
                    raise SystemExit(f"{station} {p}: 383 and XoSoTin disagree; history write blocked.")
            source = "383_supplement"
            fallback.append({"station": station, "reason": "missing_or_incomplete_383_station",
                             "fallback_source": "XoSoTin daily page"})
        # Final strict validation: exactly the expected 18 values per station.
        for prize, (count, length) in PRIZES.items():
            vals = chosen.get(prize.upper(), [])
            if len(vals) != count or any(not v.isdigit() or len(v) != length for v in vals):
                raise SystemExit(f"{station} {prize.upper()}: invalid count/number format after source selection.")
            for index, value in enumerate(vals):
                rows.append([day, station, prize.upper(), index, value, source])

    if fallback:
        # XoSoTin fallback must be confirmed by a third independent source.
        try:
            live_frame, live_url = fetch_live_xsmn_partial()
        except Exception as exc:
            raise SystemExit(f"Cannot independently verify fallback stations against sxmn.com.vn: {exc}")
        live_dates = set(live_frame["date"].astype(str).str[:10])
        if live_dates != {day}:
            raise SystemExit(f"sxmn.com.vn date mismatch: {sorted(live_dates)}")
        for entry in fallback:
            station = entry["station"]
            subset = live_frame[live_frame["province"].map(normalize_station_key) == normalize_station_key(station)]
            if len(subset) != 18:
                raise SystemExit(f"{station}: sxmn.com.vn has fewer than 18 results; history write blocked.")
            live_map = defaultdict(list)
            for _, record in subset.iterrows():
                prize = str(record["prize"]).upper().replace("ĐB", "DB")
                live_map[prize].append(str(record["number"]))
            for prize, (count, length) in PRIZES.items():
                if sorted(live_map.get(prize.upper(), [])) != sorted(chosen_for_station(rows, station, day, prize)):
                    raise SystemExit(f"{station} {prize.upper()}: XoSoTin and sxmn.com.vn disagree; history write blocked.")
            entry["third_source"] = "sxmn.com.vn"
            entry["third_source_status"] = "MATCH"
            entry["third_source_url"] = live_url

    if {r[1] for r in rows} != expected_stations or len(rows) != len(expected_stations) * 18:
        raise SystemExit("Final daily station set or row count is incomplete.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(sorted(rows, key=lambda r: (r[1], r[2], r[3])))
    audit = {"date": day, "mode": "parallel_primary_plus_station_fallback",
             "primary_source": "383.im", "fallback_source": "XoSoTin",
             "expected_stations": sorted(expected_stations), "fallback_stations": fallback,
             "fallback_station_count": len(fallback), "rows": len(rows),
             "status": "PASS", "note": "Any available complete prize in 383 must match fallback; final independent full-station comparison is required before publish."}
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"source": "383.im with XoSoTin station-level fallback",
              "window_start": day, "window_end": day, "api_latest_date": day,
              "station_day_pairs": len(expected_stations), "rows": len(rows),
              "fallback_station_count": len(fallback), "status": "PASS",
              "errors": [], "merge_status": "PREPARED_ONLY; publish script still requires independent full comparison"}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
