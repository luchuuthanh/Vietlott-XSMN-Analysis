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
        raise SystemExit("Missing daily supplement or validation report.")
    report=json.loads(VALIDATION.read_text(encoding="utf-8"))
    today=pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").date()
    day=today.isoformat()
    if report.get("status") not in ("PASS",) or report.get("window_start") != day or report.get("window_end") != day:
        raise SystemExit(f"383 feed is not validated for today {day}: {report.get('status')} {report.get('window_end')}")
    df=pd.read_csv(SUPPLEMENT,dtype={"number":str})
    if df.empty or set(df.columns) < {"date","province","prize","prize_order","number"}:
        raise SystemExit("Daily supplement is empty or has an invalid schema.")
    df["date"]=pd.to_datetime(df["date"],errors="raise").dt.strftime("%Y-%m-%d")
    df["province"]=df["province"].astype(str).str.strip()
    df["prize"]=df["prize"].astype(str).str.strip().str.upper()
    df["number"]=df["number"].astype(str).str.strip()
    if set(df.date)!={day}: raise SystemExit(f"Unexpected dates in feed: {sorted(df.date.unique())}")
    expected=SCHEDULE[today.weekday()]
    if set(df.province)!=expected: raise SystemExit(f"Station set mismatch: expected={sorted(expected)}, actual={sorted(df.province.unique())}")
    if df.duplicated(["date","province","prize","prize_order"]).any(): raise SystemExit("Duplicate daily prize rows.")
    for station,g in df.groupby("province"):
        counts=g.prize.value_counts().to_dict()
        if counts != COUNTS or len(g)!=18: raise SystemExit(f"{station}: prize structure is not exactly 18 rows: {counts}")
        for _,r in g.iterrows():
            if r.prize not in LENGTHS or not r.number.isdigit() or len(r.number)!=LENGTHS[r.prize]:
                raise SystemExit(f"Invalid result number: {r.to_dict()}")
    df["number_length"]=df.number.str.len().astype(int)
    df["last2"]=df.number.str[-2:].str.zfill(2)
    df["last2_numeric"]=pd.to_numeric(df.last2,errors="raise").astype(int)
    df["source"]="383_supplement"
    df=df[COLS].sort_values(["date","province","prize","prize_order"],kind="stable")
    PREPARED.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(PREPARED,index=False,encoding="utf-8-sig")
    print(json.dumps({"status":"PREPARED","date":day,"stations":len(expected),"rows":len(df)},ensure_ascii=False))
def publish():
    for p in (CANONICAL,MANIFEST,PREPARED,CHECK):
        if not p.exists(): raise SystemExit(f"Missing required input: {p}")
    check=json.loads(CHECK.read_text(encoding="utf-8"))
    today=pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").date().isoformat()
    if check.get("status")!="PASS" or check.get("window_start")!=today or check.get("window_end")!=today:
        raise SystemExit("Independent source comparison did not PASS for today's draw.")
    old=pd.read_csv(CANONICAL,dtype={"number":str,"last2":str})
    new=pd.read_csv(PREPARED,dtype={"number":str,"last2":str})
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status")!="PASS": raise SystemExit("Canonical manifest is not PASS.")
    if not set(COLS).issubset(old.columns) or not set(COLS).issubset(new.columns):
        raise SystemExit("Canonical/daily schema mismatch.")
    keys=["date","province","prize","prize_order"]
    if new.empty or len(new)!=len(new[["date","province"]].drop_duplicates())*18:
        # The expected 18 rows per station are independently checked again.
        for _,g in new.groupby(["date","province"]):
            if len(g)!=18: raise SystemExit("Daily file does not contain 18 rows per station.")
    if new.duplicated(keys).any() or old.duplicated(keys).any(): raise SystemExit("Duplicate keys detected.")
    existing=old[old.date.astype(str).str[:10]==today]
    if len(existing):
        cmp=existing[keys+["number"]].merge(new[keys+["number"]],on=keys,how="outer",suffixes=("_old","_new"),indicator=True)
        if len(existing)!=len(new) or not (cmp._merge=="both").all() or not (cmp.number_old==cmp.number_new).all():
            raise SystemExit("Today's date already exists but is partial or conflicting; no overwrite.")
        merged=old.copy()
        action="already_present_exact_match"
    else:
        max_day=pd.to_datetime(old.date,errors="raise").max().date().isoformat()
        if max_day >= today: raise SystemExit(f"Canonical ends at {max_day}; refusing out-of-order append.")
        merged=pd.concat([old[COLS],new[COLS]],ignore_index=True)
        action="appended"
    merged["date"]=pd.to_datetime(merged.date,errors="raise").dt.strftime("%Y-%m-%d")
    merged=merged.sort_values(keys,kind="stable")
    tmp=CANONICAL.with_suffix(".csv.tmp")
    tmp.parent.mkdir(parents=True,exist_ok=True)
    tmp.to_csv(tmp,index=False,encoding="utf-8-sig")
    tmp.replace(CANONICAL)
    manifest.update({
      "status":"PASS","updated_at_vietnam":pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").isoformat(),
      "window_end":today,"rows":int(len(merged)),"last_draw_import":today,
      "last_draw_rows":int(len(new)),"last_draw_source":"383_supplement_independent_crosscheck",
      "last_draw_verification":"Today's 18-result structure per station validated; XoSoTin independent daily-page comparison PASS.",
      "note":"Daily draw appended independently of the scheduled five-year archive audit."
    })
    mt=MANIFEST.with_suffix(".json.tmp")
    mt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    mt.replace(MANIFEST)
    print(json.dumps({"status":"PASS","action":action,"date":today,"new_rows":len(new),"total_rows":len(merged),"window_end":today},ensure_ascii=False,indent=2))
def main():
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group(required=True);g.add_argument("--prepare",action="store_true");g.add_argument("--publish",action="store_true")
    a=p.parse_args()
    prepare() if a.prepare else publish()
if __name__=="__main__": main()
