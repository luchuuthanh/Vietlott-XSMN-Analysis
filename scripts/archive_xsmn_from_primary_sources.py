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
    """Parse dated Minh Ngoc station sections; fail closed on missing prizes."""
    import re
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    lines = [re.sub(r"\s+", " ", x).strip() for x in soup.get_text("\n").splitlines()]
    lines = [x for x in lines if x]
    labels = {"Giải ĐB": "DB", "Giải nhất": "G1", "Giải nhì": "G2",
              "Giải ba": "G3", "Giải tư": "G4", "Giải năm": "G5",
              "Giải sáu": "G6", "Giải bảy": "G7", "Giải 8": "G8"}
    aliases = {"tphcm": ("TP. HCM", "TP.HCM", "Hồ Chí Minh"),
               "dongthap": ("Đồng Tháp",), "camau": ("Cà Mau",)}
    headers = [i for i, line in enumerate(lines)
               if line.upper().startswith("KẾT QUẢ XỔ SỐ ")
               and re.search(r"\d{2}/\d{2}/\d{4}", line)]
    out = {}
    for st in expected:
        candidates = [i for i in headers if any(
            normalize_station_key(name) in normalize_station_key(lines[i]) for name in aliases.get(st, (STATION[st],)))]
        if len(candidates) != 1:
            return {}
        start = candidates[0]
        end = next((i for i in headers if i > start), len(lines))
        found = {}
        current = None
        chunks = []
        def finish():
            if current is None:
                return True
            values = re.findall(r"(?<!\d)\d+(?!\d)", " ".join(chunks))
            if len(values) != COUNTS[current] or any(
                len(v) != WIDTH[current] for v in values):
                return False
            found[current] = values
            return True
        for line in lines[start + 1:end]:
            if current == "G8" and ("Đổi số trúng" in line or "In vé dò" in line):
                break
            match = next(((label, prize) for label, prize in labels.items()
                          if line.casefold().startswith(label.casefold())), None)
            if match:
                if not finish():
                    return {}
                label, current = match
                if current in found:
                    return {}
                chunks = [line[len(label):]]
            elif current is not None:
                chunks.append(line)
        if not finish() or set(found) != set(COUNTS):
            return {}
        out[st] = found
    return out

def screenshot_fallback(url, day, expected):
    """Independent browser capture; OCR never receives reference winning numbers."""
    import re, subprocess, hashlib, html
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse
    from bs4 import BeautifulSoup
    folder=Path("xsmn_independent_audit") / day
    folder.mkdir(parents=True, exist_ok=True)
    key=(urlparse(url).hostname or "source")+"-"+hashlib.sha256(url.encode()).hexdigest()[:10]
    image=folder / (key+".png")
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":1440,"height":1000},device_scale_factor=2,locale="vi-VN")
            page.goto(url,wait_until="domcontentloaded",timeout=18000)
            page.wait_for_timeout(1500)
            body=page.locator("body").inner_text(timeout=5000)
            target=datetime.fromisoformat(day)
            dates=[target.strftime("%d/%m/%Y"),target.strftime("%d-%m-%Y")]
            if not any(d in body for d in dates):
                raise RuntimeError("Requested date not visible in rendered page")
            page.screenshot(path=str(image),full_page=True,timeout=12000,animations="disabled")
            rendered=page.content()
        finally:
            browser.close()
    candidate=parse_minhngoc_station_blocks(rendered,expected) or parse_daily(rendered)
    method="rendered_html"
    if not candidate or not all(st in candidate and all(len(candidate[st].get(pr,[]))==n for pr,n in COUNTS.items()) for st in expected):
        result=subprocess.run(["tesseract",str(image),"stdout","-l","vie+eng","--psm","6"],capture_output=True,text=True,timeout=25,check=True)
        raw=result.stdout
        (folder / (key+".txt")).write_text(raw,encoding="utf-8")
        if not any(d in raw for d in dates):
            raise RuntimeError("Requested date not independently recognized by OCR")
        candidate=parse_minhngoc_station_blocks("<pre>"+html.escape(raw)+"</pre>",expected)
        method="screenshot_ocr"
    (folder / (key+".json")).write_text(json.dumps({"url":url,"date":day,"method":method,"image":str(image),"sha256":hashlib.sha256(image.read_bytes()).hexdigest()},ensure_ascii=False),encoding="utf-8")
    return candidate,method

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
        if set(groups)!=expected or any(len(groups[st].get(p,[]))!=count or any(not n.isdigit() or len(n)!=WIDTH[p] for n in groups[st].get(p,[])) for st in expected for p,count in COUNTS.items()):
            frame=None
            groups=defaultdict(lambda:defaultdict(list))
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
    stamp=datetime.fromisoformat(day).strftime("%d-%m-%Y")
    sources += [
        f"https://www.minhngoc.net.vn/ket-qua-xo-so/mien-nam/{stamp}.html",
        f"https://xosodaiphatvn.com/kqxsmn/{stamp}",
        f"https://kqxsmn.net/xsmn/{stamp}.html",
        f"https://www.xoso.net/kqxs/mien-nam/{stamp}.html",
        f"https://ketqua77.com/xo-so-ngay/mien-nam-xsmn-{stamp}.html",
        f"https://kqxs.wiki/xsmn-{stamp}",
    ]
    independent={};secondary_url=None;errors=[];parsed_sources=[]
    # Fetch independent publishers concurrently to avoid sequential 25-second
    # timeouts exhausting the workflow's 100-second verification budget.
    def fetch_publisher(url):
        try:
            resp=requests.get(url,headers={"User-Agent":"Mozilla/5.0","Accept-Language":"vi-VN,vi;q=0.9"},timeout=18)
            resp.raise_for_status()
            parsed=(parse_minhngoc_station_blocks(resp.content,expected) or parse_daily(resp.content)) if ("minhngoc.net.vn" in url or "www.xoso.net" in url) else parse_daily(resp.content)
            candidate={normalize_station_key(k):v for k,v in parsed.items()}
            return url,candidate,None
        except Exception as exc:
            return url,{},str(exc)
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures=[pool.submit(fetch_publisher,url) for url in sources]
        fetched=[future.result() for future in futures]
    capture_methods={}
    def complete_capture(candidate):
        return set(candidate)==expected and all(
            all(len(candidate[st].get(p,[]))==count and
                all(isinstance(n,str) and n.isdigit() and len(n)==WIDTH[p] for n in candidate[st][p])
                for p,count in COUNTS.items()) for st in expected)
    if os.environ.get("XSMN_BROWSER_FALLBACK")=="1":
        preferred=("minhngoc.net.vn/free/", "xosodaiphatvn.com", "kqxs.wiki")
        targets=[(i,u) for i,(u,c,e) in enumerate(fetched) if not complete_capture(c) and any(x in u for x in preferred)]
        def recover(item):
            i,u=item
            try:
                candidate,method=screenshot_fallback(u,day,expected)
                return i,u,{normalize_station_key(k):v for k,v in candidate.items()},method,None
            except Exception as exc:
                return i,u,{},"browser_failed",str(exc)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for i,u,c,method,error in pool.map(recover,targets):
                capture_methods[u]=method
                if complete_capture(c):
                    fetched[i]=(u,c,None)
                else:
                    errors.append(f"{u}: browser fallback incomplete: {error or method}")
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
        "source_errors":errors,"source_urls":sources,"capture_methods":capture_methods
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

    from urllib.parse import urlparse
    def publisher(url):
        host = (urlparse(url or "").hostname or "").removeprefix("www.")
        return "minhngoc" if host in {"minhngoc.net.vn", "xoso.net"} else host
    fallback_allowed = day != now or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M") >= "16:45"
    live_available = bool(groups) and set(groups)==expected
    live_matches = [(u,c) for u,c in parsed_sources if live_available and publisher(u)!=publisher(primary_url) and matches(groups,c)]
    if fallback_allowed and not live_matches:
        # Do not override a conflicting complete live draw automatically.
        if live_available:
            raise RuntimeError("Complete live draw conflicts with backup publishers; manual review required")
        frame=None
        pending_groups=None
    verification_checks = []
    if frame is not None or pending_groups is not None:
        if not parsed_sources:
            raise RuntimeError("Independent sources unavailable: " + "; ".join(errors))
        matched = []
        for url, candidate in parsed_sources:
            ok = matches(groups, candidate)
            verification_checks.append({"url": url, "matches_live": ok})
            if ok and publisher(url)!=publisher(primary_url) and publisher(url) not in {publisher(u) for u in matched}:
                matched.append(url)
        if len(matched) < 2:
            raise RuntimeError("Need two distinct backup publishers matching the live snapshot; checks="
                               + json.dumps(verification_checks, ensure_ascii=False)
                               + "; errors=" + "; ".join(errors))
        if any(not matches(groups, candidate) for _, candidate in parsed_sources):
            raise RuntimeError("Complete publisher disagrees with live snapshot; manual review required")
        secondary_url = matched[0]
        # Two independent backup publishers are always configured above;
        # only independently fetched, matching publishers count as evidence.
        evidence_urls = [primary_url] + matched
    else:
        if not fallback_allowed:
            raise RuntimeError("Backup-only verification starts at 16:45")
        # Backfill: select an agreeing pair from all available publishers.
        # Do not reject valid results merely because the first two disagree.
        pair = next(
            ((url_a, data_a, url_b) for i, (url_a, data_a) in enumerate(parsed_sources)
             for url_b, data_b in parsed_sources[i + 1:]
             if publisher(url_a)!=publisher(url_b) and matches(data_a, data_b)),
            None,
        )
        if pair is None:
            raise RuntimeError("Need two agreeing independent sources for backfill; available="
                               + str([url for url, _ in parsed_sources])
                               + "; errors=" + "; ".join(errors))
        primary_url, groups, secondary_url = pair
        if any(not matches(groups,candidate) for url,candidate in parsed_sources):
            raise RuntimeError("Complete backup publishers disagree; manual review required")
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
        "source_checks":verification_checks,"source_errors":errors,"capture_methods":capture_methods,
        "verification":"All winning numbers matched two independent publisher pages; no official issuer certification.",
        "official_issuer_certification":False,
        "verification_mode":"automatic_multi_source",
        "verified_at_vietnam":datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
        "distinct_publisher_count":len({publisher(u) for u in evidence_urls})}
    meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","date":day,"rows":len(rows),"sources":metadata["sources"]},ensure_ascii=False))

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(f"PRIMARY_SOURCE_VERIFICATION_FAILED: {exc}",file=sys.stderr)
        sys.exit(1)
