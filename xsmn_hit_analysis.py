"""Per-prize walk-forward analysis with method-level hit attribution."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

METHODS = ("freq_30", "freq_90", "freq_365", "gap", "ewma", "blend")
METHOD_LABELS = {
    "freq_30": "Tần suất 30 kỳ",
    "freq_90": "Tần suất 90 kỳ",
    "freq_365": "Tần suất 365 kỳ",
    "gap": "Số ít xuất hiện",
    "ewma": "EWMA",
    "blend": "Kết hợp",
}
SCOPES = ("G8", "G7", "ĐB", "Tất cả giải")


def _digits(value):
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return "".join(ch for ch in s if ch.isdigit())


def _scope_mask(df, scope):
    prize = df["prize"].astype(str).str.strip().str.upper()
    if scope == "Tất cả giải":
        return pd.Series(True, index=df.index)
    if scope == "ĐB":
        return prize.isin({"ĐB", "DB", "GĐB"})
    return prize.eq(scope)


def build_scope_history(frame, station, scope):
    required = {"date", "province", "prize", "number"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Thiếu cột dữ liệu: {sorted(required - set(frame.columns))}")
    df = frame[frame["province"].astype(str).eq(str(station))].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])
    df = df[_scope_mask(df, scope)].copy()
    source = df["last2"] if "last2" in df.columns else df["number"]
    df["_n"] = source.map(_digits).str[-2:].str.zfill(2)
    df = df[df["_n"].str.fullmatch(r"\d{2}", na=False)]
    grouped = []
    for day, group in df.groupby("date", sort=True):
        grouped.append((day, set(group["_n"].astype(int))))
    return grouped


def _score_vector(history, method):
    scores = np.zeros(100, dtype=float)
    if not history:
        return scores
    if method.startswith("freq_"):
        window = int(method.split("_")[1])
        for _, numbers in history[-window:]:
            for n in numbers:
                scores[int(n)] += 1
        return scores
    if method == "gap":
        last_seen = np.full(100, -1, dtype=int)
        for idx, (_, numbers) in enumerate(history):
            for n in numbers:
                last_seen[int(n)] = idx
        return np.where(last_seen < 0, len(history), len(history) - 1 - last_seen).astype(float)
    if method == "ewma":
        decay = math.exp(math.log(0.5) / 30.0)
        for _, numbers in history:
            scores *= decay
            for n in numbers:
                scores[int(n)] += 1.0
        return scores
    if method == "blend":
        components = []
        for method_name in ("freq_30", "freq_90", "gap"):
            vec = _score_vector(history, method_name)
            maximum = float(vec.max())
            components.append(vec / maximum if maximum else vec)
        return 0.45 * components[0] + 0.35 * components[1] + 0.20 * components[2]
    raise ValueError(f"Unknown method: {method}")


def analyze_scope(frame, station, scope, top_k=10, min_history=30, test_periods=180):
    """Each target draw is ranked using strictly earlier draws for this scope."""
    history = build_scope_history(frame, station, scope)
    if len(history) <= min_history:
        empty = pd.DataFrame()
        return empty, empty, empty, len(history)

    start_idx = max(min_history, len(history) - max(1, int(test_periods)))
    detail_rows, attribution_rows = [], []
    for idx in range(start_idx, len(history)):
        target_date, actual = history[idx]
        prior = history[:idx]
        method_picks = {}
        method_ranks = {}
        feature_scores = {method: _score_vector(prior, method) for method in METHODS}
        for method in METHODS:
            scores = feature_scores[method]
            ordered = sorted(range(100), key=lambda n: (-scores[n], n))
            picks = ordered[:int(top_k)]
            method_picks[method] = set(picks)
            method_ranks[method] = {n: rank + 1 for rank, n in enumerate(picks)}
            hits = sorted(set(picks) & actual)
            expected = int(top_k) * len(actual) / 100.0
            detail_rows.append({
                "Ngày kết quả": target_date.strftime("%d/%m/%Y"),
                "Phương pháp": METHOD_LABELS[method],
                "Số đã lọc": " · ".join(f"{n:02d}" for n in picks),
                "Số trúng": " · ".join(f"{n:02d}" for n in hits) if hits else "—",
                "Số lọc nhưng không trúng": " · ".join(f"{n:02d}" for n in sorted(set(picks) - actual)) or "—",
                "Lượt trúng": len(hits),
                "Số kỳ lịch sử": len(prior),
                "Kỳ vọng ngẫu nhiên": expected,
                "_method": method,
                "_hits": len(hits),
                "_expected": expected,
            })
        for number in sorted(actual):
            picked_by = [m for m in METHODS if number in method_picks[m]]
            attribution_rows.append({
                "Ngày kết quả": target_date.strftime("%d/%m/%Y"),
                "Số thực tế": f"{number:02d}",
                "Nằm trong phương pháp lọc": ", ".join(METHOD_LABELS[m] for m in picked_by) if picked_by else "Không phương pháp nào",
                "Thứ hạng theo phương pháp": ", ".join(
                    f"{METHOD_LABELS[m]}: #{method_ranks[m][number]}"
                    for m in picked_by
                ) if picked_by else "—",
                "Số phương pháp cùng chọn": len(picked_by),
                "Tần suất 30 kỳ trước": int(feature_scores["freq_30"][number]),
                "Tần suất 90 kỳ trước": int(feature_scores["freq_90"][number]),
                "Tần suất 365 kỳ trước": int(feature_scores["freq_365"][number]),
                "Số kỳ vắng trước đó": int(feature_scores["gap"][number]),
                "Điểm EWMA trước đó": round(float(feature_scores["ewma"][number]), 4),
                "Điểm kết hợp trước đó": round(float(feature_scores["blend"][number]), 4),
                "_hit_methods": "|".join(picked_by),
            })

    detail = pd.DataFrame(detail_rows)
    summary_rows = []
    for method in METHODS:
        rows = detail[detail["_method"].eq(method)]
        total_hits = int(rows["_hits"].sum())
        total_expected = float(rows["_expected"].sum())
        selections = int(top_k) * len(rows)
        summary_rows.append({
            "Phương pháp": METHOD_LABELS[method],
            "Số kỳ kiểm tra": len(rows),
            "Tổng lượt trúng": total_hits,
            "Kỳ có ít nhất 1 số trúng": int((rows["_hits"] > 0).sum()),
            "Tỷ lệ trúng trên lượt chọn (%)": round(100 * total_hits / selections, 3) if selections else 0,
            "Kỳ vọng ngẫu nhiên": round(total_expected, 3),
            "So với ngẫu nhiên (lần)": round(total_hits / total_expected, 3) if total_expected else None,
            "_method": method,
        })
    summary = pd.DataFrame(summary_rows).sort_values(
        ["Tổng lượt trúng", "Tỷ lệ trúng trên lượt chọn (%)"], ascending=False
    ).reset_index(drop=True)
    attribution = pd.DataFrame(attribution_rows)
    return summary, detail, attribution, len(history)
