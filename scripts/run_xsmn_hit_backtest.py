from pathlib import Path
import sys
import pandas as pd

# The runner lives in /scripts while the analysis module is at repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xsmn_hit_analysis import analyze_scope, SCOPES, METHOD_LABELS

DATA = Path("data/xsmn_5y_canonical.csv")
OUT = Path("backtest_results")
OUT.mkdir(exist_ok=True)

if not DATA.exists():
    raise SystemExit(f"Missing canonical history: {DATA}")

df = pd.read_csv(DATA, dtype={"number": str, "last2": str})
required = {"date", "province", "prize", "number"}
if not required.issubset(df.columns):
    raise SystemExit(f"Canonical CSV missing columns: {sorted(required - set(df.columns))}")

stations = sorted(df["province"].dropna().astype(str).unique())
summaries, details, attributions = [], [], []
MIN_HISTORY = 90
TEST_PERIODS = 365
TOP_K = 10

for station in stations:
    for scope in SCOPES:
        summary, detail, attribution, total_draws = analyze_scope(
            df, station, scope,
            top_k=TOP_K,
            min_history=MIN_HISTORY,
            test_periods=TEST_PERIODS,
        )
        if summary.empty:
            continue
        summary.insert(0, "Đài", station)
        summary.insert(1, "Phạm vi", scope)
        summary["Tổng kỳ lịch sử"] = total_draws
        summaries.append(summary.drop(columns=["_method"], errors="ignore"))

        detail.insert(0, "Đài", station)
        detail.insert(1, "Phạm vi", scope)
        details.append(detail.drop(columns=["_method", "_hits", "_expected"], errors="ignore"))

        attribution.insert(0, "Đài", station)
        attribution.insert(1, "Phạm vi", scope)
        attributions.append(attribution.drop(columns=["_hit_methods"], errors="ignore"))

if not summaries:
    raise SystemExit("No backtest results: each scope needs more than 90 historical draws.")

summary_df = pd.concat(summaries, ignore_index=True)
detail_df = pd.concat(details, ignore_index=True)
attribution_df = pd.concat(attributions, ignore_index=True)

summary_df.to_csv(OUT / "summary_by_station_scope.csv", index=False, encoding="utf-8-sig")
detail_df.to_csv(OUT / "walk_forward_detail.csv", index=False, encoding="utf-8-sig")
attribution_df.to_csv(OUT / "winning_number_method_attribution.csv", index=False, encoding="utf-8-sig")

overall = summary_df.groupby(["Phạm vi", "Phương pháp"], as_index=False).agg(
    Đài=("Đài", "nunique"),
    Số_kỳ_kiểm_tra=("Số kỳ kiểm tra", "sum"),
    Tổng_lượt_trúng=("Tổng lượt trúng", "sum"),
    Kỳ_có_trúng=("Kỳ có ít nhất 1 số trúng", "sum"),
    Tổng_lượt_chọn=("Tỷ lệ trúng trên lượt chọn (%)", "count"),
)
# Recompute the pooled hit rate using fixed top_k and the actual number of tested draws.
overall["Tỷ_lệ_trúng_trên_lượt_chọn_pct"] = (
    overall["Tổng_lượt_trúng"] / (overall["Số_kỳ_kiểm_tra"] * TOP_K) * 100
).round(4)
overall.to_csv(OUT / "overall_by_scope_method.csv", index=False, encoding="utf-8-sig")

# Compare station effectiveness across all six methods, per prize scope.
station_effectiveness = summary_df.groupby(["Đài", "Phạm vi"], as_index=False).agg(
    Số_phương_pháp=("Phương pháp", "nunique"),
    Số_kỳ_kiểm_tra=("Số kỳ kiểm tra", "max"),
    Tổng_lượt_trúng=("Tổng lượt trúng", "sum"),
    Tổng_kỳ_có_trúng=("Kỳ có ít nhất 1 số trúng", "sum"),
    Kỳ_vọng_ngẫu_nhiên=("Kỳ vọng ngẫu nhiên", "sum"),
)
station_effectiveness["Tổng_lượt_chọn"] = (
    station_effectiveness["Số_kỳ_kiểm_tra"] * TOP_K * station_effectiveness["Số_phương_pháp"]
)
station_effectiveness["Tỷ_lệ_trúng_trên_lượt_chọn_pct"] = (
    station_effectiveness["Tổng_lượt_trúng"] / station_effectiveness["Tổng_lượt_chọn"] * 100
).round(4)
station_effectiveness["So_với_ngẫu_nhiên_lần"] = (
    station_effectiveness["Tổng_lượt_trúng"] / station_effectiveness["Kỳ_vọng_ngẫu_nhiên"]
).replace([float("inf")], pd.NA).round(4)
best_methods = summary_df.sort_values(
    ["Đài", "Phạm vi", "Tỷ lệ trúng trên lượt chọn (%)"],
    ascending=[True, True, False]
).drop_duplicates(["Đài", "Phạm vi"])[["Đài", "Phạm vi", "Phương pháp", "Tỷ lệ trúng trên lượt chọn (%)"]]
best_methods = best_methods.rename(columns={
    "Phương pháp": "Phương_pháp_tốt_nhất",
    "Tỷ lệ trúng trên lượt chọn (%)": "Tỷ_lệ_của_phương_pháp_tốt_nhất_pct"
})
station_effectiveness = station_effectiveness.merge(best_methods, on=["Đài", "Phạm vi"], how="left")
station_effectiveness = station_effectiveness.sort_values(
    ["Phạm vi", "So_với_ngẫu_nhiên_lần", "Tỷ_lệ_trúng_trên_lượt_chọn_pct"],
    ascending=[True, False, False]
)
station_effectiveness.to_csv(OUT / "station_effectiveness.csv", index=False, encoding="utf-8-sig")

meta = [
    f"source_rows={len(df)}",
    f"stations={len(stations)}",
    f"min_history={MIN_HISTORY}",
    f"test_periods={TEST_PERIODS}",
    f"top_k={TOP_K}",
    f"scopes={','.join(SCOPES)}",
    f"methods={','.join(METHOD_LABELS)}",
]
(OUT / "run_metadata.txt").write_text("\n".join(meta), encoding="utf-8")
print("\n".join(meta))
print("\nOVERALL RESULTS")
print(overall.to_string(index=False))
