"""XSMN historical analytics and leakage-safe rolling backtests.

All candidate scores use only draws strictly before the target draw.
These are descriptive/ranking tools, not claims of predictive advantage.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
import math
import numpy as np
import pandas as pd

NUMBER_SPACE = range(100)


def prepare_xsmn_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "province", "number"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["province"] = df["province"].astype(str).str.strip()
    source = df["last2"] if "last2" in df.columns else df["number"].astype(str).str.replace(r"\D", "", regex=True).str[-2:]
    df["number2"] = pd.to_numeric(source, errors="coerce")
    df = df.dropna(subset=["date", "number2"])
    df["number2"] = df["number2"].astype(int)
    df = df[df["number2"].between(0, 99)]
    return df.sort_values(["province", "date"]).reset_index(drop=True)


def draw_history(frame: pd.DataFrame, province: str) -> list[tuple[pd.Timestamp, set[int]]]:
    df = prepare_xsmn_frame(frame)
    df = df[df["province"] == province]
    return [(d, set(g["number2"].astype(int))) for d, g in df.groupby("date", sort=True)]


def frequency_matrix(history, window: int | None = None) -> np.ndarray:
    selected = history[-window:] if window else history
    counts = np.zeros(100, dtype=float)
    for _, nums in selected:
        for value in nums:
            # Canonical history may contain digit strings (e.g. "08") as well as ints.
            # NumPy arrays require integer indices; normalize defensively at this boundary.
            try:
                n = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= n < 100:
                counts[n] += 1
    return counts


def gap_vector(history) -> np.ndarray:
    gaps = np.full(100, len(history), dtype=float)
    last = {}
    for i, (_, nums) in enumerate(history):
        for value in nums:
            try:
                n = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= n < 100:
                last[n] = i
    for n, i in last.items():
        gaps[n] = len(history) - 1 - i
    return gaps


def pair_frequency(history, top=30) -> pd.DataFrame:
    counts = Counter()
    for _, nums in history:
        counts.update(combinations(sorted(nums), 2))
    return pd.DataFrame(
        [{"Cặp": f"{a:02d}-{b:02d}", "Số kỳ cùng xuất hiện": count}
         for (a, b), count in counts.most_common(top)],
        columns=["Cặp", "Số kỳ cùng xuất hiện"],
    )


def distribution_report(history) -> dict:
    if not history:
        return {"draws": 0, "observations": 0}
    totals, evens, unique_counts = [], [], []
    all_values = []
    for _, nums in history:
        values = sorted(nums)
        if not values:
            continue
        totals.append(sum(values))
        evens.append(sum(n % 2 == 0 for n in values))
        unique_counts.append(len(values))
        all_values.extend(values)
    return {
        "draws": len(history),
        "observations": len(all_values),
        "mean_sum": round(float(np.mean(totals)), 3) if totals else None,
        "median_sum": round(float(np.median(totals)), 3) if totals else None,
        "mean_even_per_draw": round(float(np.mean(evens)), 3) if evens else None,
        "mean_unique_per_draw": round(float(np.mean(unique_counts)), 3) if unique_counts else None,
        "number_frequency": frequency_matrix(history).astype(int).tolist(),
        "gap": gap_vector(history).astype(int).tolist(),
    }


def _rank_scores(history, method: str) -> np.ndarray:
    n = len(history)
    if n == 0:
        return np.zeros(100)
    if method == "freq_30":
        return frequency_matrix(history, 30)
    if method == "freq_90":
        return frequency_matrix(history, 90)
    if method == "freq_365":
        return frequency_matrix(history, 365)
    if method == "gap":
        return gap_vector(history)
    if method == "ewma":
        scores = np.zeros(100, dtype=float)
        # Half-life of 30 station draws; only prior draws are included.
        decay = math.exp(math.log(0.5) / 30.0)
        for _, nums in history:
            scores *= decay
            for value in nums:
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    continue
                if 0 <= number < 100:
                    scores[number] += 1.0
        return scores
    if method == "blend":
        f30 = frequency_matrix(history, 30)
        f90 = frequency_matrix(history, 90)
        g = gap_vector(history)
        def norm(x):
            maximum = float(x.max())
            return x / maximum if maximum else x
        return 0.45 * norm(f30) + 0.35 * norm(f90) + 0.20 * norm(g)
    raise ValueError(f"Unknown method: {method}")


def rank_numbers(history, method="blend", top_k=10) -> pd.DataFrame:
    scores = _rank_scores(history, method)
    order = sorted(range(100), key=lambda x: (-scores[x], x))[:top_k]
    return pd.DataFrame([{"Số": f"{n:02d}", "Điểm": round(float(scores[n]), 6)} for n in order])


def rolling_backtest(frame: pd.DataFrame, province: str, methods=None,
                     top_k: int = 10, min_history: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward evaluation: prediction at date t uses only dates < t."""
    methods = methods or ["freq_30", "freq_90", "freq_365", "gap", "ewma", "blend"]
    history = draw_history(frame, province)
    rows = []
    for idx in range(min_history, len(history)):
        target_date, actual = history[idx]
        prior = history[:idx]
        if not actual:
            continue
        for method in methods:
            scores = _rank_scores(prior, method)
            ranked = sorted(range(100), key=lambda x: (-scores[x], x))
            selected = set(ranked[:top_k])
            hits = len(selected & actual)
            # Under a uniform random top-k baseline over 100 values.
            expected = top_k * len(actual) / 100.0
            rows.append({
                "date": target_date.strftime("%Y-%m-%d"),
                "method": method,
                "history_draws": len(prior),
                "top_k": top_k,
                "actual_unique": len(actual),
                "hits": hits,
                "hit_rate": hits / top_k,
                "random_expected_hits": expected,
                "lift_vs_random": hits / expected if expected else np.nan,
            })
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, pd.DataFrame(columns=["method", "tested_draws", "mean_hits", "mean_hit_rate", "mean_random_expected", "lift_vs_random"])
    summary = detail.groupby("method", as_index=False).agg(
        tested_draws=("date", "nunique"),
        mean_hits=("hits", "mean"),
        mean_hit_rate=("hit_rate", "mean"),
        mean_random_expected=("random_expected_hits", "mean"),
        total_hits=("hits", "sum"),
    )
    summary["lift_vs_random"] = summary["mean_hits"] / summary["mean_random_expected"].replace(0, np.nan)
    for col in ["mean_hits", "mean_hit_rate", "mean_random_expected", "lift_vs_random"]:
        summary[col] = summary[col].round(4)
    return detail, summary.sort_values("mean_hits", ascending=False).reset_index(drop=True)
