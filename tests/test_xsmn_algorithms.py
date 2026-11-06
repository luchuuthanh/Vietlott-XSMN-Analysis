import unittest
import pandas as pd
from xsmn_algorithms import prepare_xsmn_frame, draw_history, rank_numbers, rolling_backtest


class XSMNAlgorithmTests(unittest.TestCase):
    def setUp(self):
        rows = []
        for day in range(1, 46):
            date = f"2026-01-{day:02d}" if day <= 31 else f"2026-02-{day-31:02d}"
            for number in [f"{day%10}{(day+1)%10}", f"{(day+2)%10}{(day+3)%10}", "07"]:
                rows.append({"date": date, "province": "TEST", "number": number})
        self.frame = pd.DataFrame(rows)

    def test_prepare_preserves_two_digit_numbers(self):
        df = prepare_xsmn_frame(pd.DataFrame([{"date":"2026-01-01","province":"A","number":"00007"}]))
        self.assertEqual(df.iloc[0]["number2"], 7)

    def test_rank_returns_valid_two_digit_numbers(self):
        history = draw_history(self.frame, "TEST")
        ranked = rank_numbers(history[:-1], "blend", 10)
        self.assertEqual(len(ranked), 10)
        self.assertTrue(ranked["Số"].str.fullmatch(r"\d{2}").all())

    def test_backtest_walk_forward(self):
        detail, summary = rolling_backtest(self.frame, "TEST", methods=["freq_30","blend"], top_k=10, min_history=30)
        self.assertFalse(detail.empty)
        self.assertEqual(set(detail["method"]), {"freq_30","blend"})
        self.assertTrue((detail["history_draws"] < 45).all())
        self.assertTrue((detail["hits"] <= detail["actual_unique"]).all())


if __name__ == "__main__":
    unittest.main()
