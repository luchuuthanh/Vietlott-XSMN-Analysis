#!/usr/bin/env python3
"""Validate and export the 383.im XSMN supplement without merging it into the archive."""
from __future__ import annotations
import csv, json, os, sys
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
    available_dates=[]
    for item in root["items"]:
        try:
            available_dates.append(date.fromisoformat(item["d"]))
        except Exception:
            pass
    if not available_dates:
        raise SystemExit("API contains no valid draw dates; refusing to export an empty supplement.")
    api_latest_date=max(available_dates)
    if os.environ.get("XSMN_REQUIRE_TODAY") == "1" and api_latest_date != today:
        raise SystemExit(f"Daily XSMN feed is stale: API latest date={api_latest_date.isoformat()}, expected={today.isoformat()}. No supplement accepted.")
    end_date=min(today,api_latest_date)
    rows=[]; errors=[]; seen=set(); actual_pairs=set(); daily_dates=set()
    for day in root["items"]:
        try: draw_date=date.fromisoformat(day["d"])
        except Exception:
            errors.append({"type":"invalid_date","value":day.get("d")}); continue
        if not (START <= draw_date <= end_date): continue
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
    while cursor <= end_date:
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
    # Explicitly documented corrections supported by the project owner's screenshots.
    # Match by full row identity and old value; fail closed if the expected source value is absent
    # or appears more than once. Original values are retained in correction_audit.json.
    corrections = [
        {"date":"2026-08-29","province":"Long An","prize":"G2","old":"76719","new":"79719",
         "evidence":"User-supplied screenshot of VOH result text, 2026-11-06."},
        {"date":"2026-10-23","province":"Vinh Long","prize":"G4","old":"87992","new":"87962",
         "evidence":"User-supplied screenshot of Minh Ngoc/VOH result text explicitly noting supervisory correction, 2026-11-06."},
    ]
    applied=[]
    for correction in corrections:
        base=[i for i,row in enumerate(rows)
              if row[0]==correction["date"] and row[1]==correction["province"]
              and row[2]==correction["prize"]]
        old_matches=[i for i in base if rows[i][4]==correction["old"]]
        new_matches=[i for i in base if rows[i][4]==correction["new"]]
        if len(base)!=1 or (len(old_matches),len(new_matches)) not in ((1,0),(0,1)):
            errors.append({"type":"documented_correction_not_unique",
                           "correction":correction,"matches":len(base),
                           "old_matches":len(old_matches),"new_matches":len(new_matches)})
            continue
        i=(old_matches or new_matches)[0]
        original=list(rows[i])
        if old_matches:
            rows[i]=(original[0],original[1],original[2],original[3],correction["new"])
            correction_status="applied_by_local_audit_rule"
        else:
            correction_status="already_corrected_in_source"
        applied.append({**correction,"prize_order":original[3],"status":correction_status})
    if len(applied)!=len(corrections):
        raise SystemExit("Refusing to export: one or more documented corrections were not resolved exactly once.")

    OUT.mkdir(exist_ok=True)
    with (OUT/"xsmn_383_supplement.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["date","province","prize","prize_order","number"]); w.writerows(sorted(rows))
    (OUT/"correction_audit.json").write_text(
        json.dumps({"corrections_applied":applied,
                    "note":"Original values are preserved in this audit log; canonical CSV contains corrected values.",
                    "evidence_class":"user-supplied screenshots; secondary-source corroboration, not official issuer certification"},
                   ensure_ascii=False,indent=2),encoding="utf-8")
    report={
      "source":"383.im third-party API; not independently verified",
      "schema":root.get("schema"),"updated_at":root.get("updated_at"),
      "window_start":START.isoformat(),"window_end":end_date.isoformat(),
      "api_latest_date":max(available_dates).isoformat(),
      "days":len(daily_dates),"province_count":len({r[1] for r in rows}),
      "rows":len(rows),"station_day_pairs":len(actual_pairs),
      "expected_station_day_pairs":len(expected_pairs),
      "missing_draw_dates":len(missing_dates),"unexpected_draw_dates":len(extra_dates),
      "missing_station_days":len(missing),"unexpected_station_days":len(extra),
      "duplicate_rows":sum(e["type"]=="duplicate_row" for e in errors),
      "error_count":len(errors),"errors":errors,
      "corrections_applied":applied,
      "merge_status":"NOT_MERGED; keep as a separate supplement; documented corrections applied with audit trail"
    }
    (OUT/"validation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors: sys.exit(1)

if __name__=="__main__": main()
