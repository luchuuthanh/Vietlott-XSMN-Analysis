"""Import Cophieu68 CSV/TXT exports into StockLab without requiring a paid API."""
from __future__ import annotations
from io import BytesIO
import pandas as pd
import streamlit as st

ALIASES = {
    "symbol": {"symbol","ticker","code","stock","stockcode","ma","mack","mã","mãck","证券代码"},
    "date": {"date","datetime","time","tradingdate","ngay","ngày","thoigian","thời gian"},
    "open": {"open","o","gia mo cua","giá mở cửa","mo cua"},
    "high": {"high","h","gia cao nhat","giá cao nhất","cao nhat"},
    "low": {"low","l","gia thap nhat","giá thấp nhất","thap nhat"},
    "close": {"close","c","adjclose","gia dong cua","giá đóng cửa","dong cua"},
    "volume": {"volume","vol","v","kl","khoi luong","khối lượng"},
}

def _key(value):
    return str(value).strip().lower().replace("_"," ").replace("-"," ").replace("."," ")

def read_cophieu68_file(upload) -> pd.DataFrame:
    raw = upload.getvalue()
    df = None
    errors = []
    for encoding in ("utf-8-sig","utf-8","cp1258","latin1"):
        try:
            df = pd.read_csv(BytesIO(raw), sep=None, engine="python", encoding=encoding, skipinitialspace=True)
            if len(df.columns) > 1:
                break
        except Exception as exc:
            errors.append(str(exc))
            df = None
    if df is None:
        raise ValueError("Không đọc được file CSV/TXT. " + " | ".join(errors[-2:]))
    rename = {}
    for col in df.columns:
        k = _key(col)
        for target, names in ALIASES.items():
            if k in {_key(x) for x in names}:
                rename[col] = target
                break
    df = df.rename(columns=rename)
    required = {"date","open","high","low","close","volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Thiếu cột: " + ", ".join(sorted(missing)) + ". Cần Date, Open, High, Low, Close, Volume.")
    if "symbol" not in df.columns:
        # Accept a single-symbol file when its filename begins with a ticker.
        stem = upload.name.rsplit("/",1)[-1].split(".",1)[0].upper()
        if stem.isalnum() and 3 <= len(stem) <= 6:
            df["symbol"] = stem
        else:
            raise ValueError("File cần có cột Ticker/Symbol hoặc tên file phải bắt đầu bằng mã cổ phiếu (ví dụ FPT.csv).")
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    for col in ("open","high","low","close","volume"):
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",","",regex=False), errors="coerce")
    df = df.dropna(subset=["symbol","date","open","high","low","close","volume"])
    df = df[df["symbol"].str.fullmatch(r"[A-Z0-9]{3,6}", na=False)]
    if df.empty:
        raise ValueError("File không có dòng OHLCV hợp lệ sau khi đọc.")
    return df[["symbol","date","open","high","low","close","volume"]].sort_values(["symbol","date"])

def render_cophieu68_import():
    st.divider()
    st.header("📥 Nhập dữ liệu Cophieu68")
    st.caption("Dùng file CSV/TXT xuất từ Cophieu68 hoặc AmiBroker/MetaStock. Dữ liệu được xử lý ngay trong phiên ứng dụng; chưa tự động tải trực tiếp từ website.")
    uploads = st.file_uploader("Chọn file dữ liệu Cophieu68", type=["csv","txt"], accept_multiple_files=True, key="cophieu68_files")
    if not uploads:
        st.info("Tải file dữ liệu lên để StockLab tính MOM14, EMA100 và khối lượng trung bình 20 phiên.")
        return
    frames, problems = [], []
    for upload in uploads:
        try:
            frames.append(read_cophieu68_file(upload))
        except Exception as exc:
            problems.append(f"{upload.name}: {exc}")
    if problems:
        for problem in problems:
            st.warning(problem)
    if not frames:
        return
    data = pd.concat(frames, ignore_index=True).drop_duplicates(["symbol","date"], keep="last")
    rows = []
    for symbol, hist in data.groupby("symbol"):
        hist = hist.sort_values("date").copy()
        hist["EMA100"] = hist["close"].ewm(span=100, adjust=False, min_periods=100).mean()
        hist["MOM14"] = (hist["close"] / hist["close"].shift(14) - 1) * 100
        hist["VOL20"] = hist["volume"].rolling(20, min_periods=20).mean()
        valid = hist.dropna(subset=["EMA100","MOM14","VOL20"])
        if valid.empty:
            continue
        last = valid.iloc[-1]
        rows.append({"Mã":symbol,"Ngày":last["date"],"Giá đóng cửa":last["close"],
                     "EMA100":last["EMA100"],"MOM14 (%)":last["MOM14"],
                     "Khối lượng":last["volume"],"KL trung bình 20 phiên":last["VOL20"]})
    if not rows:
        st.warning("Chưa đủ tối thiểu 100 phiên dữ liệu/mã để tính EMA100 và MOM14.")
        st.caption(f"Đã đọc {len(data):,} dòng thuộc {data['symbol'].nunique()} mã.")
        return
    result = pd.DataFrame(rows)
    a,b,c = st.columns(3)
    a.metric("Mã có đủ dữ liệu", f"{len(result):,}")
    b.metric("Tổng dòng OHLCV", f"{len(data):,}")
    c.metric("Ngày dữ liệu mới nhất", str(data["date"].max().date()))
    mom = st.number_input("MOM14 tối thiểu (%) · Cophieu68", value=4.0, step=0.5, key="cp68_mom")
    vol = st.number_input("Khối lượng TB20 tối thiểu · Cophieu68", value=50000, step=10000, key="cp68_vol")
    ema = st.checkbox("Giá đóng cửa ≥ EMA100 · Cophieu68", value=True, key="cp68_ema")
    passed = result[(result["MOM14 (%)"] >= mom) & (result["KL trung bình 20 phiên"] >= vol)]
    if ema:
        passed = passed[passed["Giá đóng cửa"] >= passed["EMA100"]]
    passed = passed.sort_values("MOM14 (%)", ascending=False)
    st.metric("Số mã đạt bộ lọc", f"{len(passed):,}")
    st.subheader("Top 3 Cophieu68")
    st.dataframe(passed.head(3), use_container_width=True, hide_index=True)
    st.subheader("Toàn bộ mã đạt điều kiện")
    st.dataframe(passed, use_container_width=True, hide_index=True)
    st.download_button("Tải kết quả Cophieu68 CSV", passed.to_csv(index=False).encode("utf-8-sig"),
                       "stocklab_cophieu68.csv", "text/csv", key="cp68_download")
