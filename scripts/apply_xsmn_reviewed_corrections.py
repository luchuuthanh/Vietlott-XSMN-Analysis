#!/usr/bin/env python3
"""Apply reviewed corrections to the derived XSMN dataset, preserving raw inputs."""
import argparse, json
from pathlib import Path
import pandas as pd

FIXES = [
 {"date":"2026-08-29","province":"Long An","prize":"G2","prize_order":0,"old":"76719","new":"79719","basis":"independent result tables"},
 {"date":"2026-10-23","province":"Vinh Long","prize":"G4","prize_order":3,"old":"87992","new":"87962","basis":"issuer correction reported by Tuoi Tre; signed supervisory record"},
]

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--csv",required=True); p.add_argument("--report",required=True)
 a=p.parse_args()
 path=Path(a.csv); df=pd.read_csv(path,dtype={"number":str,"last2":str})
 applied=[]
 for f in FIXES:
  mask=(df.date.eq(f["date"]) & df.province.eq(f["province"]) & df.prize.eq(f["prize"]) & pd.to_numeric(df.prize_order).eq(f["prize_order"]))
  rows=df.index[mask].tolist()
  if len(rows)!=1: raise SystemExit(f"Expected exactly one target row for {f}, got {len(rows)}")
  i=rows[0]; actual=str(df.at[i,"number"])
  if actual==f["new"]:
   status="already_correct"
  elif actual==f["old"]:
   status="corrected"
   df.at[i,"number"]=f["new"]
   df.at[i,"number_length"]=len(f["new"])
   df.at[i,"last2"]=f["new"][-2:]
   df.at[i,"last2_numeric"]=int(f["new"][-2:])
   df.at[i,"source"]="383_supplement|reconciled"
  else:
   raise SystemExit(f"Unexpected source value for {f['date']} {f['province']} {f['prize']} order {f['prize_order']}: {actual}")
  applied.append({**f,"observed_before":actual,"status":status})
 df.to_csv(path,index=False,encoding="utf-8-sig")
 report={"corrections":applied,"raw_383_supplement_modified":False,
         "output_layer":"derived normalized dataset","status":"PASS" if all(x["status"] in ("corrected","already_correct") for x in applied) else "FAIL"}
 Path(a.report).parent.mkdir(parents=True,exist_ok=True)
 Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
