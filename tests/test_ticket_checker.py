import unittest
from ticket_checker import (
    normalize_ticket, expand_ticket, classify_ticket, check_tickets, rolling_backtest
)

class Power655TicketCheckerTests(unittest.TestCase):
    def setUp(self):
        self.main = [8, 23, 30, 34, 38, 47]
        self.special = 10

    def test_all_prize_tiers(self):
        self.assertEqual(classify_ticket(self.main, self.main, self.special)["tier"], "JACKPOT1")
        self.assertEqual(classify_ticket([8, 23, 30, 34, 38, 10], self.main, self.special)["tier"], "JACKPOT2")
        self.assertEqual(classify_ticket([8, 23, 30, 34, 38, 1], self.main, self.special)["tier"], "FIRST")
        self.assertEqual(classify_ticket([8, 23, 30, 34, 1, 2], self.main, self.special)["tier"], "SECOND")
        self.assertEqual(classify_ticket([8, 23, 30, 1, 2, 3], self.main, self.special)["tier"], "THIRD")
        self.assertEqual(classify_ticket([1, 2, 3, 4, 5, 6], self.main, self.special)["tier"], "NONE")

    def test_special_number_is_not_a_seventh_main_number(self):
        result = classify_ticket([8, 23, 30, 34, 38, 10], self.main, self.special)
        self.assertEqual(result["matched_main"], 5)
        self.assertTrue(result["special_match"])
        self.assertEqual(result["tier"], "JACKPOT2")

    def test_missing_special_marks_jackpot2_uncertain(self):
        result = classify_ticket([8, 23, 30, 34, 38, 10], self.main, None)
        self.assertEqual(result["tier"], "FIRST")
        self.assertTrue(result["special_unknown"])

    def test_ticket_validation(self):
        self.assertEqual(normalize_ticket("08 23 30 34 38 47"), (8, 23, 30, 34, 38, 47))
        with self.assertRaises(ValueError):
            normalize_ticket("1 2 3 4 5")
        with self.assertRaises(ValueError):
            normalize_ticket("1 2 3 4 5 5")
        with self.assertRaises(ValueError):
            normalize_ticket("1 2 3 4 5 56")

    def test_system_tickets_expand_to_all_six_number_combinations(self):
        self.assertEqual(len(expand_ticket([1, 2, 3, 4, 5])), 50)
        self.assertEqual(len(expand_ticket([1, 2, 3, 4, 5, 6, 7])), 7)
        self.assertEqual(len(expand_ticket([1, 2, 3, 4, 5, 6, 7, 8])), 28)

    def test_ticket_batch(self):
        rows = check_tickets([[8, 23, 30, 34, 38, 47]], self.main, self.special)
        self.assertEqual(rows[0]["Mã giải"], "JACKPOT1")

    def test_rolling_backtest_uses_previous_draws(self):
        draws = [
            {"draw_id": "1", "main_numbers": [1, 2, 3, 4, 5, 6], "special": 7},
            {"draw_id": "2", "main_numbers": [8, 9, 10, 11, 12, 13], "special": 14},
            {"draw_id": "3", "main_numbers": [1, 2, 3, 4, 5, 6], "special": 7},
        ]
        seen_history_lengths = []
        def builder(history):
            seen_history_lengths.append(len(history))
            return [[1, 2, 3, 4, 5, 6]]
        summary, detail = rolling_backtest(draws, builder, min_history=1)
        self.assertEqual(seen_history_lengths, [1, 2])
        self.assertEqual(summary["jackpot1"], 1)
        self.assertEqual(summary["total_tickets"], 2)
        self.assertEqual(len(detail), 2)

    def test_mega645_jackpot_and_no_special_number(self):
        result = classify_ticket([3, 12, 20, 30, 38, 45], [3, 12, 20, 30, 38, 45], game="MEGA645")
        self.assertEqual(result["tier"], "JACKPOT")
        self.assertFalse(result["special_unknown"])
        self.assertFalse(result["special_match"])

    def test_mega645_prize_tiers_and_universe(self):
        self.assertEqual(classify_ticket([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], game="MEGA645")["tier"], "JACKPOT")
        self.assertEqual(classify_ticket([1, 2, 3, 4, 5, 7], [1, 2, 3, 4, 5, 6], game="MEGA645")["tier"], "FIRST")
        self.assertEqual(classify_ticket([1, 2, 3, 4, 7, 8], [1, 2, 3, 4, 5, 6], game="MEGA645")["tier"], "SECOND")
        self.assertEqual(classify_ticket([1, 2, 3, 7, 8, 9], [1, 2, 3, 4, 5, 6], game="MEGA645")["tier"], "THIRD")
        with self.assertRaises(ValueError):
            normalize_ticket([1, 2, 3, 4, 5, 46], universe=45)
        self.assertEqual(len(expand_ticket([1, 2, 3, 4, 5], universe=45)), 40)

    def test_shared_checker_uses_selected_game(self):
        rows = check_tickets([[1, 2, 3, 4, 5, 6]], [1, 2, 3, 4, 5, 6], game="MEGA645")
        self.assertEqual(rows[0]["Mã giải"], "JACKPOT")
        self.assertEqual(rows[0]["Trùng số đặc biệt"], "Không áp dụng")

if __name__ == "__main__":
    unittest.main()
