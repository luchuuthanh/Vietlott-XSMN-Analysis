#!/usr/bin/env python3
"""Consolidate PASS daily XSMN overlays into the canonical five-year history."""
from __future__ import annotations
import json
from urllib.parse import urlparse
from pathlib import Path
import pandas as pd

ROOT=Path("data")
CANONICAL=ROOT/"xsmn_5y_canonical.csv"
MANIFEST=ROOT/"xsmn_5y_canonical.json"
COLS=["date","province","prize","prize_order","number","number_length","last2","last2_numeric","source"]
SCHEDULE={
  0:{"Ca Mau","Dong Thap","TP. HCM"},
  1:{"Bac Lieu","Ben Tre","Vung Tau"},
  2:{"Can Tho","Dong Nai","Soc Trang"},
  3:{"An Giang","Binh Thuan","Tay Ninh"},
  4:{"Binh Duong","Tra Vinh","Vinh Long"},
  5:{"Binh Phuoc","Hau Giang","Long An","TP. HCM"},
  6:{"Da Lat","Kien Giang","Tien Giang"},
}
COUNTS={"ĐB":1,"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
WIDTH={"ĐB":6,"DB":6,"G1":5,"G2":5,"G3":5,"G4":5,"G5":4,"G6":4,"G7":3,"G8":2}
KEYS=["date","province","prize","prize_order"]

def main():
    if not CANONICAL.exists() or not MANIFEST.exists():
        raise SystemExit("Canonical CSV or manifest is missing.")
    old=pd.read_csv(CANONICAL,dtype={"number":str,"last2":str})
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status")!="PASS":
        raise SystemExit("Canonical archive manifest is not PASS.")
    if not set(COLS).issubset(old.columns) or old.duplicated(KEYS).any():
        raise SystemExit("Canonical schema invalid or duplicate keys already exist.")
    canonical_latest=pd.to_datetime(old["date"],errors="raise").max().date().isoformat()
    verified=[]
    for path in sorted(ROOT.glob("xsmn_daily_verified_*.csv")):
        meta_path=path.with_suffix(".json")
        if not meta_path.exists():
            continue
        meta=json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status")!="PASS":
            continue
        day=str(meta.get("date",""))
        if not day or path.stem != f"xsmn_daily_verified_{day}":
            raise SystemExit(f"{path}: manifest date/file mismatch.")
        sources=meta.get("sources",[])
        if len(sources)<2 or meta.get("official_issuer_certification") is True:
            # Legacy overlays already inside the canonical archive do not need to be
            # re-promoted. A missing-evidence overlay beyond the archive must fail closed.
            if day <= canonical_latest:
                continue
            raise SystemExit(f"{day}: source evidence is insufficient or mislabelled.")
        frame=pd.read_csv(path,dtype={"number":str,"last2":str})
        if not set(COLS).issubset(frame.columns) or len(frame)!=meta.get("expected_rows") or len(frame)!=meta.get("actual_rows"):
            raise SystemExit(f"{day}: overlay row count or schema mismatch.")
        frame=frame[COLS].copy()
        frame["date"]=pd.to_datetime(frame["date"],errors="raise").dt.strftime("%Y-%m-%d")
        if set(frame["date"])!={day} or frame.duplicated(KEYS).any():
            raise SystemExit(f"{day}: invalid dates or duplicate prize keys.")
        frame["province"]=frame["province"].astype(str).str.strip()
        frame["prize"]=frame["prize"].astype(str).str.strip().str.upper()
        frame["number"]=frame["number"].astype(str).str.strip()
        frame["prize_order"]=pd.to_numeric(frame["prize_order"],errors="raise").astype(int)
        expected_stations=SCHEDULE[pd.Timestamp(day).weekday()]
        if set(frame["province"])!=expected_stations:
            raise SystemExit(f"{day}: station set mismatch.")
        for station,group in frame.groupby("province"):
            if len(group)!=18:
                raise SystemExit(f"{day} {station}: expected 18 rows, got {len(group)}.")
            group=group.copy()
            group["prize"]=group["prize"].replace({"DB":"ĐB"})
            expected_counts={"ĐB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
            if group["prize"].value_counts().to_dict()!=expected_counts:
                raise SystemExit(f"{day} {station}: prize counts do not match the 18-row structure.")
            for prize,count in expected_counts.items():
                subset=group[group["prize"]==prize]
                if sorted(subset["prize_order"].tolist())!=list(range(1,count+1)):
                    raise SystemExit(f"{day} {station} {prize}: prize_order must be one-based and complete.")
                for number in subset["number"]:
                    if not number.isdigit() or len(number)!=WIDTH[prize]:
                        raise SystemExit(f"{day} {station} {prize}: invalid number {number!r}.")
        frame["number_length"]=frame["number"].str.len().astype(int)
        frame["last2"]=frame["number"].str[-2:].str.zfill(2)
        frame["last2_numeric"]=pd.to_numeric(frame["last2"],errors="raise").astype(int)
        if frame["source"].isna().any():
            raise SystemExit(f"{day}: source attribution missing.")
        verified.append((day,frame,meta))
    if not verified:
        print(json.dumps({"status":"NO_VERIFIED_OVERLAYS","rows_added":0},ensure_ascii=False))
        return
    verified.sort(key=lambda x:x[0])
    additions=[]
    imported=[]
    for day,frame,meta in verified:
        existing=old[old["date"].astype(str).str[:10]==day]
        if existing.empty:
            additions.append(frame)
            imported.append((day,frame,meta))
        else:
            left=existing[COLS].copy()
            right=frame[COLS].copy()
            left["prize"]=left["prize"].astype(str).str.upper()
            right["prize"]=right["prize"].astype(str).str.upper()
            left=left.sort_values(KEYS).reset_index(drop=True)
            right=right.sort_values(KEYS).reset_index(drop=True)
            # Source labels and derived numeric columns may differ between
            # independent ingestion paths. Never overwrite historical rows:
            # require the prize keys and the exact zero-padded winning numbers
            # to match before treating an existing day as already integrated.
            compare_cols=KEYS+["number"]
            left["number"]=left["number"].astype(str).str.strip()
            right["number"]=right["number"].astype(str).str.strip()
            if not left[compare_cols].equals(right[compare_cols]):
                diff=left[compare_cols].merge(right[compare_cols],on=KEYS,
                    how="outer",suffixes=("_canonical","_overlay"),indicator=True)
                mismatch=diff[(diff["_merge"]!="both") |
                              (diff["number_canonical"]!=diff["number_overlay"])]
                raise SystemExit(f"{day}: {len(mismatch)} prize-key/number mismatches; refusing overwrite. Sample: {mismatch.head(3).to_dict('records')}")
            print(f"{day}: existing prize keys and winning numbers match; source metadata may differ.")
    # Even when every winning number is already present, refresh the manifest\n    # with the independently verified evidence instead of returning early.\n    if additions:
        max_old=pd.to_datetime(old["date"],errors="raise").max().date()
        new_days=sorted(x[0] for x in imported)
        expected=pd.date_range(pd.Timestamp(max_old)+pd.Timedelta(days=1),pd.Timestamp(new_days[-1]),freq="D").strftime("%Y-%m-%d").tolist()
        if expected!=new_days:
            raise SystemExit(f"Non-contiguous history gap: expected {expected}, supplied {new_days}.")
        merged=pd.concat([old[COLS],pd.concat(additions,ignore_index=True)[COLS]],ignore_index=True)
    else:
        merged=old[COLS].copy()
    merged["date"]=pd.to_datetime(merged["date"],errors="raise").dt.strftime("%Y-%m-%d")
    merged=merged.sort_values(KEYS,kind="stable")
    if merged.duplicated(KEYS).any():
        raise SystemExit("Duplicate keys detected after overlay consolidation.")
    tmp=CANONICAL.with_suffix(".csv.tmp")
    merged.to_csv(tmp,index=False,encoding="utf-8-sig")
    tmp.replace(CANONICAL)
    now=pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").isoformat()
    latest=max(x[0] for x in verified)
    latest_frame=next(x[1] for x in verified if x[0]==latest)
    overlays=manifest.setdefault("verified_daily_overlays",[])
    integrated=manifest.setdefault("integrated_daily_updates",[])
    for day,frame,meta in verified:
        item={"date":day,"file":f"data/xsmn_daily_verified_{day}.csv","rows":len(frame),
              "stations":frame["province"].nunique(),"status":"PASS",
              "verification":meta.get("verification","Multiple published sources cross-checked; not official issuer certification.")}
        overlays=[x for x in overlays if x.get("date")!=day]+[item]
        integrated=[x for x in integrated if x.get("date")!=day]+[{"date":day,"rows":len(frame),"stations":frame["province"].nunique(),"status":"PASS"}]
    manifest.update({
      "status":"PASS","updated_at_vietnam":now,"window_end":max(pd.to_datetime(merged["date"]).dt.strftime("%Y-%m-%d")),
      "rows":int(len(merged)),"last_draw_import":latest,"last_draw_rows":int(len(latest_frame)),
      "last_draw_source":"manual_multi_source_verified",
      "last_draw_source_ids":[urlparse(u).netloc for u in next(x[2]["sources"] for x in verified if x[0]==latest)],
      "last_draw_verification":next(x[2].get("verification","") for x in verified if x[0]==latest),
      "verified_daily_overlays":sorted(overlays,key=lambda x:x["date"]),
      "integrated_daily_updates":sorted(integrated,key=lambda x:x["date"]),
      "history_overlay_note":"Tất cả các ngày PASS đã được hợp nhất trực tiếp vào canonical CSV; tệp daily verified được giữ làm bằng chứng đối chiếu.",
      "last_history_sync":{"checked_at_vietnam":now,"status":"PASS","dates_checked":[x[0] for x in verified],
                           "new_rows_added":int(sum(len(x[1]) for x in imported)),
                           "canonical_rows":int(len(merged)),"duplicate_keys":0}
    })
    mt=MANIFEST.with_suffix(".json.tmp")
    mt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    mt.replace(MANIFEST)
    print(json.dumps({"status":"PASS","dates_checked":[x[0] for x in verified],
                      "dates_appended":[x[0] for x in imported],
                      "rows_added":int(sum(len(x[1]) for x in imported)),
                      "canonical_rows":int(len(merged)),"window_end":manifest["window_end"],
                      "duplicate_keys":0},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
