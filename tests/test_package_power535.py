import csv
import tempfile
import unittest
from pathlib import Path

from scripts.package_power535 import write_csv


class Power535PackageCsvTests(unittest.TestCase):
    def test_write_csv_unions_fields_across_backtest_rows(self):
        rows = [
            {"DRAW": "01001", "THIRD": 1},
            {"DRAW": "01002", "FIFTH": 2},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "details.csv"
            write_csv(path, rows)
            with path.open(newline="", encoding="utf-8-sig") as handle:
                saved = list(csv.DictReader(handle))

        self.assertEqual(saved[0]["DRAW"], "01001")
        self.assertEqual(saved[0]["THIRD"], "1")
        self.assertEqual(saved[0]["FIFTH"], "")
        self.assertEqual(saved[1]["DRAW"], "01002")
        self.assertEqual(saved[1]["FIFTH"], "2")


if __name__ == "__main__":
    unittest.main()
