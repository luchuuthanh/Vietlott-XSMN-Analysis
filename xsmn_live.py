"""Fetch and parse latest XSMN results with fail-closed date identification."""
from __future__ import annotations

from datetime import datetime
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://sxmn.com.vn/"
PRIZE_LABELS = {"G8", "G7", "G6", "G5", "G4", "G3", "G2", "G1", "ĐB", "DB"}
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")
EXPECTED = {"ĐB": 1, "G1": 1, "G2": 1, "G3": 2, "G4": 7, "G5": 1, "G6": 3, "G7": 1, "G8": 1}


def normalize_station_key(value: object) -> str:
    """Normalize official XSMN station aliases to one stable comparison key."""
    import unicodedata
    text = str(value).strip().casefold().replace("đ", "d")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    key = re.sub(r"[^a-z0-9]+", "", text)
    aliases = {
        "tphcm": "tphcm",
        "tphochiminh": "tphcm",
        "thanhphohcm": "tphcm",
        "thanhphohochiminh": "tphcm",
        "hochiminh": "tphcm",
        "hochiminhcity": "tphcm",
        "hcm": "tphcm",
        "dalat": "dalat",
        "lamdong": "dalat",
    }
    return aliases.get(key, key)


def _table_draw_date(table) -> str:
    """Read draw date only from headings immediately preceding this table; never use today's date."""
    candidates = []
    for heading in table.find_all_previous(["h1", "h2", "h3", "h4"], limit=4):
        text = heading.get_text(" ", strip=True)
        match = DATE_RE.search(text)
        if match:
            candidates.append(datetime.strptime("/".join(match.groups()), "%d/%m/%Y").date().isoformat())
            break
    if not candidates:
        # Some source revisions put the draw date in the table's own caption.
        caption = table.find("caption")
        if caption:
            match = DATE_RE.search(caption.get_text(" ", strip=True))
            if match:
                candidates.append(datetime.strptime("/".join(match.groups()), "%d/%m/%Y").date().isoformat())
    if not candidates:
        raise ValueError("Không nhận diện được ngày quay từ tiêu đề/caption của chính bảng kết quả; từ chối dùng ngày máy chủ.")
    return candidates[0]


def validate_live_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate date, station schedule, prize structure, and number width before display or sync."""
    if frame.empty:
        raise ValueError("Bảng kết quả trực tuyến đang trống.")
    required = {"date", "province", "prize", "number"}
    if not required.issubset(frame.columns):
        raise ValueError("Thiếu cột bắt buộc trong dữ liệu trực tuyến.")
    out = frame.copy()
    parsed_dates = pd.to_datetime(out["date"], errors="coerce")
    if parsed_dates.isna().any() or parsed_dates.dt.normalize().nunique() != 1:
        raise ValueError("Ngày quay không hợp lệ hoặc bảng chứa nhiều ngày.")
    draw_date = parsed_dates.dt.date.iloc[0]
    schedule = {
        0: {"TP.HCM", "Đồng Tháp", "Cà Mau"},
        1: {"Bến Tre", "Vũng Tàu", "Bạc Liêu"},
        2: {"Đồng Nai", "Cần Thơ", "Sóc Trăng"},
        3: {"Tây Ninh", "An Giang", "Bình Thuận"},
        4: {"Vĩnh Long", "Bình Dương", "Trà Vinh"},
        5: {"TP.HCM", "Long An", "Bình Phước", "Hậu Giang"},
        6: {"Tiền Giang", "Kiên Giang", "Đà Lạt"},
    }
    expected_stations = {normalize_station_key(x) for x in schedule[draw_date.weekday()]}
    actual_stations = {normalize_station_key(x) for x in out["province"].dropna().unique()}
    if not actual_stations or not actual_stations.issubset(expected_stations):
        raise ValueError(f"Tên đài không khớp lịch mở thưởng ngày {draw_date.strftime('%d/%m/%Y')}: {', '.join(map(str, out['province'].dropna().unique()))}.")
    out["prize"] = out["prize"].astype(str).str.strip().str.upper().replace({"DB": "ĐB"})
    if not set(out["prize"]).issubset(set(EXPECTED)):
        raise ValueError("Có nhãn giải không hợp lệ.")
    digit_width = {"ĐB": 6, "G1": 5, "G2": 5, "G3": 5, "G4": 5, "G5": 4, "G6": 4, "G7": 3, "G8": 2}
    normalized_numbers = []
    for _, row in out.iterrows():
        value = str(row["number"]).strip()
        if not value.isdigit() or len(value) != digit_width[row["prize"]]:
            raise ValueError(f"Sai độ dài hoặc ký tự số tại {row['province']} {row['prize']}: {value!r}.")
        normalized_numbers.append(value)
    out["number"] = normalized_numbers
    if out.duplicated(["date", "province", "prize", "number"]).any():
        raise ValueError("Dữ liệu có kết quả trùng lặp.")
    for station, group in out.groupby("province"):
        counts = group["prize"].value_counts().to_dict()
        if counts != EXPECTED or len(group) != 18:
            raise ValueError(f"Đài {station}: cơ cấu giải không đủ/không đúng 18 kết quả.")
    return out



def validate_partial_live_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate any published subset without requiring the draw's 18 results to be complete."""
    if frame.empty:
        return frame.copy()
    required = {"date", "province", "prize", "number"}
    if not required.issubset(frame.columns):
        raise ValueError("Thiếu cột bắt buộc trong dữ liệu trực tuyến.")
    out = frame.copy()
    parsed_dates = pd.to_datetime(out["date"], errors="coerce")
    if parsed_dates.isna().any() or parsed_dates.dt.normalize().nunique() != 1:
        raise ValueError("Ngày quay không hợp lệ hoặc bảng chứa nhiều ngày.")
    draw_date = parsed_dates.dt.date.iloc[0]
    schedule = {
        0: {"TP.HCM", "Đồng Tháp", "Cà Mau"}, 1: {"Bến Tre", "Vũng Tàu", "Bạc Liêu"},
        2: {"Đồng Nai", "Cần Thơ", "Sóc Trăng"}, 3: {"Tây Ninh", "An Giang", "Bình Thuận"},
        4: {"Vĩnh Long", "Bình Dương", "Trà Vinh"}, 5: {"TP.HCM", "Long An", "Bình Phước", "Hậu Giang"},
        6: {"Tiền Giang", "Kiên Giang", "Đà Lạt"},
    }
    expected_stations = {normalize_station_key(x) for x in schedule[draw_date.weekday()]}
    actual_stations = {normalize_station_key(x) for x in out["province"].dropna().unique()}
    if not actual_stations or not actual_stations.issubset(expected_stations):
        raise ValueError("Tên đài không khớp lịch mở thưởng của ngày quay.")
    out["prize"] = out["prize"].astype(str).str.strip().str.upper().replace({"DB": "ĐB"})
    if not set(out["prize"]).issubset(set(EXPECTED)):
        raise ValueError("Có nhãn giải không hợp lệ.")
    widths = {"ĐB": 6, "G1": 5, "G2": 5, "G3": 5, "G4": 5, "G5": 4, "G6": 4, "G7": 3, "G8": 2}
    for idx, row in out.iterrows():
        value = str(row["number"]).strip()
        prize = row["prize"]
        if not value.isdigit() or len(value) != widths[prize]:
            raise ValueError(f"Sai độ dài số tại {row['province']} {prize}: {value!r}.")
    if out.duplicated(["date", "province", "prize", "number"]).any():
        raise ValueError("Dữ liệu tạm có kết quả trùng lặp.")
    for station, group in out.groupby("province"):
        counts = group["prize"].value_counts().to_dict()
        if any(counts.get(prize, 0) > maximum for prize, maximum in EXPECTED.items()):
            raise ValueError(f"Đài {station}: số lượng một giải vượt cơ cấu cho phép.")
    return out


def fetch_live_xsmn_partial() -> tuple[pd.DataFrame, str]:
    """Fetch currently published numbers; missing prizes are allowed for live display only."""
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; XSMNAnalysisLab/1.0)"},
        timeout=15,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if cells:
                rows.append([cell.get_text(" ", strip=True) for cell in cells])
        if not rows:
            continue
        labels = {row[0].strip().upper() for row in rows if row}
        if not ({"G8", "G7", "G6", "G5", "G4", "G3", "G2", "G1"} <= labels and ({"ĐB", "DB"} & labels)):
            continue
        first = next((i for i, row in enumerate(rows) if row and row[0].strip().upper() == "G8"), None)
        if first is None or first == 0:
            continue
        provinces = [str(name).strip() for name in rows[first - 1][1:] if str(name).strip()]
        if not provinces:
            continue
        draw_date = _table_draw_date(table)
        records = []
        for row in rows[first:]:
            if not row:
                continue
            prize = row[0].strip().upper()
            if prize not in PRIZE_LABELS:
                continue
            for idx, province in enumerate(provinces, start=1):
                if idx >= len(row):
                    continue
                numbers = re.findall(r"(?<!\d)\d{2,6}(?!\d)", row[idx].strip())
                canonical_prize = "ĐB" if prize == "DB" else prize
                width = {"ĐB": 6, "G1": 5, "G2": 5, "G3": 5, "G4": 5, "G5": 4, "G6": 4, "G7": 3, "G8": 2}[canonical_prize]
                for number in numbers:
                    if len(number) == width:
                        records.append({"date": draw_date, "province": province, "prize": canonical_prize, "number": number})
        frame = validate_partial_live_frame(pd.DataFrame(records, columns=["date", "province", "prize", "number"]))
        return frame, response.url
    raise ValueError("Không tìm thấy bảng kết quả trực tuyến có ngày quay xác định.")


def fetch_xosodaiphat_xsmn_partial(draw_date: str) -> tuple[pd.DataFrame, str]:
    """Fallback live feed: parse Xo So Dai Phat's current XSMN live scoreboard."""
    target = pd.to_datetime(draw_date, errors="coerce")
    if pd.isna(target):
        raise ValueError("Ngày yêu cầu nguồn dự phòng không hợp lệ.")
    target_date = target.date()
    url = "https://xosodaiphat.com/xsmn-truc-tiep.html"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; XSMNAnalysisLab/1.0)"}, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    page_dates = set()
    for node in soup.find_all(["h1", "h2", "h3", "h4", "caption"]):
        for match in DATE_RE.finditer(node.get_text(" ", strip=True)):
            try:
                page_dates.add(datetime.strptime("/".join(match.groups()), "%d/%m/%Y").date())
            except ValueError:
                pass
    if target_date not in page_dates:
        found = ", ".join(sorted(d.strftime("%d/%m/%Y") for d in page_dates)) or "không xác định"
        raise ValueError(f"Trang dự phòng chưa xác nhận kỳ {target_date.strftime('%d/%m/%Y')} (ngày trên trang: {found}).")

    station_names = {"vinhlong": "Vĩnh Long", "binhduong": "Bình Dương", "travinh": "Trà Vinh"}
    prize_aliases = {
        "G8": "G8", "G.8": "G8", "G7": "G7", "G.7": "G7", "G6": "G6", "G.6": "G6",
        "G5": "G5", "G.5": "G5", "G4": "G4", "G.4": "G4", "G3": "G3", "G.3": "G3",
        "G2": "G2", "G.2": "G2", "G1": "G1", "G.1": "G1", "ĐB": "ĐB", "DB": "ĐB",
        "GĐB": "ĐB", "G.ĐB": "ĐB"
    }
    widths = {"ĐB": 6, "G1": 5, "G2": 5, "G3": 5, "G4": 5, "G5": 4, "G6": 4, "G7": 3, "G8": 2}
    maximums = {"ĐB": 1, "G1": 1, "G2": 1, "G3": 2, "G4": 7, "G5": 1, "G6": 3, "G7": 1, "G8": 1}
    records = []
    found_station_table = False
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if cells:
                rows.append([cell.get_text(" ", strip=True) for cell in cells])
        header_idx, header_keys = None, []
        for idx, row in enumerate(rows):
            keys = [normalize_station_key(cell) for cell in row]
            if all(key in keys for key in station_names):
                header_idx, header_keys = idx, keys
                break
        if header_idx is None:
            continue
        found_station_table = True
        columns = {key: header_keys.index(key) for key in station_names}
        for row in rows[header_idx + 1:]:
            if not row:
                continue
            raw_label = re.sub(r"\s+", "", row[0]).upper()
            prize = prize_aliases.get(raw_label)
            if not prize:
                continue
            for station_key, col_idx in columns.items():
                if col_idx >= len(row):
                    continue
                values = [v for v in re.findall(r"(?<!\d)\d{2,6}(?!\d)", row[col_idx]) if len(v) == widths[prize]]
                if len(values) > maximums[prize]:
                    raise ValueError(f"{station_names[station_key]} {prize}: nguồn dự phòng trả quá số lượng cho phép.")
                records.extend({"date": target_date.isoformat(), "province": station_names[station_key], "prize": prize, "number": v} for v in values)
        break
    if not found_station_table:
        raise ValueError("Không tìm thấy bảng trực tiếp có đủ cột Vĩnh Long, Bình Dương và Trà Vinh.")
    frame = validate_partial_live_frame(pd.DataFrame(records, columns=["date", "province", "prize", "number"]))
    return frame, response.url

def fetch_live_xsmn() -> tuple[pd.DataFrame, str]:
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; XSMNAnalysisLab/1.0)"},
        timeout=15,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    for table in tables:
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if cells:
                rows.append([cell.get_text(" ", strip=True) for cell in cells])
        if not rows:
            continue
        labels = {row[0].strip().upper() for row in rows if row}
        if not ({"G8", "G7", "G6", "G5", "G4", "G3", "G2", "G1"} <= labels and ({"ĐB", "DB"} & labels)):
            continue
        first_prize_row = next((i for i, row in enumerate(rows) if row and row[0].strip().upper() == "G8"), None)
        if first_prize_row is None or first_prize_row == 0:
            continue
        headers = rows[first_prize_row - 1]
        provinces = [str(name).strip() for name in headers[1:] if str(name).strip()]
        if not provinces:
            continue
        draw_date = _table_draw_date(table)
        records = []
        for row in rows[first_prize_row:]:
            if not row:
                continue
            prize = row[0].strip().upper()
            if prize not in PRIZE_LABELS:
                continue
            for idx, province in enumerate(provinces, start=1):
                if idx >= len(row):
                    raise ValueError(f"Bảng kết quả thiếu cột của đài {province}.")
                cell_text = row[idx].strip()
                numbers = re.findall(r"(?<!\d)\d{2,6}(?!\d)", cell_text)
                if not numbers:
                    raise ValueError(f"Đài {province} giải {prize} chưa có số; kết quả có thể chưa quay xong.")
                records.extend({"date": draw_date, "province": province, "prize": "ĐB" if prize == "DB" else prize, "number": number} for number in numbers)
        frame = validate_live_frame(pd.DataFrame(records))
        return frame, response.url
    raise ValueError("Không tìm thấy bảng giải XSMN có đủ nhãn giải và ngày quay nhận diện được.")
