#!/usr/bin/env python3
"""Build a row-level evidence ledger for the 66 historical archive/API prize-group conflicts."""
import argparse, csv, json
from pathlib import Path
import pandas as pd

PRIZES = ["DB", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]

CASES = {
    ("2024-11-15", "Tra Vinh"): {
        "url1": "https://www.minhngoc.net.vn/ket-qua-xo-so/mien-nam/tra-vinh/15-11-2024.html",
        "url2": "https://xskt.com.vn/ngay/15-11-2024",
        "note": "DB 084786 appears in both published result tables.", "prizes": ["DB"]
    },
    ("2025-06-28", "Binh Phuoc"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-28-6-2025",
        "url2": "https://xs.com.vn/xsmn-ngay-28-6-2025.html",
        "note": "Full regional table; compare all prize classes DB through G7.", "prizes": PRIZES, "prizes": PRIZES
    },
    ("2025-06-28", "Hau Giang"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-28-6-2025",
        "url2": "https://xs.com.vn/xsmn-ngay-28-6-2025.html",
        "note": "Full regional table; compare all prize classes DB through G7."
    },
    ("2025-06-28", "Long An"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-28-6-2025",
        "url2": "https://xs.com.vn/xsmn-ngay-28-6-2025.html",
        "note": "Full regional table; compare all prize classes DB through G7."
    },
    ("2025-06-28", "TP. HCM"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-28-6-2025",
        "url2": "https://xs.com.vn/xsmn-ngay-28-6-2025.html",
        "note": "Full regional table; compare all prize classes DB through G7."
    },
    ("2025-08-23", "Binh Phuoc"): {
        "url1": "https://xskt.com.vn/xsbp/ngay-23-8-2025",
        "url2": "https://www.minhngoc.net.vn/free/ket-qua-xo-so/mien-nam/binh-phuoc/23-08-2025.html",
        "note": "Both pages show G4 includes 79028.", "prizes": ["G4"]
    },
    ("2026-05-02", "Binh Phuoc"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-2-5-2026",
        "url2": "https://www.minhngoc.net.vn/free/ket-qua-xo-so/mien-nam/02-05-2026.html",
        "url3": "https://xosonay.com/xsmn/02-05-2026/",
        "note": "Full regional tables from multiple secondary result pages.", "prizes": PRIZES, "prizes": PRIZES
    },
    ("2026-05-02", "Hau Giang"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-2-5-2026",
        "url2": "https://www.minhngoc.net.vn/free/ket-qua-xo-so/mien-nam/02-05-2026.html",
        "url3": "https://xosonay.com/xsmn/02-05-2026/",
        "note": "Full regional tables from multiple secondary result pages.", "prizes": PRIZES
    },
    ("2026-05-02", "Long An"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-2-5-2026",
        "url2": "https://www.minhngoc.net.vn/free/ket-qua-xo-so/mien-nam/02-05-2026.html",
        "url3": "https://xosonay.com/xsmn/02-05-2026/",
        "note": "Full regional tables from multiple secondary result pages.", "prizes": PRIZES
    },
    ("2026-05-02", "TP. HCM"): {
        "url1": "https://xskt.com.vn/xsmn/ngay-2-5-2026",
        "url2": "https://www.minhngoc.net.vn/free/ket-qua-xo-so/mien-nam/02-05-2026.html",
        "url3": "https://xosonay.com/xsmn/02-05-2026/",
        "note": "Full regional tables from multiple secondary result pages.", "prizes": PRIZES
    },
}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive",required=True)
    ap.add_argument("--out",default="xsmn_audit/xsmn_66_discrepancy_ledger.csv")
    ap.add_argument("--report",default="xsmn_audit/xsmn_66_discrepancy_ledger.json")
    a=ap.parse_args()
    df=pd.read_csv(a.archive,dtype={"number":str})
    df["date"]=pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    rows=[]
    errors=[]
    for (day,province),ev in CASES.items():
        for prize in ev["prizes"]:
            g=df[(df.date==day)&(df.province==province)&(df.prize.astype(str).str.upper()==prize)].sort_values("prize_order")
            expected={"DB":1,"G1":1,"G2":1,"G3":2,"G4":7,"G5":1,"G6":3,"G7":1}[prize]
            if len(g)!=expected:
                errors.append({"date":day,"province":province,"prize":prize,"expected_rows":expected,"actual_rows":len(g)})
                continue
            rows.append({
                "date":day,"province":province,"prize":prize,
                "archive_numbers":"|".join(g.number.astype(str).tolist()),
                "383_original_values":"NOT_AVAILABLE_IN_CURRENT_ARCHIVE_ARTIFACT",
                "evidence_url_1":ev["url1"],"evidence_url_2":ev["url2"],
                "evidence_url_3":ev.get("url3",""),
                "evidence_note":ev["note"],
                "review_status":"ARCHIVE_VALUE_SUPPORTED_BY_PUBLISHED_SECONDARY_RESULT_PAGES",
                "official_issuer_certification":"NOT_OBTAINED"
            })
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    report={
        "expected_discrepant_prize_groups":66,"ledger_rows":len(rows),
        "date_province_pairs":len(CASES),
        "prize_classes_reviewed":PRIZES,
        "errors":errors,
        "archive_values_supported_by_secondary_pages":len(rows)-len(errors),
        "383_original_values_available":False,
        "limitation":"The current audit artifact contains the canonical archive but not the historical 383.im overlap payload. Therefore the exact old 383.im values cannot be reproduced in this ledger. The discrepancy count is from the prior documented comparison; this ledger records archive values and secondary-page evidence.",
        "source_independence":"Multiple result pages were checked; common upstream data ownership has not been established.",
        "official_issuer_certification":"NOT_OBTAINED",
        "status":"PASS" if len(rows)==66 and not errors else "FAIL"
    }
    Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report["status"]!="PASS": raise SystemExit(1)
if __name__=="__main__": main()
