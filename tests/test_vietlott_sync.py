import json
import unittest
from scripts.sync_vietlott import audit_payload, apply_verified_corrections, validate_result

class VietlottSyncTests(unittest.TestCase):
    def test_power655(self):
        # Six main balls and the separately drawn special ball are distinct.
        self.assertIsNone(validate_result("POWER655", [1, 2, 3, 4, 5, 6, 7]))
        # Historical rows without a special ball remain loadable and are flagged.
        self.assertIsNone(validate_result("POWER655", [1, 12, 21, 28, 30, 44]))
        self.assertIsNotNone(validate_result("POWER655", [1, 1, 3, 4, 5, 6, 7]))
        self.assertIsNotNone(validate_result("POWER655", [1, 2, 3, 4, 5, 6, 6]))
        self.assertIsNotNone(validate_result("POWER655", [1, 2, 3, 4, 5, 6, 56]))
        self.assertIsNotNone(validate_result("POWER655", [1, 2, 3, 4, 5, 6, 0]))

    def test_verified_power655_draw_00944_correction(self):
        rows = [
            {"date": "2022-09-22", "id": "00779", "result": [12, 14, 19, 29, 44, 47, 26]},
            {"date": "2022-09-23", "id": "00944", "result": [1, 12, 21, 28, 30, 44]},
            {"date": "2022-09-24", "id": "00780", "result": [1, 4, 5, 17, 42, 47, 9]},
            {"date": "2023-10-12", "id": "00943", "result": [5, 8, 9, 20, 36, 50, 35]},
            {"date": "2023-10-17", "id": "00945", "result": [13, 22, 33, 41, 46, 47, 9]},
        ]
        payload = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
        corrected = apply_verified_corrections("POWER655", payload)
        result = [json.loads(line) for line in corrected.decode().splitlines()]
        draw = next(row for row in result if row["id"] == "00944")
        self.assertEqual(draw["date"], "2023-10-14")
        self.assertEqual(draw["result"], [8, 23, 30, 34, 38, 47, 10])
        self.assertEqual([row["id"] for row in result], ["00779", "00780", "00943", "00944", "00945"])

    def test_mega645(self):
        self.assertIsNone(validate_result("MEGA645", [1, 2, 3, 4, 5, 45]))
        self.assertIsNotNone(validate_result("MEGA645", [1, 2, 3, 4, 5, 46]))

    def test_power535(self):
        self.assertIsNone(validate_result("POWER535", [1, 2, 3, 4, 5, 6]))

    def test_bingo18(self):
        self.assertIsNone(validate_result("BINGO18", [1, 3, 6]))

    def test_max3d(self):
        result = {"special": ["001", "002"], "first": ["003", "004", "005", "006"],
                  "second": ["007", "008", "009", "010", "011", "012"],
                  "third": ["013", "014", "015", "016", "017", "018", "019", "020"]}
        self.assertIsNone(validate_result("MAX3D", result))

    def test_latest_draw_id_uses_last_draw_on_latest_date(self):
        rows = [
            {"date": "2026-11-04", "id": "00987", "result": [2, 7, 8, 13, 14, 7]},
            {"date": "2026-11-04", "id": "00988", "result": [6, 10, 15, 20, 24, 4]},
        ]
        payload = ("\n".join(json.dumps(x) for x in rows) + "\n").encode()
        summary = audit_payload("POWER535", payload)
        self.assertEqual(summary["latest_draw_id"], "00988")

    def test_audit_duplicate_ids_rejected(self):
        row = {"date": "2026-01-01", "id": "00001", "result": [1, 2, 3, 4, 5, 6]}
        payload = (json.dumps(row) + "\n" + json.dumps(row) + "\n").encode()
        with self.assertRaises(RuntimeError):
            audit_payload("MEGA645", payload)

if __name__ == "__main__":
    unittest.main()
