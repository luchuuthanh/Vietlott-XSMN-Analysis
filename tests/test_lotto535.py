import json, tempfile, unittest
from pathlib import Path
from lotto535_analyzer import load_draws, classify_ticket, generate_tickets, rolling_backtest

class Lotto535Tests(unittest.TestCase):
    def test_separate_special_can_overlap_main_value(self):
        result = classify_ticket([1,2,3,4,5], 9, [1,2,3,4,9], 9)
        self.assertEqual(result["tier"], "FIRST")
        self.assertTrue(result["special_match"])

    def test_jackpot_and_prize_tiers(self):
        self.assertEqual(classify_ticket([1,2,3,4,5], 7, [1,2,3,4,5], 7)["tier"], "JACKPOT")
        self.assertEqual(classify_ticket([1,2,3,4,8], 7, [1,2,3,4,5], 7)["tier"], "SECOND")
        self.assertEqual(classify_ticket([1,2,3,8,9], 7, [1,2,3,4,5], 7)["tier"], "FOURTH")
        self.assertEqual(classify_ticket([8,9,10,11,12], 7, [1,2,3,4,5], 7)["tier"], "ENCOURAGEMENT")

    def test_ticket_validation(self):
        with self.assertRaises(ValueError): classify_ticket([1,2,3,4,4], 1, [1,2,3,4,5], 1)
        with self.assertRaises(ValueError): classify_ticket([1,2,3,4,5], 13, [1,2,3,4,5], 1)

    def test_real_archive_and_backtest(self):
        rows = load_draws()
        self.assertEqual(len(rows), 988)
        self.assertEqual(rows[0]["draw_id"], "00001")
        self.assertEqual(rows[-1]["draw_id"], "00988")
        self.assertEqual(len(generate_tickets(rows[:200], 5)), 5)
        bt = rolling_backtest(rows, 200, 5)
        self.assertEqual(bt["tested_draws"], 788)
        self.assertEqual(bt["total_tickets"], 3940)

if __name__ == "__main__": unittest.main()
