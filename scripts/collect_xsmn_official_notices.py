#!/usr/bin/env python3
"""Capture XSMN result notices from verified issuer sites and the Council portal."""
from __future__ import annotations
import hashlib,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
OUT=Path("xsmn_official_source_probe")
REGISTRY=Path("config/xsmn_official_sources.json")
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; XSMNResearchBot/1.0; +https://github.com/luchuuthanh/Vietlott-XSMN-Analysis)"}
KEYWORDS=("kqxskt","kết quả","ket-qua","xổ số","xo-so","quay số","quay-so","trúng thưởng","trung-thuong")
def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def same_host(url:str,host:str)->bool:return urlparse(url).netloc.lower().removeprefix("www.")==host.lower().removeprefix("www.")
def main():
 registry=json.loads(REGISTRY.read_text(encoding="utf-8"));OUT.mkdir(parents=True,exist_ok=True)
 session=requests.Session();session.headers.update(HEADERS)
 sources=[{"company":x["company"],"url":x["url"],"kind":"issuer","status":x["status"]} for x in registry["verified_direct_issuer_websites"]]
 sources.append({"company":"Hội đồng XSKT miền Nam","url":registry["discovery_hub"]["url"],"kind":"council","status":"regional_portal"})
 notices=[];failures=[];source_results=[]
 for si,source in enumerate(sources):
  root=source["url"]
  try:
   home=session.get(root,timeout=30);home.raise_for_status();soup=BeautifulSoup(home.content,"html.parser");host=urlparse(home.url).netloc
   candidates={home.url:"Trang chủ"}
   for a in soup.select("a[href]"):
    title=" ".join(a.get_text(" ",strip=True).split());url=urljoin(home.url,a.get("href",""))
    if urlparse(url).scheme not in ("http","https") or not same_host(url,host):continue
    if any(k in (title+" "+url).lower() for k in KEYWORDS):candidates[url]=title or url
   source_results.append({"company":source["company"],"kind":source["kind"],"root":root,"root_status":home.status_code,"candidate_pages":len(candidates)})
   for pi,(url,title) in enumerate(sorted(candidates.items())):
    try:
     r=session.get(url,timeout=25);r.raise_for_status();page=BeautifulSoup(r.content,"html.parser");body=" ".join(page.get_text(" ",strip=True).split());media=[]
     nodes=page.select("img[src],a[href]")
     for j,node in enumerate(nodes[:80]):
      raw=node.get("src") or node.get("href") or "";mu=urljoin(url,raw);path=urlparse(mu).path.lower()
      if not path.endswith((".jpg",".jpeg",".png",".webp",".pdf")) or not same_host(mu,host):continue
      try:
       mr=session.get(mu,timeout=25);mr.raise_for_status();ext=Path(urlparse(mu).path).suffix.lower() or ".bin"
       name=f"src{si:02d}_page{pi:03d}_media{j:02d}{ext}";(OUT/name).write_bytes(mr.content)
       media.append({"file":name,"url":mu,"sha256":sha(mr.content),"bytes":len(mr.content),"content_type":mr.headers.get("Content-Type","")})
      except Exception as exc:failures.append({"url":mu,"error":str(exc)})
     html_name=f"src{si:02d}_page{pi:03d}.html";(OUT/html_name).write_bytes(r.content)
     dates=sorted(set(re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b",title+" "+body[:5000])))
     notices.append({"company":source["company"],"source_kind":source["kind"],"issuer_identity_status":source["status"],"title":title,"url":url,"http_status":r.status_code,"date_hints":dates,"html_file":html_name,"html_sha256":sha(r.content),"media":media,"text_excerpt":body[:1800]})
     time.sleep(.15)
    except Exception as exc:failures.append({"company":source["company"],"url":url,"error":str(exc)})
  except Exception as exc:failures.append({"company":source["company"],"url":root,"error":str(exc)})
 manifest={"collector":"XSMN direct issuer notice capture","captured_at_utc":datetime.now(timezone.utc).isoformat(),"verified_issuer_sites_attempted":len(registry["verified_direct_issuer_websites"]),"sources":source_results,"notice_pages_captured":len(notices),"failures":failures,"notices":notices,"policy":"Evidence capture only. No OCR or canonical prize updates in this phase. Issuer identity verification is distinct from result parser verification."}
 (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({k:v for k,v in manifest.items() if k!="notices"},ensure_ascii=False,indent=2))
 if not notices:raise SystemExit("No notice pages captured.")
if __name__=="__main__":main()
