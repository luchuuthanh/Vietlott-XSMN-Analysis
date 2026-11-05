"""Run expanding-window out-of-sample backtests for both Vietlott games."""
import argparse
import csv
import json
from pathlib import Path

from analytics import frequency_table, gap_table, score_candidates
from generator import make_sets
from ticket_checker import rolling_backtest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "vietlott"
OUT = ROOT / "reports" / "rolling_backtest"


def load_draws(path, game):
    universe = 55 if game == "POWER655" else 45
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            result = obj.get("result")
            expected = 7 if game == "POWER655" else 6
            if not isinstance(result, list) or len(result) != expected:
                raise ValueError(f"{path}:{line_no}: expected {expected} result values")
            main = [int(x) for x in result[:6]]
            special = int(result[6]) if game == "POWER655" else None
            if len(set(main)) != 6 or any(n < 1 or n > universe for n in main):
                raise ValueError(f"{path}:{line_no}: invalid main numbers {main}")
            if special is not None and (special < 1 or special > universe or special in main):
                raise ValueError(f"{path}:{line_no}: invalid special number {special}")
            rows.append({
                "draw_id": str(obj["id"]).zfill(5),
                "date": str(obj["date"]),
                "main_numbers": sorted(main),
                "special": special,
            })
    rows.sort(key=lambda x: (x["date"], int(x["draw_id"])))
    ids = [int(row["draw_id"]) for row in rows]
    if ids != list(range(ids[0], ids[-1] + 1)):
        raise ValueError(f"{path}: draw IDs are not continuous")
    if any(rows[i]["date"] > rows[i + 1]["date"] for i in range(len(rows) - 1)):
        raise ValueError(f"{path}: dates are not chronological")
    return rows


def candidate_builder(history, universe, tickets_per_draw):
    flat = [n for draw in history for n in draw["main_numbers"]]
    draws = [draw["main_numbers"] for draw in history]
    freq = frequency_table(flat, universe)
    gaps = gap_table(draws, universe)
    ranked = score_candidates(freq, gaps, universe, universe)
    generated = make_sets(ranked, count=6, sets=tickets_per_draw)
    return [[int(part.strip()) for part in item["Bộ số"].split("-")] for item in generated]


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_game(game, filename, universe, min_history, tickets_per_draw):
    draws = load_draws(DATA / filename, game)
    if len(draws) <= min_history:
        raise ValueError(f"{game}: only {len(draws)} draws; need more than {min_history}")
    builder = lambda history: candidate_builder(history, universe, tickets_per_draw)
    summary, details = rolling_backtest(
        draws, builder, min_history=min_history, history_window=None, game=game
    )
    total = summary["total_tickets"]
    prize_tickets = total - summary["no_prize"]
    row = {
        "game": game,
        "data_draws": len(draws),
        "first_draw_id": draws[0]["draw_id"],
        "first_date": draws[0]["date"],
        "last_draw_id": draws[-1]["draw_id"],
        "last_date": draws[-1]["date"],
        "warmup_draws": min_history,
        "tickets_per_draw_requested": tickets_per_draw,
        "tested_draws": summary["tested_draws"],
        "total_tickets": total,
        "jackpot_1": summary["jackpot1"],
        "jackpot": summary["jackpot"],
        "jackpot_2": summary["jackpot2"],
        "first_prize": summary["first"],
        "second_prize": summary["second"],
        "third_prize": summary["third"],
        "no_prize": summary["no_prize"],
        "tickets_with_any_prize": prize_tickets,
        "any_prize_rate_pct": round(prize_tickets / total * 100, 4) if total else 0,
    }
    for item in details:
        item["game"] = game
    return row, details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-history", type=int, default=200)
    parser.add_argument("--tickets-per-draw", type=int, default=5)
    args = parser.parse_args()
    if args.min_history < 1 or args.tickets_per_draw < 1:
        parser.error("--min-history and --tickets-per-draw must be positive")
    OUT.mkdir(parents=True, exist_ok=True)
    configs = [
        ("POWER655", "power655.jsonl", 55),
        ("MEGA645", "power645.jsonl", 45),
    ]
    summaries, all_details = [], []
    for game, filename, universe in configs:
        summary, details = run_game(
            game, filename, universe, args.min_history, args.tickets_per_draw
        )
        summaries.append(summary)
        all_details.extend(details)
        print(
            f"{game}: {summary['data_draws']} draws | "
            f"{summary['tested_draws']} tested | {summary['total_tickets']} tickets | "
            f"Jackpot1={summary['jackpot_1']} Jackpot={summary['jackpot']} "
            f"Jackpot2={summary['jackpot_2']} G1={summary['first_prize']} "
            f"G2={summary['second_prize']} G3={summary['third_prize']}"
        )
    write_csv(OUT / "summary.csv", summaries)
    write_csv(OUT / "draw_details.csv", all_details)
    (OUT / "summary.json").write_text(
        json.dumps(
            {"method": "expanding-window; each target draw uses only all prior draws",
             "min_history": args.min_history,
             "tickets_per_draw": args.tickets_per_draw,
             "games": summaries},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"Reports written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
