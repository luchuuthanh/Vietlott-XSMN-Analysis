#!/usr/bin/env python3
"""Archive a completed XSMN draw from the live publisher, not from 383.

Fail closed: an independently parsed publisher page must match all 18
zero-padded prize numbers per station before any PASS overlay is written.
383 is not consulted or required by this primary pipeline.
"""
import csv, json, sys, os
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from xsmn_live import fetch_live_xsmn, normalize_station_key
from scripts.verify_xsmn_supplement_sources_v2 import parse_daily

COUNTS={"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
WIDTH={"DB":6,"G1":5,"G2":5,"G3":5,"G4":5,"G5":4,"G6":4,"G7":3,"G8":2}
STATION={"vinhlong":"Vinh Long","binhduong":"Binh Duong","travinh":"Tra Vinh","camau":"Ca Mau","dongthap":"Dong Thap","tphcm":"TP. HCM","baclieu":"Bac Lieu","bentre":"Ben Tre","vungtau":"Vung Tau","cantho":"Can Tho","dongnai":"Dong Nai","soctrang":"Soc Trang","angiang":"An Giang","binhthuan":"Binh Thuan","tayninh":"Tay Ninh","binhphuoc":"Binh Phuoc","haugiang":"Hau Giang","longan":"Long An","dalat":"Da Lat","kiengiang":"Kien Giang","tiengiang":"Tien Giang"}
SCHEDULE={0:{"camau","dongthap","tphcm"},1:{"baclieu","bentre","vungtau"},2:{"cantho","dongnai","soctrang"},3:{"angiang","binhthuan","tayninh"},4:{"vinhlong","binhduong","travinh"},5:{"binhphuoc","haugiang","longan","tphcm"},6:{"dalat","kiengiang","tiengiang"}}
FIELDS=["date","province","prize","prize_order","number","number_length","last2","last2_numeric","source"]

def main():
    now=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    day=os.environ.get("XSMN_TARGET_DATE",now)
    if date.fromisoformat(day)>date.fromisoformat(now):raise RuntimeError("Cannot archive a future draw")
    frame=None;primary_url=None
    if day==now:
        try:
            candidate,url=fetch_live_xsmn()
            if set(candidate.date.astype(str).str[:10])=={day}:
                frame,primary_url=candidate,url
        except Exception as exc:
            print(f"Live publisher unavailable: {exc}; trying independent published archives",file=sys.stderr)
    expected=SCHEDULE[datetime.fromisoformat(day).weekday()]
    groups=defaultdict(lambda:defaultdict(list))
    if frame is not None:
        for r in frame.itertuples(index=False):
            key=normalize_station_key(r.province)
            p="DB" if r.prize in ("ĐB","DB") else r.prize
            groups[key][p].append(str(r.number))
        if set(groups)!=expected:raise RuntimeError(f"Station set differs: {set(groups)}")
    # Independent fallback publishers. Minh Ngoc intentionally excluded.
    # Validate every station, prize count and exact zero-padded value before writing.
    sources=[
        f"https://xskt.net/xsmn/{datetime.fromisoformat(day):%d-%m-%Y}",
        f"https://kqsx.vn/ket-qua-ngay/xsmn-{datetime.fromisoformat(day):%d-%m-%Y}",
    ]
    independent={};secondary_url=None;errors=[];parsed_sources=[]
    for url in sources:
        try:
            resp=requests.get(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"vi-VN,vi;q=0.9"},timeout=25)
            resp.raise_for_status()
            parsed=parse_daily(resp.content)
            candidate={normalize_station_key(k):v for k,v in parsed.items()}
            if set(candidate)==expected and all(all(len(candidate[st].get(p,[]))==count and all(n.isdigit() and len(n)==WIDTH[p] for n in candidate[st][p]) for p,count in COUNTS.items()) for st in expected):
                parsed_sources.append((url,candidate))
            else:errors.append(f"{url}: incomplete station/prize parse {list(candidate)}")
        except Exception as exc:errors.append(f"{url}: {exc}")
    if frame is not None:
        if not parsed_sources:raise RuntimeError("Independent sources unavailable: "+"; ".join(errors))
        secondary_url,independent=parsed_sources[0]
    else:
        if len(parsed_sources)<2:raise RuntimeError("Need two complete independent sources for backfill/fallback: "+"; ".join(errors))
        primary_url,groups=parsed_sources[0]
        secondary_url,independent=parsed_sources[1]
        for st in expected:
            for p in COUNTS:
                groups[st][p]=list(groups[st][p])
    rows=[]
    for st in sorted(expected):
        for prize,count in COUNTS.items():
            primary=groups[st].get(prize,[])
            secondary=independent[st].get(prize,[])
            if len(primary)!=count or len(secondary)!=count or sorted(primary)!=sorted(secondary):
                raise RuntimeError(f"Independent mismatch {day} {st} {prize}: primary={primary}, secondary={secondary}")
            if any(not n.isdigit() or len(n)!=WIDTH[prize] for n in primary):
                raise RuntimeError(f"Invalid number width {st} {prize}")
            for i,n in enumerate(primary,1):
                rows.append({"date":day,"province":STATION[st],"prize":"ĐB" if prize=="DB" else prize,"prize_order":i,
                    "number":n,"number_length":len(n),"last2":n[-2:],
                    "last2_numeric":int(n[-2:]),"source":"sxmn_independent_crosscheck"})
    expected_rows=18*len(expected)
    if len(rows)!=expected_rows:raise RuntimeError(f"Expected {expected_rows} rows, got {len(rows)}")
    csv_path=Path(f"data/xsmn_daily_verified_{day}.csv")
    meta_path=csv_path.with_suffix(".json")
    # Write only after the primary and independent source match every result.
    with csv_path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    metadata={"status":"PASS","date":day,"expected_rows":expected_rows,"actual_rows":expected_rows,
        "stations":sorted(STATION[k] for k in expected),"station_count":len(expected),
        "sources":[primary_url,secondary_url],"source_count":2,
        "verification":"All winning numbers matched two independent publisher pages; no official issuer certification.",
        "official_issuer_certification":False}
    meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","date":day,"rows":len(rows),"sources":metadata["sources"]},ensure_ascii=False))

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(f"PRIMARY_SOURCE_VERIFICATION_FAILED: {exc}",file=sys.stderr)
        sys.exit(1)
