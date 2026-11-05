"""Isolated Lotto 5/35 analysis and ticket validation. Never imports 6/55 or 6/45 data."""
from collections import Counter
from itertools import combinations
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "vietlott" / "power535.jsonl"

def load_draws(path=DATA):
    rows = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        result = obj.get("result")
        if (not isinstance(result, list) or len(result) != 6
                or any(type(n) is not int for n in result)):
            raise ValueError(f"{path}:{line_no}: expected 5 main integers plus special")
        main, special = result[:5], result[5]
        if len(set(main)) != 5 or any(n < 1 or n > 35 for n in main):
            raise ValueError(f"{path}:{line_no}: main numbers must be 5 distinct values in 1..35")
        if not 1 <= special <= 12:
            raise ValueError(f"{path}:{line_no}: special number must be in 1..12")
        rows.append({"draw_id": str(obj["id"]).zfill(5), "date": str(obj["date"])[:10],
                     "main_numbers": sorted(main), "special": special})
    if not rows:
        raise ValueError("Lotto 5/35 archive is empty")
    rows.sort(key=lambda x: (x["date"], int(x["draw_id"])))
    ids = [int(x["draw_id"]) for x in rows]
    if ids != list(range(ids[0], ids[-1] + 1)):
        raise ValueError("Lotto 5/35 draw IDs are not continuous")
    if len({x["draw_id"] for x in rows}) != len(rows):
        raise ValueError("Lotto 5/35 duplicate draw IDs")
    return rows

def frequency(draws, field="main_numbers", universe=35):
    c = Counter(n for d in draws for n in (d[field] if field == "main_numbers" else [d[field]]))
    return [{"number": n, "appearances": c[n]} for n in range(1, universe + 1)]

def current_gaps(draws, field="main_numbers", universe=35):
    last = {}
    for i, d in enumerate(draws):
        values = d[field] if field == "main_numbers" else [d[field]]
        for n in values:
            last[n] = i
    return [{"number": n, "draws_since_last": len(draws)-1-last[n] if n in last else len(draws)}
            for n in range(1, universe+1)]

def rank_numbers(draws, field="main_numbers", universe=35):
    freq = {r["number"]: r["appearances"] for r in frequency(draws, field, universe)}
    gaps = {r["number"]: r["draws_since_last"] for r in current_gaps(draws, field, universe)}
    fmax, gmax = max(max(freq.values()), 1), max(max(gaps.values()), 1)
    return sorted(range(1, universe+1),
                  key=lambda n: (-(0.55*freq[n]/fmax + 0.45*gaps[n]/gmax), n))

def generate_tickets(history, count=5):
    """Rank main and special groups independently; special is not a sixth main ball."""
    main_rank = rank_numbers(history, "main_numbers", 35)
    special_rank = rank_numbers(history, "special", 12)
    pool = main_rank[:22]
    candidates = []
    for combo in combinations(pool, 5):
        evens = sum(n % 2 == 0 for n in combo)
        if 2 <= evens <= 3:
            candidates.append(combo)
    candidates.sort(key=lambda c: (abs(sum(n % 2 == 0 for n in c)-2.5), sum(c), c))
    if not candidates:
        candidates = list(combinations(main_rank[:10], 5))
    return [{"main_numbers": list(combo), "special": special_rank[i % len(special_rank)]}
            for i, combo in enumerate(candidates[:count])]

def classify_ticket(main_ticket, special_ticket, draw_main, draw_special):
    ticket = tuple(sorted(set(int(n) for n in main_ticket)))
    actual = set(int(n) for n in draw_main)
    if len(ticket) != 5 or any(n < 1 or n > 35 for n in ticket):
        raise ValueError("A Lotto 5/35 ticket needs 5 distinct main numbers from 01–35")
    if not 1 <= int(special_ticket) <= 12:
        raise ValueError("Ticket special number must be from 01–12")
    if len(actual) != 5 or any(n < 1 or n > 35 for n in actual):
        raise ValueError("Draw must contain 5 distinct main numbers from 01–35")
    if not 1 <= int(draw_special) <= 12:
        raise ValueError("Draw special number must be from 01–12")
    matched = len(set(ticket) & actual)
    special_match = int(special_ticket) == int(draw_special)
    # Special is drawn from its own 01–12 group; numeric overlap with a main ball is allowed.
    if matched == 5 and special_match: tier = "JACKPOT"
    elif matched == 5: tier = "FIRST"
    elif matched == 4 and special_match: tier = "SECOND"
    elif matched == 4: tier = "THIRD"
    elif matched == 3 and special_match: tier = "FOURTH"
    elif matched == 3: tier = "FIFTH"
    elif special_match: tier = "ENCOURAGEMENT"
    else: tier = "NONE"
    return {"matched_main": matched, "special_match": special_match, "tier": tier}

def rolling_backtest(draws, warmup=200, tickets_per_draw=5):
    if len(draws) <= warmup:
        raise ValueError("Not enough draws for out-of-sample backtest")
    totals = Counter()
    details = []
    for i in range(warmup, len(draws)):
        target = draws[i]
        tickets = generate_tickets(draws[:i], tickets_per_draw)
        per_draw = Counter()
        for ticket in tickets:
            result = classify_ticket(ticket["main_numbers"], ticket["special"],
                                     target["main_numbers"], target["special"])
            per_draw[result["tier"]] += 1
            totals[result["tier"]] += 1
        details.append({"draw_id": target["draw_id"], "date": target["date"],
                        "tickets": len(tickets), **dict(per_draw)})
    return {"warmup_draws": warmup, "tested_draws": len(details),
            "tickets_per_draw": tickets_per_draw, "total_tickets": sum(x["tickets"] for x in details),
            "prize_counts": dict(totals), "details": details}
