"""Ứng dụng phân tích XSMN độc lập."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path
import html
import re
import requests
import streamlit as st
import pandas as pd
from analytics import frequency_table, gap_table
from data_loader import load_xsmn
from xsmn_archive import fetch_xsmn_five_years
from xsmn_algorithms import draw_history, rank_numbers, pair_frequency, distribution_report, rolling_backtest
from xsmn_live import fetch_live_xsmn

st.set_page_config(page_title="XSMN Analysis Lab", page_icon="🍀", layout="wide")

PRIZE_DIGITS = {
    "ĐB": 6, "DB": 6, "GĐB": 6,
    "G1": 5, "G2": 5, "G3": 5, "G4": 5,
    "G5": 4, "G6": 4, "G7": 3, "G8": 2,
}

def format_prize_number(prize, number):
    """Format result to the official digit count for its prize; keep significant leading zeros."""
    label = str(prize).strip().upper()
    digits = PRIZE_DIGITS.get(label)
    value = "".join(ch for ch in str(number) if ch.isdigit())
    if not digits or not value:
        return value
    return value[-digits:].zfill(digits)


def suffix_statistics(frame, provinces, digits, periods, prize_scope):
    """Count unique last-N-digit results per draw for selected stations/prize scope."""
    if isinstance(provinces, str):
        provinces = [provinces]
    df = frame[frame["province"].astype(str).isin([str(p) for p in provinces])].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])
    if prize_scope != "Tất cả giải":
        labels = df["prize"].astype(str).str.strip().str.upper()
        if prize_scope == "ĐB":
            df = df[labels.isin({"ĐB", "DB", "GĐB"})]
        else:
            df = df[labels == prize_scope]
    dates = sorted(df["date"].dropna().unique())
    selected_dates = dates[-max(1, int(periods)):]
    df = df[df["date"].isin(selected_dates)].copy()
    def clean_digits(value):
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]
        return "".join(ch for ch in text if ch.isdigit())

    digits_only = df["number"].map(clean_digits)
    df["_suffix"] = digits_only.str[-digits:].str.zfill(digits)
    df = df[df["_suffix"].str.fullmatch(r"\d{" + str(digits) + r"}", na=False)]
    draws = [
        sorted({int(value) for value in group["_suffix"].tolist()})
        for _, group in df.groupby("date", sort=True)
    ]
    flat = [value for draw in draws for value in draw]
    universe = (10 ** digits) - 1
    freq = frequency_table(flat, universe, start=0)
    gaps = gap_table(draws, universe, start=0)
    return freq, gaps, len(selected_dates)


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

/* Nút cập nhật kết quả trực tuyến: màu đỏ riêng */
[class*="st-key-refresh_live_xsmn"] button {
 background:linear-gradient(100deg,#b5122a,#f04455) !important;
 color:#ffffff !important;
 border:2px solid #ff8995 !important;
 border-radius:14px !important;
 min-height:58px !important;
 padding:12px 22px !important;
 box-shadow:0 5px 18px rgba(220,45,70,.28) !important;
}
[class*="st-key-refresh_live_xsmn"] button *,
[class*="st-key-refresh_live_xsmn"] button p,
[class*="st-key-refresh_live_xsmn"] button span {
 color:#ffffff !important;
 font-size:1.08rem !important;
 font-weight:900 !important;
 letter-spacing:.01em !important;
 opacity:1 !important;
}
[class*="st-key-refresh_live_xsmn"] button:hover {
 background:#fa5365 !important;
 color:#ffffff !important;
 border-color:#ffd0d5 !important;
}
.station-heading {
 display:flex; align-items:center; justify-content:center; text-align:center; gap:10px;
 margin:22px 0 10px; padding:13px 17px;
 text-transform:uppercase;
 border:2px solid #35d0ae; border-left:7px solid #35d0ae;
 border-radius:14px;
 background:linear-gradient(100deg,#15534f,#123744 72%,#1a3544);
 color:#f4fffd; font-size:1.18rem; line-height:1.35;
 font-weight:900; letter-spacing:.025em;
 box-shadow:0 7px 20px rgba(0,0,0,.22);
}
.station-heading:before { content:"🎯"; font-size:1.05rem; }
input, textarea, [data-baseweb="select"] > div { background:#10232c !important; border-color:var(--line) !important; border-radius:10px !important; }
hr { border-color:var(--line); }

.draw-heading { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:20px 22px; margin:8px 0 16px; border:1px solid rgba(69,220,184,.28); border-radius:18px; background:linear-gradient(115deg,#123b40,#102832 65%,#172b36); box-shadow:0 12px 30px rgba(0,0,0,.18); }
.draw-eyebrow { color:#68dfbf; font-size:.68rem; font-weight:800; letter-spacing:.16em; }
.draw-date { color:#f4fbfc; font-size:1.8rem; line-height:1.25; font-weight:800; margin-top:5px; }
.draw-location { color:#a9c2c8; font-size:.82rem; margin-top:4px; }
.draw-count { min-width:72px; text-align:center; border-left:1px solid rgba(255,255,255,.13); padding-left:16px; }
.draw-count strong { display:block; color:#65e0c0; font-size:1.65rem; line-height:1.1; }
.draw-count span { color:#9eb7be; font-size:.72rem; }
.prize-row { display:grid; grid-template-columns:116px minmax(0,1fr); align-items:center; gap:14px; padding:14px; margin:9px 0; border:1px solid rgba(148,190,199,.18); border-radius:15px; background:linear-gradient(110deg,rgba(19,43,53,.96),rgba(14,31,40,.96)); }
.prize-name { display:flex; align-items:center; justify-content:center; text-align:center; color:#75dfc5; font-size:.9rem; line-height:1.35; font-weight:800; letter-spacing:.035em; border-right:1px solid rgba(148,190,199,.18); padding:6px 10px 6px 2px; }
.prize-numbers { display:flex; flex-wrap:wrap; gap:9px; align-items:center; justify-content:center; min-width:0; }
.number-chip { display:inline-flex; align-items:center; justify-content:center; min-width:112px; min-height:58px; padding:11px 14px; border-radius:11px; background:#1a3943; border:1px solid rgba(89,205,183,.25); color:#f0f8fa; font-size:1.32rem; font-weight:800; font-variant-numeric:tabular-nums; letter-spacing:.075em; }
.prize-jackpot { border-color:rgba(242,198,109,.48); background:linear-gradient(105deg,rgba(82,59,28,.55),rgba(31,43,45,.96)); padding-top:17px; padding-bottom:17px; }
.prize-jackpot .prize-name { color:#f2c66d; }
.jackpot-chip { min-width:176px; min-height:68px; padding:14px 18px; color:#ffe5a3; border-color:rgba(242,198,109,.48); background:linear-gradient(135deg,#5b421e,#342d25); font-size:1.55rem; letter-spacing:.1em; }
@media (max-width:600px) { .draw-heading { padding:16px; } .draw-date { font-size:1.55rem; } .prize-row { grid-template-columns:100px minmax(0,1fr); gap:9px; padding:10px 9px; } .prize-name { font-size:.82rem; padding:5px 7px 5px 0; } .prize-numbers { gap:7px; } .number-chip { min-width:102px; min-height:58px; font-size:1.24rem; padding:9px 10px; } .jackpot-chip { min-width:145px; min-height:64px; font-size:1.35rem; } }

[data-testid="stAlert"] { border-radius:13px; }
/* Chữ tiêu đề chọn thứ lớn, đậm và cân giữa trong khung */
.st-key-xsmn_weekday [data-testid="stRadio"] > label {
 font-size:1.55rem !important; font-weight:900 !important;
 color:#f4fbfc !important; letter-spacing:.01em !important;
 min-height:68px !important;
}
/* Thanh điều hướng: phủ hết chiều ngang, tối đa 2 hàng */
.st-key-xsmn_main_navigation [role="radiogroup"] {
 display:grid !important;
 grid-template-columns:repeat(3,minmax(0,1fr)) !important;
 gap:9px !important; width:100% !important;
}
.st-key-xsmn_main_navigation [role="radiogroup"] label {
 width:100% !important; min-width:0 !important;
 min-height:58px !important; box-sizing:border-box !important;
 display:flex !important; align-items:center !important; justify-content:center !important;
 text-align:center !important; padding:8px 6px !important; margin:0 !important;
}
.st-key-xsmn_main_navigation [role="radiogroup"] label p {
 font-size:clamp(.78rem,2.8vw,1rem) !important;
 line-height:1.2 !important; text-align:center !important;
 white-space:normal !important; display:-webkit-box !important;
 -webkit-line-clamp:2 !important; -webkit-box-orient:vertical !important;
 overflow:hidden !important; margin:0 !important;
}
@media (max-width:600px) {
 .st-key-xsmn_weekday [data-testid="stRadio"] > label,
 .st-key-xsmn_weekday [data-testid="stRadio"] > label p,
 .st-key-xsmn_weekday [data-testid="stRadio"] > label span,
 .st-key-xsmn_weekday [data-testid="stRadio"] > label div {
   font-size:1.75rem !important; font-weight:900 !important; height:88px !important; min-height:88px !important;
 }
 .st-key-xsmn_main_navigation [role="radiogroup"] { grid-template-columns:repeat(3,minmax(0,1fr)) !important; gap:7px !important; }
 .st-key-xsmn_main_navigation [role="radiogroup"] label { min-height:60px !important; padding:7px 3px !important; }
}
.weekday-heading {
 display:flex !important; align-items:center !important; justify-content:center !important;
 width:100% !important; height:88px !important; box-sizing:border-box !important;
 margin:0 0 8px 0 !important; padding:8px 12px !important;
 border:1.5px solid rgba(150,190,200,.42) !important; border-radius:15px !important;
 background:linear-gradient(145deg,#142d37,#10232c) !important;
 color:#ffffff !important; text-align:center !important;
 font-size:1.75rem !important; font-weight:900 !important; line-height:1.15 !important;
}
/* Tiêu đề nằm trong ô riêng; chỉ các lựa chọn ngày mới là thẻ */
/* Radio không còn tiêu đề riêng; ẩn hẳn vùng label rỗng do Streamlit tạo */
.st-key-xsmn_weekday [data-testid="stRadio"] > label {
 display:none !important; height:0 !important; min-height:0 !important;
 margin:0 !important; padding:0 !important; border:0 !important;
}
.st-key-xsmn_weekday [data-testid="stRadio"] [role="radiogroup"] {
 display:grid !important; grid-template-columns:repeat(4,minmax(0,1fr)) !important;
 gap:10px !important; width:100%;
}
.st-key-xsmn_weekday [role="radiogroup"] label {
 display:flex !important; align-items:center !important; justify-content:center !important;
 text-align:center !important; min-height:62px !important; padding:12px 8px !important;
 margin:0 !important; border:1.5px solid rgba(150,190,200,.42) !important;
 border-radius:15px !important; background:linear-gradient(145deg,#142d37,#10232c) !important;
}
.st-key-xsmn_weekday [role="radiogroup"] label p {
 color:#e8f1f4 !important; font-size:1.12rem !important; font-weight:800 !important;
 text-align:center !important; margin:0 !important;
}
.st-key-xsmn_weekday [role="radiogroup"] label:has(input:checked) {
 background:linear-gradient(145deg,#713044,#3b2635) !important;
 border:2px solid #f04465 !important; box-shadow:0 5px 16px rgba(220,65,85,.2);
}
.st-key-xsmn_weekday [role="radiogroup"] label > div:first-child { display:none !important; }
/* Station cards use independent checkbox + text, not Streamlit's truncated checkbox label */
.st-key-xsmn-station-row [data-testid="stHorizontalBlock"] {
 display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)) !important;
 gap:8px !important; width:100% !important; align-items:stretch !important;
}
.st-key-xsmn-station-row [data-testid="column"] {
 width:auto !important; min-width:0 !important; max-width:none !important;
 flex:none !important; padding:0 !important; margin:0 !important;
}
[class*="st-key-xsmn-station-card-"] {
 width:100% !important; min-width:0 !important; min-height:68px !important;
 box-sizing:border-box !important; padding:8px 5px !important;
 border:2px solid rgba(150,190,200,.42) !important; border-radius:16px !important;
 background:linear-gradient(145deg,#142d37,#10232c) !important;
 display:flex !important; align-items:center !important; justify-content:center !important;
}
[class*="st-key-xsmn-station-card-"]:has(input:checked) {
 background:linear-gradient(145deg,#15534f,#123744) !important;
 border:2px solid #35d0ae !important; box-shadow:0 5px 16px rgba(53,208,174,.16) !important;
}
[class*="st-key-xsmn-station-card-"] [data-testid="stHorizontalBlock"] {
 display:flex !important; align-items:center !important; gap:2px !important;
 width:100% !important;
}
[class*="st-key-xsmn-station-card-"] [data-testid="column"] {
 min-width:0 !important; padding:0 !important; flex:none !important;
}
[class*="st-key-xsmn-station-card-"] [data-testid="column"]:first-child { width:25% !important; }
[class*="st-key-xsmn-station-card-"] [data-testid="column"]:last-child { width:75% !important; }
[class*="st-key-xsmn-station-card-"] [data-testid="stCheckbox"] { margin:0 !important; padding:0 !important; }
[class*="st-key-xsmn-station-card-"] [data-testid="stCheckbox"] label { justify-content:center !important; }
[class*="st-key-xsmn-station-card-"] [data-testid="stMarkdown"] { width:100% !important; }
[class*="st-key-xsmn-station-card-"] p {
 color:#e8f1f4 !important; font-size:clamp(12px,2.7vw,16px) !important;
 font-weight:800 !important; text-align:center !important; line-height:1.15 !important;
 margin:0 !important; padding:0 !important; white-space:normal !important;
 overflow-wrap:anywhere !important;
}
/* Các mục người dùng yêu cầu ẩn: giữ nguyên nội dung/chức năng trong mã, chỉ ẩn giao diện */
.st-key-hidden-xsmn-summary-metrics,
.st-key-hidden-xsmn-lookback,
.st-key-hidden-xsmn-metrics,
.st-key-hidden-xsmn-prize,
.st-key-hidden-xsmn-data,
.st-key-hidden-xsmn-coverage,
.st-key-hidden-xsmn-archive-status,
.st-key-hidden-xsmn-algo-pairs,
.st-key-hidden-xsmn-two-chart { display:none !important; }
@media (max-width: 700px) {
 .block-container { padding:1rem .8rem 2rem .8rem; }
 .hero-xsmn { padding:20px 18px; border-radius:17px; }
 .hero-title { font-size:1.45rem; }
 h1 { font-size:1.7rem !important; }
 [data-testid="stMetric"] { padding:12px; }
}
 .st-key-hidden-xsmn-overview { display:none !important; }
.st-key-hidden-xsmn-validated-data-caption { display:none !important; }
</style>
<div class="hero-xsmn">
 <div class="hero-kicker">XSMN • ANALYTICS LAB</div>
 <div class="hero-title">Trung tâm phân tích xổ số miền Nam</div>
 <div class="hero-sub">Thống kê lịch sử · Chu kỳ · Thuật toán · Kiểm định cuốn chiếu — trình bày dữ liệu rõ ràng, không khẳng định khả năng dự đoán chắc chắn.</div>
</div>
""", unsafe_allow_html=True)

# Giữ nguyên tiêu đề Tổng quan trong mã nhưng ẩn khỏi giao diện theo yêu cầu.
with st.container(key="hidden-xsmn-overview"):
    st.title("Tổng quan XSMN")
    st.caption("Không gian phân tích dữ liệu miền Nam")

source = st.session_state.get("xsmn_data_source", "Kho lịch sử 5 năm")
upload = None
with st.sidebar:
    st.header("XSMN")
    # Nguồn dữ liệu là tùy chọn nâng cao; thu gọn để sidebar trên điện thoại gọn hơn.
    with st.expander("Tùy chọn dữ liệu nâng cao", expanded=False):
        source = st.radio(
            "Nguồn dữ liệu",
            ["Kho lịch sử 5 năm", "Tải CSV riêng"],
            key="xsmn_data_source",
        )
        if source == "Tải CSV riêng":
            st.file_uploader(
                "Tải CSV lịch sử XSMN",
                type=["csv"],
                key="xsmn_csv_upload",
            )
        st.caption("Kho lịch sử công khai: SQLite theo quý. Cửa sổ mục tiêu từ 04/11/2021.")
source = st.session_state.get("xsmn_data_source", "Kho lịch sử 5 năm")
upload = st.session_state.get("xsmn_csv_upload") if source == "Tải CSV riêng" else None

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
            # Merge separately verified daily results when the main archive pipeline
            # has not published that draw yet. Canonical rows take precedence on overlap.
            daily_verified = Path("data/xsmn_daily_verified_2026-11-07.csv")
            daily_meta = Path("data/xsmn_daily_verified_2026-11-07.json")
            if daily_verified.exists() and daily_meta.exists():
                daily_info = json.loads(daily_meta.read_text(encoding="utf-8"))
                if daily_info.get("status") == "PASS" and daily_info.get("actual_rows") == daily_info.get("expected_rows"):
                    daily = pd.read_csv(daily_verified, dtype={"number": str, "last2": str})
                    raw = pd.concat([raw, daily], ignore_index=True)
                    raw = raw.drop_duplicates(
                        subset=["date", "province", "prize", "prize_order"],
                        keep="first",
                    )
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
    with st.container(key="hidden-xsmn-archive-status"):
        with st.expander("Tình trạng tải dữ liệu theo quý", expanded=True):
            st.dataframe(archive_status, use_container_width=True, hide_index=True)
if raw.empty:
    st.info("Chọn kho lịch sử 5 năm hoặc tải CSV để bắt đầu phân tích.")
    st.stop()

try:
    if "last2" not in raw.columns:
        raw["last2"] = raw["number"].astype(str).str[-2:].astype(int)
    available_provinces = sorted(raw["province"].dropna().astype(str).unique().tolist())
    schedule = {
        "Thứ 2": ["TP.HCM", "Đồng Tháp", "Cà Mau"],
        "Thứ 3": ["Bến Tre", "Vũng Tàu", "Bạc Liêu"],
        "Thứ 4": ["Đồng Nai", "Cần Thơ", "Sóc Trăng"],
        "Thứ 5": ["Tây Ninh", "An Giang", "Bình Thuận"],
        "Thứ 6": ["Vĩnh Long", "Bình Dương", "Trà Vinh"],
        "Thứ 7": ["TP.HCM", "Long An", "Bình Phước", "Hậu Giang"],
        "Chủ nhật": ["Tiền Giang", "Kiên Giang", "Đà Lạt"],
    }
    weekday_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
    today_index = (date.today().weekday())
    default_day = weekday_names[today_index]
    st.markdown(
        '<div class="weekday-heading">Chọn thứ mở thưởng</div>',
        unsafe_allow_html=True,
    )
    weekday = st.radio(
        " ",
        weekday_names,
        index=today_index,
        horizontal=True,
        key="xsmn_weekday",
        label_visibility="collapsed",
    )
    scheduled = schedule[weekday]
    def normalize_station_name(value):
        import unicodedata
        value = str(value).strip().casefold().replace("đ", "d")
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = re.sub(r"[^a-z0-9]+", " ", value).strip()
        value = re.sub(r"^(tinh|thanh pho|tp)\\s+", "", value)
        return value

    def resolve_station(label):
        aliases = {
            "TP.HCM": ["TP.HCM", "TP HCM", "TP Hồ Chí Minh", "Thành phố Hồ Chí Minh",
                       "Hồ Chí Minh", "Ho Chi Minh", "Ho Chi Minh City", "HCM"],
            "Đà Lạt": ["Đà Lạt", "Da Lat", "Lâm Đồng"],
        }
        candidates = [label, *aliases.get(label, [])]
        normalized = {normalize_station_name(p): p for p in available_provinces}
        for candidate in candidates:
            match = normalized.get(normalize_station_name(candidate))
            if match:
                return match
        target = normalize_station_name(label)
        for name, actual in normalized.items():
            if target and (name.endswith(" " + target) or name.startswith(target + " ")):
                return actual
        return None
    station_map = {label: resolve_station(label) for label in scheduled}
    st.markdown("### Chọn đài")
    selected_stations = []
    valid_stations = [(label, station_map[label]) for label in scheduled if station_map[label] is not None]
    missing_stations = [label for label in scheduled if station_map[label] is None]
    for missing in missing_stations:
        st.warning(f"Chưa tìm thấy dữ liệu tỉnh: {missing}")
    # Thẻ đài riêng: checkbox không chứa nhãn; tên đài là phần tử độc lập để không bị Streamlit cắt chữ.
    with st.container(key="xsmn-station-row"):
        for row_start in range(0, len(valid_stations), 3):
            cols = st.columns(3, gap="small")
            for col_idx, (label, actual) in enumerate(valid_stations[row_start:row_start + 3]):
                with cols[col_idx]:
                    card_key = f"xsmn-station-card-{weekday}-{row_start + col_idx}"
                    with st.container(key=card_key):
                        check_col, name_col = st.columns([1, 3], gap="small", vertical_alignment="center")
                        with check_col:
                            checked = st.checkbox(
                                " ",
                                value=True,
                                key=f"xsmn_station_{weekday}_{label}",
                                label_visibility="collapsed",
                            )
                        with name_col:
                            st.markdown(
                                f"<p>{label}</p>",
                                unsafe_allow_html=True,
                            )
                    if checked:
                        selected_stations.append(actual)
    if not selected_stations:
        st.info("Hãy tích chọn ít nhất một đài để xem dữ liệu.")
        st.stop()
    provinces = selected_stations
    province = ", ".join(selected_stations)
    data = raw[raw["province"].astype(str).isin(selected_stations)].copy()
    dates = sorted(data["date"].dropna().unique())
    if not dates:
        st.warning("Tỉnh này chưa có ngày dữ liệu hợp lệ.")
        st.stop()
    # Giữ nguyên bộ lọc số kỳ; chỉ ẩn thanh điều khiển khỏi giao diện.
    with st.container(key="hidden-xsmn-lookback"):
        recent_n = st.slider("Số ngày/kỳ gần nhất", 1, len(dates), min(90, len(dates)))
    chosen_dates = set(dates[-recent_n:])
    subset = data[data["date"].isin(chosen_dates)].copy()
    draws = subset.groupby("date")["last2"].apply(list).tolist()
    flat = subset["last2"].astype(int).tolist()
    freq = frequency_table(flat, 99, start=0)
    gaps = gap_table(draws, 99, start=0)
    # Ẩn chỉ số 'Đài đã chọn' khỏi giao diện theo yêu cầu.
    # Giữ lại 3 chỉ số cũ nhưng ẩn khỏi giao diện theo yêu cầu.
    with st.container(key="hidden-xsmn-metrics"):
        c2, c3, c4 = st.columns(3)
        c2.metric("Ngày có dữ liệu", len(dates))
        c3.metric("Số kết quả", len(data))
        c4.metric("Số tỉnh trong kho", raw["province"].nunique())
    # Chỉ hiển thị mục Trực tuyến và nút cập nhật trong khung giờ
    # 16:20 đến trước 17:35 theo giờ Việt Nam.
    vn_now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).time()
    live_window_start = time(16, 20)
    live_window_end = time(17, 35)
    live_window_open = live_window_start <= vn_now < live_window_end
    nav_options = ["Lịch sử kết quả", "Thống kê hai số", "Thống kê ba số", "Thống kê cặp số", "Thuật toán"]
    if live_window_open:
        nav_options.insert(0, "🔴 Trực tuyến")
    st.markdown("""
    <style>
    div[data-testid="stRadio"] > div {
        display: flex; flex-wrap: wrap; gap: 8px;
    }
    div[data-testid="stRadio"] label {
        border: 1px solid rgba(150,170,180,.35);
        border-radius: 12px; padding: 8px 13px;
        background: rgba(120,140,150,.08);
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        background: rgba(220,65,85,.18);
        border-color: #dc4155;
    }
    </style>
    """, unsafe_allow_html=True)
    selected_nav = st.radio(
        "Chọn mục",
        nav_options,
        horizontal=True,
        label_visibility="collapsed",
        key="xsmn_main_navigation",
    )
    if selected_nav == "🔴 Trực tuyến":
        st.subheader("Kết quả XSMN trực tuyến")
        st.caption("Dữ liệu được lấy tự động từ nguồn kết quả SXMN và dựng lại bằng giao diện riêng của XSMN Analysis Lab.")
        refresh_clicked = st.button("↻ Cập nhật kết quả", key="refresh_live_xsmn")
        @st.cache_data(ttl=60, show_spinner=False)
        def _load_live_xsmn():
            return fetch_live_xsmn()
        try:
            if refresh_clicked:
                st.cache_data.clear()
            with st.spinner("Đang lấy kết quả XSMN mới nhất..."):
                live_frame, live_source = fetch_live_xsmn() if refresh_clicked else _load_live_xsmn()
            live_station = live_frame[live_frame["province"].astype(str).map(normalize_station_name).isin({normalize_station_name(p) for p in selected_stations})].copy()
            if live_station.empty:
                raise ValueError("Nguồn trực tuyến chưa có kết quả cho các đài đã chọn.")
            live_station["prize"] = live_station["prize"].astype(str).str.upper().replace({"DB": "ĐB"})
            order = {"ĐB": 0, "G1": 1, "G2": 2, "G3": 3, "G4": 4, "G5": 5, "G6": 6, "G7": 7, "G8": 8}
            expected = {"ĐB": 1, "G1": 1, "G2": 1, "G3": 2, "G4": 7, "G5": 1, "G6": 3, "G7": 1, "G8": 1}
            live_station["number"] = live_station.apply(lambda row: format_prize_number(row["prize"], row["number"]), axis=1)
            live_station["_order"] = live_station["prize"].map(order).fillna(99)
            live_station = live_station.sort_values(["province", "_order"])
            live_date = pd.to_datetime(live_station["date"].iloc[0]).date()
            if live_station["date"].nunique() != 1:
                raise ValueError("Nguồn trực tuyến trả về nhiều ngày mở thưởng; từ chối ghi nhận.")
            # Ghi nhận chỉ khi đủ toàn bộ 18 kết quả của từng đài đã chọn.
            for station, group in live_station.groupby("province"):
                counts = group["prize"].value_counts().to_dict()
                if counts != expected or len(group) != 18:
                    raise ValueError(f"Đài {station}: chưa đủ cơ cấu 18 kết quả hoặc số giải không khớp; chưa ghi dữ liệu.")
            st.markdown(f"**{live_date.strftime('%d/%m/%Y')} · Kết quả theo từng đài**")
            for station, station_rows in live_station.groupby("province", sort=False):
                st.markdown(f'<div class="station-heading">{html.escape(str(station))}</div>', unsafe_allow_html=True)
                for prize, rows in station_rows.groupby("prize", sort=False):
                    prize_label = "ĐẶC BIỆT" if prize == "ĐB" else f"GIẢI {prize}"
                    values = "".join(
                        f'<span class="number-chip {"jackpot-chip" if prize == "ĐB" else ""}">{html.escape(v)}</span>'
                        for v in rows["number"].tolist()
                    )
                    st.markdown(
                        f'<div class="prize-row {"prize-jackpot" if prize == "ĐB" else ""}>'
                        f'<div class="prize-name">{prize_label}</div><div class="prize-numbers">{values}</div></div>',
                        unsafe_allow_html=True,
                    )
            st.caption(f"Nguồn trực tuyến: {live_source} · Đủ 18 kết quả/đài · Tự làm mới mỗi 60 giây.")
            st.divider()
            st.markdown("**Ghi nhận kết quả vào kho lịch sử 5 năm**")
            if st.button("Lưu kết quả đã kiểm tra vào dữ liệu lịch sử", key="save_live_xsmn"):
                import base64
                import json
                import os
                repo = "luchuuthanh/Vietlott-XSMN-Analysis"
                token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
                if not token:
                    st.error("Chưa cấu hình GITHUB_TOKEN trong Streamlit Secrets. Không có dữ liệu nào được ghi.")
                else:
                    api = "https://api.github.com"
                    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
                    path = "data/xsmn_5y_canonical.csv"
                    manifest_path = "data/xsmn_5y_canonical.json"
                    try:
                        with st.spinner("Đang xác minh và ghi kết quả vào kho dữ liệu chuẩn..."):
                            ref_url = f"{api}/repos/{repo}/git/ref/heads/main"
                            publish_ref_url = f"{api}/repos/{repo}/git/refs/heads/main"
                            ref_resp = requests.get(ref_url, headers=headers, timeout=30)
                            ref_resp.raise_for_status()
                            base_commit = ref_resp.json()["object"]["sha"]
                            commit_resp = requests.get(f"{api}/repos/{repo}/git/commits/{base_commit}", headers=headers, timeout=30)
                            commit_resp.raise_for_status()
                            base_tree = commit_resp.json()["tree"]["sha"]
                            meta_url = f"{api}/repos/{repo}/contents/{path}"
                            meta_resp = requests.get(meta_url, headers=headers, timeout=30)
                            meta_resp.raise_for_status()
                            raw_resp = requests.get(f"https://raw.githubusercontent.com/{repo}/{base_commit}/{path}", timeout=60)
                            raw_resp.raise_for_status()
                            from io import StringIO
                            canonical_df = pd.read_csv(StringIO(raw_resp.text), dtype={"number": str, "last2": str})
                            required = ["date", "province", "prize", "prize_order", "number", "number_length", "last2", "last2_numeric", "source"]
                            if not set(required).issubset(canonical_df.columns):
                                raise ValueError("Cấu trúc kho dữ liệu chuẩn không đúng; đã hủy ghi.")
                            new_rows = []
                            for station, group in live_station.groupby("province", sort=False):
                                matches = canonical_df.loc[canonical_df["province"].astype(str).map(normalize_station_name) == normalize_station_name(station), "province"].drop_duplicates().tolist()
                                if len(matches) != 1:
                                    raise ValueError(f"Không ánh xạ được tên đài {station} duy nhất trong kho chuẩn.")
                                canonical_station = matches[0]
                                for prize, prize_rows in group.groupby("prize", sort=False):
                                    for prize_index, (_, row) in enumerate(prize_rows.iterrows(), start=1):
                                        number = str(row["number"])
                                        prize = str(row["prize"])
                                        new_rows.append({"date": live_date.isoformat(), "province": canonical_station, "prize": prize, "prize_order": prize_index, "number": number, "number_length": len(number), "last2": number[-2:].zfill(2), "last2_numeric": int(number[-2:]), "source": "live_sxmn_com_vn_validated"})
                            new_df = pd.DataFrame(new_rows, columns=required)
                            keys = ["date", "province", "prize", "prize_order"]
                            if new_df.duplicated(keys).any():
                                raise ValueError("Dữ liệu mới có khóa giải trùng; từ chối ghi.")
                            selected_stations = set(new_df["province"].astype(str))
                            existing = canonical_df[(canonical_df["date"].astype(str) == live_date.isoformat()) & canonical_df["province"].astype(str).isin(selected_stations)]
                            overlap = existing.merge(new_df, on=keys, how="inner", suffixes=("_old", "_new"))
                            if len(existing):
                                if len(existing) != len(new_df) or len(overlap) != len(new_df) or not (overlap["number_old"].astype(str) == overlap["number_new"].astype(str)).all():
                                    raise ValueError("Ngày này đã có dữ liệu khác hoặc chỉ có một phần; không ghi đè kho chuẩn.")
                                st.success("Kết quả ngày này đã được ghi nhận trước đó và khớp hoàn toàn. Không thêm dòng trùng.")
                            else:
                                merged = pd.concat([canonical_df[required], new_df], ignore_index=True)
                                merged["date"] = pd.to_datetime(merged["date"], errors="raise").dt.strftime("%Y-%m-%d")
                                merged = merged.sort_values(keys, kind="stable")
                                csv_text = merged.to_csv(index=False)
                                manifest_url = f"{api}/repos/{repo}/contents/{manifest_path}"
                                manifest_meta_resp = requests.get(manifest_url, headers=headers, timeout=30)
                                manifest_meta_resp.raise_for_status()
                                manifest_raw = requests.get(f"https://raw.githubusercontent.com/{repo}/{base_commit}/{manifest_path}", timeout=30)
                                manifest_raw.raise_for_status()
                                manifest_data = json.loads(manifest_raw.text)
                                manifest_data.update({"status": "PASS", "updated_at_vietnam": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(), "window_end": max(str(manifest_data.get("window_end", "")), live_date.isoformat()), "rows": int(len(merged)), "last_draw_import": live_date.isoformat(), "last_draw_rows": int(len(new_df)), "last_draw_source": "live_sxmn_com_vn_validated", "last_draw_verification": "Prize structure validated at 18 rows per selected station; source is SXMN live page."})
                                manifest_text = json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n"
                                def create_blob(content):
                                    response = requests.post(f"{api}/repos/{repo}/git/blobs", headers=headers, json={"content": content, "encoding": "utf-8"}, timeout=60)
                                    response.raise_for_status()
                                    return response.json()["sha"]
                                csv_blob = create_blob(csv_text)
                                manifest_blob = create_blob(manifest_text)
                                tree_resp = requests.post(f"{api}/repos/{repo}/git/trees", headers=headers, json={"base_tree": base_tree, "tree": [{"path": path, "mode": "100644", "type": "blob", "sha": csv_blob}, {"path": manifest_path, "mode": "100644", "type": "blob", "sha": manifest_blob}]}, timeout=60)
                                tree_resp.raise_for_status()
                                commit_create = requests.post(f"{api}/repos/{repo}/git/commits", headers=headers, json={"message": f"Record verified live XSMN draw {live_date.isoformat()}", "tree": tree_resp.json()["sha"], "parents": [base_commit]}, timeout=60)
                                commit_create.raise_for_status()
                                new_commit = commit_create.json()["sha"]
                                latest_ref = requests.get(ref_url, headers=headers, timeout=30)
                                latest_ref.raise_for_status()
                                if latest_ref.json()["object"]["sha"] != base_commit:
                                    raise RuntimeError("Kho dữ liệu vừa thay đổi; chưa công bố tệp nào. Tải lại rồi thử lại.")
                                publish = requests.patch(publish_ref_url, headers=headers, json={"sha": new_commit, "force": False}, timeout=30)
                                if publish.status_code == 422:
                                    raise RuntimeError("GitHub từ chối cập nhật nhánh do có thay đổi đồng thời; chưa công bố dữ liệu.")
                                publish.raise_for_status()
                                st.success(f"Đã ghi đồng thời {len(new_df)} kết quả của {new_df['province'].nunique()} đài và manifest trong cùng một commit.")
                                st.info("Bản dữ liệu chuẩn sẽ được ứng dụng tải lại sau khi GitHub hoàn tất triển khai.")
                    except Exception as exc:
                        st.error(f"Không ghi được dữ liệu lịch sử: {exc}")
            else:
                st.info("Chỉ ghi khi đủ 18 kết quả mỗi đài; dữ liệu thiếu, trùng hoặc xung đột sẽ bị từ chối.")
        except Exception as exc:
            st.error(f"Chưa lấy được kết quả trực tuyến: {exc}")
            st.info("Phần lịch sử vẫn hoạt động ở tab Lịch sử kết quả.")

    if selected_nav == "Lịch sử kết quả":
        st.subheader(f"Kết quả lịch sử XSMN — {province}")
        st.caption("Kết quả được trình bày trực tiếp trong XSMN Analysis Lab từ kho dữ liệu hiện có; không nhúng website bên ngoài.")
        live_dates = sorted(data["date"].dropna().astype(str).unique(), reverse=True)
        if live_dates:
            latest_date = live_dates[0]
            selected_live_date = st.selectbox(
                "Ngày mở thưởng",
                live_dates,
                index=0,
                format_func=lambda value: pd.to_datetime(value).strftime("%d/%m/%Y"),
                key="xsmn_live_date",
            )
            live_result = data[data["date"].astype(str) == selected_live_date].copy()
            live_result["number"] = live_result.apply(lambda row: format_prize_number(row["prize"], row["number"]), axis=1)
            prize_order = {"ĐB": 0, "DB": 0, "GĐB": 0, "G1": 1, "G2": 2, "G3": 3, "G4": 4, "G5": 5, "G6": 6, "G7": 7, "G8": 8}
            live_result["_order"] = live_result["prize"].astype(str).str.upper().map(prize_order).fillna(99)
            live_result = live_result.sort_values(["_order", "prize"], ascending=True)
            date_label = pd.to_datetime(selected_live_date).strftime("%d/%m/%Y")
            st.markdown(f"""
            <div class="draw-heading">
              <div><div class="draw-eyebrow">KẾT QUẢ MỞ THƯỞNG</div>
              <div class="draw-date">{date_label}</div>
              <div class="draw-location">{html.escape(str(province))} · Miền Nam</div></div>
              <div class="draw-count"><strong>{len(live_result)}</strong><span>con số</span></div>
            </div>
            """, unsafe_allow_html=True)
            for station, station_rows in live_result.groupby("province", sort=False):
                st.markdown(f'<div class="station-heading">{html.escape(str(station))}</div>', unsafe_allow_html=True)
                for prize, rows in station_rows.groupby("prize", sort=False):
                    prize_label = str(prize).upper()
                    values = [html.escape(str(v)) for v in rows["number"].tolist()]
                    is_jackpot = prize_label in {"ĐB", "DB", "GĐB"}
                    chips = "".join(f'<span class="number-chip {"jackpot-chip" if is_jackpot else ""}">{v}</span>' for v in values)
                    st.markdown(
                        f'<div class="prize-row {"prize-jackpot" if is_jackpot else ""}>'
                        f'<div class="prize-name">{"ĐẶC BIỆT" if is_jackpot else "GIẢI " + html.escape(prize_label)}</div>'
                        f'<div class="prize-numbers">{chips}</div></div>',
                        unsafe_allow_html=True,
                    )
            st.caption(f"Ngày mới nhất hiện có trong kho các đài đã chọn: {pd.to_datetime(latest_date).strftime('%d/%m/%Y')}.")
        else:
            st.warning("Chưa có ngày mở thưởng hợp lệ trong dữ liệu tỉnh đã chọn.")
    history = [(d, set(g["last2"].astype(int))) for d, g in data.assign(last2=pd.to_numeric(data["last2"], errors="coerce")).dropna(subset=["last2"]).groupby("date", sort=True)]
    if selected_nav == "Thống kê cặp số":
        # 3) Thống kê cặp số: giữ thuật toán hiện có và bộ chọn kỳ độc lập.
        st.markdown("### Thống kê cặp số")
        pair_periods = st.slider(
            "Số kỳ dùng để thống kê cặp số", 1, max(1, len(history)),
            min(30, max(1, len(history))), key="loto_pair_periods"
        )
        selected_history = history[-pair_periods:]
        pair_rows = pair_frequency(selected_history, top=100)
        st.caption(f"Thống kê các cặp cùng xuất hiện trong {pair_periods} kỳ gần nhất.")
        st.dataframe(pair_rows.head(20), use_container_width=True, hide_index=True)

    if selected_nav == "Thống kê ba số":
        # Thống kê ba số: bộ lọc và số kỳ riêng, không phụ thuộc phần hai số.
        st.markdown("### Thống kê ba số")
        three_periods = st.slider(
            "Số kỳ thống kê ba số", 1, max(1, len(dates)),
            min(30, max(1, len(dates))), key="stats_three_periods"
        )
        three_scope = st.radio(
            "Chọn giải", ["G7", "Tất cả giải"],
            horizontal=True, key="stats_three_scope"
        )
        three_freq, three_gaps, three_used = suffix_statistics(
            raw, selected_stations, 3, three_periods, three_scope
        )
        three_display = three_freq.drop(columns=["Tỷ lệ (%)"], errors="ignore").copy()
        three_display["Số"] = three_display["Số"].map(lambda n: f"{int(n):03d}")
        st.caption(f"Phạm vi: {three_scope} · {three_used} kỳ gần nhất.")
        st.dataframe(three_display.head(20), use_container_width=True, hide_index=True)
        st.markdown("### Số ba chữ số lâu chưa xuất hiện")
        three_gaps_display = three_gaps.copy()
        three_gaps_display["Số"] = three_gaps_display["Số"].map(lambda n: f"{int(n):03d}")
        st.dataframe(three_gaps_display.head(20), use_container_width=True, hide_index=True)


    if selected_nav == "Thống kê hai số":
        # 1) Thống kê hai số: độc lập chọn số kỳ và phạm vi giải.
        st.markdown("### Thống kê hai số")
        two_periods = st.slider(
            "Số kỳ thống kê tần suất", 1, max(1, len(dates)),
            min(30, max(1, len(dates))), key="stats_two_periods"
        )
        two_scope = st.radio(
            "Chọn giải",
            ["G8", "ĐB", "Tất cả giải"],
            horizontal=True,
            key="stats_two_scope"
        )
        two_freq, _, two_used = suffix_statistics(
            raw, selected_stations, 2, two_periods, two_scope
        )
        two_display = two_freq.drop(columns=["Tỷ lệ (%)"], errors="ignore").copy()
        two_display["Số"] = two_display["Số"].map(lambda n: f"{int(n):02d}")
        st.caption(f"Phạm vi: {two_scope} · {two_used} kỳ gần nhất.")
        st.dataframe(two_display.head(20), use_container_width=True, hide_index=True)

        st.markdown("### Số lâu chưa xuất hiện")
        gap_periods = st.slider(
            "Số kỳ xét số lâu chưa xuất hiện", 1, max(1, len(dates)),
            min(30, max(1, len(dates))), key="stats_two_gap_periods"
        )
        _, two_gaps, gap_used = suffix_statistics(
            raw, selected_stations, 2, gap_periods, two_scope
        )
        st.caption(f"Phạm vi: {two_scope} · {gap_used} kỳ gần nhất.")
        two_gaps_display = two_gaps.copy()
        two_gaps_display["Số"] = two_gaps_display["Số"].map(lambda n: f"{int(n):02d}")
        st.dataframe(two_gaps_display.head(20), use_container_width=True, hide_index=True)

        # Biểu đồ được ẩn khỏi giao diện, vẫn giữ nguyên phép tính và mã hiển thị.
        with st.container(key="hidden-xsmn-two-chart"):
            st.markdown("### Biểu đồ tần suất hai số")
            st.bar_chart(two_freq.set_index("Số")["Số lần"])


    # Khôi phục nội dung tab Theo giải; giữ nguyên nhưng ẩn khỏi giao diện.
    with st.container(key="hidden-xsmn-prize"):
        by_prize = subset.groupby("prize")["number"].count().sort_values(ascending=False).rename("Số kết quả")
        st.dataframe(by_prize, use_container_width=True)

    # Khôi phục nội dung tab Dữ liệu; giữ nguyên bảng và nút tải CSV nhưng ẩn khỏi giao diện.
    with st.container(key="hidden-xsmn-data"):
        st.dataframe(data.sort_values(["date", "prize"], ascending=[False, True]), use_container_width=True, hide_index=True)
        st.download_button("Tải dữ liệu tỉnh CSV", data.to_csv(index=False).encode("utf-8-sig"), "xsmn_clean.csv", "text/csv")

    # Khôi phục nội dung tab Kiểm tra độ phủ; giữ nguyên nhưng ẩn khỏi giao diện.
    with st.container(key="hidden-xsmn-coverage"):
        st.metric("Ngày đầu có dữ liệu", pd.to_datetime(data["date"]).min().strftime("%d/%m/%Y"))
        st.metric("Ngày cuối có dữ liệu", pd.to_datetime(data["date"]).max().strftime("%d/%m/%Y"))
        if not archive_status.empty:
            st.dataframe(archive_status, use_container_width=True, hide_index=True)
        st.caption("Bảng này cho biết tình trạng tải từng quý; cần đối chiếu số kỳ theo lịch quay và nguồn chính thức trước khi xác nhận dữ liệu đầy đủ.")

    if selected_nav == "Thuật toán":
        st.subheader("Xếp hạng thống kê 00–99")
        st.caption("Điểm chỉ mô tả dữ liệu quá khứ; không phải xác suất chắc chắn xuất hiện ở kỳ tới.")
        method = st.radio(
            "Phương pháp xếp hạng",
            ["freq_30", "freq_90", "freq_365", "gap"],
            format_func=lambda x: {
                "freq_30": "Tần suất 30 kỳ",
                "freq_90": "Tần suất 90 kỳ",
                "freq_365": "Tần suất 365 kỳ",
                "gap": "Số ít xuất hiện",
            }[x],
            horizontal=True,
            key="algorithm_method",
        )
        top_k = st.slider("Số lượng số hiển thị", 5, 30, 10, key="algorithm_top_k")
        ranked = rank_numbers(history, method, top_k)
        if method == "gap":
            display_ranked = ranked.rename(columns={"Điểm": "Số lần chưa xuất hiện"})
        elif method in {"freq_30", "freq_90", "freq_365"}:
            display_ranked = ranked.rename(columns={"Điểm": "Số kỳ xuất hiện"})
        else:
            display_ranked = ranked.drop(columns=["Điểm"], errors="ignore")
        st.dataframe(display_ranked, use_container_width=True, hide_index=True)
        # Giữ nguyên thống kê cặp cũ nhưng ẩn tại tab Thuật toán;
        # bảng có bộ chọn số kỳ được hiển thị trong tab Lô tô 2 số.
        with st.container(key="hidden-xsmn-algo-pairs"):
            pairs = pair_frequency(history, 30)
            st.markdown("**Các cặp cùng xuất hiện nhiều nhất**")
            st.dataframe(pairs.head(20), use_container_width=True, hide_index=True)
        report = distribution_report(history)
        # Giữ nguyên ba chỉ số và phép tính; chỉ ẩn khỏi giao diện theo yêu cầu.
        with st.container(key="hidden-xsmn-summary-metrics"):
            a, b, d = st.columns(3)
            a.metric("Số kỳ lịch sử", report["draws"])
            b.metric("Tổng lượt xuất hiện", report["observations"])
            d.metric("Tổng trung bình mỗi kỳ", report.get("mean_sum") or 0)
    if False:  # Backtest giữ nguyên mã nguồn nhưng không hiển thị trên thanh điều hướng.
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
