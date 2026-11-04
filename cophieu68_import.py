"""Import Cophieu68 CSV/TXT exports into StockLab without requiring a paid API."""
from __future__ import annotations
from io import BytesIO
import unicodedata
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
    value = unicodedata.normalize("NFKD", str(value).strip().lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.replace("_"," ").replace("-"," ").replace("."," ")

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

def fetch_cophieu68_history(symbol: str, max_pages: int = 10) -> pd.DataFrame:
    """Read public paginated OHLCV history from Cophieu68."""
    import requests
    symbol = symbol.strip().upper()
    if not symbol.isalnum() or not 3 <= len(symbol) <= 6:
        raise ValueError("Mã cổ phiếu không hợp lệ")
    frames = []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://cophieu68.vn/"})
    for page in range(1, max_pages + 1):
        params = {"id": symbol, "cP": 1}
        if page > 1:
            params["cP"] = page
        response = session.get("https://cophieu68.vn/quote/history.php", params=params, timeout=25)
        response.raise_for_status()
        found = False
        for table in pd.read_html(response.text):
            table.columns = [" ".join(map(str, c)).strip() if isinstance(c, tuple) else str(c).strip() for c in table.columns]
            normalized = {_key(c): c for c in table.columns}
            def col(*parts):
                return next((v for k, v in normalized.items() if any(p in k for p in parts)), None)
            d, close, vol = col("ngay", "date"), col("gia khop", "close"), col("khoi luong", "volume")
            op, hi, lo = col("mo cua", "open"), col("cao nhat", "high"), col("thap nhat", "low")
            if not all((d, close, vol, op, hi, lo)):
                continue
            part = pd.DataFrame({
                "symbol": symbol,
                "date": pd.to_datetime(table[d], errors="coerce", dayfirst=True),
                "open": pd.to_numeric(table[op].astype(str).str.replace(",", "", regex=False), errors="coerce"),
                "high": pd.to_numeric(table[hi].astype(str).str.replace(",", "", regex=False), errors="coerce"),
                "low": pd.to_numeric(table[lo].astype(str).str.replace(",", "", regex=False), errors="coerce"),
                "close": pd.to_numeric(table[close].astype(str).str.replace(",", "", regex=False), errors="coerce"),
                "volume": pd.to_numeric(table[vol].astype(str).str.replace(",", "", regex=False), errors="coerce")
            }).dropna(subset=["date", "open", "high", "low", "close", "volume"])
            if not part.empty:
                frames.append(part)
                found = True
                break
        if not found:
            break
    if not frames:
        raise ValueError("Không đọc được bảng lịch sử OHLCV từ Cophieu68")
    return pd.concat(frames, ignore_index=True).drop_duplicates("date").sort_values("date")


def render_cophieu68_import():
    st.divider()
    st.header("📥 Nhập dữ liệu Cophieu68")
    st.caption("Lấy lịch sử trực tiếp từ Cophieu68 theo từng mã hoặc nhập file CSV/TXT của AmiBroker.")
    symbols_text = st.text_input("Mã cổ phiếu lấy trực tiếp (phân cách dấu phẩy)", value="FPT,HPG,VCB", key="cp68_direct_symbols")
    max_pages = st.selectbox("Số trang lịch sử mỗi mã", [2, 5, 10, 20], index=2, key="cp68_pages")
    if st.button("🌐 Tải lịch sử trực tiếp từ Cophieu68", key="cp68_fetch_direct"):
        symbols = list(dict.fromkeys(s.strip().upper() for s in symbols_text.split(",") if s.strip()))[:50]
        direct_frames, direct_errors = [], []
        progress = st.progress(0)
        for i, symbol in enumerate(symbols):
            try:
                direct_frames.append(fetch_cophieu68_history(symbol, int(max_pages)))
            except Exception as exc:
                direct_errors.append(f"{symbol}: {exc}")
            progress.progress((i + 1) / max(1, len(symbols)))
        if direct_frames:
            st.session_state["cp68_direct_data"] = pd.concat(direct_frames, ignore_index=True)
        st.session_state["cp68_direct_errors"] = direct_errors
    direct_data = st.session_state.get("cp68_direct_data")
    if isinstance(direct_data, pd.DataFrame) and not direct_data.empty:
        st.success(f"Đã lấy {len(direct_data):,} phiên của {direct_data['symbol'].nunique()} mã trực tiếp từ Cophieu68.")
        st.download_button("Tải dữ liệu lịch sử CSV", direct_data.to_csv(index=False).encode("utf-8-sig"), "cophieu68_history.csv", "text/csv", key="cp68_direct_download")
    for err in st.session_state.get("cp68_direct_errors", []):
        st.warning(err)
    uploads = st.file_uploader("Hoặc chọn file CSV/TXT xuất từ Cophieu68/AmiBroker", type=["csv","txt"], accept_multiple_files=True, key="cophieu68_files")
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
