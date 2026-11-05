"""Ứng dụng phân tích Vietlott độc lập."""
import streamlit as st
import pandas as pd
from analytics import frequency_table, gap_table, pair_table, draw_metrics, score_candidates
from data_loader import load_vietlott
from generator import make_sets
from data_sources import fetch_vietlott

st.set_page_config(page_title="Vietlott Analysis Lab", page_icon="🎯", layout="wide")
st.title("🎯 VIETLOTT ANALYSIS LAB")
st.caption("Phân tích Power 6/55 và Mega 6/45. Với Power 6/55, 6 số chính và số đặc biệt được thống kê riêng; số đặc biệt không tham gia tần suất 6 số chính.")

with st.sidebar:
    st.header("Nguồn dữ liệu")
    upload = st.file_uploader("Tải CSV lịch sử Vietlott", type=["csv"])
    st.caption("CSV mẫu: data/vietlott_template.csv")

try:
    if upload is not None:
        raw = load_vietlott(upload)
    else:
        with st.spinner("Đang tải dữ liệu Vietlott..."):
            raw = pd.concat([fetch_vietlott("POWER655"), fetch_vietlott("MEGA645")], ignore_index=True)
    games = sorted(raw["game"].unique().tolist())
    if not games:
        st.warning("Chưa có dữ liệu Vietlott.")
        st.stop()
    selected = st.sidebar.selectbox("Loại vé", games)
    data = raw[raw["game"] == selected].copy()
    cols = ["n1", "n2", "n3", "n4", "n5", "n6"]
    universe = 55 if "655" in selected else 45
    if len(data) < 10:
        st.warning("Cần tối thiểu 10 kỳ quay để thống kê ổn định.")
        st.stop()
    recent_n = st.slider("Số kỳ gần nhất đưa vào thống kê", 10, len(data), min(200, len(data)))
    subset = data.tail(recent_n)
    draws = subset[cols].astype(int).values.tolist()
    flat = [n for draw in draws for n in draw]
    freq = frequency_table(flat, universe)
    gaps = gap_table(draws, universe)
    st.subheader(f"Phân tích {selected}")
    st.caption(f"Phạm vi dữ liệu: {data['date'].min():%d/%m/%Y} – {data['date'].max():%d/%m/%Y}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Số kỳ đã nạp", f"{len(data):,}")
    c2.metric("Kỳ đang phân tích", f"{len(subset):,}")
    c3.metric("Số lớn nhất", universe)
    c4.metric("Kỳ mới nhất", str(data.iloc[-1]["draw_id"]))
    t1, t2, t3, t4, t5 = st.tabs(["Tần suất & gan", "Cặp số", "Cấu trúc kỳ quay", "Bộ số tham khảo", "Dữ liệu"])
    with t1:
        a, b = st.columns(2)
        with a:
            st.markdown("**Tần suất cao nhất**")
            st.dataframe(freq.head(20), use_container_width=True, hide_index=True)
        with b:
            st.markdown("**Số lâu chưa xuất hiện**")
            st.dataframe(gaps.head(20), use_container_width=True, hide_index=True)
        st.bar_chart(freq.set_index("Số")["Số lần"])
        if "special" in subset.columns:
            special = pd.to_numeric(subset["special"], errors="coerce").dropna().astype(int)
            if not special.empty:
                st.markdown("**Số đặc biệt Power 6/55 — quay riêng sau 6 số chính, chỉ dùng xét Jackpot 2**")
                special_freq = special.value_counts().rename_axis("Số đặc biệt").reset_index(name="Số lần")
                st.dataframe(special_freq, use_container_width=True, hide_index=True)
            missing_special = int(pd.to_numeric(subset["special"], errors="coerce").isna().sum())
            if missing_special:
                st.caption(f"Có {missing_special} kỳ trong phạm vi đang xem chưa có dữ liệu số đặc biệt; hệ thống không tự điền hoặc suy đoán.")
    with t2:
        st.dataframe(pair_table(draws, 30), use_container_width=True, hide_index=True)
    with t3:
        metrics = draw_metrics(draws)
        st.dataframe(metrics.tail(100).iloc[::-1], use_container_width=True, hide_index=True)
        st.bar_chart(metrics.set_index("Kỳ")[["Tổng", "Delta"]])
    with t4:
        ranked = score_candidates(freq, gaps, universe, universe)
        st.caption("Điểm là công thức xếp hạng thống kê nội bộ, không phải xác suất trúng.")
        st.dataframe(ranked.head(20), use_container_width=True, hide_index=True)
        n = st.selectbox("Số lượng số mỗi bộ", [6, 7, 8], index=0)
        k = st.slider("Số bộ muốn tạo", 1, 10, 5)
        sets = make_sets(ranked, count=n, sets=k)
        st.dataframe(pd.DataFrame(sets), use_container_width=True, hide_index=True)
        if sets:
            st.download_button("Tải bộ số CSV", pd.DataFrame(sets).to_csv(index=False).encode("utf-8-sig"), "bo_so_tham_khao.csv", "text/csv")
    with t5:
        st.dataframe(data.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
        st.download_button("Tải dữ liệu đã chuẩn hóa", data.to_csv(index=False).encode("utf-8-sig"), "vietlott_clean.csv", "text/csv")
except Exception as exc:
    st.error(f"Không đọc được dữ liệu Vietlott: {exc}")
    st.info("Kiểm tra kết nối nguồn dữ liệu hoặc định dạng theo data/vietlott_template.csv.")
