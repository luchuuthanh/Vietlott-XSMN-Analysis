"""Ứng dụng phân tích XSMN độc lập."""
from datetime import date
from pathlib import Path
import streamlit as st
import pandas as pd
from analytics import frequency_table, gap_table
from data_loader import load_xsmn
from xsmn_archive import fetch_xsmn_five_years
from xsmn_algorithms import draw_history, rank_numbers, pair_frequency, distribution_report, rolling_backtest

st.set_page_config(page_title="XSMN Analysis Lab", page_icon="🍀", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');
:root { --ink:#e8f1f4; --muted:#91a7b0; --panel:#10232c; --panel2:#142c36; --line:rgba(148,190,199,.16); --mint:#35d0ae; --gold:#f2c66d; }
html, body, [class*="css"] { font-family:'Be Vietnam Pro',sans-serif; }
.stApp { background: radial-gradient(ellipse at 12% 0%, #163d45 0%, #0b1820 42%, #08131b 100%); color:var(--ink); }
[data-testid="stHeader"] { background:rgba(8,19,27,.82); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#10252e,#0b1921); border-right:1px solid var(--line); }
[data-testid="stSidebar"] * { color:var(--ink); }
.block-container { max-width:1440px; padding-top:2rem; padding-bottom:3rem; }
h1,h2,h3 { color:#f2f8fa !important; letter-spacing:-.035em; }
h1 { font-size:2.2rem !important; font-weight:800 !important; }
p, label, .stCaption { color:var(--muted); }
.hero-xsmn { background:linear-gradient(115deg,rgba(23,75,78,.96),rgba(16,37,49,.96) 58%,rgba(31,47,57,.96)); border:1px solid rgba(90,213,183,.25); border-radius:22px; padding:26px 28px; margin:0 0 22px 0; box-shadow:0 18px 50px rgba(0,0,0,.22); position:relative; overflow:hidden; }
.hero-xsmn:after { content:'🍀'; position:absolute; right:30px; top:12px; font-size:68px; opacity:.13; }
.hero-kicker { color:#70e2c4; text-transform:uppercase; letter-spacing:.16em; font-size:.72rem; font-weight:800; }
.hero-title { color:#f4fbfc; font-size:1.85rem; font-weight:800; margin-top:7px; }
.hero-sub { color:#b2c8ce; font-size:.92rem; margin-top:6px; max-width:760px; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#142d37,#10232c); border:1px solid var(--line); border-radius:16px; padding:16px 18px; box-shadow:0 8px 22px rgba(0,0,0,.14); }
[data-testid="stMetricLabel"] { color:#9db6bd !important; font-size:.8rem !important; }
[data-testid="stMetricValue"] { color:#f4fbfc !important; font-weight:800; }
[data-testid="stTabs"] button { color:#9eb6bd; font-weight:700; border-radius:10px 10px 0 0; }
[data-testid="stTabs"] button[aria-selected="true"] { color:#5ee0bd !important; border-bottom:3px solid #35d0ae !important; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
.stButton button, .stDownloadButton button { background:linear-gradient(100deg,#1ca98f,#35d0ae); color:#06231f; border:0; border-radius:11px; font-weight:800; }
.stButton button:hover, .stDownloadButton button:hover { background:#6be6c9; color:#06231f; }
input, textarea, [data-baseweb="select"] > div { background:#10232c !important; border-color:var(--line) !important; border-radius:10px !important; }
hr { border-color:var(--line); }
[data-testid="stAlert"] { border-radius:13px; }
@media (max-width: 700px) {
 .block-container { padding:1rem .8rem 2rem .8rem; }
 .hero-xsmn { padding:20px 18px; border-radius:17px; }
 .hero-title { font-size:1.45rem; }
 h1 { font-size:1.7rem !important; }
 [data-testid="stMetric"] { padding:12px; }
}
</style>
<div class="hero-xsmn">
 <div class="hero-kicker">XSMN • ANALYTICS LAB</div>
 <div class="hero-title">Trung tâm phân tích xổ số miền Nam</div>
 <div class="hero-sub">Thống kê lịch sử · Chu kỳ · Thuật toán · Kiểm định cuốn chiếu — trình bày dữ liệu rõ ràng, không khẳng định khả năng dự đoán chắc chắn.</div>
</div>
""", unsafe_allow_html=True)

st.title("Tổng quan XSMN")
st.caption("Không gian phân tích dữ liệu miền Nam")

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
    t1, t2, t3, t4, t5, t6 = st.tabs(["Lô tô 2 số", "Theo giải", "Dữ liệu", "Kiểm tra độ phủ", "Thuật toán", "Backtest"])
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
    history = draw_history(raw, province)
    with t5:
        st.subheader("Xếp hạng thống kê 00–99")
        st.caption("Điểm chỉ mô tả dữ liệu quá khứ; không phải xác suất chắc chắn xuất hiện ở kỳ tới.")
        method = st.selectbox("Phương pháp xếp hạng", ["blend", "freq_30", "freq_90", "freq_365", "ewma", "gap"],
                              format_func=lambda x: {"blend":"Kết hợp tần suất + gan", "freq_30":"Tần suất 30 kỳ",
                              "freq_90":"Tần suất 90 kỳ", "freq_365":"Tần suất 365 kỳ",
                              "ewma":"Trọng số giảm dần theo thời gian", "gap":"Độ gan"}[x])
        top_k = st.slider("Số lượng số hiển thị", 5, 30, 10, key="algorithm_top_k")
        ranked = rank_numbers(history, method, top_k)
        st.dataframe(ranked, use_container_width=True, hide_index=True)
        pairs = pair_frequency(history, 30)
        st.markdown("**Các cặp cùng xuất hiện nhiều nhất**")
        st.dataframe(pairs.head(20), use_container_width=True, hide_index=True)
        report = distribution_report(history)
        a, b, d = st.columns(3)
        a.metric("Số kỳ lịch sử", report["draws"])
        b.metric("Tổng lượt xuất hiện", report["observations"])
        d.metric("Tổng trung bình mỗi kỳ", report.get("mean_sum") or 0)
    with t6:
        st.subheader("Kiểm định cuốn chiếu – không nhìn trước kết quả")
        st.caption("Mỗi kỳ được dự đoán chỉ sử dụng dữ liệu của các kỳ trước đó. So sánh với mức kỳ vọng nếu chọn ngẫu nhiên cùng số lượng.")
        min_history = st.slider("Số kỳ lịch sử tối thiểu trước lần kiểm tra đầu", 30, 180, 90, step=10)
        backtest_k = st.slider("Số ứng viên mỗi kỳ", 5, 30, 10, key="backtest_top_k")
        if len(history) <= min_history:
            st.warning(f"Tỉnh này chỉ có {len(history)} kỳ; cần nhiều hơn {min_history} kỳ để backtest.")
        else:
            with st.spinner("Đang chạy kiểm định cuốn chiếu trên lịch sử tỉnh đã chọn..."):
                detail, summary = rolling_backtest(raw, province, top_k=backtest_k, min_history=min_history)
            if summary.empty:
                st.warning("Không đủ dữ liệu hợp lệ để tính backtest.")
            else:
                st.markdown("**So sánh các phương pháp**")
                st.dataframe(summary, use_container_width=True, hide_index=True)
                st.caption("Lift > 1 chỉ cho biết kết quả backtest cao hơn mức ngẫu nhiên trong mẫu đã kiểm tra; chưa chứng minh hiệu quả ở tương lai.")
                st.markdown("**Chi tiết từng kỳ kiểm tra**")
                st.dataframe(detail, use_container_width=True, hide_index=True)
                st.download_button("Tải kết quả backtest CSV", detail.to_csv(index=False).encode("utf-8-sig"),
                                   f"xsmn_backtest_{province}.csv", "text/csv")
except Exception as exc:
    st.error(f"Không thể phân tích dữ liệu XSMN: {exc}")
    st.info("CSV cần có các cột: date, province, prize, number.")
