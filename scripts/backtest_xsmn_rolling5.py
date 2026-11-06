from __future__ import annotations
import argparse, json
from pathlib import Path
from math import erf, sqrt
import numpy as np
import pandas as pd

def histories_by_province(df):
    x=df.copy()
    x["date"]=pd.to_datetime(x["date"],errors="coerce").dt.normalize()
    x["province"]=x["province"].astype(str).str.strip()
    col=x["last2"] if "last2" in x.columns else x["number"].astype(str).str.replace(r"\D","",regex=True).str[-2:]
    x["n2"]=pd.to_numeric(col,errors="coerce")
    x=x.dropna(subset=["date","n2"])
    x=x[x.n2.between(0,99)]
    out={}
    for province,g in x.groupby("province",sort=True):
        out[province]=[(d,set(z.n2.astype(int))) for d,z in g.groupby("date",sort=True)]
    return out

def score_methods(prior):
    counts=np.zeros(100); last=np.full(100,-1,dtype=int); recent=np.zeros(100)
    for j,(_,nums) in enumerate(prior):
        for n in nums:
            counts[n]+=1; last[n]=j; recent[n]+=0.7**(4-j)
    gap=np.where(last<0,5,4-last).astype(float)
    freq3=np.array([sum(n in nums for _,nums in prior[-3:]) for n in range(100)],dtype=float)
    return {"freq5":counts,"gap5":gap,"recent5":recent,
            "freq_gap5":counts/5+gap/5,"cold5":-counts,"freq3":freq3}

def run(data_path,outdir):
    df=pd.read_csv(data_path); histories=histories_by_province(df); rows=[]
    for province,history in histories.items():
        for i in range(5,len(history)):
            date,actual=history[i]; scores=score_methods(history[i-5:i])
            for method,score in scores.items():
                ranked=sorted(range(100),key=lambda n:(-score[n],n))
                for k in (5,10,15):
                    hits=len(set(ranked[:k]) & actual); expected=k*len(actual)/100
                    rows.append({"date":date.strftime("%Y-%m-%d"),"province":province,"method":method,
                      "top_k":k,"history_draws":5,"actual_unique":len(actual),"hits":hits,
                      "random_expected_hits":expected,"excess_vs_random":hits-expected})
    detail=pd.DataFrame(rows); out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    detail.to_csv(out/"rolling5_detail.csv",index=False)
    summaries=[]
    for k,gk in detail.groupby("top_k"):
        for method,g in gk.groupby("method"):
            ex=g.excess_vs_random.to_numpy(float); mean=float(ex.mean())
            se=float(ex.std(ddof=1)/np.sqrt(len(ex))); lo,hi=mean-1.96*se,mean+1.96*se
            actual=int(g.hits.sum()); nums=g.actual_unique.to_numpy(float)
            variance=float(np.sum(k*(nums/100)*(1-nums/100)*(100-k)/99))
            expected=float(g.random_expected_hits.sum())
            z=(actual-expected)/sqrt(variance) if variance else 0
            p=0.5*(1-erf(z/sqrt(2)))
            summaries.append({"top_k":int(k),"method":method,"evaluations":len(g),"total_hits":actual,
              "mean_hits":float(g.hits.mean()),"mean_random_expected":float(g.random_expected_hits.mean()),
              "mean_excess":mean,"lift":float(actual/expected),"paired_95_low":lo,"paired_95_high":hi,
              "normal_approx_p_upper":p,"random_total_mean":expected,"random_total_sd":sqrt(variance)})
    summary=pd.DataFrame(summaries).sort_values(["top_k","mean_hits"],ascending=[True,False])
    summary.to_csv(out/"rolling5_summary.csv",index=False)
    by=detail[detail.top_k==10].groupby(["province","method"],as_index=False).agg(
      evaluations=("hits","size"),mean_hits=("hits","mean"),mean_expected=("random_expected_hits","mean"),total_hits=("hits","sum"))
    by["excess"]=by.mean_hits-by.mean_expected; by.to_csv(out/"rolling5_by_province.csv",index=False)
    meta={"data_min":str(pd.to_datetime(df.date).min().date()),"data_max":str(pd.to_datetime(df.date).max().date()),
      "provinces":len(histories),"province_draw_evaluations":int(detail[detail.top_k==10].groupby(["date","province"]).ngroups),
      "rolling_window_draws":5,"methods":["freq5","gap5","recent5","freq_gap5","cold5","freq3"],
      "top_k_values":[5,10,15],"interval":"paired normal approximation 95% CI",
      "random_baseline":"hypergeometric mean/variance; upper-tail normal approximation"}
    (out/"rolling5_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False)); print(summary[summary.top_k==10].to_string(index=False))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--data",default="data/xsmn_5y_canonical.csv")
    p.add_argument("--outdir",default="artifacts/rolling5")
    a=p.parse_args(); run(a.data,a.outdir)
