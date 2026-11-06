"""Fetch and parse latest XSMN results into native app data."""
from __future__ import annotations

from datetime import datetime
from io import StringIO
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://sxmn.com.vn/"
PRIZE_LABELS = {"G8", "G7", "G6", "G5", "G4", "G3", "G2", "G1", "ĐB", "DB"}


def fetch_live_xsmn() -> tuple[pd.DataFrame, str]:
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; XSMNAnalysisLab/1.0)"},
        timeout=15,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    parsed = None
    for table in tables:
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if cells:
                rows.append([cell.get_text(" ", strip=True) for cell in cells])
        if not rows:
            continue
        labels = {row[0].strip().upper() for row in rows if row}
        if {"G8", "G7", "G6", "G5", "G4", "G3", "G2", "G1"} <= labels and ({"ĐB", "DB"} & labels):
            parsed = rows
            break
    if not parsed:
        raise ValueError("Không tìm thấy bảng giải XSMN trên nguồn dữ liệu.")

    first_prize_row = next(
        (i for i, row in enumerate(parsed) if row and row[0].strip().upper() == "G8"),
        None,
    )
    if first_prize_row is None or first_prize_row == 0:
        raise ValueError("Không xác định được hàng tiêu đề tỉnh trong bảng kết quả.")
    header_index = first_prize_row - 1
    headers = parsed[header_index]
    provinces = [str(name).strip() for name in headers[1:] if str(name).strip()]
    if not provinces:
        raise ValueError("Bảng kết quả chưa có tên tỉnh.")

    records = []
    for row in parsed[header_index + 1:]:
        if not row:
            continue
        prize = row[0].strip().upper()
        if prize not in PRIZE_LABELS:
            continue
        for idx, province in enumerate(provinces, start=1):
            if idx >= len(row):
                continue
            numbers = re.findall(r"(?<!\d)\d{2,6}(?!\d)", row[idx])
            for number in numbers:
                records.append({"province": province, "prize": "ĐB" if prize == "DB" else prize, "number": number})

    if not records:
        raise ValueError("Bảng có cấu trúc nhưng chưa có kết quả số.")
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", soup.get_text(" ", strip=True))
    draw_date = datetime.strptime(date_match.group(1), "%d/%m/%Y").date().isoformat() if date_match else datetime.now().date().isoformat()
    frame = pd.DataFrame(records)
    frame.insert(0, "date", draw_date)
    return frame, response.url
