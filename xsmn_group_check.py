"""Kiểm tra chọn 3 số theo từng nhóm 10 kỳ, đối chiếu kỳ N+1."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from xsmn_algorithms import rank_numbers


METHOD_LABELS = {
    "freq_30": "Tần suất 30 kỳ",
    "freq_90": "Tần suất 90 kỳ",
    "freq_365": "Tần suất 365 kỳ",
    "gap": "Số ít xuất hiện",
}


def _digits(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return "".join(ch for ch in text if ch.isdigit())


def _prepare_station_draws(frame, station):
    required = {"date", "province", "prize", "number"}
    if not required.issubset(frame.columns):
        return []
    df = frame[frame["province"].astype(str) == str(station)].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])
    df["_prize"] = df["prize"].astype(str).str.strip().str.upper()
    source = df["last2"] if "last2" in df.columns else df["number"]
    df["_last2"] = source.map(_digits).str[-2:].str.zfill(2)
    df = df[df["_last2"].str.fullmatch(r"\d{2}", na=False)]
    rows = []
    for draw_date, group in df.groupby("date", sort=True):
        values = group["_last2"].tolist()
        g7 = group.loc[group["_prize"] == "G7", "_last2"].tolist()
        db = group.loc[group["_prize"].isin({"ĐB", "DB", "GĐB"}), "_last2"].tolist()
        rows.append({
            "date": draw_date,
            "all": set(values),
            "g7": set(g7),
            "db": set(db),
            "all_text": ", ".join(sorted(set(values))),
            "g7_text": ", ".join(g7) if g7 else "Chưa có",
            "db_text": ", ".join(db) if db else "Chưa có",
        })
    return rows


def _rate(hits, selections):
    return (100.0 * hits / selections) if selections else 0.0


def render_group_check(frame, stations):
    st.subheader("Kiểm tra thuật toán – Chọn 3 số")
    st.caption(
        "Chia nhóm cố định 10 kỳ. Mỗi kỳ N chỉ dùng dữ liệu đến hết N để chọn 3 số, "
        "sau đó mới đối chiếu với kết quả N+1."
    )
    if not stations:
        st.warning("Chưa chọn đài.")
        return

    station = st.selectbox("Đài kiểm tra", stations, key="group_check_station")
    method = st.selectbox(
        "Thuật toán chọn số",
        list(METHOD_LABELS),
        format_func=lambda value: METHOD_LABELS[value],
        key="group_check_method",
    )
    draws = _prepare_station_draws(frame, station)
    if len(draws) < 2:
        st.warning("Đài chưa có đủ ít nhất 2 kỳ dữ liệu để kiểm tra.")
        return

    history = [(item["date"], {int(value) for value in item["all"]}) for item in draws]
    transitions = []
    for idx in range(len(draws) - 1):
        selected = rank_numbers(history[:idx + 1], method, top_k=3)["Số"].tolist()
        selected_set = set(selected)
        target = draws[idx + 1]
        hits_g7 = sorted(selected_set & target["g7"])
        hits_db = sorted(selected_set & target["db"])
        hits_all = sorted(selected_set & target["all"])
        transitions.append({
            "n": idx + 1,
            "target": idx + 2,
            "group": idx // 10,
            "date_n": draws[idx]["date"],
            "date_target": target["date"],
            "selected": " · ".join(selected),
            "g7_actual": target["g7_text"],
            "g7_hits": " · ".join(hits_g7) if hits_g7 else "—",
            "db_actual": target["db_text"],
            "db_hits": " · ".join(hits_db) if hits_db else "—",
            "all_actual": target["all_text"],
            "all_hits": " · ".join(hits_all) if hits_all else "—",
            "g7_count": len(hits_g7),
            "db_count": len(hits_db),
            "all_count": len(hits_all),
        })

    group_count = (len(transitions) + 9) // 10
    group_options = list(range(group_count))
    selected_group = st.selectbox(
        "Nhóm 10 kỳ",
        group_options,
        format_func=lambda value: f"Kỳ {value * 10 + 1}–{value * 10 + 10}",
        key="group_check_period",
    )
    current = [row for row in transitions if row["group"] == selected_group]
    if not current:
        st.info("Nhóm này chưa có kỳ N+1 để đối chiếu.")
        return

    st.markdown("#### Kết quả đối chiếu từng kỳ")
    detail = pd.DataFrame([{
        "Kỳ N → N+1": f'{row["n"]} → {row["target"]}',
        "3 số chọn": row["selected"],
        "G7 · KQ N+1": row["g7_actual"],
        "G7 · Trúng": row["g7_hits"],
        "ĐB · KQ N+1": row["db_actual"],
        "ĐB · Trúng": row["db_hits"],
        "Tất cả giải · KQ N+1": row["all_actual"],
        "Tất cả giải · Trúng": row["all_hits"],
    } for row in current])
    st.dataframe(detail, use_container_width=True, hide_index=True)

    scopes = [("G7", "g7_count"), ("Giải Đặc biệt", "db_count"), ("Tất cả giải", "all_count")]
    cumulative = []
    for pos in range(1, 11):
        sample = current[:pos]
        if not sample:
            continue
        record = {"Sau kỳ": pos}
        for label, key in scopes:
            hits = sum(row[key] for row in sample)
            selections = 3 * len(sample)
            record[label] = f"{_rate(hits, selections):.1f}% ({hits}/{selections})".replace(".", ",")
        cumulative.append(record)

    st.markdown("#### Tỷ lệ lũy kế sau từng kỳ")
    st.dataframe(pd.DataFrame(cumulative), use_container_width=True, hide_index=True)

    summary = []
    for label, key in scopes:
        hits = sum(row[key] for row in current)
        tested = len(current)
        summary.append({
            "Phạm vi": label,
            "Số trúng / lượt chọn": f"{hits} / {tested * 3}",
            "Tỷ lệ đạt": f"{_rate(hits, tested * 3):.1f}%".replace(".", ","),
            "Số kỳ có ít nhất 1 số trúng": f'{sum(row[key] > 0 for row in current)} / {tested}',
        })
    st.markdown(f"#### Tổng kết nhóm kỳ {selected_group * 10 + 1}–{selected_group * 10 + 10}")
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
    st.caption(
        "Tỷ lệ đạt = tổng số dự đoán trúng / (3 số × số kỳ đã kiểm tra). "
        "Cột số kỳ có trúng được tính riêng. KQ N+1 của tất cả giải là danh sách hai số cuối, "
        "mỗi số dự đoán chỉ tính trúng một lần trong một kỳ."
    )
