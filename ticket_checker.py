"""Power 6/55 ticket checker and leakage-aware rolling backtest helpers."""
from collections import Counter
from itertools import combinations

PRIZE_LABELS = {
    "JACKPOT1": "Jackpot 1",
    "JACKPOT2": "Jackpot 2",
    "FIRST": "Giải nhất",
    "SECOND": "Giải nhì",
    "THIRD": "Giải ba",
    "NONE": "Không trúng",
}

def normalize_ticket(values):
    """Return a sorted six-number ticket or raise ValueError."""
    if isinstance(values, str):
        raw = values.replace(",", " ").replace("-", " ").replace(";", " ").split()
    else:
        raw = list(values)
    try:
        nums = [int(str(x).strip()) for x in raw]
    except (TypeError, ValueError):
        raise ValueError("Vé chỉ được chứa số nguyên từ 01 đến 55.")
    if len(nums) != 6:
        raise ValueError("Mỗi bộ vé phải có đúng 6 số.")
    if len(set(nums)) != 6:
        raise ValueError("6 số trên một bộ vé không được trùng nhau.")
    if any(n < 1 or n > 55 for n in nums):
        raise ValueError("Số trên vé phải nằm trong khoảng 01–55.")
    return tuple(sorted(nums))

def expand_ticket(values):
    """Expand Bao 7–15/18 into all six-number combinations."""
    nums = sorted(set(int(x) for x in values))
    if len(nums) not in set(range(6, 16)) | {18}:
        raise ValueError("Vé bao cần chọn 6–15 hoặc 18 số khác nhau.")
    if any(n < 1 or n > 55 for n in nums):
        raise ValueError("Số trên vé phải nằm trong khoảng 01–55.")
    return list(combinations(nums, 6))

def classify_ticket(ticket, main_numbers, special=None):
    """Return the single highest prize tier for one six-number combination."""
    chosen = set(normalize_ticket(ticket))
    main = set(int(x) for x in main_numbers)
    if len(main) != 6 or len(main) != len(set(main)) or any(n < 1 or n > 55 for n in main):
        raise ValueError("Kết quả kỳ quay phải có đúng 6 số chính khác nhau trong 01–55.")
    if special is not None:
        special = int(special)
        if special < 1 or special > 55 or special in main:
            raise ValueError("Số đặc biệt phải khác 6 số chính và nằm trong 01–55.")
    matched = len(chosen & main)
    special_match = (special is not None and special in chosen)
    uncertain = (matched == 5 and special is None)
    if matched == 6:
        tier = "JACKPOT1"
    elif matched == 5 and special_match:
        tier = "JACKPOT2"
    elif matched == 5:
        tier = "FIRST"
    elif matched == 4:
        tier = "SECOND"
    elif matched == 3:
        tier = "THIRD"
    else:
        tier = "NONE"
    return {
        "matched_main": matched,
        "special_match": special_match,
        "special_unknown": uncertain,
        "tier": tier,
        "prize": PRIZE_LABELS[tier] + (" (chưa xác định Jackpot 2 do thiếu số đặc biệt)" if uncertain else ""),
    }

def check_tickets(tickets, main_numbers, special=None):
    """Check a list of ticket combinations against one draw."""
    rows = []
    for index, ticket in enumerate(tickets, 1):
        result = classify_ticket(ticket, main_numbers, special)
        rows.append({
            "Vé": index,
            "Bộ số": " - ".join(f"{n:02d}" for n in normalize_ticket(ticket)),
            "Trùng số chính": result["matched_main"],
            "Trùng số đặc biệt": "Có" if result["special_match"] else ("Chưa có dữ liệu" if result["special_unknown"] else "Không"),
            "Kết quả": result["prize"],
            "Mã giải": result["tier"],
        })
    return rows

def rolling_backtest(draws, candidate_builder, min_history=100, history_window=None):
    """Build tickets using only prior draws, then test on the next unseen draw.

    draws: chronological dictionaries with main_numbers, optional special, draw_id/date.
    candidate_builder(history_draw_dicts) returns six-number tickets.
    """
    if min_history < 1:
        raise ValueError("min_history phải lớn hơn 0.")
    if len(draws) <= min_history:
        raise ValueError("Không đủ kỳ lịch sử để chạy kiểm định ngoài mẫu.")
    counts = Counter()
    tested_draws = 0
    total_tickets = 0
    detail = []
    for index in range(min_history, len(draws)):
        start = 0 if history_window is None else max(0, index - int(history_window))
        history = draws[start:index]
        candidates = candidate_builder(history) or []
        if not candidates:
            continue
        target = draws[index]
        per_draw = Counter()
        for candidate in candidates:
            result = classify_ticket(candidate, target["main_numbers"], target.get("special"))
            per_draw[result["tier"]] += 1
            counts[result["tier"]] += 1
            total_tickets += 1
        tested_draws += 1
        detail.append({
            "draw_id": target.get("draw_id", ""),
            "date": target.get("date", ""),
            "tickets": len(candidates),
            "Jackpot 1": per_draw["JACKPOT1"],
            "Jackpot 2": per_draw["JACKPOT2"],
            "Giải nhất": per_draw["FIRST"],
            "Giải nhì": per_draw["SECOND"],
            "Giải ba": per_draw["THIRD"],
            "Không trúng": per_draw["NONE"],
        })
    summary = {
        "tested_draws": tested_draws,
        "total_tickets": total_tickets,
        "jackpot1": counts["JACKPOT1"],
        "jackpot2": counts["JACKPOT2"],
        "first": counts["FIRST"],
        "second": counts["SECOND"],
        "third": counts["THIRD"],
        "no_prize": counts["NONE"],
    }
    return summary, detail
