"""Thống kê mô tả cho Vietlott và XSMN; không phải mô hình dự đoán."""
from collections import Counter
from itertools import combinations
import pandas as pd

def _clean(values):
    out = []
    for value in values:
        try:
            n = int(value)
            if n >= 0:
                out.append(n)
        except (TypeError, ValueError):
            continue
    return out

def frequency_table(values, universe):
    counts = Counter(_clean(values))
    df = pd.DataFrame({"Số": range(1, universe + 1)})
    df["Số lần"] = df["Số"].map(counts).fillna(0).astype(int)
    total = int(df["Số lần"].sum())
    df["Tỷ lệ (%)"] = (df["Số lần"] / total * 100).round(2) if total else 0
    return df.sort_values(["Số lần", "Số"], ascending=[False, True]).reset_index(drop=True)

def gap_table(draws, universe):
    last = {}
    for idx, draw in enumerate(draws):
        for n in set(_clean(draw)):
            if 1 <= n <= universe:
                last[n] = idx
    size = len(draws)
    rows = [{"Số": n, "Số kỳ vắng": size - 1 - last[n] if n in last else size,
             "Đã xuất hiện": n in last} for n in range(1, universe + 1)]
    return pd.DataFrame(rows).sort_values(["Số kỳ vắng", "Số"], ascending=[False, True])

def pair_table(draws, top=30):
    counts = Counter()
    for draw in draws:
        nums = sorted(set(_clean(draw)))
        counts.update(combinations(nums, 2))
    return pd.DataFrame([{"Cặp": f"{a:02d}-{b:02d}", "Số lần cùng xuất hiện": c}
                         for (a, b), c in counts.most_common(top)],
                        columns=["Cặp", "Số lần cùng xuất hiện"])

def draw_metrics(draws):
    rows = []
    for i, draw in enumerate(draws):
        nums = sorted(set(_clean(draw)))
        rows.append({"Kỳ": i + 1, "Số lượng": len(nums), "Tổng": sum(nums),
                     "Chẵn": sum(n % 2 == 0 for n in nums),
                     "Lẻ": sum(n % 2 for n in nums),
                     "Delta": max(nums) - min(nums) if nums else 0})
    return pd.DataFrame(rows)

def score_candidates(freq_df, gap_df, universe, count, recent_draws=None):
    """Điểm cân bằng tần suất + độ vắng; chỉ dùng để xếp hạng tham khảo."""
    f = freq_df.set_index("Số")["Số lần"]
    g = gap_df.set_index("Số")["Số kỳ vắng"]
    fmax = max(float(f.max()), 1.0)
    gmax = max(float(g.max()), 1.0)
    rows = []
    for n in range(1, universe + 1):
        score = 0.55 * (float(f.get(n, 0)) / fmax) + 0.45 * (float(g.get(n, 0)) / gmax)
        rows.append({"Số": n, "Điểm tham khảo": round(score * 100, 2),
                     "Tần suất": int(f.get(n, 0)), "Kỳ vắng": int(g.get(n, 0))})
    return pd.DataFrame(rows).sort_values(["Điểm tham khảo", "Số"], ascending=[False, True]).head(count)
