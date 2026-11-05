#!/usr/bin/env python3
"""Independent row-level comparison of the 383.im supplement with XoSoTin daily XSMN pages.

XoSoTin publishes a dedicated daily page with all stations and all nine prize tiers.
This is a secondary source cross-check, not official issuer certification.
"""
import argparse, csv, json, re, sys, time, unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
import requests
from bs4 import BeautifulSoup

COUNTS={"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
LENGTHS={"DB":6,"G1":5,"G2":5,"G3":5,"G4":5,"G5":4,"G6":4,"G7":3,"G8":2}
STATIONS={
"angiang":"An Giang","baclieu":"Bac Lieu","bentre":"Ben Tre","binhduong":"Binh Duong",
"binhphuoc":"Binh Phuoc","binhthuan":"Binh Thuan","camau":"Ca Mau","cantho":"Can Tho",
"dongnai":"Dong Nai","dongthap":"Dong Thap","dalat":"Da Lat","lamdong":"Da Lat",
"haugiang":"Hau Giang","kiengiang":"Kien Giang","longan":"Long An","soctrang":"Soc Trang",
"tayninh":"Tay Ninh","tiengiang":"Tien Giang","tphcm":"TP. HCM","hochiminh":"TP. HCM",
"thanhphohochiminh":"TP. HCM","travinh":"Tra Vinh","vinhlong":"Vinh Long","vungtau":"Vung Tau"}
NUM=re.compile(r"(?<!\d)\d{2,6}(?!\d)")

def norm(s):
    s=unicodedata.normalize("NFD",s or "")
    s="".join(c for c in s if unicodedata.category(c)!="Mn").replace("đ","d").replace("Đ","D")
    return re.sub(r"[^a-z0-9]","",s.lower())

def map_station(label):
    k=norm(label)
    for key,value in sorted(STATIONS.items(),key=lambda x:-len(x[0])):
        if key in k: return value
    return None

def prize_code(label):
    s=norm(label)
    if s in ("db","dacbiet","giaidacbiet"): return "DB"
    m=re.search(r"g(?:iai)?([1-8])",s)
    return "G"+m.group(1) if m else None

def parse_daily(html, draw_date):
    soup=BeautifulSoup(html,"html.parser")
    for table in soup.find_all("table"):
        trs=table.find_all("tr")
        if len(trs)<10: continue
        head=trs[0].find_all(["th","td"],recursive=False)
        if len(head)<4: continue
        station_names=[map_station(c.get_text(" ",strip=True)) for c in head[1:]]
        if any(x is None for x in station_names) or len(set(station_names))!=len(station_names): continue
        result={s:defaultdict(list) for s in station_names}
        for tr in trs[1:]:
            cells=tr.find_all(["th","td"],recursive=False)
            if len(cells)<len(station_names)+1: continue
            p=prize_code(cells[0].get_text(" ",strip=True))
            if not p: continue
            for idx,s in enumerate(station_names,1):
                result[s][p].extend(NUM.findall(cells[idx].get_text(" ",strip=True)))
        if all(all(len(result[s].get(p,[]))==n for p,n in COUNTS.items()) for s in station_names):
            return result
    return {}

def load_expected(path,start,end):
    exp=defaultdict(lambda:defaultdict(list))
    with open(path,encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("source")!="383_supplement": continue
            d=r["date"][:10]
            if not start<=d<=end: continue
            exp[(d,r["province"].strip())][r["prize"].upper()].append(str(r["number"]).strip())
    return exp

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--start",default="2026-07-01"); ap.add_argument("--end",default="2026-11-05")
    ap.add_argument("--delay",type=float,default=0.25)
    a=ap.parse_args()
    expected=load_expected(a.csv,a.start,a.end)
    session=requests.Session()
    session.headers.update({"User-Agent":"Mozilla/5.0 (compatible; XSMN-independent-audit/1.0)","Accept-Language":"vi,en;q=0.8"})
    observed={}; errors=[]
    dates=sorted({k[0] for k in expected})
    for d in dates:
        dt=date.fromisoformat(d); url=f"https://xosotin.net/ket-qua/xsmn/{dt:%d-%m-%Y}.html"
        try:
            res=session.get(url,timeout=35); res.raise_for_status()
            parsed=parse_daily(res.text,d)
            if not parsed:
                soup=BeautifulSoup(res.text,"html.parser")
                errors.append({"date":d,"url":res.url,"error":"result table not parsed","http_status":res.status_code,
                               "page_title":soup.title.get_text(" ",strip=True) if soup.title else ""})
            else:
                for station,prizes in parsed.items(): observed[(d,station)]=prizes
        except Exception as e: errors.append({"date":d,"url":url,"error":str(e)})
        time.sleep(a.delay)
    details=[]; compared=matched=pair_mismatch=missing=wrong_count=0; matching_numbers=0
    for key,prizes in sorted(expected.items()):
        src=observed.get(key)
        if src is None:
            missing+=1; details.append([key[0],key[1],"SOURCE_MISSING","","",""]); continue
        compared+=1; bad=False
        for p,n in COUNTS.items():
            x=sorted(prizes.get(p,[])); y=sorted(src.get(p,[]))
            valid=(len(x)==n and all(len(v)==LENGTHS[p] and v.isdigit() for v in x))
            if len(x)!=n or len(y)!=n or x!=y or not valid:
                bad=True
                if len(x)!=n or len(y)!=n: wrong_count+=1
                details.append([key[0],key[1],"MISMATCH",p,"|".join(x),"|".join(y)])
            else:
                matching_numbers+=n
        if bad: pair_mismatch+=1
        else:
            matched+=1
            details.append([key[0],key[1],"MATCH","","",""])
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f); w.writerow(["date","province","status","prize","supplement_numbers","independent_numbers"]); w.writerows(details)
    report={"source":"XoSoTin daily XSMN pages (secondary source)","source_base":"https://xosotin.net/ket-qua/xsmn/DD-MM-YYYY.html",
    "window_start":a.start,"window_end":a.end,"expected_station_days":len(expected),"dates_requested":len(dates),
    "station_days_parsed":len(observed),"station_days_compared":compared,"station_days_match":matched,
    "station_days_with_mismatch":pair_mismatch,"station_days_missing_from_source":missing,
    "prize_count_mismatches":wrong_count,"matching_numbers":matching_numbers,
    "expected_numbers":sum(sum(COUNTS.values()) for _ in expected),"source_errors":errors,
    "status":"PASS" if not errors and compared==len(expected) and matched==len(expected) and not wrong_count else "INCOMPLETE_OR_MISMATCH",
    "caveat":"Secondary-source comparison only; not official issuer certification. Preserve source provenance and do not silently replace discrepant numbers."}
    Path(a.out).with_suffix(".json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report["status"]!="PASS": sys.exit(1)
if __name__=="__main__": main()
