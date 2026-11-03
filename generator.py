"""Tạo bộ số tham khảo từ điểm thống kê, không khẳng định xác suất thắng."""
from itertools import combinations
import pandas as pd

def make_sets(ranked, count=6, sets=5, even_min=2, even_max=4, sum_min=None, sum_max=None):
    nums = ranked["Số"].astype(int).tolist()
    if len(nums) < count:
        return []
    results = []
    # Tìm trong nhóm ứng viên đứng đầu; giới hạn để chạy nhanh.
    pool = nums[:min(22, len(nums))]
    for combo in combinations(pool, count):
        even = sum(n % 2 == 0 for n in combo)
        total = sum(combo)
        if not even_min <= even <= even_max:
            continue
        if sum_min is not None and total < sum_min:
            continue
        if sum_max is not None and total > sum_max:
            continue
        results.append((combo, total, even))
        if len(results) >= sets * 8:
            break
    results.sort(key=lambda x: (abs(x[2] - count / 2), x[1]))
    return [{"Bộ số": " - ".join(f"{n:02d}" for n in c), "Tổng": s, "Chẵn": e,
             "Lẻ": count - e} for c, s, e in results[:sets]]
