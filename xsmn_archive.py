"""Tải và chuẩn hóa kho SQLite XSMN công khai theo quý.

Nguồn archive: https://github.com/itgi8vn/api-kqxs-archives-quarterly
Chỉ đọc miền Nam (MN), lọc đúng cửa sổ 5 năm và giữ số kết quả dạng chuỗi.
"""
from __future__ import annotations

import io
import sqlite3
from datetime import date
from typing import Iterable

import pandas as pd
import requests
import streamlit as st

ARCHIVE_RAW = (
    "https://raw.githubusercontent.com/itgi8vn/api-kqxs-archives-quarterly/"
    "main/archives/{year}/Q{quarter}/kqxs_{year}_Q{quarter}.sqlite"
)
START_DATE = date(2021, 11, 4)
TIMEOUT = 45


def _quarters(start: date, end: date) -> Iterable[tuple[int, int]]:
    year, quarter = start.year, (start.month - 1) // 3 + 1
    while (year, quarter) <= (end.year, (end.month - 1) // 3 + 1):
        yield year, quarter
        if quarter == 4:
            year, quarter = year + 1, 1
        else:
            quarter += 1


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _read_archive(payload: bytes, start_iso: str, end_iso: str) -> pd.DataFrame:
    conn = sqlite3.connect(":memory:")
    try:
        conn.deserialize(payload)
        required_tables = {"lottery_draws", "lottery_results", "lottery_provinces"}
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not required_tables.issubset(tables):
            raise ValueError("SQLite archive thiếu bảng KQXS bắt buộc.")

        dcols = _columns(conn, "lottery_draws")
        rcols = _columns(conn, "lottery_results")
        pcols = _columns(conn, "lottery_provinces")
        for col in ("draw_key", "draw_date", "province_code", "region_code"):
            if col not in dcols:
                raise ValueError(f"Không thấy cột lottery_draws.{col}")
        for col in ("draw_key", "prize_code", "prize_order", "result_number"):
            if col not in rcols:
                raise ValueError(f"Không thấy cột lottery_results.{col}")
        pcode = "province_code" if "province_code" in pcols else "code"
        pname = next((c for c in ("province_name", "name", "display_name") if c in pcols), None)
        if not pname:
            raise ValueError("Không nhận diện được cột tên tỉnh trong archive.")
        sql = f"""
            SELECT d.draw_date AS date, p.{pname} AS province,
                   r.prize_code AS prize, r.prize_order AS prize_order,
                   CAST(r.result_number AS TEXT) AS number
            FROM lottery_draws d
            JOIN lottery_results r ON r.draw_key = d.draw_key
            JOIN lottery_provinces p ON p.{pcode} = d.province_code
            WHERE d.region_code = 'MN'
              AND d.draw_date >= ? AND d.draw_date <= ?
            ORDER BY d.draw_date, p.{pname}, r.prize_code, r.prize_order
        """
        return pd.read_sql_query(sql, conn, params=(start_iso, end_iso))
    finally:
        conn.close()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_xsmn_five_years(end_iso: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    end = date.fromisoformat(end_iso)
    start_iso = START_DATE.isoformat()
    frames, status = [], []
    session = requests.Session()
    for year, quarter in _quarters(START_DATE, end):
        url = ARCHIVE_RAW.format(year=year, quarter=quarter)
        try:
            response = session.get(url, timeout=TIMEOUT)
            if response.status_code == 404:
                status.append({"Quý": f"{year} Q{quarter}", "Trạng thái": "Chưa có archive"})
                continue
            response.raise_for_status()
            frame = _read_archive(response.content, start_iso, end.isoformat())
            frames.append(frame)
            status.append({
                "Quý": f"{year} Q{quarter}",
                "Trạng thái": "Đã tải",
                "Số kết quả": len(frame),
                "Số tỉnh": frame["province"].nunique() if not frame.empty else 0,
            })
        except Exception as exc:
            status.append({"Quý": f"{year} Q{quarter}", "Trạng thái": f"Lỗi: {exc}"})
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["date", "province", "prize", "prize_order", "number"]
    )
    if not data.empty:
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data["province"] = data["province"].astype(str).str.strip()
        data["prize"] = data["prize"].astype(str)
        data["number"] = data["number"].astype(str).str.replace(r"\D", "", regex=True)
        data = data.dropna(subset=["date"])
        data = data[(data["date"] >= pd.Timestamp(start_iso)) &
                    (data["date"] <= pd.Timestamp(end.isoformat()))]
        data["last2"] = data["number"].str[-2:].astype("Int64")
        data = data.dropna(subset=["last2"]).drop_duplicates(
            subset=["date", "province", "prize", "prize_order", "number"]
        ).reset_index(drop=True)
    return data, pd.DataFrame(status)
