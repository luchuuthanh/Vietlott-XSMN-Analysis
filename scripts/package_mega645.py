"""Build a reproducible, self-contained Mega 6/45 data and statistics package."""
import csv
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
from shutil import copyfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vietlott"
OUT = ROOT / "reports" / "mega645_final_package"
SOURCE = DATA / "power645.jsonl"
BACKFILL = DATA / "mega645_backfill_00001_00197.jsonl"

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_counter(path, counter, columns):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for key, count in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
            values = key if isinstance(key, tuple) else (key,)
            w.writerow([*values, count])

def main():
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1584:
        raise ValueError(f"Expected 1,584 Mega 6/45 draws, got {len(rows)}")
    ids = [int(r["id"]) for r in rows]
    if ids != list(range(1, 1585)):
        raise ValueError("Mega 6/45 draw IDs must be continuous from 00001 to 01584")
    dates = [r["date"] for r in rows]
    if dates != sorted(dates):
        raise ValueError("Draw dates are not chronological")
    frequency = Counter()
    gaps = {n: None for n in range(1, 46)}
    pair_counts, triple_counts = Counter(), Counter()
    for idx, row in enumerate(rows):
        nums = row.get("result")
        if not isinstance(nums, list) or len(nums) != 6 or len(set(nums)) != 6 or any(not isinstance(n, int) or n < 1 or n > 45 for n in nums):
            raise ValueError(f"Invalid Mega 6/45 result at draw {row.get('id')}")
        nums = sorted(nums)
        frequency.update(nums)
        for n in nums:
            gaps[n] = len(rows) - 1 - idx
        pair_counts.update(itertools.combinations(nums, 2))
        triple_counts.update(itertools.combinations(nums, 3))

    OUT.mkdir(parents=True, exist_ok=True)
    copyfile(SOURCE, OUT / "mega645_draws_00001_01584.jsonl")
    copyfile(BACKFILL, OUT / "mega645_original_backfill_00001_00197.jsonl")
    write_counter(OUT / "frequency_01_45.csv", frequency, ["number", "appearances"])
    with (OUT / "current_gap_01_45.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["number", "draws_since_last_appearance"])
        for n in range(1, 46): w.writerow([n, gaps[n]])
    write_counter(OUT / "pair_frequency.csv", pair_counts, ["number_1", "number_2", "appearances"])
    write_counter(OUT / "triple_frequency.csv", triple_counts, ["number_1", "number_2", "number_3", "appearances"])

    manifest = {
        "package": "Mega 6/45 finalized historical dataset and statistics",
        "game": "MEGA645", "snapshot_date": "2026-11-05",
        "draw_count": len(rows), "first_draw_id": rows[0]["id"], "first_date": dates[0],
        "last_draw_id": rows[-1]["id"], "last_date": dates[-1],
        "draw_id_range": "00001-01584", "continuous_draw_ids": True,
        "main_numbers_per_draw": 6, "number_universe": "01-45",
        "special_number": None, "bonus_number": None,
        "source_file": "mega645_draws_00001_01584.jsonl",
        "source_sha256": sha256(SOURCE), "source_bytes": SOURCE.stat().st_size,
        "backfill_file": "mega645_original_backfill_00001_00197.jsonl",
        "backfill_draw_range": "00001-00197", "backfill_sha256": sha256(BACKFILL),
        "backfill_note": "Original immutable historical backfill; source CSV includes Vietlott source-page/PDF links. Not every row was independently re-checked against official PDFs.",
        "statistics": {"frequency_rows": 45, "pair_combinations": len(pair_counts),
            "triple_combinations": len(triple_counts), "pair_count_total": sum(pair_counts.values()),
            "triple_count_total": sum(triple_counts.values()),
            "gap_definition": "number of subsequent draws since each number's latest appearance; 0 means present in latest draw"},
        "backtest": {"method": "expanding-window; only draws before each target draw are used",
            "warmup_draws": 200, "tested_draws": 1384, "tickets_per_draw": 5,
            "total_simulated_tickets": 6920, "jackpot": 0, "first_prize": 0,
            "second_prize": 3, "third_prize": 153},
        "provenance": {"primary_mirror": "https://github.com/vietvudanh/vietlott-data",
            "historical_backfill": "https://github.com/NhanAZ-Data/vietlott-research/blob/main/datasets/draws/mega645/all.csv",
            "quality_note": "Merged archive from two sources; not all historical rows independently verified against official Vietlott PDFs."}
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = """# MEGA 6/45 — Gói dữ liệu đã chốt

- 1.584 kỳ, mã 00001–01584 liên tục.
- Phạm vi ngày: 20/07/2016–04/11/2026.
- Mỗi kỳ gồm đúng 6 số chính từ 01–45; không có số đặc biệt/số bonus.
- mega645_draws_00001_01584.jsonl: dữ liệu hợp nhất đã chuẩn hóa.
- mega645_original_backfill_00001_00197.jsonl: bản backfill gốc được giữ riêng để truy vết.
- frequency_01_45.csv, current_gap_01_45.csv, pair_frequency.csv, triple_frequency.csv: thống kê toàn bộ lịch sử.
- manifest.json: phạm vi, kiểm tra liên tục mã kỳ, SHA-256, nguồn và kết quả backtest.
- Backtest expanding-window: bỏ 200 kỳ đầu làm warm-up; 1.384 kỳ kiểm tra; 5 vé/kỳ; tổng 6.920 vé. Kết quả: Jackpot 0, giải nhất 0, giải nhì 3, giải ba 153.

Giới hạn nguồn: 197 kỳ đầu lấy từ NhanAZ-Data/vietlott-research (CSV có liên kết nguồn trang/PDF Vietlott); các kỳ sau lấy từ vietvudanh/vietlott-data. Không khẳng định mọi dòng đã được đối chiếu độc lập với PDF chính thức. Thống kê lịch sử chỉ để tham khảo, không bảo đảm dự đoán kết quả.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(f"MEGA645 package built: {len(rows)} draws; {len(pair_counts)} pairs; {len(triple_counts)} triples; SHA256={manifest['source_sha256']}")

if __name__ == "__main__":
    main()
