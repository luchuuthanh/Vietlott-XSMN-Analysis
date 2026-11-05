import argparse, csv, json, re, sys, time, unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
import requests
from bs4 import BeautifulSoup

COUNTS = {"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1,"G8":1}
PAGES = ["2026-07","2026-08","2026-09","2026-10","2026-11"]
NUM = re.compile(r"(?<!\d)\d{2,6}(?!\d)")
DRE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](20\d{2})")

def clean(s):
    s=unicodedata.normalize("NFD",s or "")
    s="".join(c for c in s if unicodedata.category(c)!="Mn").replace("đ","d").replace("Đ","D")
    return re.sub(r"[^a-z0-9]","",s.lower())

def station(s):
    k=clean(s)
    aliases={"tphcm":"TP. HCM","hcm":"TP. HCM","hochiminh":"TP. HCM","thanhphohochiminh":"TP. HCM",
    "dalat":"Da Lat","angiang":"An Giang","baclieu":"Bac Lieu","bentre":"Ben Tre",
    "binhduong":"Binh Duong","binhphuoc":"Binh Phuoc","binhthuan":"Binh Thuan","camau":"Ca Mau",
    "cantho":"Can Tho","dongnai":"Dong Nai","dongthap":"Dong Thap","haugiang":"Hau Giang",
    "kiengiang":"Kien Giang","longan":"Long An","soctrang":"Soc Trang","tayninh":"Tay Ninh",
    "tiengiang":"Tien Giang","travinh":"Tra Vinh","vinhlong":"Vinh Long","vungtau":"Vung Tau"}
    return aliases.get(k,s.strip())

def getdate(s):
    m=DRE.search(s or "")
    if not m:return None
    d,mo,y=map(int,m.groups())
    try:return date(y,mo,d).isoformat()
    except ValueError:return None

def parse_page(html):
    soup=BeautifulSoup(html,"html.parser")
    out={}
    for h in soup.find_all(["h2","h3"]):
        dt=getdate(h.get_text(" ",strip=True))
        if not dt: continue
        t=h.find_next("table")
        if not t: continue
        trs=t.find_all("tr")
        if not trs: continue
        head=trs[0].find_all(["th","td"],recursive=False)
        names=[x.get_text(" ",strip=True) for x in head]
        if len(names)<4 or clean(names[0]) not in ("tinh","tinhthanh"): continue
        stations=[station(x) for x in names[1:]]
        vals={s:defaultdict(list) for s in stations}
        active=None
        for tr in trs[1:]:
            cells=tr.find_all(["th","td"],recursive=False)
            if len(cells)<len(stations)+1: continue
            label=clean(cells[0].get_text(" ",strip=True))
            if label in ("db","dacbiet"): active="DB"
            elif label in COUNTS: active=label
            if not active: continue
            for i,s in enumerate(stations,1):
                vals[s][active].extend(NUM.findall(cells[i].get_text(" ",strip=True)))
        for s,v in vals.items():
            if any(v.get(p) for p in COUNTS):
                out[(dt,s)]={p:v.get(p,[]) for p in COUNTS}
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--start",default="2026-07-01"); ap.add_argument("--end",default="2026-11-05")
    a=ap.parse_args()
    expected=defaultdict(lambda:defaultdict(list))
    with open(a.csv,encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if r["source"]!="383_supplement": continue
            k=(r["date"][:10],station(r["province"]))
            if a.start<=k[0]<=a.end: expected[k][r["prize"].upper()].append(r["number"].strip())
    session=requests.Session(); session.headers["User-Agent"]="Mozilla/5.0 XSMN-audit/1.0"
    observed={}; errors=[]
    for m in PAGES:
        if not a.start[:7]<=m<=a.end[:7]: continue
        url=f"https://xskt.net/xsmn/{m[5:]}-{m[:4]}"
        try:
            res=session.get(url,timeout=45); res.raise_for_status()
            got=parse_page(res.text); observed.update({k:v for k,v in got.items() if a.start<=k[0]<=a.end})
            if not got: errors.append({"month":m,"error":"no monthly result tables parsed"})
        except Exception as e: errors.append({"month":m,"error":str(e)})
        time.sleep(1)
    details=[]; compared=match=bad=missing=0
    for k,prizes in sorted(expected.items()):
        src=observed.get(k)
        if src is None:
            missing+=1; details.append([*k,"SOURCE_MISSING","","",""]); continue
        compared+=1; pairbad=False
        for p,n in COUNTS.items():
            x=sorted(prizes.get(p,[])); y=sorted(src.get(p,[]))
            if len(x)!=n or len(y)!=n or x!=y:
                pairbad=True; bad+=1
                details.append([*k,"MISMATCH",p,"|".join(x),"|".join(y)])
        if not pairbad: match+=1; details.append([*k,"MATCH","","",""])
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f); w.writerow(["date","province","status","prize","expected","observed"]); w.writerows(details)
    report={"source":"XSKT.net monthly archive (secondary source)","window_start":a.start,"window_end":a.end,
    "expected_station_days":len(expected),"parsed_source_station_days":len(observed),"compared_station_days":compared,
    "matching_station_days":match,"station_days_with_prize_mismatches":len({(r[0],r[1]) for r in details if r[2]=="MISMATCH"}),
    "station_days_missing_from_source":missing,"prize_mismatch_count":bad,
    "source_errors":errors,"status":"PASS" if not errors and compared==len(expected) and not missing and not bad else "INCOMPLETE_OR_MISMATCH",
    "note":"Secondary-source comparison only; not official issuer certification."}
    Path(a.out).with_suffix(".json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report["status"]!="PASS": sys.exit(1)
if __name__=="__main__": main()
