"""Build isolated Lotto 5/35 data, statistics and leakage-free backtest package."""
import csv, hashlib, json, sys
from collections import Counter
from itertools import combinations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lotto535_analyzer import load_draws, frequency, current_gaps, rolling_backtest
SOURCE = ROOT / "data/vietlott/power535.jsonl"
OUT = ROOT / "reports/power535_final_package"

def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Backtest rows can contain different prize-tier keys. Build a stable union
    # of all fields so later rows never fail with "dict contains fields not in fieldnames".
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def main():
    draws = load_draws(SOURCE)
    pair, triple = Counter(), Counter()
    for d in draws:
        pair.update(combinations(d["main_numbers"], 2))
        triple.update(combinations(d["main_numbers"], 3))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "power535_draws.jsonl").write_bytes(SOURCE.read_bytes())
    write_csv(OUT / "main_frequency_01_35.csv", frequency(draws))
    write_csv(OUT / "special_frequency_01_12.csv", frequency(draws, "special", 12))
    write_csv(OUT / "main_current_gap_01_35.csv", current_gaps(draws))
    write_csv(OUT / "special_current_gap_01_12.csv", current_gaps(draws, "special", 12))
    write_csv(OUT / "pair_frequency.csv", [{"number_1":a,"number_2":b,"appearances":n} for (a,b),n in pair.most_common()])
    write_csv(OUT / "triple_frequency.csv", [{"number_1":a,"number_2":b,"number_3":c,"appearances":n} for (a,b,c),n in triple.most_common()])
    bt = rolling_backtest(draws, warmup=200, tickets_per_draw=5)
    write_csv(OUT / "backtest_draw_details.csv", bt["details"])
    (OUT / "backtest_summary.json").write_text(json.dumps({k:v for k,v in bt.items() if k!="details"}, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    manifest = {"game":"LOTTO535","draw_count":len(draws),"first_draw_id":draws[0]["draw_id"],"first_date":draws[0]["date"],
      "last_draw_id":draws[-1]["draw_id"],"last_date":draws[-1]["date"],"continuous_ids":True,
      "main_numbers":"5 distinct values from 01-35","special_number":"1 value from 01-12, drawn/validated separately; numeric overlap with main group is allowed",
      "source_file":"power535_draws.jsonl","source_sha256":digest,"source_bytes":SOURCE.stat().st_size,
      "statistics":{"main_frequency_rows":35,"special_frequency_rows":12,"pair_combinations":len(pair),"triple_combinations":len(triple)},
      "backtest":{k:v for k,v in bt.items() if k!="details"},
      "provenance":"Third-party vietvudanh/vietlott-data mirror; verify material results against official Vietlott publications."}
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"README.md").write_text(f"""# Lotto 5/35 — gói dữ liệu và phân tích riêng

- {len(draws):,} kỳ, mã {draws[0]['draw_id']}–{draws[-1]['draw_id']}, {draws[0]['date']} đến {draws[-1]['date']}.
- Mỗi kỳ gồm 5 số chính khác nhau 01–35 và 1 số đặc biệt 01–12.
- Số đặc biệt thuộc nhóm riêng; có thể trùng giá trị với số chính.
- Thống kê số chính và số đặc biệt được tính tách biệt; cặp/bộ ba chỉ tính trong 5 số chính.
- Backtest expanding-window: {bt['warmup_draws']} kỳ warm-up, {bt['tested_draws']} kỳ ngoài mẫu, {bt['total_tickets']} vé.
- Nguồn dữ liệu là bản mirror bên thứ ba; đối chiếu kết quả quan trọng với Vietlott chính thức.
- Thống kê/backtest chỉ mô tả quá khứ, không bảo đảm kết quả tương lai.
""",encoding="utf-8")
    print(f"POWER535 package built: {len(draws)} draws; {len(pair)} pairs; {len(triple)} triples; backtest={bt['tested_draws']} draws; sha256={digest}")
if __name__=="__main__": main()
