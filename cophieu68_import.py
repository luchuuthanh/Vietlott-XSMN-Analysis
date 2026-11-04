"""Import Cophieu68 CSV/TXT exports into StockLab without requiring a paid API."""
from __future__ import annotations
from io import BytesIO, StringIO
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

def fetch_cophieu68_listing() -> pd.DataFrame:
    """Fetch listed tickers directly from Cophieu68 HOSE/HNX/UPCOM boards."""
    import re
    import requests
    frames = []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://cophieu68.vn/"})
    for exchange, stcid in (("HOSE", "1"), ("HNX", "2"), ("UPCOM", "3")):
        response = session.get("https://www.cophieu68.vn/stockonline.php",
                               params={"stcid": stcid, "nd": 2000}, timeout=30)
        response.raise_for_status()
        tables = pd.read_html(StringIO(response.text))
        found = set()
        for table in tables:
            if table.empty:
                continue
            first = table.iloc[:, 0].astype(str).str.strip().str.upper()
            found.update(str(x) for x in first if re.fullmatch(r"[A-Z0-9]{3,6}", str(x)))
        if not found:
            # Some Cophieu68 pages expose symbols only as ticker links.
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.find_all("a", href=True):
                label = anchor.get_text(" ", strip=True).upper()
                href = anchor["href"].lower()
                if re.fullmatch(r"[A-Z0-9]{3,6}", label) and ("quote" in href or "stock" in href):
                    found.add(label)
        if not found:
            raise ValueError(f"Cophieu68 không trả danh sách mã {exchange}")
        frames.append(pd.DataFrame({"symbol": sorted(found), "exchange": exchange}))
    return pd.concat(frames, ignore_index=True).drop_duplicates("symbol").reset_index(drop=True)


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
        for table in pd.read_html(StringIO(response.text)):
            table.columns = [" ".join(map(str, c)).strip() if isinstance(c, tuple) else str(c).strip() for c in table.columns]
            normalized = {_key(c): c for c in table.columns}
            def col(*parts):
                return next((v for k, v in normalized.items() if any(p in k for p in parts)), None)
            d, close, vol = col("ngay", "date"), col("gia khop", "close"), col("khoi luong", "volume")
            op, hi, lo = col("mo cua", "open"), col("cao nhat", "high"), col("thap nhat", "low")
            # Cophieu68's history table may have blank/merged headers. Its
            # observed row layout is date, close, volume, open, high, low, ...
            if all((d, close, vol, op, hi, lo)):
                date_s, close_s, vol_s = table[d], table[close], table[vol]
                open_s, high_s, low_s = table[op], table[hi], table[lo]
            elif table.shape[1] >= 6:
                date_s, close_s, vol_s = table.iloc[:, 0], table.iloc[:, 1], table.iloc[:, 2]
                open_s, high_s, low_s = table.iloc[:, 3], table.iloc[:, 4], table.iloc[:, 5]
            else:
                continue
            def numeric(series):
                return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.replace(" ", "", regex=False), errors="coerce")
            parsed_date = pd.to_datetime(date_s, errors="coerce", dayfirst=True)
            if parsed_date.notna().sum() < 5:
                continue
            part = pd.DataFrame({
                "symbol": symbol,
                "date": parsed_date,
                "open": numeric(open_s),
                "high": numeric(high_s),
                "low": numeric(low_s),
                "close": numeric(close_s),
                "volume": numeric(vol_s)
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
    st.subheader("Quét toàn bộ thị trường bằng dữ liệu Cophieu68")
    st.caption("Tự động lấy danh sách đầy đủ (tối đa 2.000 mã mỗi sàn) từ Cophieu68 và quét toàn bộ HOSE/HNX/UPCOM trong một lần bấm.")
    if st.button("▶ Quét toàn bộ thị trường (HOSE/HNX/UPCOM)", key="cp68_market_scan"):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        try:
            universe = fetch_cophieu68_listing()
            scan_rows, scan_errors = [], []
            progress = st.progress(0)
            status = st.empty()
            def scan_one(item):
                ticker = item.symbol
                try:
                    hist = fetch_cophieu68_history(ticker, 2).sort_values("date")
                    hist["EMA100"] = hist["close"].ewm(span=100, adjust=False, min_periods=100).mean()
                    hist["MOM14"] = (hist["close"] / hist["close"].shift(14) - 1) * 100
                    hist["VOL20"] = hist["volume"].rolling(20, min_periods=20).mean()
                    valid = hist.dropna(subset=["EMA100", "MOM14", "VOL20"])
                    if valid.empty:
                        return None, f"{ticker}: insufficient history"
                    last = valid.iloc[-1]
                    return {"Mã": ticker, "Sàn": item.exchange, "Ngày": last["date"],
                            "Giá đóng cửa": last["close"], "EMA100": last["EMA100"],
                            "MOM14 (%)": last["MOM14"], "KL trung bình 20 phiên": last["VOL20"]}, None
                except Exception as exc:
                    return None, f"{ticker}: {exc}"
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(scan_one, item) for item in universe.itertuples(index=False)]
                for i, future in enumerate(as_completed(futures), 1):
                    row, error = future.result()
                    if row is not None:
                        scan_rows.append(row)
                    if error:
                        scan_errors.append(error)
                    if i % 25 == 0 or i == len(futures):
                        progress.progress(i / max(1, len(futures)))
                        status.caption(f"Đã xử lý {i}/{len(futures)} mã · dữ liệu hợp lệ {len(scan_rows)} · lỗi {len(scan_errors)}")
            st.session_state["cp68_market_rows"] = scan_rows
            st.session_state["cp68_market_errors"] = scan_errors
            st.session_state["cp68_market_total"] = len(universe)
            st.session_state["cp68_market_scanned"] = len(universe)
            st.success(f"Quét xong {len(universe)} mã từ Cophieu68; dữ liệu hợp lệ {len(scan_rows)}; lỗi {len(scan_errors)}.")
        except Exception as exc:
            st.error(f"Không quét được thị trường: {exc}")
    market_rows = st.session_state.get("cp68_market_rows", [])
    if market_rows:
        market_df = pd.DataFrame(market_rows).drop_duplicates("Mã", keep="last")
        st.caption(f"Đã có dữ liệu {len(market_df)} mã · {st.session_state.get('cp68_market_scanned', 0)}/{st.session_state.get('cp68_market_total', 0)} mã đã xử lý")
        m1 = st.number_input("MOM14 tối thiểu (%) · quét thị trường", value=4.0, step=0.5, key="cp68_market_mom")
        v1 = st.number_input("Khối lượng TB20 tối thiểu · quét thị trường", value=50000, step=10000, key="cp68_market_vol")
        e1 = st.checkbox("Giá đóng cửa ≥ EMA100 · quét thị trường", value=True, key="cp68_market_ema")
        selected = market_df[(market_df["MOM14 (%)"] >= m1) & (market_df["KL trung bình 20 phiên"] >= v1)]
        if e1:
            selected = selected[selected["Giá đóng cửa"] >= selected["EMA100"]]
        selected = selected.sort_values("MOM14 (%)", ascending=False)
        st.metric("Số mã đạt điều kiện Cophieu68", len(selected))
        st.dataframe(selected.head(3), use_container_width=True, hide_index=True)
        st.dataframe(selected, use_container_width=True, hide_index=True)
        st.download_button("Tải kết quả quét thị trường CSV", selected.to_csv(index=False).encode("utf-8-sig"),
                           "stocklab_cophieu68_market.csv", "text/csv", key="cp68_market_download")
    for err in st.session_state.get("cp68_market_errors", []):
        st.caption(err)

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
