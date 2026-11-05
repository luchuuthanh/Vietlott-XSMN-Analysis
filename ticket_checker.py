"""Shared Vietlott ticket checker for Power 6/55 and Mega 6/45."""
from collections import Counter
from itertools import combinations

GAME_RULES = {
    "POWER655": {"universe": 55, "jackpot": "Jackpot 1", "special_jackpot": "Jackpot 2"},
    "MEGA645": {"universe": 45, "jackpot": "Jackpot", "special_jackpot": None},
}
PRIZE_LABELS = {
    "JACKPOT1": "Jackpot 1", "JACKPOT": "Jackpot", "JACKPOT2": "Jackpot 2",
    "FIRST": "Giải nhất", "SECOND": "Giải nhì", "THIRD": "Giải ba", "NONE": "Không trúng",
}

def _game(game):
    key = str(game or "POWER655").upper().strip()
    if key not in GAME_RULES:
        raise ValueError("Bộ dò hiện hỗ trợ Power 6/55 và Mega 6/45.")
    return key

def normalize_ticket(values, universe=55):
    if isinstance(values, str):
        raw = values.replace(",", " ").replace("-", " ").replace(";", " ").split()
    else:
        raw = list(values)
    try:
        nums = [int(str(x).strip()) for x in raw]
    except (TypeError, ValueError):
        raise ValueError(f"Vé chỉ được chứa số nguyên từ 01 đến {int(universe):02d}.")
    if len(nums) != 6:
        raise ValueError("Mỗi bộ vé phải có đúng 6 số.")
    if len(set(nums)) != 6:
        raise ValueError("6 số trên một bộ vé không được trùng nhau.")
    if any(n < 1 or n > int(universe) for n in nums):
        raise ValueError(f"Số trên vé phải nằm trong khoảng 01–{int(universe):02d}.")
    return tuple(sorted(nums))

def expand_ticket(values, universe=55):
    nums = sorted(set(int(x) for x in values))
    if len(nums) == 5:
        if any(n < 1 or n > universe for n in nums):
            raise ValueError(f"Số trên vé phải nằm trong khoảng 01–{universe:02d}.")
        return [tuple(sorted((*nums, extra))) for extra in range(1, universe + 1) if extra not in nums]
    if len(nums) not in set(range(6, 16)) | {18}:
        raise ValueError("Vé hệ thống cần chọn 5 số, 6–15 số hoặc 18 số khác nhau.")
    if any(n < 1 or n > universe for n in nums):
        raise ValueError(f"Số trên vé phải nằm trong khoảng 01–{universe:02d}.")
    return list(combinations(nums, 6))

def classify_ticket(ticket, main_numbers, special=None, game="POWER655"):
    game = _game(game)
    universe = GAME_RULES[game]["universe"]
    chosen = set(normalize_ticket(ticket, universe))
    main = set(int(x) for x in main_numbers)
    if len(main) != 6 or len(main) != len(set(main)) or any(n < 1 or n > universe for n in main):
        raise ValueError(f"Kết quả kỳ quay phải có đúng 6 số chính khác nhau trong 01–{universe:02d}.")
    if game == "MEGA645":
        special = None
    elif special is not None:
        special = int(special)
        if special < 1 or special > universe or special in main:
            raise ValueError("Số đặc biệt phải khác 6 số chính và nằm trong 01–55.")
    matched = len(chosen & main)
    special_match = special is not None and special in chosen
    uncertain = game == "POWER655" and matched == 5 and special is None
    if matched == 6:
        tier = "JACKPOT1" if game == "POWER655" else "JACKPOT"
    elif matched == 5 and game == "POWER655" and special_match:
        tier = "JACKPOT2"
    elif matched == 5:
        tier = "FIRST"
    elif matched == 4:
        tier = "SECOND"
    elif matched == 3:
        tier = "THIRD"
    else:
        tier = "NONE"
    suffix = " (chưa xác định Jackpot 2 do thiếu số đặc biệt)" if uncertain else ""
    return {"matched_main": matched, "special_match": bool(special_match),
            "special_unknown": uncertain, "tier": tier,
            "prize": PRIZE_LABELS[tier] + suffix}

def check_tickets(tickets, main_numbers, special=None, game="POWER655"):
    game = _game(game)
    universe = GAME_RULES[game]["universe"]
    rows = []
    for index, ticket in enumerate(tickets, 1):
        result = classify_ticket(ticket, main_numbers, special, game)
        rows.append({"Vé": index, "Bộ số": " - ".join(f"{n:02d}" for n in normalize_ticket(ticket, universe)),
                     "Trùng số chính": result["matched_main"],
                     "Trùng số đặc biệt": ("Có" if result["special_match"] else
                         ("Chưa có dữ liệu" if result["special_unknown"] else
                          ("Không áp dụng" if game == "MEGA645" else "Không"))),
                     "Kết quả": result["prize"], "Mã giải": result["tier"]})
    return rows

def rolling_backtest(draws, candidate_builder, min_history=100, history_window=None, game="POWER655"):
    game = _game(game)
    if min_history < 1:
        raise ValueError("min_history phải lớn hơn 0.")
    if len(draws) <= min_history:
        raise ValueError("Không đủ kỳ lịch sử để chạy kiểm định ngoài mẫu.")
    counts, tested_draws, total_tickets, detail = Counter(), 0, 0, []
    for index in range(min_history, len(draws)):
        start = 0 if history_window is None else max(0, index - int(history_window))
        history = draws[start:index]
        candidates = candidate_builder(history) or []
        if not candidates:
            continue
        target = draws[index]
        per_draw = Counter()
        for candidate in candidates:
            result = classify_ticket(candidate, target["main_numbers"], target.get("special"), game)
            per_draw[result["tier"]] += 1
            counts[result["tier"]] += 1
            total_tickets += 1
        tested_draws += 1
        detail.append({"draw_id": target.get("draw_id", ""), "date": target.get("date", ""),
                       "tickets": len(candidates), "Jackpot 1": per_draw["JACKPOT1"],
                       "Jackpot": per_draw["JACKPOT"], "Jackpot 2": per_draw["JACKPOT2"],
                       "Giải nhất": per_draw["FIRST"], "Giải nhì": per_draw["SECOND"],
                       "Giải ba": per_draw["THIRD"], "Không trúng": per_draw["NONE"]})
    return {"tested_draws": tested_draws, "total_tickets": total_tickets,
            "jackpot1": counts["JACKPOT1"], "jackpot": counts["JACKPOT"],
            "jackpot2": counts["JACKPOT2"], "first": counts["FIRST"],
            "second": counts["SECOND"], "third": counts["THIRD"],
            "no_prize": counts["NONE"]}, detail
