"""FireAnt stock scanner: daily OHLCV, EMA100 and 14-session momentum."""
from __future__ import annotations

from datetime import date, timedelta
import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://restv2.fireant.vn"
EXCHANGES = {"HOSE", "HNX", "UPCOM"}

class FireAntError(RuntimeError):
    pass

def _headers(token: str | None) -> dict:
    h = {"Accept": "application/json", "User-Agent": "VietnamStockScanner/1.0"}
    if token and token.strip():
        h["Authorization"] = f"Bearer {token.strip()}"
    return h

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_instruments(token: str = "") -> pd.DataFrame:
    r = requests.get(f"{BASE_URL}/instruments", headers=_headers(token), timeout=30)
    if r.status_code in (401, 403):
        raise FireAntError("FireAnt từ chối truy cập danh sách mã. Hãy kiểm tra access token/quyền symbols-read.")
    r.raise_for_status()
    payload = r.json()
    df = pd.DataFrame(payload if isinstance(payload, list) else payload.get("items", []))
    required = {"symbol", "exchange"}
    if df.empty or not required.issubset(df.columns):
        raise FireAntError("FireAnt trả về danh sách mã không đúng cấu trúc dự kiến.")
    df["exchange"] = df["exchange"].astype(str).str.upper().str.strip()
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    return df[df["exchange"].isin(EXCHANGES)].drop_duplicates("symbol").reset_index(drop=True)

def _normalize_quotes(payload) -> pd.DataFrame:
    df = pd.DataFrame(payload if isinstance(payload, list) else payload.get("items", []))
    mapping = {
        "date": "date", "priceOpen": "open", "priceHigh": "high",
        "priceLow": "low", "priceClose": "close", "totalVolume": "volume",
    }
    df = df.rename(columns=mapping)
    missing = [c for c in mapping.values() if c not in df.columns]
    if missing:
        raise FireAntError("Thiếu trường dữ liệu giá: " + ", ".join(missing))
    df = df[list(mapping.values())].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_convert("Asia/Ho_Chi_Minh").dt.tz_localize(None)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)

@st.cache_data(ttl=900, show_spinner=False)
def fetch_daily_quotes(symbol: str, start_date: str, end_date: str, token: str = "") -> pd.DataFrame:
    url = f"{BASE_URL}/symbols/{symbol}/historical-quotes"
    params = {"startDate": f"{start_date}T00:00:00Z", "endDate": f"{end_date}T23:59:59Z", "offset": 0, "limit": 1000}
    r = requests.get(url, params=params, headers=_headers(token), timeout=30)
    if r.status_code in (401, 403):
        raise FireAntError(f"FireAnt không cho phép đọc lịch sử {symbol}. Kiểm tra access token/quyền symbols-read.")
    r.raise_for_status()
    return _normalize_quotes(r.json())

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["EMA20"] = out["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    out["EMA50"] = out["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    out["EMA100"] = out["close"].ewm(span=100, adjust=False, min_periods=100).mean()
    # MOM14 is expressed as percentage change from 14 trading sessions earlier.
    out["MOM14"] = (out["close"] / out["close"].shift(14) - 1) * 100
    return out

@st.cache_data(ttl=21600, show_spinner=False)
def scan_market(instruments: pd.DataFrame, token: str = "", lookback_days: int = 260, _progress=None) -> tuple[pd.DataFrame, dict]:
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    end = date.today().isoformat()
    rows, errors = [], []
    symbols = instruments.to_dict("records")
    for i, item in enumerate(symbols):
        symbol = item["symbol"]
        try:
            hist = add_indicators(fetch_daily_quotes(symbol, start, end, token))
            valid = hist.dropna(subset=["EMA100", "MOM14"])
            if not valid.empty:
                last = valid.iloc[-1]
                rows.append({
                    "Mã": symbol, "Sàn": item.get("exchange", ""),
                    "Giá đóng cửa": last["close"], "EMA100": last["EMA100"],
                    "MOM14 (%)": last["MOM14"], "Khối lượng": last["volume"],
                    "Ngày dữ liệu": last["date"],
                    "Đạt MOM14": bool(last["MOM14"] >= 4),
                    "Đạt EMA100": bool(last["close"] >= last["EMA100"]),
                    "Đạt bộ lọc": bool(last["MOM14"] >= 4 and last["close"] >= last["EMA100"]),
                })
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
        if _progress:
            _progress((i + 1) / max(len(symbols), 1), text=f"Đang quét {symbol} ({i+1}/{len(symbols)})")
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["Đạt bộ lọc", "MOM14 (%)"], ascending=[False, False]).reset_index(drop=True)
    return result, {"scanned": len(symbols), "success": len(rows), "errors": errors}

def render_stock_dashboard():
    st.header("📈 CHỨNG KHOÁN VIỆT NAM — FIREANT")
    st.caption("Quét HOSE, HNX, UPCoM · MOM14 ≥ 4% · Giá đóng cửa ≥ EMA100")
    with st.expander("Kết nối FireAnt", expanded=True):
        token = st.text_input("FireAnt access token (nếu API yêu cầu)", type="password",
                              help="Lấy token theo quyền đọc dữ liệu. Không gửi token trong chat và không lưu vào GitHub.")
        st.caption("Token chỉ được dùng trong phiên ứng dụng này. Có thể cần quyền symbols-read.")
    c1, c2 = st.columns(2)
    with c1:
        days = st.selectbox("Lịch sử dùng để tính EMA100", [260, 365, 520, 730], index=1)
    with c2:
        view = st.selectbox("Khung biểu đồ", ["D1 (ngày)", "H1 (giờ — chưa xác minh endpoint)"])
    if view.startswith("H1"):
        st.warning("Tài liệu FireAnt REST v1 công khai xác nhận historical-quotes nhưng chưa mô tả tham số nến 1 giờ. Vì vậy chưa bật H1 để tránh hiển thị dữ liệu sai. D1 dùng dữ liệu lịch sử đã xác nhận.")
    if st.button("🔄 Thu thập và quét toàn thị trường", type="primary", use_container_width=True):
        try:
            instruments = fetch_instruments(token)
            st.success(f"Đã lấy danh sách {len(instruments):,} mã thuộc HOSE, HNX và UPCoM.")
            bar = st.progress(0)
            result, stats = scan_market(instruments, token, days, bar.progress)
            st.session_state["fireant_scan"] = result
            st.session_state["fireant_scan_stats"] = stats
        except Exception as exc:
            st.error(f"Không thể hoàn tất quét FireAnt: {exc}")
            st.info("Kiểm tra quyền truy cập API, access token và giới hạn truy vấn của FireAnt.")
    result = st.session_state.get("fireant_scan")
    stats = st.session_state.get("fireant_scan_stats")
    # Reuse Streamlit's shared cache when a browser session is recreated.
    if result is None:
        try:
            with st.spinner("Đang tải kết quả quét đã lưu (nếu có)…"):
                instruments = fetch_instruments(token)
                result, stats = scan_market(instruments, token, days)
                st.session_state["fireant_scan"] = result
                st.session_state["fireant_scan_stats"] = stats
        except Exception as exc:
            st.info(f"Chưa có kết quả quét được lưu hoặc chưa kết nối được FireAnt: {exc}")
    if result is not None:
        if stats:
            st.write(f"Đã quét {stats['scanned']} mã; nhận dữ liệu hợp lệ {stats['success']} mã.")
        passed = result[result["Đạt bộ lọc"]]
        st.subheader(f"Cổ phiếu đạt điều kiện: {len(passed)} mã")
        st.dataframe(passed, use_container_width=True, hide_index=True)
        st.download_button("Tải danh sách đạt điều kiện CSV", passed.to_csv(index=False).encode("utf-8-sig"),
                           "fireant_stocks_mom14_ema100.csv", "text/csv")
        st.subheader("Tra cứu biểu đồ từng mã")
        symbols = result["Mã"].tolist()
        selected = st.selectbox("Chọn mã cổ phiếu", symbols)
        instrument = instruments[instruments["symbol"] == selected].iloc[0] if "instruments" in locals() else None
        start = (date.today() - timedelta(days=days)).isoformat()
        try:
            chart = add_indicators(fetch_daily_quotes(selected, start, date.today().isoformat(), token))
            st.line_chart(chart.set_index("date")[["close", "EMA20", "EMA50", "EMA100"]], use_container_width=True)
            st.line_chart(chart.set_index("date")[["MOM14"]], use_container_width=True)
            st.dataframe(chart.tail(30).sort_values("date", ascending=False), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Không tải được biểu đồ {selected}: {exc}")
        if stats and stats["errors"]:
            with st.expander(f"Lỗi ở {len(stats['errors'])} mã"):
                st.code("\n".join(stats["errors"][:100]))
