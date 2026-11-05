#!/usr/bin/env python3
"""Compare 383.im supplement with XoSoTin daily pages (secondary source only)."""
import argparse,csv,json,re,sys,time,unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
import requests
from bs4 import BeautifulSoup
COUNTS={"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
LENGTHS={"DB":6,"G1":5,"G2":5,"G3":5,"G4":5,"G5":4,"G6":4,"G7":3,"G8":2}
STATIONS={"angiang":"An Giang","baclieu":"Bac Lieu","bentre":"Ben Tre","binhduong":"Binh Duong","binhphuoc":"Binh Phuoc","binhthuan":"Binh Thuan","camau":"Ca Mau","cantho":"Can Tho","dongnai":"Dong Nai","dongthap":"Dong Thap","dalat":"Da Lat","lamdong":"Da Lat","haugiang":"Hau Giang","kiengiang":"Kien Giang","longan":"Long An","soctrang":"Soc Trang","tayninh":"Tay Ninh","tiengiang":"Tien Giang","tphcm":"TP. HCM","hochiminh":"TP. HCM","thanhphohochiminh":"TP. HCM","travinh":"Tra Vinh","vinhlong":"Vinh Long","vungtau":"Vung Tau"}
NUM=re.compile(r"(?<!\d)\d{2,6}(?!\d)")
def norm(s):
 s=unicodedata.normalize("NFD",s or "");s="".join(c for c in s if unicodedata.category(c)!="Mn").replace("đ","d").replace("Đ","D");return re.sub(r"[^a-z0-9]","",s.lower())
def station(s):
 k=norm(s)
 for a,b in sorted(STATIONS.items(),key=lambda x:-len(x[0])):
  if a in k:return b
def prize(s):
 s=norm(s)
 if s in ("db","dacbiet","giaidacbiet"):return "DB"
 m=re.search(r"(?:g|giai)([1-8])",s);return "G"+m.group(1) if m else None
def cells(row):
 c=row.find_all(["th","td"],recursive=True);return c or row.find_all(attrs={"role":"cell"},recursive=True)
def parse_daily(html):
 soup=BeautifulSoup(html,"html.parser");groups=[]
 for t in soup.find_all("table"):
  r=t.find_all("tr")
  if r:groups.append(r)
 rr=soup.find_all(attrs={"role":"row"})
 if rr:groups.append(rr)
 for rows in groups:
  for hi,row in enumerate(rows):
   h=cells(row)
   if len(h)<4:continue
   names=[station(c.get_text(" ",strip=True)) for c in h[1:]]
   if any(x is None for x in names) or len(set(names))!=len(names):continue
   out={s:defaultdict(list) for s in names}
   for r in rows[hi+1:]:
    cs=cells(r)
    if len(cs)<len(names)+1:continue
    p=prize(cs[0].get_text(" ",strip=True))
    if p:
     for i,s in enumerate(names,1):out[s][p].extend(NUM.findall(cs[i].get_text(" ",strip=True)))
   if all(all(len(out[s].get(p,[]))==n for p,n in COUNTS.items()) for s in names):return out
 return {}
def load(path,start,end):
 out=defaultdict(lambda:defaultdict(list))
 with open(path,encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):
   if r.get("source")=="383_supplement" and start<=r["date"][:10]<=end:out[(r["date"][:10],r["province"].strip())][r["prize"].upper()].append(str(r["number"]).strip())
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--csv",required=True);ap.add_argument("--out",required=True);ap.add_argument("--start",default="2026-07-01");ap.add_argument("--end",default="2026-11-05");ap.add_argument("--delay",type=float,default=.25);a=ap.parse_args()
 exp=load(a.csv,a.start,a.end);s=requests.Session();s.headers.update({"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36","Accept-Language":"vi-VN,vi;q=0.9,en;q=0.8"})
 obs={};errors=[];dates=sorted({k[0] for k in exp})
 for d in dates:
  u=f"https://xosotin.net/ket-qua/xsmn/{date.fromisoformat(d):%d-%m-%Y}.html"
  try:
   r=s.get(u,timeout=20);r.raise_for_status();p=parse_daily(r.text)
   if p:
    for st,pr in p.items():obs[(d,st)]=pr
   else:
    so=BeautifulSoup(r.text,"html.parser");errors.append({"date":d,"url":r.url,"error":"result grid not parsed","http_status":r.status_code,"html_bytes":len(r.content),"table_count":len(so.find_all("table")),"row_count":len(so.find_all("tr")),"role_row_count":len(so.find_all(attrs={"role":"row"})),"title":so.title.get_text(" ",strip=True) if so.title else ""})
  except Exception as e:errors.append({"date":d,"url":u,"error":str(e)})
  time.sleep(a.delay)
 details=[];matched=badpairs=missing=wrong=compared=matchnums=0
 for key,pr in sorted(exp.items()):
  src=obs.get(key)
  if src is None:missing+=1;details.append([*key,"SOURCE_MISSING","","",""]);continue
  compared+=1;bad=False
  for p,n in COUNTS.items():
   x=sorted(pr.get(p,[]));y=sorted(src.get(p,[]));valid=len(x)==n and all(v.isdigit() and len(v)==LENGTHS[p] for v in x)
   if len(x)!=n or len(y)!=n or x!=y or not valid:
    bad=True
    if len(x)!=n or len(y)!=n:wrong+=1
    details.append([*key,"MISMATCH",p,"|".join(x),"|".join(y)])
   else:matchnums+=n
  if bad:badpairs+=1
  else:matched+=1;details.append([*key,"MATCH","","",""])
 Path(a.out).parent.mkdir(parents=True,exist_ok=True)
 with open(a.out,"w",encoding="utf-8-sig",newline="") as f:
  w=csv.writer(f);w.writerow(["date","province","status","prize","supplement_numbers","independent_numbers"]);w.writerows(details)
 report={"source":"XoSoTin daily pages (secondary source)","window_start":a.start,"window_end":a.end,"expected_station_days":len(exp),"dates_requested":len(dates),"station_days_parsed":len(obs),"station_days_compared":compared,"station_days_match":matched,"station_days_with_mismatch":badpairs,"station_days_missing_from_source":missing,"prize_count_mismatches":wrong,"matching_numbers":matchnums,"expected_numbers":sum(sum(COUNTS.values()) for _ in exp),"source_errors":errors,"status":"PASS" if not errors and compared==len(exp) and matched==len(exp) and not wrong else "INCOMPLETE_OR_MISMATCH","caveat":"Secondary-source comparison only; not official issuer certification."}
 Path(a.out).with_suffix(".json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(report,ensure_ascii=False,indent=2))
 if report["status"]!="PASS":sys.exit(1)
if __name__=="__main__":main()
