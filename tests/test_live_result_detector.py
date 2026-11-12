import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from live_result_detector import consensus_events, classify_sequence, parse_large_numeric_tokens


class LiveResultDetectorTests(unittest.TestCase):
    def test_only_large_confident_tokens_inside_game_range(self):
        data = {
            "text": ["12", "60", "18"],
            "conf": ["90", "99", "90"],
            "height": ["50", "50", "10"],
            "width": ["30", "30", "20"],
            "left": ["10", "20", "30"],
            "top": ["10", "10", "10"],
        }
        found = parse_large_numeric_tokens(data, 1280, 720, 55)
        self.assertEqual([item["number"] for item in found], [12])

    def test_number_requires_repeated_frame_agreement(self):
        rows = [
            {"elapsed_seconds": 0, "numeric_candidates": [{"number": 12, "confidence": 80}]},
            {"elapsed_seconds": 2, "numeric_candidates": [{"number": 12, "confidence": 91}]},
            {"elapsed_seconds": 4, "numeric_candidates": [{"number": 33, "confidence": 88}]},
            {"elapsed_seconds": 6, "numeric_candidates": [{"number": 33, "confidence": 86}]},
        ]
        events = consensus_events(rows)
        self.assertEqual([event["number"] for event in events], [12, 33])

    def test_power_special_position_is_only_a_possible_special(self):
        events = [{"number": n} for n in [2, 9, 14, 25, 33, 51, 7]]
        labeled = classify_sequence(events, "POWER655")
        self.assertEqual(labeled[5]["position"], "main_6")
        self.assertEqual(labeled[6]["position"], "possible_special")

    def test_mega_has_only_six_main_positions(self):
        events = [{"number": n} for n in [2, 9, 14, 25, 33, 41, 7]]
        labeled = classify_sequence(events, "MEGA645")
        self.assertEqual(labeled[5]["position"], "main_6")
        self.assertEqual(labeled[6]["position"], "extra_or_false_positive")


if __name__ == "__main__":
    unittest.main()
