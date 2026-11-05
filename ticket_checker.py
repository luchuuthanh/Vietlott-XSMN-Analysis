"""Shared Vietlott ticket checker for Power 6/55, Mega 6/45 and Lotto 5/35."""
from collections import Counter
from itertools import combinations

GAME_RULES = {
    "POWER655": {"universe": 55, "main_count": 6, "special_universe": 55},
    "MEGA645": {"universe": 45, "main_count": 6, "special_universe": None},
    "POWER535": {"universe": 35, "main_count": 5, "special_universe": 12},
}
PRIZE_LABELS = {
    "JACKPOT1": "Jackpot 1", "JACKPOT": "Jackpot", "JACKPOT2": "Jackpot 2",
    "FIRST": "Giải nhất", "SECOND": "Giải nhì", "THIRD": "Giải ba",
    "FOURTH": "Giải tư", "FIFTH": "Giải năm",
    "ENCOURAGEMENT": "Giải khuyến khích", "NONE": "Không trúng",
}

def _game(game):
    key = str(game or "POWER655").upper().strip()
    if key not in GAME_RULES:
        raise ValueError("Bộ dò hỗ trợ Power 6/55, Mega 6/45 và Lotto 5/35.")
    return key

def _tokens(values):
    if isinstance(values, str):
        return values.replace(",", " ").replace("-", " ").replace(";", " ").replace("|", " ").split()
    return list(values)

def normalize_ticket(values, universe=55):
    raw = _tokens(values)
    try: nums = [int(str(x).strip()) for x in raw]
    except (TypeError, ValueError): raise ValueError(f"Vé chỉ được chứa số nguyên từ 01 đến {int(universe):02d}.")
    if len(nums) != 6: raise ValueError("Mỗi bộ vé phải có đúng 6 số.")
    if len(set(nums)) != 6: raise ValueError("6 số trên một bộ vé không được trùng nhau.")
    if any(n < 1 or n > int(universe) for n in nums): raise ValueError(f"Số trên vé phải nằm trong khoảng 01–{int(universe):02d}.")
    return tuple(sorted(nums))

def normalize_power535_ticket(values):
    """Lotto 5/35 input: five main numbers followed by the separate 01–12 special number."""
    raw = _tokens(values)
    try: nums = [int(str(x).strip()) for x in raw]
    except (TypeError, ValueError): raise ValueError("Vé 5/35 gồm 5 số chính và 1 số đặc biệt, đều là số nguyên.")
    if len(nums) != 6: raise ValueError("Vé Lotto 5/35 phải có 5 số chính và 1 số đặc biệt (ví dụ: 01 08 15 22 35 | 09).")
    main, special = nums[:5], nums[5]
    if len(set(main)) != 5: raise ValueError("5 số chính trên vé 5/35 không được trùng nhau.")
    if any(n < 1 or n > 35 for n in main): raise ValueError("5 số chính phải nằm trong khoảng 01–35.")
    if not 1 <= special <= 12: raise ValueError("Số đặc biệt 5/35 phải nằm trong khoảng 01–12.")
    return tuple(main), special

def expand_ticket(values, universe=55):
    nums = sorted(set(int(x) for x in values))
    if len(nums) == 5:
        if any(n < 1 or n > universe for n in nums): raise ValueError(f"Số trên vé phải nằm trong khoảng 01–{universe:02d}.")
        return [tuple(sorted((*nums, extra))) for extra in range(1, universe + 1) if extra not in nums]
    if len(nums) not in set(range(6, 16)) | {18}: raise ValueError("Vé hệ thống cần chọn 5 số, 6–15 số hoặc 18 số khác nhau.")
    if any(n < 1 or n > universe for n in nums): raise ValueError(f"Số trên vé phải nằm trong khoảng 01–{universe:02d}.")
    return list(combinations(nums, 6))

def classify_ticket(ticket, main_numbers, special=None, game="POWER655"):
    game = _game(game)
    rules = GAME_RULES[game]
    universe, main_count = rules["universe"], rules["main_count"]
    if game == "POWER535":
        if isinstance(ticket, dict):
            chosen, ticket_special = normalize_power535_ticket([*ticket.get("main_numbers", []), ticket.get("special")])
        else:
            chosen, ticket_special = normalize_power535_ticket(ticket)
        main = [int(x) for x in main_numbers]
        if len(main) != 5 or len(set(main)) != 5 or any(n < 1 or n > 35 for n in main):
            raise ValueError("Kết quả Lotto 5/35 phải có đúng 5 số chính khác nhau trong 01–35.")
        if special is None or not 1 <= int(special) <= 12:
            raise ValueError("Kết quả Lotto 5/35 cần số đặc biệt trong 01–12.")
        matched = len(set(chosen) & set(main))
        special_match = ticket_special == int(special)
        if matched == 5 and special_match: tier = "JACKPOT"
        elif matched == 5: tier = "FIRST"
        elif matched == 4 and special_match: tier = "SECOND"
        elif matched == 4: tier = "THIRD"
        elif matched == 3 and special_match: tier = "FOURTH"
        elif matched == 3: tier = "FIFTH"
        elif special_match: tier = "ENCOURAGEMENT"
        else: tier = "NONE"
        return {"matched_main": matched, "special_match": special_match,
                "special_unknown": False, "tier": tier, "prize": PRIZE_LABELS[tier]}
    chosen = set(normalize_ticket(ticket, universe))
    main = set(int(x) for x in main_numbers)
    if len(main) != main_count or len(main) != len(set(main)) or any(n < 1 or n > universe for n in main):
        raise ValueError(f"Kết quả kỳ quay phải có đúng {main_count} số chính khác nhau trong 01–{universe:02d}.")
    if game == "MEGA645": special = None
    elif special is not None:
        special = int(special)
        if special < 1 or special > universe or special in main:
            raise ValueError("Số đặc biệt phải khác 6 số chính và nằm trong 01–55.")
    matched = len(chosen & main)
    special_match = special is not None and special in chosen
    uncertain = game == "POWER655" and matched == 5 and special is None
    if matched == 6: tier = "JACKPOT1" if game == "POWER655" else "JACKPOT"
    elif matched == 5 and game == "POWER655" and special_match: tier = "JACKPOT2"
    elif matched == 5: tier = "FIRST"
    elif matched == 4: tier = "SECOND"
    elif matched == 3: tier = "THIRD"
    else: tier = "NONE"
    suffix = " (chưa xác định Jackpot 2 do thiếu số đặc biệt)" if uncertain else ""
    return {"matched_main": matched, "special_match": bool(special_match),
            "special_unknown": uncertain, "tier": tier, "prize": PRIZE_LABELS[tier] + suffix}

def check_tickets(tickets, main_numbers, special=None, game="POWER655"):
    game = _game(game)
    universe = GAME_RULES[game]["universe"]
    rows = []
    for index, ticket in enumerate(tickets, 1):
        result = classify_ticket(ticket, main_numbers, special, game)
        if game == "POWER535":
            main_ticket, ticket_special = normalize_power535_ticket(ticket if not isinstance(ticket, dict) else [*ticket["main_numbers"], ticket["special"]])
            label = " - ".join(f"{n:02d}" for n in main_ticket) + f" | ĐB {ticket_special:02d}"
        else:
            label = " - ".join(f"{n:02d}" for n in normalize_ticket(ticket, universe))
        rows.append({"Vé": index, "Bộ số": label, "Trùng số chính": result["matched_main"],
            "Trùng số đặc biệt": "Có" if result["special_match"] else
                ("Chưa có dữ liệu" if result["special_unknown"] else ("Không áp dụng" if game == "MEGA645" else "Không")),
            "Kết quả": result["prize"], "Mã giải": result["tier"]})
    return rows

def rolling_backtest(draws, candidate_builder, min_history=100, history_window=None, game="POWER655"):
    game = _game(game)
    if min_history < 1: raise ValueError("min_history phải lớn hơn 0.")
    if len(draws) <= min_history: raise ValueError("Không đủ kỳ lịch sử để chạy kiểm định ngoài mẫu.")
    counts, tested_draws, total_tickets, detail = Counter(), 0, 0, []
    for index in range(min_history, len(draws)):
        start = 0 if history_window is None else max(0, index - int(history_window))
        candidates = candidate_builder(draws[start:index]) or []
        if not candidates: continue
        target, per_draw = draws[index], Counter()
        for candidate in candidates:
            result = classify_ticket(candidate, target["main_numbers"], target.get("special"), game)
            per_draw[result["tier"]] += 1; counts[result["tier"]] += 1; total_tickets += 1
        tested_draws += 1
        detail.append({"draw_id": target.get("draw_id", ""), "date": target.get("date", ""),
            "tickets": len(candidates), **{PRIZE_LABELS[k]:v for k,v in per_draw.items()}})
    return {"tested_draws": tested_draws, "total_tickets": total_tickets,
        "jackpot1": counts["JACKPOT1"], "jackpot": counts["JACKPOT"],
        "jackpot2": counts["JACKPOT2"], "first": counts["FIRST"], "second": counts["SECOND"],
        "third": counts["THIRD"], "fourth": counts["FOURTH"], "fifth": counts["FIFTH"],
        "encouragement": counts["ENCOURAGEMENT"], "no_prize": counts["NONE"]}, detail
