#!/usr/bin/env python3
"""Prepare and publish one independently verified XSMN draw without auditing the five-year archive."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

SUPPLEMENT = Path("xsmn_383_supplement/xsmn_383_supplement.csv")
VALIDATION = Path("xsmn_383_supplement/validation_report.json")
CANONICAL = Path("data/xsmn_5y_canonical.csv")
MANIFEST = Path("data/xsmn_5y_canonical.json")
PREPARED = Path("xsmn_daily_verified.csv")
CHECK = Path("xsmn_independent_audit/today_comparison.json")
COLS = ["date","province","prize","prize_order","number","number_length","last2","last2_numeric","source"]
SCHEDULE = {
  0: {"Ca Mau","Dong Thap","TP. HCM"},
  1: {"Bac Lieu","Ben Tre","Vung Tau"},
  2: {"Can Tho","Dong Nai","Soc Trang"},
  3: {"An Giang","Binh Thuan","Tay Ninh"},
  4: {"Binh Duong","Tra Vinh","Vinh Long"},
  5: {"Binh Phuoc","Hau Giang","Long An","TP. HCM"},
  6: {"Da Lat","Kien Giang","Tien Giang"},
}
COUNTS = {"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
LENGTHS = {"DB":6,"G1":5,"G2":5,"G3":5,"G4":5,"G5":4,"G6":4,"G7":3,"G8":2}
def prepare():
    if not SUPPLEMENT.exists() or not VALIDATION.exists():
        raise SystemExit("Missing daily/backfill supplement or validation report.")
    report=json.loads(VALIDATION.read_text(encoding="utf-8"))
    if report.get("status") != "PASS":
        raise SystemExit(f"383 feed validation did not PASS: {report.get('status')}")
    start_day=report.get("window_start")
    end_day=report.get("window_end")
    if not start_day or not end_day or start_day > end_day:
        raise SystemExit("Invalid validated backfill window.")
    if int(report.get("rows",0)) == 0:
        print(json.dumps({"status":"NO_NEW_DATA","window_start":start_day,"window_end":end_day},ensure_ascii=False))
        return
    df=pd.read_csv(SUPPLEMENT,dtype={"number":str})
    if df.empty or not set(COLS[:-4]).issubset(df.columns):
        raise SystemExit("Daily/backfill supplement is empty or has an invalid schema.")
    df["date"]=pd.to_datetime(df["date"],errors="raise").dt.strftime("%Y-%m-%d")
    df["province"]=df["province"].astype(str).str.strip()
    df["prize"]=df["prize"].astype(str).str.strip().str.upper().replace({"DB":"DB"})
    df["number"]=df["number"].astype(str).str.strip()
    dates=sorted(set(df.date))
    if dates[0] != start_day or dates[-1] != end_day:
        raise SystemExit(f"Prepared dates do not match validation window: {dates[0]}..{dates[-1]} vs {start_day}..{end_day}")
    expected_dates=pd.date_range(start_day,end_day,freq="D").strftime("%Y-%m-%d").tolist()
    if dates != expected_dates:
        raise SystemExit(f"Backfill has missing draw dates: expected {expected_dates}, got {dates}")
    expected_rows=[]
    for day in dates:
        expected_stations=SCHEDULE[pd.Timestamp(day).weekday()]
        day_frame=df[df.date==day]
        if set(day_frame.province)!=expected_stations:
            raise SystemExit(f"{day}: station set mismatch: expected={sorted(expected_stations)}, actual={sorted(day_frame.province.unique())}")
        for station,g in day_frame.groupby("province"):
            counts=g.prize.value_counts().to_dict()
            if counts != COUNTS or len(g)!=18:
                raise SystemExit(f"{day} {station}: prize structure is not exactly 18 rows: {counts}")
            if g.duplicated(["date","province","prize","prize_order"]).any():
                raise SystemExit(f"{day} {station}: duplicate prize key.")
            for _,r in g.iterrows():
                if r.prize not in LENGTHS or not r.number.isdigit() or len(r.number)!=LENGTHS[r.prize]:
                    raise SystemExit(f"Invalid result number: {r.to_dict()}")
        expected_rows.append(len(day_frame))
    if df.duplicated(["date","province","prize","prize_order"]).any():
        raise SystemExit("Duplicate daily/backfill prize keys.")
    df["number_length"]=df.number.str.len().astype(int)
    df["last2"]=df.number.str[-2:].str.zfill(2)
    df["last2_numeric"]=pd.to_numeric(df.last2,errors="raise").astype(int)
    df["source"]="383_supplement"
    df=df[COLS].sort_values(["date","province","prize","prize_order"],kind="stable")
    PREPARED.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(PREPARED,index=False,encoding="utf-8-sig")
    print(json.dumps({"status":"PREPARED","window_start":start_day,"window_end":end_day,"dates":len(dates),"stations":int(df[["date","province"]].drop_duplicates().shape[0]),"rows":len(df)},ensure_ascii=False))
def publish():
    for p in (CANONICAL,MANIFEST,PREPARED,CHECK):
        if not p.exists(): raise SystemExit(f"Missing required input: {p}")
    check=json.loads(CHECK.read_text(encoding="utf-8"))
    old=pd.read_csv(CANONICAL,dtype={"number":str,"last2":str})
    new=pd.read_csv(PREPARED,dtype={"number":str,"last2":str})
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status")!="PASS": raise SystemExit("Canonical manifest is not PASS.")
    if new.empty or not set(COLS).issubset(old.columns) or not set(COLS).issubset(new.columns):
        raise SystemExit("Canonical/daily schema mismatch or empty prepared file.")
    keys=["date","province","prize","prize_order"]
    if new.duplicated(keys).any() or old.duplicated(keys).any():
        raise SystemExit("Duplicate keys detected.")
    new_dates=sorted(new.date.astype(str).str[:10].unique())
    start_day,end_day=new_dates[0],new_dates[-1]
    if check.get("status")!="PASS" or check.get("window_start")!=start_day or check.get("window_end")!=end_day:
        raise SystemExit("Independent source comparison did not PASS for the exact prepared backfill window.")
    if int(check.get("station_days_match",-1)) != int(new[["date","province"]].drop_duplicates().shape[0]):
        raise SystemExit("Independent comparison did not match every station-day.")
    additions=[]
    for day in new_dates:
        old_day=old[old.date.astype(str).str[:10]==day]
        new_day=new[new.date.astype(str).str[:10]==day]
        if old_day.empty:
            additions.append(new_day)
            continue
        left=old_day[keys+["number"]].sort_values(keys).reset_index(drop=True)
        right=new_day[keys+["number"]].sort_values(keys).reset_index(drop=True)
        if not left.equals(right):
            raise SystemExit(f"{day}: canonical already contains partial/conflicting rows; refusing overwrite.")
    missing_days=[d for d in new_dates if old[old.date.astype(str).str[:10]==d].empty]
    if missing_days:
        max_old=pd.to_datetime(old.date,errors="raise").max().date()
        expected=pd.date_range(pd.Timestamp(max_old)+pd.Timedelta(days=1),pd.Timestamp(missing_days[-1]),freq="D").strftime("%Y-%m-%d").tolist()
        if expected != missing_days:
            raise SystemExit(f"Backfill is not contiguous after canonical end {max_old}: missing sequence {expected}, supplied {missing_days}")
    merged=old.copy() if not additions else pd.concat([old[COLS],pd.concat(additions,ignore_index=True)[COLS]],ignore_index=True)
    merged["date"]=pd.to_datetime(merged.date,errors="raise").dt.strftime("%Y-%m-%d")
    merged=merged.sort_values(keys,kind="stable")
    if merged.duplicated(keys).any():
        raise SystemExit("Duplicate keys found after merge.")
    tmp_path=CANONICAL.with_suffix(".csv.tmp")
    merged.to_csv(tmp_path,index=False,encoding="utf-8-sig")
    tmp_path.replace(CANONICAL)
    now=pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").isoformat()
    total_new=int(sum(len(x) for x in additions))
    manifest.update({
      "status":"PASS","updated_at_vietnam":now,
      "window_end":max(new_dates),"rows":int(len(merged)),
      "last_draw_import":max(new_dates),
      "last_draw_rows":int(len(new[new.date.astype(str).str[:10]==max(new_dates)])),
      "last_draw_source":"383_supplement_independent_crosscheck",
      "last_draw_verification":"Every station-day in the imported backfill window passed 18-row structure validation and XoSoTin secondary-source comparison; not official issuer certification.",
      "last_backfill_window":{"start":start_day,"end":end_day,"rows":total_new,"station_days":int(new[["date","province"]].drop_duplicates().shape[0]),"status":"PASS"},
      "note":"Daily and missed-date XSMN results are appended in chronological order after independent comparison; missed dates are backfilled automatically."
    })
    overlays=manifest.setdefault("verified_daily_overlays",[])
    for day in new_dates:
        day_frame=new[new.date.astype(str).str[:10]==day]
        rows=int(len(day_frame))
        stations=sorted(day_frame.province.astype(str).unique().tolist())
        overlay_path=Path(f"data/xsmn_daily_verified_{day}.csv")
        overlay_manifest=overlay_path.with_suffix(".json")
        day_frame.to_csv(overlay_path,index=False,encoding="utf-8-sig")
        day_meta={
          "status":"PASS","date":day,"expected_rows":rows,"actual_rows":rows,
          "stations":stations,"station_count":len(stations),
          "verification":"383 supplement structure validated and every station-day matched the independent XoSoTin result page; secondary-source comparison, not official issuer certification.",
          "sources":["https://api.383.im/lottery/region/mn.json",f"https://xosotin.net/ket-qua/xsmn/{pd.Timestamp(day):%d-%m-%Y}.html"],
          "official_issuer_certification":False
        }
        overlay_manifest.write_text(json.dumps(day_meta,ensure_ascii=False,indent=2),encoding="utf-8")
        overlays=[x for x in overlays if x.get("date")!=day]
        overlays.append({"date":day,"file":str(overlay_path),"rows":rows,"stations":len(stations),"status":"PASS","verification":"383 feed and XoSoTin daily page matched; secondary-source evidence, not official issuer certification."})
    manifest["verified_daily_overlays"]=sorted(overlays,key=lambda x:x["date"])
    mt=MANIFEST.with_suffix(".json.tmp")
    mt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    mt.replace(MANIFEST)
    print(json.dumps({"status":"PASS","action":"appended" if total_new else "already_present_exact_match","window_start":start_day,"window_end":end_day,"new_rows":total_new,"total_rows":len(merged),"window_end_canonical":max(new_dates)},ensure_ascii=False,indent=2))
def main():
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group(required=True);g.add_argument("--prepare",action="store_true");g.add_argument("--publish",action="store_true")
    a=p.parse_args()
    prepare() if a.prepare else publish()
if __name__=="__main__": main()
