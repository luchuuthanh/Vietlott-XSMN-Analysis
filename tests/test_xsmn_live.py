import unittest
import pandas as pd
from xsmn_live import validate_live_frame


def make_frame(day="2026-11-09", station="TP.HCM"):
    values = {
        "ĐB": ["123456"], "G1": ["12345"], "G2": ["23456"],
        "G3": ["34567", "45678"], "G4": [f"{i:05d}" for i in range(7)],
        "G5": ["1234"], "G6": ["1234", "2345", "3456"],
        "G7": ["123"], "G8": ["12"],
    }
    return pd.DataFrame([
        {"date": day, "province": station, "prize": prize, "number": number}
        for prize, numbers in values.items() for number in numbers
    ])


class XSMNLiveValidationTests(unittest.TestCase):
    def test_accepts_valid_monday_draw(self):
        self.assertEqual(len(validate_live_frame(make_frame())), 18)

    def test_rejects_station_on_wrong_weekday(self):
        with self.assertRaisesRegex(ValueError, "không khớp lịch"):
            validate_live_frame(make_frame(day="2026-11-10"))

    def test_rejects_incomplete_prize_structure(self):
        with self.assertRaisesRegex(ValueError, "cơ cấu giải"):
            validate_live_frame(make_frame().iloc[:-1])

    def test_rejects_wrong_digit_width(self):
        bad = make_frame()
        bad.loc[bad["prize"] == "ĐB", "number"] = "12345"
        with self.assertRaisesRegex(ValueError, "độ dài"):
            validate_live_frame(bad)

    def test_rejects_duplicate_results(self):
        bad = pd.concat([make_frame(), make_frame().iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "trùng"):
            validate_live_frame(bad)


if __name__ == "__main__":
    unittest.main()
