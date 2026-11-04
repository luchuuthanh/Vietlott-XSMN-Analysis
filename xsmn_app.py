"""Ứng dụng phân tích XSMN độc lập."""
import streamlit as st
import pandas as pd
from analytics import frequency_table, gap_table
from data_loader import load_xsmn

st.set_page_config(page_title="XSMN Analysis Lab", page_icon="🍀", layout="wide")
st.title("🍀 XSMN ANALYSIS LAB")
st.caption("Thống kê lô tô miền Nam theo tỉnh, ngày và giải. Không phải công cụ bảo đảm dự đoán.")

with st.sidebar:
    st.header("Dữ liệu XSMN")
    upload = st.file_uploader("Tải CSV lịch sử XSMN", type=["csv"])
    st.caption("CSV mẫu: data/xsmn_template.csv")

if upload is None:
    st.info("Tải CSV kết quả XSMN để bắt đầu phân tích. Ứng dụng chưa tự động kết nối nguồn kết quả trực tiếp.")
    st.stop()

try:
    raw = load_xsmn(upload)
    if raw.empty:
        st.warning("File chưa có kết quả hợp lệ.")
        st.stop()
    provinces = sorted(raw["province"].unique().tolist())
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
    c1, c2, c3 = st.columns(3)
    c1.metric("Tỉnh đã chọn", province)
    c2.metric("Ngày có dữ liệu", len(dates))
    c3.metric("Số kết quả", len(subset))
    t1, t2, t3 = st.tabs(["Lô tô 2 số", "Theo giải", "Dữ liệu"])
    with t1:
        a, b = st.columns(2)
        with a:
            st.markdown("**Tần suất xuất hiện**")
            st.dataframe(freq.head(20), use_container_width=True, hide_index=True)
        with b:
            st.markdown("**Số lâu chưa xuất hiện**")
            st.dataframe(gaps.head(20), use_container_width=True, hide_index=True)
        st.bar_chart(freq.set_index("Số")["Số lần"])
        st.caption("Gan tính theo số ngày/kỳ có dữ liệu của tỉnh đã chọn, không phải số ngày lịch.")
    with t2:
        by_prize = subset.groupby("prize")["number"].count().sort_values(ascending=False).rename("Số kết quả")
        st.dataframe(by_prize, use_container_width=True)
    with t3:
        st.dataframe(data.sort_values(["date", "prize"], ascending=[False, True]), use_container_width=True, hide_index=True)
        st.download_button("Tải dữ liệu tỉnh CSV", data.to_csv(index=False).encode("utf-8-sig"), "xsmn_clean.csv", "text/csv")
except Exception as exc:
    st.error(f"Không đọc được dữ liệu XSMN: {exc}")
    st.info("Định dạng cần có: date, province, prize, number. Xem data/xsmn_template.csv.")
