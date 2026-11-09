import unittest

import pandas as pd

from xsmn_issuer_sources import parse_issuer_html, compare_issuer_with_secondary


VALUES = [
    ("Giải Tám", "12"), ("Giải Bảy", "123"), ("Giải Sáu", "1234 - 2345 - 3456"),
    ("Giải Năm", "1234"), ("Giải Tư", "12345 - 22345 - 32345 - 42345 - 52345 - 62345 - 72345"),
    ("Giải Ba", "12345 - 22345"), ("Giải Nhì", "12345"), ("Giải Nhất", "12345"),
    ("Giải Đặc Biệt", "123456"),
]


def html_fixture(station, date_line):
    body = [date_line]
    if station == "An Giang":
        body[0] = f"KẾT QUẢ XỔ SỐ KIẾN THIẾT AN GIANG KỲ MỞ NGÀY {date_line}"
    if station == "Tiền Giang":
        body[0] = f"Ký hiệu TGB; Mở ngày: {date_line}"
    if station == "Sóc Trăng":
        body[0] = f"Ngày xổ số: {date_line}"
    for label, numbers in VALUES:
        body.extend([label, numbers])
    return "<html><body>" + "".join(f"<p>{line}</p>" for line in body) + "</body></html>"


class XSMNIssuerParserTests(unittest.TestCase):
    def test_parses_all_five_station_page_shapes(self):
        fixtures = [
            ("TP.HCM", "Thứ Hai, ngày 9-11-2026", "2026-11-09"),
            ("Vĩnh Long", "06-11-2026", "2026-11-06"),
            ("Sóc Trăng", "04-11-2026", "2026-11-04"),
            ("An Giang", "05/11/2026", "2026-11-05"),
            ("Tiền Giang", "08-11-2026", "2026-11-08"),
        ]
        for station, date_line, expected_date in fixtures:
            with self.subTest(station=station):
                frame = parse_issuer_html(html_fixture(station, date_line), station)
                self.assertEqual(len(frame), 18)
                self.assertEqual(set(frame["date"].astype(str)), {expected_date})

    def test_rejects_missing_prize(self):
        html = html_fixture("TP.HCM", "Thứ Hai, ngày 9-11-2026").replace("<p>Giải Tư</p><p>12345 - 22345 - 32345 - 42345 - 52345 - 62345 - 72345</p>", "")
        with self.assertRaisesRegex(ValueError, "chưa cung cấp đủ"):
            parse_issuer_html(html, "TP.HCM")

    def test_secondary_mismatch_is_blocked(self):
        issuer = parse_issuer_html(html_fixture("TP.HCM", "Thứ Hai, ngày 9-11-2026"), "TP.HCM")
        secondary = issuer.copy()
        secondary.loc[secondary["prize"] == "ĐB", "number"] = "654321"
        with self.assertRaisesRegex(ValueError, "không trùng khớp"):
            compare_issuer_with_secondary(issuer, secondary, "TP.HCM")


if __name__ == "__main__":
    unittest.main()
