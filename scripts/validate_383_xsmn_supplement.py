#!/usr/bin/env python3
"""Validate and export the 383.im XSMN supplement without merging it into the archive."""
from __future__ import annotations
import csv, json, sys
from collections import Counter
from datetime import date
from pathlib import Path

SOURCE = Path("xsmn_383_probe/region_sample.json")
OUT = Path("xsmn_383_supplement")
START = date(2026, 7, 1)
PROVINCES = {
    "an-giang":"An Giang", "bac-lieu":"Bac Lieu", "ben-tre":"Ben Tre",
    "binh-duong":"Binh Duong", "binh-phuoc":"Binh Phuoc", "binh-thuan":"Binh Thuan",
    "ca-mau":"Ca Mau", "can-tho":"Can Tho", "dong-nai":"Dong Nai",
    "dong-thap":"Dong Thap", "hau-giang":"Hau Giang", "kien-giang":"Kien Giang",
    "lam-dong":"Da Lat", "long-an":"Long An", "soc-trang":"Soc Trang",
    "tay-ninh":"Tay Ninh", "tien-giang":"Tien Giang", "tp-hcm":"TP. HCM",
    "tra-vinh":"Tra Vinh", "vinh-long":"Vinh Long", "vung-tau":"Vung Tau",
}
SCHEDULE = {
    "mon":{"ca-mau","dong-thap","tp-hcm"},
    "tue":{"bac-lieu","ben-tre","vung-tau"},
    "wed":{"can-tho","dong-nai","soc-trang"},
    "thu":{"an-giang","binh-thuan","tay-ninh"},
    "fri":{"binh-duong","tra-vinh","vinh-long"},
    "sat":{"binh-phuoc","hau-giang","long-an","tp-hcm"},
    "sun":{"lam-dong","kien-giang","tien-giang"},
}
PRIZES = {"db":(1,6),"g1":(1,5),"g2":(1,5),"g3":(2,5),"g4":(7,5),
          "g5":(1,4),"g6":(3,4),"g7":(1,3),"g8":(1,2)}

def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing API sample: {SOURCE}")
    root=json.loads(SOURCE.read_text(encoding="utf-8"))
    if root.get("schema") != "lottery_region_v1" or not isinstance(root.get("items"),list):
        raise SystemExit("Unexpected API schema; refusing to export.")
    today=date.today()
    rows=[]; errors=[]; seen=set(); actual_pairs=set(); daily_dates=set()
    for day in root["items"]:
        try: draw_date=date.fromisoformat(day["d"])
        except Exception:
            errors.append({"type":"invalid_date","value":day.get("d")}); continue
        if not (START <= draw_date <= today): continue
        daily_dates.add(draw_date.isoformat())
        weekday=day.get("w")
        if weekday not in SCHEDULE:
            errors.append({"type":"invalid_weekday","date":draw_date.isoformat(),"value":weekday})
        stations=day.get("ps")
        if not isinstance(stations,list):
            errors.append({"type":"invalid_station_list","date":draw_date.isoformat()}); continue
        for station in stations:
            slug=station.get("i"); prizes=station.get("g")
            if slug not in PROVINCES:
                errors.append({"type":"unknown_station","date":draw_date.isoformat(),"station":slug}); continue
            actual_pairs.add((draw_date.isoformat(),slug))
            if not isinstance(prizes,dict):
                errors.append({"type":"invalid_prizes","date":draw_date.isoformat(),"station":slug}); continue
            if set(prizes) != set(PRIZES):
                errors.append({"type":"prize_set_mismatch","date":draw_date.isoformat(),"station":slug,
                               "missing":sorted(set(PRIZES)-set(prizes)),"extra":sorted(set(prizes)-set(PRIZES))})
            for prize,(expected_count,expected_len) in PRIZES.items():
                values=prizes.get(prize,[])
                if not isinstance(values,list) or len(values)!=expected_count:
                    errors.append({"type":"prize_count","date":draw_date.isoformat(),"station":slug,
                                   "prize":prize,"expected":expected_count,
                                   "actual":len(values) if isinstance(values,list) else None})
                    continue
                for idx,value in enumerate(values):
                    number=str(value)
                    if not number.isdigit() or len(number)!=expected_len:
                        errors.append({"type":"number_format","date":draw_date.isoformat(),"station":slug,
                                       "prize":prize,"value":number,"expected_length":expected_len})
                    key=(draw_date.isoformat(),slug,prize,idx)
                    if key in seen: errors.append({"type":"duplicate_row","key":key})
                    seen.add(key)
                    rows.append((draw_date.isoformat(),PROVINCES[slug],prize.upper(),idx,number))
    expected_pairs=set()
    expected_dates=set()
    cursor=START
    while cursor <= today:
        iso=cursor.isoformat()
        expected_dates.add(iso)
        wd=("mon","tue","wed","thu","fri","sat","sun")[cursor.weekday()]
        expected_pairs.update((iso,station) for station in SCHEDULE[wd])
        cursor=date.fromordinal(cursor.toordinal()+1)
    missing_dates=sorted(expected_dates-daily_dates)
    extra_dates=sorted(daily_dates-expected_dates)
    missing=sorted(expected_pairs-actual_pairs); extra=sorted(actual_pairs-expected_pairs)
    if missing_dates: errors.append({"type":"missing_draw_dates","count":len(missing_dates),"dates":missing_dates[:30]})
    if extra_dates: errors.append({"type":"unexpected_draw_dates","count":len(extra_dates),"dates":extra_dates[:30]})
    if missing: errors.append({"type":"missing_station_days","count":len(missing),"examples":missing[:30]})
    if extra: errors.append({"type":"unexpected_station_days","count":len(extra),"examples":extra[:30]})
    OUT.mkdir(exist_ok=True)
    with (OUT/"xsmn_383_supplement.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["date","province","prize","prize_order","number"]); w.writerows(sorted(rows))
    report={
      "source":"383.im third-party API; not independently verified",
      "schema":root.get("schema"),"updated_at":root.get("updated_at"),
      "window_start":START.isoformat(),"window_end":today.isoformat(),
      "days":len(daily_dates),"province_count":len({r[1] for r in rows}),
      "rows":len(rows),"station_day_pairs":len(actual_pairs),
      "expected_station_day_pairs":len(expected_pairs),
      "missing_draw_dates":len(missing_dates),"unexpected_draw_dates":len(extra_dates),
      "missing_station_days":len(missing),"unexpected_station_days":len(extra),
      "duplicate_rows":sum(e["type"]=="duplicate_row" for e in errors),
      "error_count":len(errors),"errors":errors,
      "merge_status":"NOT_MERGED; keep as a separate supplement until independently verified"
    }
    (OUT/"validation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors: sys.exit(1)

if __name__=="__main__": main()
