from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from xsmn_algorithms import prepare_xsmn_frame, rolling_backtest
CSV = ROOT / "data" / "xsmn_5y_canonical.csv"
META = ROOT / "data" / "xsmn_5y_canonical.json"
OUT = ROOT / "dist" / "xsmn_backtest"
METHODS = ["freq_30", "freq_90", "freq_365", "gap", "ewma", "blend"]

def main():
    meta = json.loads(META.read_text(encoding="utf-8"))
    if meta.get("status") != "PASS":
        raise SystemExit("Canonical data is not PASS")
    raw = pd.read_csv(CSV, encoding="utf-8-sig")
    if len(raw) != int(meta["rows"]):
        raise SystemExit("CSV row count does not match canonical metadata")
    frame = prepare_xsmn_frame(raw)
    provinces = sorted(frame["province"].unique())
    if len(provinces) != 21:
        raise SystemExit(f"Expected 21 provinces, got {len(provinces)}")
    details, summaries = [], []
    for province in provinces:
        detail, summary = rolling_backtest(frame, province, methods=METHODS, top_k=10, min_history=90)
        if detail.empty or summary.empty:
            raise SystemExit(f"No backtest results for {province}")
        detail.insert(0, "province", province)
        summary.insert(0, "province", province)
        details.append(detail)
        summaries.append(summary)
    detail = pd.concat(details, ignore_index=True)
    by_province = pd.concat(summaries, ignore_index=True)
    overall = detail.groupby("method", as_index=False).agg(
        province_draw_evaluations=("date", "count"),
        mean_hits=("hits", "mean"),
        mean_hit_rate=("hit_rate", "mean"),
        total_hits=("hits", "sum"),
        total_random_expected=("random_expected_hits", "sum"),
    )
    overall["lift_vs_random"] = overall["total_hits"] / overall["total_random_expected"]
    overall["relative_improvement_pct"] = (overall["lift_vs_random"] - 1) * 100
    overall = overall.sort_values("lift_vs_random", ascending=False).reset_index(drop=True)
    winners = by_province.sort_values(["province", "mean_hits"], ascending=[True, False]).groupby("province").head(1)
    OUT.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUT / "backtest_detail_all_21.csv", index=False, encoding="utf-8-sig")
    by_province.to_csv(OUT / "backtest_summary_by_province.csv", index=False, encoding="utf-8-sig")
    overall.to_csv(OUT / "backtest_overall_methods.csv", index=False, encoding="utf-8-sig")
    winners.to_csv(OUT / "best_method_by_province.csv", index=False, encoding="utf-8-sig")
    result = {
        "dataset_status": meta["status"], "dataset_rows": len(raw),
        "window_start": meta["window_start"], "window_end": meta["window_end"],
        "provinces": provinces, "province_count": len(provinces),
        "min_history_draws": 90, "top_k": 10,
        "prediction_rows": len(detail), "province_draw_evaluations": int(detail[["province","date"]].drop_duplicates().shape[0]),
        "methods": overall.to_dict(orient="records"),
        "best_method_by_province": winners[["province","method","mean_hits","mean_hit_rate"]].to_dict(orient="records"),
        "warning": "Historical backtest is not evidence of a reliable lottery prediction edge. Small differences may be noise."
    }
    (OUT / "backtest_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"province_count":len(provinces),"prediction_rows":len(detail),"overall":result["methods"]},ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
