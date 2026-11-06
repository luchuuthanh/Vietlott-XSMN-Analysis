from __future__ import annotations

"""Strict final-holdout validation for XSMN ranking methods.

The latest 365 calendar days are a sealed evaluation window. All scores for a
target draw use only earlier draws from the same province. A Monte Carlo
uniform-random top-10 baseline is simulated independently for every target.
This is a research diagnostic, not a lottery-prediction claim.
"""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from xsmn_algorithms import draw_history, prepare_xsmn_frame, _rank_scores

CSV = ROOT / "data" / "xsmn_5y_canonical.csv"
META = ROOT / "data" / "xsmn_5y_canonical.json"
OUT = ROOT / "dist" / "xsmn_final_holdout"
METHODS = ["freq_30", "freq_90", "freq_365", "gap", "ewma", "blend"]
HOLDOUT_DAYS = 365
MIN_HISTORY = 90
TOP_K = 10
RANDOM_REPLICATES = 1000
BOOTSTRAP_REPLICATES = 5000
SEED = 20261106


def _bootstrap_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan"), float("nan")
    # Batch resampling keeps memory bounded for the full 21-province panel.
    means = []
    batch = 250
    for start in range(0, BOOTSTRAP_REPLICATES, batch):
        count = min(batch, BOOTSTRAP_REPLICATES - start)
        indices = rng.integers(0, len(values), size=(count, len(values)))
        means.extend(values[indices].mean(axis=1).tolist())
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def main() -> None:
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

    data_end = pd.to_datetime(meta["window_end"]).normalize()
    holdout_start = data_end - pd.Timedelta(days=HOLDOUT_DAYS - 1)
    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    random_totals = np.zeros(RANDOM_REPLICATES, dtype=np.int64)

    for province in provinces:
        history = draw_history(frame, province)
        for idx, (target_date, actual) in enumerate(history):
            if target_date < holdout_start or target_date > data_end or idx < MIN_HISTORY or not actual:
                continue
            prior = history[:idx]
            record = {
                "date": target_date.strftime("%Y-%m-%d"),
                "year": int(target_date.year),
                "province": province,
                "history_draws": len(prior),
                "actual_unique": len(actual),
                "random_expected_hits": TOP_K * len(actual) / 100.0,
            }
            actual_arr = np.fromiter(actual, dtype=int)
            for method in METHODS:
                scores = _rank_scores(prior, method)
                # Stable deterministic tie-break: smaller number first.
                ranked = sorted(range(100), key=lambda n: (-scores[n], n))
                selected = np.asarray(ranked[:TOP_K], dtype=int)
                record[f"hits_{method}"] = int(np.isin(selected, actual_arr).sum())

            # Independent uniform random top-10 selections for this target.
            random_keys = rng.random((RANDOM_REPLICATES, 100))
            random_selected = np.argpartition(random_keys, TOP_K - 1, axis=1)[:, :TOP_K]
            random_hits = np.isin(random_selected, actual_arr).sum(axis=1)
            random_totals += random_hits.astype(np.int64)
            rows.append(record)

    detail = pd.DataFrame(rows)
    if detail.empty:
        raise SystemExit("No final-holdout rows; check date range and minimum history")
    if detail["date"].min() < holdout_start.strftime("%Y-%m-%d"):
        raise SystemExit("Holdout leakage: an evaluation date precedes holdout start")
    if int(detail["history_draws"].min()) < MIN_HISTORY:
        raise SystemExit("Holdout leakage: insufficient prior history")

    summary_rows = []
    ci_rng = np.random.default_rng(SEED + 1)
    random_mean = float(random_totals.mean())
    random_sd = float(random_totals.std(ddof=1))
    for method in METHODS:
        hits = detail[f"hits_{method}"].to_numpy(dtype=float)
        expected = detail["random_expected_hits"].to_numpy(dtype=float)
        differences = hits - expected
        ci_low, ci_high = _bootstrap_ci(differences, ci_rng)
        observed_total = int(hits.sum())
        p_value = (1 + int(np.count_nonzero(random_totals >= observed_total))) / (RANDOM_REPLICATES + 1)
        summary_rows.append({
            "method": method,
            "evaluation_draws": len(detail),
            "total_hits": observed_total,
            "mean_hits_per_top10": float(hits.mean()),
            "mean_random_expected": float(expected.mean()),
            "excess_hits_per_draw": float(differences.mean()),
            "excess_hits_ci95_low": ci_low,
            "excess_hits_ci95_high": ci_high,
            "aggregate_random_mean_hits": random_mean,
            "aggregate_random_sd_hits": random_sd,
            "monte_carlo_p_upper": p_value,
            "monte_carlo_random_replicates": RANDOM_REPLICATES,
        })
    overall = pd.DataFrame(summary_rows).sort_values(
        ["excess_hits_per_draw", "method"], ascending=[False, True]
    ).reset_index(drop=True)

    yearly_rows = []
    for (year, method), group in detail.melt(
        id_vars=["year", "province", "date", "random_expected_hits"],
        value_vars=[f"hits_{m}" for m in METHODS],
        var_name="method", value_name="hits"
    ).assign(method=lambda x: x["method"].str.removeprefix("hits_")).groupby(["year", "method"]):
        yearly_rows.append({
            "year": int(year), "method": method, "evaluation_draws": len(group),
            "mean_hits_per_top10": float(group["hits"].mean()),
            "mean_random_expected": float(group["random_expected_hits"].mean()),
            "excess_hits_per_draw": float((group["hits"] - group["random_expected_hits"]).mean()),
        })
    yearly = pd.DataFrame(yearly_rows).sort_values(["year", "excess_hits_per_draw"], ascending=[True, False])

    province_rows = []
    melted = detail.melt(
        id_vars=["province", "random_expected_hits"],
        value_vars=[f"hits_{m}" for m in METHODS],
        var_name="method", value_name="hits"
    )
    melted["method"] = melted["method"].str.removeprefix("hits_")
    for (province, method), group in melted.groupby(["province", "method"]):
        province_rows.append({
            "province": province, "method": method, "evaluation_draws": len(group),
            "mean_hits_per_top10": float(group["hits"].mean()),
            "mean_random_expected": float(group["random_expected_hits"].mean()),
            "excess_hits_per_draw": float((group["hits"] - group["random_expected_hits"]).mean()),
        })
    by_province = pd.DataFrame(province_rows).sort_values(
        ["province", "excess_hits_per_draw"], ascending=[True, False]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUT / "final_holdout_detail.csv", index=False, encoding="utf-8-sig")
    overall.to_csv(OUT / "final_holdout_overall.csv", index=False, encoding="utf-8-sig")
    yearly.to_csv(OUT / "final_holdout_by_year.csv", index=False, encoding="utf-8-sig")
    by_province.to_csv(OUT / "final_holdout_by_province.csv", index=False, encoding="utf-8-sig")
    report = {
        "dataset_status": meta["status"],
        "dataset_rows": len(raw),
        "dataset_window": [meta["window_start"], meta["window_end"]],
        "holdout_window": [holdout_start.strftime("%Y-%m-%d"), data_end.strftime("%Y-%m-%d")],
        "holdout_days": HOLDOUT_DAYS,
        "province_count": int(detail["province"].nunique()),
        "evaluation_province_draws": len(detail),
        "min_prior_draws": MIN_HISTORY,
        "top_k": TOP_K,
        "methods": METHODS,
        "random_replicates": RANDOM_REPLICATES,
        "random_seed": SEED,
        "overall": overall.to_dict(orient="records"),
        "interpretation": (
            "The final year is evaluated without tuning on it. Positive excess or a low "
            "Monte Carlo p-value alone does not prove a durable edge; inspect the 95% "
            "bootstrap interval, year/province stability, and replicate count. Lottery "
            "draws are random and these results are not betting advice."
        ),
    }
    (OUT / "final_holdout_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "holdout_window": report["holdout_window"],
        "province_count": report["province_count"],
        "evaluation_province_draws": report["evaluation_province_draws"],
        "overall": report["overall"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
