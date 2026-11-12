import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import live_draw_monitor as monitor


class LiveDrawMonitorTests(unittest.TestCase):
    def test_game_schedule(self):
        self.assertEqual(monitor.game_for_date(date(2026, 11, 10)), "POWER655")  # Tuesday
        self.assertEqual(monitor.game_for_date(date(2026, 11, 11)), "MEGA645")   # Wednesday
        self.assertEqual(monitor.game_for_date(date(2026, 11, 12)), "POWER655")  # Thursday
        self.assertEqual(monitor.game_for_date(date(2026, 11, 13)), "MEGA645")   # Friday
        self.assertIsNone(monitor.game_for_date(date(2026, 11, 16)))             # Monday

    def test_vali_label_detection(self):
        candidate, va = monitor.is_candidate("Nhãn trên vali: VA2")
        self.assertTrue(candidate)
        self.assertTrue(va)

    def test_seal_number_is_candidate_not_vali_confirmation(self):
        candidate, va = monitor.is_candidate("Số khóa niêm phong 001346")
        self.assertTrue(candidate)
        self.assertFalse(va)

    def test_unrelated_text_is_not_candidate(self):
        candidate, va = monitor.is_candidate("Kính mời quý vị theo dõi chương trình")
        self.assertFalse(candidate)
        self.assertFalse(va)


if __name__ == "__main__":
    unittest.main()
