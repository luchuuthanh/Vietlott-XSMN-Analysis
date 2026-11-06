"""Ứng dụng phân tích XSMN độc lập."""
from datetime import date
from pathlib import Path
import streamlit as st
import pandas as pd
from analytics import frequency_table, gap_table
from data_loader import load_xsmn
from xsmn_archive import fetch_xsmn_five_years

st.set_page_config(page_title="XSMN Analysis Lab", page_icon="🍀", layout="wide")
st.title("🍀 XSMN ANALYSIS LAB")
st.caption("Thống kê lô tô miền Nam theo tỉnh, ngày và giải. Không phải công cụ bảo đảm dự đoán.")

with st.sidebar:
    st.header("Dữ liệu XSMN")
    source = st.radio("Nguồn dữ liệu", ["Kho lịch sử 5 năm", "Tải CSV riêng"])
    upload = st.file_uploader("Tải CSV lịch sử XSMN", type=["csv"]) if source == "Tải CSV riêng" else None
    st.caption("Kho lịch sử công khai: SQLite theo quý. Cửa sổ mục tiêu từ 04/11/2021.")

raw = pd.DataFrame()
archive_status = pd.DataFrame()
if source == "Kho lịch sử 5 năm":
    canonical = Path("data/xsmn_5y_canonical.csv")
    manifest = Path("data/xsmn_5y_canonical.json")
    if canonical.exists() and manifest.exists():
        try:
            import json
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            if meta.get("status") != "PASS":
                raise ValueError("Manifest chưa xác nhận PASS")
            raw = pd.read_csv(canonical, dtype={"number": str, "last2": str})
            st.caption(f"Dữ liệu chuẩn đã kiểm định: {meta.get('window_start')} → {meta.get('window_end')} · {meta.get('rows')} dòng · cập nhật {meta.get('updated_at_vietnam')}")
        except Exception as exc:
            st.error(f"Không đọc được bản dữ liệu chuẩn đã xuất bản: {exc}")
            st.stop()
    else:
        st.warning("Chưa có bản dữ liệu chuẩn được xuất bản; đang dùng kho SQLite dự phòng.")
        with st.spinner("Đang tải kho SQLite XSMN theo quý..."):
            try:
                archive, archive_status = fetch_xsmn_five_years(date.today().isoformat())
                if not archive.empty:
                    raw = archive.copy()
                else:
                    st.error("Chưa tải được dữ liệu từ kho lịch sử. Có thể chuyển sang tải CSV.")
            except Exception as exc:
                st.error(f"Không tải được kho lịch sử: {exc}")
elif upload is not None:
    try:
        raw = load_xsmn(upload)
    except Exception as exc:
        st.error(f"Không đọc được CSV: {exc}")

if not archive_status.empty:
    with st.expander("Tình trạng tải dữ liệu theo quý", expanded=True):
        st.dataframe(archive_status, use_container_width=True, hide_index=True)
if raw.empty:
    st.info("Chọn kho lịch sử 5 năm hoặc tải CSV để bắt đầu phân tích.")
    st.stop()

try:
    if "last2" not in raw.columns:
        raw["last2"] = raw["number"].astype(str).str[-2:].astype(int)
    provinces = sorted(raw["province"].dropna().unique().tolist())
    province = st.sidebar.selectbox("Tỉnh", provinces)
    data = raw[raw["province"] == province].copy()
    dates = sorted(data["date"].dropna().unique())
    if not dates:
        st.warning("Tỉnh này chưa có ngày dữ liệu hợp lệ.")
        st.stop()
    recent_n = st.slider("Số ngày/kỳ gần nhất", 1, len(dates), min(90, len(dates)))
    chosen_dates = set(dates[-recent_n:])
    subset = data[data["date"].isin(chosen_dates)].copy()
    draws = subset.groupby("date")["last2"].apply(list).tolist()
    flat = subset["last2"].astype(int).tolist()
    freq = frequency_table(flat, 99, start=0)
    gaps = gap_table(draws, 99, start=0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tỉnh đã chọn", province)
    c2.metric("Ngày có dữ liệu", len(dates))
    c3.metric("Số kết quả", len(data))
    c4.metric("Số tỉnh trong kho", raw["province"].nunique())
    t1, t2, t3, t4 = st.tabs(["Lô tô 2 số", "Theo giải", "Dữ liệu", "Kiểm tra độ phủ"])
    with t1:
        a, b = st.columns(2)
        with a:
            st.markdown("**Tần suất xuất hiện**")
            st.dataframe(freq.head(20), use_container_width=True, hide_index=True)
        with b:
            st.markdown("**Số lâu chưa xuất hiện**")
            st.dataframe(gaps.head(20), use_container_width=True, hide_index=True)
        st.bar_chart(freq.set_index("Số")["Số lần"])
        st.caption("Gan tính theo số kỳ có dữ liệu của tỉnh đã chọn, không phải số ngày lịch.")
    with t2:
        by_prize = subset.groupby("prize")["number"].count().sort_values(ascending=False).rename("Số kết quả")
        st.dataframe(by_prize, use_container_width=True)
    with t3:
        st.dataframe(data.sort_values(["date", "prize"], ascending=[False, True]), use_container_width=True, hide_index=True)
        st.download_button("Tải dữ liệu tỉnh CSV", data.to_csv(index=False).encode("utf-8-sig"), "xsmn_clean.csv", "text/csv")
    with t4:
        st.metric("Ngày đầu có dữ liệu", pd.to_datetime(data["date"]).min().strftime("%d/%m/%Y"))
        st.metric("Ngày cuối có dữ liệu", pd.to_datetime(data["date"]).max().strftime("%d/%m/%Y"))
        if not archive_status.empty:
            st.dataframe(archive_status, use_container_width=True, hide_index=True)
        st.caption("Bảng này cho biết tình trạng tải từng quý; cần đối chiếu số kỳ theo lịch quay và nguồn chính thức trước khi xác nhận dữ liệu đầy đủ.")
except Exception as exc:
    st.error(f"Không thể phân tích dữ liệu XSMN: {exc}")
    st.info("CSV cần có các cột: date, province, prize, number.")
