#!/usr/bin/env python3
"""Archive a completed XSMN draw from the live publisher, not from 383.

Fail closed: an independently parsed publisher page must match all 18
zero-padded prize numbers per station before any PASS overlay is written.
383 is not consulted or required by this primary pipeline.
"""
import csv, json, sys, os
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def parse_minhngoc_station_blocks(html, expected):
    """Read Minh Ngoc's station-first daily result layout, not a prize-row grid.

    The publisher displays G8, G7, G6, G5, G4, G3, G2, G1, DB in
    that order under each station. Reject ambiguous/missing blocks.
    """
    import re
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser")
    # Keep line boundaries so unrelated analysis/loto tables cannot be
    # mistaken for the winning-number sequence.
    lines=[re.sub(r"\\s+"," ",x).strip() for x in soup.get_text("\\n").splitlines()]
    lines=[x for x in lines if x]
    aliases={"tphcm":("TP. HCM","TP.HCM","Thành Phố Hồ Chí Minh"),
             "dongthap":("Đồng Tháp",),"camau":("Cà Mau",)}
    sequence=[("G8",1,2),("G7",1,3),("G6",3,4),("G5",1,4),
              ("G4",7,5),("G3",2,5),("G2",1,5),("G1",1,5),("DB",1,6)]
    result={}
    for station in expected:
        names=aliases.get(station,())
        candidates=[]
        for i,line in enumerate(lines):
            if line not in names:continue
            # Skip lottery ticket identifiers; consume only number-only
            # lines, in strict order, and stop at the next station header.
            window=[]
            for item in lines[i+1:i+100]:
                if any(item==name for group in aliases.values() for name in group):
                    break
                if re.fullmatch(r"[0-9]+(?:\\s+[0-9]+)*",item):
                    window.extend(item.split())
                if len(window)>=18:break
            offset=0;parsed={}
            for prize,count,width in sequence:
                vals=window[offset:offset+count]
                if len(vals)!=count or any(len(v)!=width for v in vals):
                    break
                parsed[prize]=vals;offset+=count
            if len(parsed)==len(sequence):candidates.append(parsed)
        if len(candidates)!=1:
            return {}
        result[station]=candidates[0]
    return result

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
    # Preserve complete live results immediately, even if independent publishers fail.
    # This is a pending snapshot, NOT a verified historical overlay.
    if frame is not None:
        live_groups=defaultdict(lambda:defaultdict(list))
        for row in frame.itertuples(index=False):
            key=normalize_station_key(row.province)
            prize="DB" if row.prize in ("ĐB","DB") else row.prize
            live_groups[key][prize].append(str(row.number))
        if set(live_groups)==expected and all(
            len(live_groups[station].get(prize,[]))==count
            and all(n.isdigit() and len(n)==WIDTH[prize] for n in live_groups[station][prize])
            for station in expected for prize,count in COUNTS.items()
        ):
            pending=Path(f"data/xsmn_live_pending_{day}.json")
            payload={"status":"PENDING_INDEPENDENT_VERIFICATION","date":day,
                     "source":primary_url,"stations":len(expected),
                     "rows":18*len(expected),
                     "results":{station:dict(prizes) for station,prizes in live_groups.items()}}
            pending.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            print(f"LIVE_SNAPSHOT_SAVED: {pending}; awaiting independent verification",flush=True)

    # Recover the durable live capture on later runs, including historical backfills.
    # Pending data is a primary candidate only; it can NEVER independently pass.
    pending_path=Path(f"data/xsmn_live_pending_{day}.json")
    pending_groups=None
    if pending_path.exists():
        snapshot=json.loads(pending_path.read_text(encoding="utf-8"))
        raw=snapshot.get("results",{})
        recovered={normalize_station_key(k):{p:list(nums) for p,nums in v.items()} for k,v in raw.items()}
        valid=(snapshot.get("date")==day and
               snapshot.get("status")=="PENDING_INDEPENDENT_VERIFICATION" and
               set(recovered)==expected and
               all(set(recovered[st])==set(COUNTS) and
                   all(len(recovered[st][p])==count and
                       all(isinstance(n,str) and n.isdigit() and len(n)==WIDTH[p]
                           for n in recovered[st][p])
                       for p,count in COUNTS.items())
                   for st in expected))
        if not valid:
            raise RuntimeError(f"Invalid pending live snapshot: {pending_path}")
        pending_groups=recovered
        if frame is None:
            primary_url=snapshot.get("source")
            if not isinstance(primary_url,str) or not primary_url.startswith("https://"):
                raise RuntimeError("Pending snapshot missing valid original publisher URL")
            print(f"RECOVERED_LIVE_SNAPSHOT: {pending_path}",flush=True)
    groups=defaultdict(lambda:defaultdict(list))
    if frame is not None:
        for r in frame.itertuples(index=False):
            key=normalize_station_key(r.province)
            p="DB" if r.prize in ("ĐB","DB") else r.prize
            groups[key][p].append(str(r.number))
        if set(groups)!=expected:raise RuntimeError(f"Station set differs: {set(groups)}")
    if frame is None and pending_groups is not None:
        for st in expected:
            for p in COUNTS:
                groups[st][p]=list(pending_groups[st][p])
    # Independent fallback publishers. Minh Ngoc intentionally excluded.
    # Validate every station, prize count and exact zero-padded value before writing.
    # Reuse the publisher set documented by the successful 2026-11-14
    # verified overlay. SXMN remains the primary live publisher, so its
    # archive is not counted as an independent second publisher.
    sources=[
        f"https://www.minhngoc.net.vn/free/kqxs/mien-nam/{datetime.fromisoformat(day):%d-%m-%Y}.html",
        f"https://www.xsmn.net/kqxs-ngay-{datetime.fromisoformat(day):%d-%m-%Y}",
        f"https://xskt.net/xsmn/{datetime.fromisoformat(day):%d-%m-%Y}",
        f"https://kqsx.vn/ket-qua-ngay/xsmn-{datetime.fromisoformat(day):%d-%m-%Y}",
        f"https://xosotin.net/ket-qua/xsmn/{datetime.fromisoformat(day):%d-%m-%Y}.html",
    ]
    independent={};secondary_url=None;errors=[];parsed_sources=[]
    # Fetch independent publishers concurrently to avoid sequential 25-second
    # timeouts exhausting the workflow's 100-second verification budget.
    def fetch_publisher(url):
        try:
            resp=requests.get(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"vi-VN,vi;q=0.9"},timeout=18)
            resp.raise_for_status()
            parsed=(parse_minhngoc_station_blocks(resp.content,expected) if "minhngoc.net.vn" in url else parse_daily(resp.content))
            candidate={normalize_station_key(k):v for k,v in parsed.items()}
            return url,candidate,None
        except Exception as exc:
            return url,{},str(exc)
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures=[pool.submit(fetch_publisher,url) for url in sources]
        fetched=[future.result() for future in futures]
    station_checks={st:[] for st in sorted(expected)}
    for url,candidate,error in fetched:
        if error:
            errors.append(f"{url}: {error}")
            for st in expected: station_checks[st].append({"url":url,"status":"FETCH_ERROR","error":error})
            continue
        for st in sorted(expected):
            prizes=candidate.get(st,{})
            complete=(all(len(prizes.get(p,[]))==count and
                          all(n.isdigit() and len(n)==WIDTH[p] for n in prizes.get(p,[]))
                          for p,count in COUNTS.items()))
            if not complete:
                station_checks[st].append({"url":url,"status":"INCOMPLETE","prizes_found":{p:len(prizes.get(p,[])) for p in COUNTS}})
            else:
                reference=groups.get(st,{})
                mismatches=[p for p in COUNTS if sorted(prizes[p])!=sorted(reference.get(p,[]))]
                station_checks[st].append({"url":url,"status":"MATCH" if not mismatches else "MISMATCH","mismatched_prizes":mismatches})
        if set(candidate)==expected and all(
            all(len(candidate[st].get(p,[]))==count and
                all(n.isdigit() and len(n)==WIDTH[p] for n in candidate[st][p])
                for p,count in COUNTS.items()) for st in expected):
            parsed_sources.append((url,candidate))
        else:
            errors.append(f"{url}: incomplete station/prize parse {list(candidate)}")
    # Diagnostics are not a PASS overlay and never enter canonical history.
    diagnostic_path=Path(f"data/xsmn_verification_diagnostics_{day}.json")
    diagnostic_path.write_text(json.dumps({
        "status":"DIAGNOSTIC_ONLY","date":day,"stations":station_checks,
        "source_errors":errors,"source_urls":sources
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"VERIFICATION_DIAGNOSTICS: {diagnostic_path}",flush=True)
    # Match the live snapshot against ANY available independent publisher,
    # not merely the first publisher that responds. Keep all candidate sources
    # and their discrepancies in the verification evidence.
    def matches(a, b):
        return all(
            sorted(a[st].get(p, [])) == sorted(b[st].get(p, []))
            for st in expected for p in COUNTS
        )

    verification_checks = []
    if frame is not None or pending_groups is not None:
        if not parsed_sources:
            raise RuntimeError("Independent sources unavailable: " + "; ".join(errors))
        matched = []
        for url, candidate in parsed_sources:
            ok = matches(groups, candidate)
            verification_checks.append({"url": url, "matches_live": ok})
            if ok:
                matched.append(url)
        if not matched:
            raise RuntimeError("No independent publisher matches the live snapshot; checks="
                               + json.dumps(verification_checks, ensure_ascii=False)
                               + "; errors=" + "; ".join(errors))
        secondary_url = matched[0]
        # Two independent backup publishers are always configured above;
        # only independently fetched, matching publishers count as evidence.
        evidence_urls = [primary_url] + matched
    else:
        # Backfill: select an agreeing pair from all available publishers.
        # Do not reject valid results merely because the first two disagree.
        pair = next(
            ((url_a, data_a, url_b) for i, (url_a, data_a) in enumerate(parsed_sources)
             for url_b, data_b in parsed_sources[i + 1:]
             if matches(data_a, data_b)),
            None,
        )
        if pair is None:
            raise RuntimeError("Need two agreeing independent sources for backfill; available="
                               + str([url for url, _ in parsed_sources])
                               + "; errors=" + "; ".join(errors))
        primary_url, groups, secondary_url = pair
        evidence_urls = [primary_url, secondary_url]
        verification_checks = [{"url": url, "matches_selected": matches(groups, candidate)}
                               for url, candidate in parsed_sources]
    independent = next(candidate for url, candidate in parsed_sources if url == secondary_url)
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
        "sources":evidence_urls,"source_count":len(evidence_urls),
        "configured_independent_sources":sources,
        "source_checks":verification_checks,"source_errors":errors,
        "verification":"All winning numbers matched two independent publisher pages; no official issuer certification.",
        "official_issuer_certification":False}
    meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","date":day,"rows":len(rows),"sources":metadata["sources"]},ensure_ascii=False))

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(f"PRIMARY_SOURCE_VERIFICATION_FAILED: {exc}",file=sys.stderr)
        sys.exit(1)
