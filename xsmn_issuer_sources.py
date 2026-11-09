"""Direct issuer adapters for the five selected XSMN stations.

Parsers are deliberately fail-closed: a page that does not expose a clear draw date
and all 18 prize numbers is rejected rather than guessed or silently substituted.
"""
from __future__ import annotations

from datetime import datetime
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from xsmn_live import normalize_station_key, validate_live_frame

ISSUER_SOURCES = {
    "tphcm": ("TP.HCM", "https://www.xskthcm.com/xskt", "issuer_xskthcm"),
    "vinhlong": ("Vĩnh Long", "https://xosovinhlong.com.vn/", "issuer_xosovinhlong"),
    "soctrang": ("Sóc Trăng", "https://xsktsoctrang.vn/", "issuer_xsktsoctrang"),
    "angiang": ("An Giang", "https://xsktangiang.com.vn/ket-qua-xo-so", "issuer_xsktangiang"),
    "tiengiang": ("Tiền Giang", "https://www.xskttg.com.vn/", "issuer_xskttg"),
}
PRIZES = [
    ("ĐB", ("giải đặc biệt", "giai dac biet", "giải đb", "giai db")),
    ("G1", ("giải nhất", "giai nhat")),
    ("G2", ("giải nhì", "giai nhi")),
    ("G3", ("giải ba", "giai ba")),
    ("G4", ("giải tư", "giai tu")),
    ("G5", ("giải năm", "giai nam")),
    ("G6", ("giải sáu", "giai sau")),
    ("G7", ("giải bảy", "giai bay")),
    ("G8", ("giải tám", "giai tam")),
]
WIDTH = {"ĐB": 6, "G1": 5, "G2": 5, "G3": 5, "G4": 5, "G5": 4, "G6": 4, "G7": 3, "G8": 2}
COUNT = {"ĐB": 1, "G1": 1, "G2": 1, "G3": 2, "G4": 7, "G5": 1, "G6": 3, "G7": 1, "G8": 1}
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?!\d)")
NUM_RE = re.compile(r"(?<!\d)\d{2,6}(?!\d)")


def _clean_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    return [re.sub(r"\s+", " ", x).strip() for x in soup.get_text("\n").splitlines() if x.strip()]


def _date_from_lines(lines: list[str], station: str) -> tuple[str, int]:
    key = normalize_station_key(station)
    candidates = []
    for i, line in enumerate(lines):
        low = line.casefold()
        if key == "angiang" and "kết quả xổ số kiến thiết an giang" not in low and "ket qua xo so kien thiet an giang" not in low:
            continue
        if key == "tiengiang" and "mở ngày" not in low and "mo ngay" not in low:
            continue
        if key == "soctrang" and "ngày xổ số" not in low and "ngay xo so" not in low:
            continue
        if key == "tphcm" and "ngày" not in low and "ngay" not in low:
            continue
        match = DATE_RE.search(line)
        if not match:
            # The date can be in a nearby input/heading line, but keep the search local.
            for nearby in lines[max(0, i - 1): min(len(lines), i + 3)]:
                match = DATE_RE.search(nearby)
                if match:
                    break
        if match:
            day, month, year = map(int, match.groups())
            try:
                candidates.append((datetime(year, month, day).date().isoformat(), i))
            except ValueError:
                continue
    if not candidates:
        # Generic first date is allowed only when the page has a single date.
        all_dates = []
        for i, line in enumerate(lines):
            match = DATE_RE.search(line)
            if match:
                day, month, year = map(int, match.groups())
                try:
                    all_dates.append((datetime(year, month, day).date().isoformat(), i))
                except ValueError:
                    pass
        unique = {x[0] for x in all_dates}
        if len(unique) == 1:
            return all_dates[0]
        raise ValueError(f"{station}: không nhận diện được ngày quay của khối kết quả mới nhất.")
    # The newest result block is normally first on issuer pages.
    return candidates[0]


def parse_issuer_html(html: str, station: str) -> pd.DataFrame:
    lines = _clean_lines(html)
    draw_date, date_index = _date_from_lines(lines, station)
    # Only parse a bounded result section after the identified draw date.
    section = lines[date_index: date_index + 90]
    records = []
    used = set()
    for prize, labels in PRIZES:
        found = False
        for i, line in enumerate(section):
            low = line.casefold()
            if not any(label in low for label in labels):
                continue
            # Prefer numbers on the label line; otherwise use the immediately following line.
            numbers = NUM_RE.findall(line)
            if not numbers and i + 1 < len(section):
                numbers = NUM_RE.findall(section[i + 1])
            if len(numbers) == COUNT[prize] and all(len(n) == WIDTH[prize] for n in numbers):
                records.extend({"date": draw_date, "province": station, "prize": prize, "number": n} for n in numbers)
                used.add(prize)
                found = True
                break
        if not found:
            raise ValueError(f"{station}: nguồn nhà đài chưa cung cấp đủ/đúng {prize}; từ chối dùng dữ liệu.")
    frame = validate_live_frame(pd.DataFrame(records))
    if len(frame) != 18:
        raise ValueError(f"{station}: kết quả nhà đài không đủ 18 số.")
    return frame


def fetch_issuer_xsmn(station: str) -> tuple[pd.DataFrame, str, str]:
    key = normalize_station_key(station)
    if key not in ISSUER_SOURCES:
        raise KeyError(f"{station} không thuộc nhóm 5 nguồn nhà đài chính.")
    official_name, url, source_id = ISSUER_SOURCES[key]
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; XSMNAnalysisLab/1.0)"},
        timeout=20,
    )
    response.raise_for_status()
    frame = parse_issuer_html(response.text, official_name)
    return frame, response.url, source_id


def compare_issuer_with_secondary(issuer: pd.DataFrame, secondary: pd.DataFrame, station: str) -> None:
    """Raise on any date/number discrepancy; never overwrite either source."""
    left = issuer[issuer["province"].map(normalize_station_key) == normalize_station_key(station)].copy()
    right = secondary[secondary["province"].map(normalize_station_key) == normalize_station_key(station)].copy()
    if left.empty or right.empty:
        raise ValueError(f"{station}: thiếu dữ liệu từ một trong hai nguồn để đối chiếu.")
    left["prize"] = left["prize"].astype(str).str.upper().replace({"DB": "ĐB"})
    right["prize"] = right["prize"].astype(str).str.upper().replace({"DB": "ĐB"})
    cols = ["date", "prize", "number"]
    a = left[cols].sort_values(cols).reset_index(drop=True)
    b = right[cols].sort_values(cols).reset_index(drop=True)
    if len(a) != 18 or len(b) != 18 or not a.equals(b):
        raise ValueError(f"{station}: số liệu nguồn nhà đài và nguồn đối chiếu không trùng khớp; chặn đồng bộ kho chuẩn.")
