#!/usr/bin/env python3
"""Safely merge a separately cross-checked XSMN draw into the canonical five-year file."""
import json
from pathlib import Path
import pandas as pd

CANONICAL = Path("data/xsmn_5y_canonical.csv")
MANIFEST = Path("data/xsmn_5y_canonical.json")
DAILY = Path("data/xsmn_daily_verified_2026-11-07.csv")
DAILY_META = Path("data/xsmn_daily_verified_2026-11-07.json")
KEYS = ["date", "province", "prize", "prize_order"]
COLS = ["date","province","prize","prize_order","number","number_length","last2","last2_numeric","source"]
EXPECTED_STATIONS = {"Binh Phuoc","Hau Giang","Long An","TP. HCM"}
EXPECTED_PRIZES = {"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}

def main():
    for p in (CANONICAL, MANIFEST, DAILY, DAILY_META):
        if not p.exists(): raise SystemExit(f"Missing required input: {p}")
    old = pd.read_csv(CANONICAL, dtype={"number":str,"last2":str})
    new = pd.read_csv(DAILY, dtype={"number":str,"last2":str})
    meta = json.loads(DAILY_META.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS": raise SystemExit("Existing canonical manifest is not PASS")
    if not set(COLS).issubset(old.columns) or not set(COLS).issubset(new.columns):
        raise SystemExit("Canonical or daily file schema mismatch")
    if meta.get("status") != "PASS" or meta.get("actual_rows") != 72 or len(new) != 72:
        raise SystemExit("Daily source metadata/row count gate failed")
    new["date"] = pd.to_datetime(new["date"], errors="raise").dt.strftime("%Y-%m-%d")
    old["date"] = pd.to_datetime(old["date"], errors="raise").dt.strftime("%Y-%m-%d")
    if set(new["date"]) != {"2026-11-07"}: raise SystemExit("Unexpected date in daily file")
    if set(new["province"]) != EXPECTED_STATIONS: raise SystemExit("Station set mismatch")
    if new.duplicated(KEYS).any(): raise SystemExit("Duplicate keys in daily file")
    if new["source"].nunique() != 1 or new["source"].iloc[0] != "manual_multi_source_verified":
        raise SystemExit("Daily source provenance mismatch")
    counts = new.groupby("prize").size().to_dict()
    if counts != EXPECTED_PRIZES: raise SystemExit(f"Prize row counts mismatch: {counts}")
    for _, row in new.iterrows():
        number = str(row["number"])
        if not number.isdigit() or len(number) != int(row["number_length"]):
            raise SystemExit(f"Invalid number/length: {row.to_dict()}")
        if number[-2:].zfill(2) != str(row["last2"]).zfill(2):
            raise SystemExit(f"Invalid last2: {row.to_dict()}")
    if old.duplicated(KEYS).any(): raise SystemExit("Existing canonical contains duplicate keys")
    existing_day = old[old["date"] == "2026-11-07"]
    if len(existing_day):
        # Idempotent: accept an exact existing day's data, reject partial/conflicting rows.
        check = existing_day[KEYS + ["number"]].merge(new[KEYS + ["number"]], on=KEYS, how="outer", suffixes=("_old","_new"), indicator=True)
        if len(existing_day) != 72 or not (check["_merge"] == "both").all() or not (check["number_old"] == check["number_new"]).all():
            raise SystemExit("Canonical already has conflicting/partial 2026-11-07 records")
        merged = old.copy()
    else:
        if old["date"].max() != "2026-11-06":
            raise SystemExit(f"Expected canonical to end 2026-11-06, got {old['date'].max()}")
        merged = pd.concat([old[COLS], new[COLS]], ignore_index=True)
    merged = merged.sort_values(KEYS, kind="stable")
    merged.to_csv(CANONICAL, index=False, encoding="utf-8-sig")
    manifest.update({
        "status":"PASS",
        "updated_at_vietnam":pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").isoformat(),
        "window_end":"2026-11-07",
        "rows":int(len(merged)),
        "last_draw_import":"2026-11-07",
        "last_draw_rows":72,
        "last_draw_source":"manual_multi_source_verified",
        "last_draw_verification":"Four independent published result pages agree; official issuer confirmation remains authoritative.",
        "note":"Canonical five-year file includes the verified 2026-11-07 draw. Source provenance is retained per row."
    })
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"PASS","rows":len(merged),"window_start":merged.date.min(),"window_end":merged.date.max(),"today_rows":int((merged.date=="2026-11-07").sum())},ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
