#!/usr/bin/env python3
"""Archive a completed XSMN draw from the live publisher, not from 383.

Fail closed: the independently parsed XoSoTin page must match all 18
zero-padded prize numbers per station before any PASS overlay is written.
383 is not consulted or required by this primary pipeline.
"""
import csv, json, sys, re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from bs4 import BeautifulSoup
from xsmn_live import fetch_live_xsmn, normalize_station_key
from scripts.verify_xsmn_supplement_sources_v2 import parse_daily

COUNTS={"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
WIDTH={"DB":6,"G1":5,"G2":5,"G3":5,"G4":5,"G5":4,"G6":4,"G7":3,"G8":2}
STATION={"vinhlong":"Vinh Long","binhduong":"Binh Duong","travinh":"Tra Vinh","camau":"Ca Mau","dongthap":"Dong Thap","tphcm":"TP. HCM","baclieu":"Bac Lieu","bentre":"Ben Tre","vungtau":"Vung Tau","cantho":"Can Tho","dongnai":"Dong Nai","soctrang":"Soc Trang","angiang":"An Giang","binhthuan":"Binh Thuan","tayninh":"Tay Ninh","binhphuoc":"Binh Phuoc","haugiang":"Hau Giang","longan":"Long An","dalat":"Da Lat","kiengiang":"Kien Giang","tiengiang":"Tien Giang"}
SCHEDULE={0:{"camau","dongthap","tphcm"},1:{"baclieu","bentre","vungtau"},2:{"cantho","dongnai","soctrang"},3:{"angiang","binhthuan","tayninh"},4:{"vinhlong","binhduong","travinh"},5:{"binhphuoc","haugiang","longan","tphcm"},6:{"dalat","kiengiang","tiengiang"}}
FIELDS=["date","province","prize","prize_order","number","number_length","last2","last2_numeric","source"]

def main():
    frame,primary_url=fetch_live_xsmn()
    dates=sorted(set(frame.date.astype(str).str[:10]))
    if len(dates)!=1:raise RuntimeError("Primary returned multiple draw dates")
    day=dates[0]
    now=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    if day!=now:raise RuntimeError(f"Primary draw date {day} is not today {now}")
    expected=SCHEDULE[datetime.fromisoformat(day).weekday()]
    groups=defaultdict(lambda:defaultdict(list))
    for r in frame.itertuples(index=False):
        key=normalize_station_key(r.province)
        p="DB" if r.prize in ("ĐB","DB") else r.prize
        groups[key][p].append(str(r.number))
    if set(groups)!=expected:raise RuntimeError(f"Station set differs: {set(groups)}")
    # XoSoTin was repeatedly returning HTTP 522. Use Minh Ngoc as the
    # independent source, with kqsx.vn as an alternative publisher.
    sources=[
        f"https://www.minhngoc.net.vn/kqxs/mien-nam/{datetime.fromisoformat(day):%d-%m-%Y}.html",
        f"https://kqsx.vn/ket-qua-ngay/xsmn-{day}",
    ]
    def parse_minhngoc(content):
        soup=BeautifulSoup(content,"html.parser")
        text=soup.get_text(" ",strip=True)
        out={}
        for st in expected:
            label=STATION[st]
            # The site prints one complete station section, followed by the next.
            pattern=r"KẾT QUẢ XỔ SỐ\\s+"+re.escape(label)+r"\\s*-\\s*"+datetime.fromisoformat(day).strftime("%d/%m/%Y")
            match=re.search(pattern,text,re.I)
            if not match:continue
            section=text[match.end():]
            next_station=re.search(r"KẾT QUẢ XỔ SỐ\\s+[^\\n]{2,70}?\\s*-\\s*\\d{2}/\\d{2}/\\d{4}",section,re.I)
            if next_station:section=section[:next_station.start()]
            prizes={}
            labels=[("DB",r"Giải\\s*(?:ĐB|đặc biệt)"),("G1",r"Giải\\s*(?:nhất|1)"),("G2",r"Giải\\s*(?:nhì|2)"),("G3",r"Giải\\s*(?:ba|3)"),("G4",r"Giải\\s*(?:tư|4)"),("G5",r"Giải\\s*(?:năm|5)"),("G6",r"Giải\\s*(?:sáu|6)"),("G7",r"Giải\\s*(?:bảy|7)"),("G8",r"Giải\\s*(?:8|tám)")]
            spans=[]
            for p,pat in labels:
                m=re.search(pat,section,re.I)
                if m:spans.append((m.start(),m.end(),p))
            spans.sort()
            for i,(_,endpos,p) in enumerate(spans):
                fragment=section[endpos:spans[i+1][0] if i+1<len(spans) else len(section)]
                nums=re.findall(r"(?<!\\d)\\d{2,6}(?!\\d)",fragment)
                if len(nums)==COUNTS[p] and all(len(n)==WIDTH[p] for n in nums):prizes[p]=nums
            if all(len(prizes.get(p,[]))==n for p,n in COUNTS.items()):out[st]=prizes
        return out
    independent={};secondary_url=None;errors=[]
    for url in sources:
        try:
            resp=requests.get(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"vi-VN,vi;q=0.9"},timeout=25)
            resp.raise_for_status()
            parsed=parse_daily(resp.content)
            candidate={normalize_station_key(k):v for k,v in parsed.items()}
            if set(candidate)!=expected and "minhngoc.net.vn" in url:
                candidate=parse_minhngoc(resp.content)
            if set(candidate)==expected:
                independent=candidate;secondary_url=url;break
            errors.append(f"{url}: incomplete station/prize parse {list(candidate)}")
        except Exception as exc:errors.append(f"{url}: {exc}")
    if secondary_url is None:raise RuntimeError("Independent sources unavailable: "+"; ".join(errors))
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
                    "last2_numeric":int(n[-2:]),"source":"sxmn_xosotin_crosscheck"})
    expected_rows=18*len(expected)
    if len(rows)!=expected_rows:raise RuntimeError(f"Expected {expected_rows} rows, got {len(rows)}")
    csv_path=Path(f"data/xsmn_daily_verified_{day}.csv")
    meta_path=csv_path.with_suffix(".json")
    # Write only after both sources have matched every result.
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
