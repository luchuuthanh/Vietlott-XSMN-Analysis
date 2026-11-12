import unittest
import pandas as pd

from xsmn_hit_analysis import build_scope_history, analyze_scope, METHODS


class XSMNHitAttributionTests(unittest.TestCase):
    def setUp(self):
        rows = []
        for day in range(1, 61):
            date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=day - 1)
            rows.extend([
                {"date": date, "province": "TEST", "prize": "G8", "number": f"{day % 10:02d}"},
                {"date": date, "province": "TEST", "prize": "G7", "number": f"{(day + 1) % 10:03d}"},
                {"date": date, "province": "TEST", "prize": "ĐB", "number": f"{(day + 2) % 100:06d}"},
            ])
        self.frame = pd.DataFrame(rows)

    def test_scope_history_separates_prizes(self):
        g8 = build_scope_history(self.frame, "TEST", "G8")
        g7 = build_scope_history(self.frame, "TEST", "G7")
        all_prizes = build_scope_history(self.frame, "TEST", "Tất cả giải")
        self.assertEqual(len(g8), 60)
        self.assertEqual(len(g7), 60)
        self.assertEqual(g8[0][1], {1})
        self.assertEqual(g7[0][1], {2})
        self.assertEqual(all_prizes[0][1], {1, 2, 3})

    def test_walk_forward_records_method_membership_of_actual_hits(self):
        summary, detail, attribution, total = analyze_scope(
            self.frame, "TEST", "G8", top_k=10, min_history=30, test_periods=20
        )
        self.assertEqual(total, 60)
        self.assertEqual(set(detail["_method"].unique()), set(METHODS))
        self.assertEqual(len(summary), len(METHODS))
        self.assertIn("Nằm trong phương pháp lọc", attribution.columns)
        self.assertIn("Thứ hạng theo phương pháp", attribution.columns)
        self.assertEqual(len(detail), 20 * len(METHODS))


if __name__ == "__main__":
    unittest.main()
