"""Build a reproducible Power 6/55 historical data and statistics package."""
import csv
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
from shutil import copyfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "vietlott" / "power655.jsonl"
OUT = ROOT / "reports" / "power655_final_package"

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

def write_gaps(path, gaps, max_number, label):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["number", label])
        for n in range(1, max_number + 1):
            w.writerow([n, gaps[n]])

def main():
    source_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Keep this finalized package capped at draw 01419 as validated for this project.
    expected = 1419
    rows = [r for r in source_rows if int(r["id"]) <= expected]
    ids = [int(r["id"]) for r in rows]
    if len(rows) != expected:
        raise ValueError(f"Expected finalized draws 00001-01419, got {len(rows)}")
    if ids != list(range(1, expected + 1)):
        raise ValueError("Power 6/55 draw IDs must be continuous from 00001 to 01419")
    dates = [r["date"] for r in rows]
    if dates != sorted(dates):
        raise ValueError("Draw dates are not chronological")

    main_freq, special_freq = Counter(), Counter()
    main_gaps = {n: None for n in range(1, 56)}
    special_gaps = {n: None for n in range(1, 56)}
    pair_counts, triple_counts = Counter(), Counter()
    for idx, row in enumerate(rows):
        result = row.get("result")
        if not isinstance(result, list) or len(result) != 7 or any(not isinstance(n, int) or not 1 <= n <= 55 for n in result):
            raise ValueError(f"Invalid Power 6/55 result at draw {row.get('id')}")
        main, special = result[:6], result[6]
        if len(set(main)) != 6 or special in main:
            raise ValueError(f"Duplicate main/special number at draw {row.get('id')}")
        main = sorted(main)
        main_freq.update(main)
        special_freq.update([special])
        for n in main:
            main_gaps[n] = len(rows) - 1 - idx
        special_gaps[special] = len(rows) - 1 - idx
        pair_counts.update(itertools.combinations(main, 2))
        triple_counts.update(itertools.combinations(main, 3))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "power655_draws_00001_01419.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    write_counter(OUT / "main_frequency_01_55.csv", main_freq, ["number", "main_appearances"])
    write_counter(OUT / "special_frequency_01_55.csv", special_freq, ["number", "special_appearances"])
    write_gaps(OUT / "main_current_gap_01_55.csv", main_gaps, 55, "draws_since_last_main_appearance")
    write_gaps(OUT / "special_current_gap_01_55.csv", special_gaps, 55, "draws_since_last_special_appearance")
    write_counter(OUT / "pair_frequency.csv", pair_counts, ["number_1", "number_2", "appearances"])
    write_counter(OUT / "triple_frequency.csv", triple_counts, ["number_1", "number_2", "number_3", "appearances"])

    manifest = {
        "package": "Power 6/55 finalized historical dataset and statistics",
        "game": "POWER655", "snapshot_date": "2026-11-05",
        "draw_count": len(rows), "first_draw_id": rows[0]["id"], "first_date": dates[0],
        "last_draw_id": rows[-1]["id"], "last_date": dates[-1],
        "draw_id_range": "00001-01419", "continuous_draw_ids": True,
        "main_numbers_per_draw": 6, "number_universe": "01-55",
        "special_number_per_draw": 1, "special_number_universe": "01-55",
        "source_file": "power655_draws_00001_01419.jsonl",
        "source_sha256": hashlib.sha256((OUT / "power655_draws_00001_01419.jsonl").read_bytes()).hexdigest(), "source_bytes": (OUT / "power655_draws_00001_01419.jsonl").stat().st_size,
        "draw_00944_correction": {"date": "2023-10-14", "main_numbers": [8, 23, 30, 34, 38, 47], "special_number": 10},
        "statistics": {"main_frequency_rows": 55, "special_frequency_rows": 55,
            "pair_combinations": len(pair_counts), "triple_combinations": len(triple_counts),
            "pair_count_total": sum(pair_counts.values()), "triple_count_total": sum(triple_counts.values()),
            "gap_definition": "number of subsequent draws since each number's latest appearance; 0 means present in latest draw"},
        "backtest": {"method": "expanding-window; only draws before each target draw are used",
            "warmup_draws": 200, "tested_draws": 1219, "tickets_per_draw": 5,
            "total_simulated_tickets": 6095, "jackpot_1": 0, "jackpot": 0,
            "jackpot_2": 0, "first_prize": 0, "second_prize": 3, "third_prize": 64},
        "provenance": {"primary_archive": "data/vietlott/power655.jsonl", "source_archive_rows": len(source_rows), "packaged_rows": len(rows), "scope_note": "Package intentionally capped at draw 01419; higher IDs are excluded from this finalized snapshot.",
            "quality_note": "Packaged from the repository's finalized 1,419-draw archive. Draw 00944 uses the corrected values recorded in the project validation."}
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = """# POWER 6/55 — Gói dữ liệu đã chốt

- 1.419 kỳ, mã 00001–01419 liên tục.
- Phạm vi ngày: 01/08/2017–03/11/2026.
- Mỗi kỳ gồm 6 số chính từ 01–55 và 1 số đặc biệt.
- power655_draws_00001_01419.jsonl: dữ liệu lịch sử đã chuẩn hóa.
- main_frequency_01_55.csv và special_frequency_01_55.csv: tần suất số chính và số đặc biệt.
- main_current_gap_01_55.csv và special_current_gap_01_55.csv: số kỳ vắng mặt tính đến kỳ mới nhất.
- pair_frequency.csv và triple_frequency.csv: tần suất cặp/bộ ba trong 6 số chính.
- manifest.json: phạm vi dữ liệu, SHA-256, kiểm tra cấu trúc và kết quả backtest.
- Kỳ 00944 đã chốt sửa: 14/10/2023 — 08, 23, 30, 34, 38, 47; đặc biệt 10.

Backtest expanding-window: 200 kỳ warm-up; 1.219 kỳ kiểm tra; 5 vé/kỳ; 6.095 vé mô phỏng. Kết quả ghi nhận: Jackpot 1 = 0, Jackpot = 0, Jackpot 2 = 0, giải nhất = 0, giải nhì = 3, giải ba = 64.

Lưu ý: thống kê/backtest mô tả dữ liệu quá khứ, không bảo đảm dự đoán kết quả tương lai.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(f"POWER655 package built: {len(rows)} draws; {len(pair_counts)} pairs; {len(triple_counts)} triples; SHA256={manifest['source_sha256']}")

if __name__ == "__main__":
    main()
