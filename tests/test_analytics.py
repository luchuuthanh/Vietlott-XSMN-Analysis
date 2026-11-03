import unittest
from analytics import frequency_table, gap_table, pair_table, draw_metrics
from generator import make_sets

class AnalyticsTests(unittest.TestCase):
    def test_frequency_includes_zero_when_requested(self):
        result = frequency_table([0, 12, 12], 99, start=0).set_index("Số")
        self.assertEqual(int(result.loc[0, "Số lần"]), 1)
        self.assertEqual(int(result.loc[12, "Số lần"]), 2)

    def test_gap_counts_draws_since_last_seen(self):
        result = gap_table([[1, 2], [2, 3], [3, 4]], 4).set_index("Số")
        self.assertEqual(int(result.loc[1, "Số kỳ vắng"]), 2)
        self.assertEqual(int(result.loc[4, "Số kỳ vắng"]), 0)

    def test_pairs(self):
        result = pair_table([[1, 2, 3], [1, 2]], 5)
        self.assertEqual(result.iloc[0]["Cặp"], "01-02")
        self.assertEqual(int(result.iloc[0]["Số lần cùng xuất hiện"]), 2)

    def test_metrics(self):
        result = draw_metrics([[1, 2, 3, 4, 5, 6]])
        self.assertEqual(int(result.iloc[0]["Tổng"]), 21)
        self.assertEqual(int(result.iloc[0]["Delta"]), 5)

if __name__ == "__main__":
    unittest.main()
