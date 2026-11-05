#!/usr/bin/env python3
"""Audit the public quarterly XSMN SQLite archive without modifying source data."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.request import urlopen
import pandas as pd

OWNER_REPO = "itgi8vn/api-kqxs-archives-quarterly"
START = date(2021, 11, 5)
END = date.today()
BASE = f"https://raw.githubusercontent.com/{OWNER_REPO}/main/archives"
OUT = Path("xsmn_audit")
OUT.mkdir(exist_ok=True)


def quarters(start: date, end: date):
    y, q = start.year, (start.month - 1) // 3 + 1
    last_y, last_q = end.year, (end.month - 1) // 3 + 1
    while (y, q) <= (last_y, last_q):
        yield y, q
        if q == 4:
            y, q = y + 1, 1
        else:
            q += 1


def fetch_quarter(year: int, quarter: int):
    errors = []
    for suffix in ("", "_v2"):
        url = f"{BASE}/{year}/Q{quarter}/kqxs_{year}_Q{quarter}{suffix}.sqlite"
        try:
            with urlopen(url, timeout=60) as response:
                payload = response.read()
            conn = sqlite3.connect(":memory:")
            conn.deserialize(payload)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required = {"lottery_draws", "lottery_results", "lottery_provinces"}
            if not required.issubset(tables):
                raise ValueError(f"missing tables: {sorted(required - tables)}")
            integrity = [row[0] for row in conn.execute("PRAGMA quick_check")]\n            if integrity != ["ok"]:\n                raise ValueError(f"SQLite quick_check failed: {integrity[:5]}")\n            foreign_key_errors = list(conn.execute("PRAGMA foreign_key_check"))\n            if foreign_key_errors:\n                raise ValueError(f"SQLite foreign_key_check found {len(foreign_key_errors)} errors")\n            dcols = {r[1] for r in conn.execute("PRAGMA table_info(lottery_draws)")}
            rcols = {r[1] for r in conn.execute("PRAGMA table_info(lottery_results)")}
            pcols = {r[1] for r in conn.execute("PRAGMA table_info(lottery_provinces)")}
            for col in ("draw_key", "draw_date", "province_code", "region_code"):
                if col not in dcols: raise ValueError(f"missing lottery_draws.{col}")
            for col in ("draw_key", "prize_code", "prize_order", "result_number"):
                if col not in rcols: raise ValueError(f"missing lottery_results.{col}")
            pcode = "province_code" if "province_code" in pcols else "code"
            pname = next((c for c in ("province_name", "name", "display_name") if c in pcols), None)
            if pcode not in pcols or not pname: raise ValueError("unrecognized province columns")
            sql = f"""
              SELECT d.draw_date AS date, p.{pname} AS province,
                     r.prize_code AS prize, r.prize_order AS prize_order,
                     CAST(r.result_number AS TEXT) AS number
              FROM lottery_draws d
              JOIN lottery_results r ON r.draw_key=d.draw_key
              JOIN lottery_provinces p ON p.{pcode}=d.province_code
              WHERE d.region_code='MN' AND d.draw_date>=? AND d.draw_date<=?
              ORDER BY d.draw_date,p.{pname},r.prize_code,r.prize_order
            """
            frame = pd.read_sql_query(sql, conn, params=(START.isoformat(), END.isoformat()))
            conn.close()
            return frame, {"quarter": f"{year}Q{quarter}", "status": "downloaded",
                           "source_variant": suffix or "v1", "sqlite_integrity": "ok",\n                           "foreign_key_errors": 0, "rows": len(frame),
                           "provinces": int(frame.province.nunique()) if len(frame) else 0,
                           "url": url}
        except Exception as exc:
            errors.append(f"{suffix or 'v1'}: {exc}")
    return pd.DataFrame(columns=["date","province","prize","prize_order","number"]), {
        "quarter": f"{year}Q{quarter}", "status": "missing_or_error",
        "details": " | ".join(errors)
    }


def main():
    frames, statuses = [], []
    for year, quarter in quarters(START, END):
        frame, status = fetch_quarter(year, quarter)
        statuses.append(status)
        if not frame.empty:
            frames.append(frame)

    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["date","province","prize","prize_order","number"])
    if not data.empty:
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data["province"] = data["province"].astype(str).str.strip()
        data["prize"] = data["prize"].astype(str).str.strip()
        data["number"] = data["number"].astype(str).str.replace(r"\D", "", regex=True)
        data = data.dropna(subset=["date"])
        data = data[(data.date >= pd.Timestamp(START)) & (data.date <= pd.Timestamp(END))]
        key = ["date","province","prize","prize_order","number"]
        duplicates = data[data.duplicated(key, keep=False)].sort_values(key)
        data["number_length"] = data.number.str.len()
        invalid = data[~data.number_length.between(2, 6)].copy()
        data["last2"] = data.number.str[-2:]
        data["last2_numeric"] = pd.to_numeric(data.last2, errors="coerce")
        province = data.groupby("province").agg(
            first_date=("date","min"), last_date=("date","max"),
            draw_dates=("date","nunique"), result_rows=("number","size"),
            prize_codes=("prize","nunique")).reset_index()
        prize = data.groupby(["province","prize"]).size().rename("rows").reset_index()
        daily = data.groupby(["date","province"]).agg(rows=("number","size"),
            prize_codes=("prize","nunique")).reset_index()
        data.sort_values(["date","province","prize","prize_order"]).to_csv(
            OUT/"xsmn_cleaned_rows.csv", index=False)
        duplicates.to_csv(OUT/"duplicates.csv", index=False)
        invalid.to_csv(OUT/"invalid_numbers.csv", index=False)
        province.to_csv(OUT/"province_coverage.csv", index=False)
        prize.to_csv(OUT/"province_prize_coverage.csv", index=False)
        daily.to_csv(OUT/"daily_province_coverage.csv", index=False)
        date_min, date_max = str(data.date.min().date()), str(data.date.max().date())
        province_count = int(data.province.nunique())
        row_count = int(len(data))
        duplicate_rows = int(len(duplicates))
        invalid_rows = int(len(invalid))
        unique_last2 = int(data.last2_numeric.nunique())
        missing_last2 = sorted(set(range(100)) - set(
            data.last2_numeric.dropna().astype(int).tolist()))
        last2_rows = []
        for province_name, group in data.groupby("province"):
            seen = set(group.last2_numeric.dropna().astype(int).tolist())
            missing = sorted(set(range(100)) - seen)
            last2_rows.append({
                "province": province_name,
                "distinct_last2": len(seen),
                "missing_count": len(missing),
                "missing_values": " ".join(f"{n:02d}" for n in missing),
            })
        pd.DataFrame(last2_rows).to_csv(OUT/"last2_00_99_by_province.csv", index=False)
    else:
        date_min = date_max = None
        province_count = row_count = duplicate_rows = invalid_rows = unique_last2 = 0
        missing_last2 = list(range(100))
        for name, cols in (("duplicates.csv", ["date","province","prize","prize_order","number"]),
                           ("invalid_numbers.csv", ["date","province","prize","prize_order","number"]),
                           ("province_coverage.csv", ["province","first_date","last_date","draw_dates","result_rows","prize_codes"]),
                           ("province_prize_coverage.csv", ["province","prize","rows"]),
                           ("daily_province_coverage.csv", ["date","province","rows","prize_codes"]),
                           ("last2_00_99_by_province.csv", ["province","distinct_last2","missing_count","missing_values"])):
            pd.DataFrame(columns=cols).to_csv(OUT/name, index=False)

    pd.DataFrame(statuses).to_csv(OUT/"quarter_status.csv", index=False)
    summary = {
        "window_start": START.isoformat(), "window_end": END.isoformat(),
        "actual_data_start": date_min, "actual_data_end": date_max,
        "quarter_count_expected": len(statuses),
        "quarter_count_downloaded": sum(s["status"] == "downloaded" for s in statuses),
        "quarter_count_missing_or_error": sum(s["status"] != "downloaded" for s in statuses),
        "result_rows": row_count, "province_count": province_count,
        "duplicate_rows_flagged": duplicate_rows, "invalid_number_rows": invalid_rows,
        "distinct_last_two_digit_values": unique_last2,
        "missing_last_two_digit_values": missing_last2,
        "note": "Coverage is descriptive. This report does not certify expected draws or official correctness."
    }
    (OUT/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
