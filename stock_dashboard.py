"""Vietnam stock scanner using Vnstock data sources with VCI/KBS fallback."""
from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

EXCHANGES = {"HOSE", "HNX", "UPCOM"}
DATA_SOURCES = ("vci", "kbs")

class MarketDataError(RuntimeError):
    pass

def _vnstock_classes():
    try:
        from vnstock import Listing, Quote
        return Listing, Quote
    except Exception as exc:
        raise MarketDataError(
            "Không nạp được Vnstock. Hãy kiểm tra gói vnstock trong requirements.txt "
            "và khởi động lại ứng dụng. Chi tiết: " + str(exc)
        ) from exc

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_instruments() -> pd.DataFrame:
    Listing, _ = _vnstock_classes()
    errors = []
    for source in DATA_SOURCES:
        try:
            raw = Listing(source=source).symbols_by_exchange()
            df = pd.DataFrame(raw)
            if df.empty or "symbol" not in df.columns or "exchange" not in df.columns:
                raise MarketDataError(f"Nguồn {source} không trả đủ cột symbol/exchange.")
            df["exchange"] = df["exchange"].astype(str).str.upper().str.strip()
            df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
            df = df[df["exchange"].isin(EXCHANGES)].drop_duplicates("symbol")
            if not df.empty:
                return df.reset_index(drop=True)
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    raise MarketDataError("Không lấy được danh sách mã từ Vnstock. " + " | ".join(errors))

def _normalize_quotes(payload) -> pd.DataFrame:
    df = pd.DataFrame(payload).copy()
    mapping = {"time": "date", "date": "date", "open": "open",
               "high": "high", "low": "low", "close": "close", "volume": "volume"}
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise MarketDataError("Thiếu trường dữ liệu OHLCV: " + ", ".join(missing))
    df = df[required].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    # Vnstock may return timezone-aware Vietnam timestamps or naive timestamps.
    if df["date"].dt.tz is not None:
        df["date"] = df["date"].dt.tz_convert("Asia/Ho_Chi_Minh").dt.tz_localize(None)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)

@st.cache_data(ttl=900, show_spinner=False)
def fetch_daily_quotes(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    _, Quote = _vnstock_classes()
    errors = []
    for source in DATA_SOURCES:
        try:
            raw = Quote(source=source, symbol=symbol).history(start=start_date, end=end_date)
            df = _normalize_quotes(raw)
            if not df.empty:
                return df
            errors.append(f"{source}: không có dữ liệu")
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    raise MarketDataError(f"Không tải được lịch sử {symbol}. " + " | ".join(errors))

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["EMA20"] = out["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    out["EMA50"] = out["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    out["EMA100"] = out["close"].ewm(span=100, adjust=False, min_periods=100).mean()
    # MOM14 is expressed as percentage change from 14 trading sessions earlier.
    out["MOM14"] = (out["close"] / out["close"].shift(14) - 1) * 100
    delta = out["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    out["RSI14"] = 100 - (100 / (1 + rs))
    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_SIGNAL"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_HIST"] = out["MACD"] - out["MACD_SIGNAL"]
    return out

@st.cache_data(ttl=21600, show_spinner=False)
def scan_market(instruments: pd.DataFrame, lookback_days: int = 260, _progress=None) -> tuple[pd.DataFrame, dict]:
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    end = date.today().isoformat()
    rows, errors = [], []
    symbols = instruments.to_dict("records")
    for i, item in enumerate(symbols):
        symbol = item["symbol"]
        try:
            hist = add_indicators(fetch_daily_quotes(symbol, start, end))
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
    st.header("📈 STOCKLAB VIỆT NAM")
    st.caption("Bảng giá · Bộ lọc cổ phiếu · Biểu đồ nến · EMA · RSI · MACD · Khối lượng")

    st.caption("Dữ liệu nến ngày từ Vnstock; tự thử VCI rồi KBS khi nguồn đầu gặp lỗi.")

    left, right = st.columns([1, 1])
    with left:
        days = st.selectbox("Số ngày lịch sử", [260, 365, 520, 730], index=1)
    with right:
        min_volume = st.number_input("Khối lượng tối thiểu (cổ phiếu)", min_value=0, value=50000, step=10000)
    mom_floor = st.number_input("MOM14 tối thiểu (%)", value=4.0, step=0.5)
    require_ema = st.checkbox("Chỉ lấy giá đóng cửa ≥ EMA100", value=True)

    if st.button("🔄 Cập nhật dữ liệu và quét thị trường", type="primary", use_container_width=True):
        try:
            instruments = fetch_instruments()
            st.info(f"Đang quét {len(instruments):,} mã HOSE, HNX và UPCoM. Quá trình có thể mất vài phút.")
            progress = st.progress(0)
            result, stats = scan_market(instruments, days, progress.progress)
            st.session_state["vnstock_scan"] = result
            st.session_state["vnstock_scan_stats"] = stats
            st.session_state["vnstock_instruments"] = instruments
            
            st.session_state["vnstock_days"] = days
        except Exception as exc:
            st.error(f"Không thể quét dữ liệu Vnstock: {exc}")
            st.stop()

    result = st.session_state.get("vnstock_scan")
    stats = st.session_state.get("vnstock_scan_stats")
    if result is None or result.empty:
        st.info("Chưa có dữ liệu quét. Nhấn nút 'Cập nhật dữ liệu và quét thị trường' để bắt đầu.")
        return

    result = result.copy()
    result["Đạt MOM14"] = result["MOM14 (%)"] >= mom_floor
    result["Đạt EMA100"] = result["Giá đóng cửa"] >= result["EMA100"]
    result["Đạt khối lượng"] = result["Khối lượng"] >= min_volume
    result["Đạt bộ lọc"] = result["Đạt MOM14"] & result["Đạt khối lượng"]
    if require_ema:
        result["Đạt bộ lọc"] = result["Đạt bộ lọc"] & result["Đạt EMA100"]
    filtered = result[result["Đạt bộ lọc"]].copy()
    filtered = filtered.sort_values("MOM14 (%)", ascending=False).reset_index(drop=True)

    if stats:
        a, b, c = st.columns(3)
        a.metric("Mã đã quét", f"{stats['scanned']:,}")
        b.metric("Mã có dữ liệu", f"{stats['success']:,}")
        c.metric("Mã đạt bộ lọc", f"{len(filtered):,}")

    tab_scan, tab_chart, tab_all = st.tabs(["🔎 Bộ lọc cổ phiếu", "📊 Biểu đồ kỹ thuật", "📋 Toàn bộ thị trường"])
    with tab_scan:
        st.subheader("Danh sách cổ phiếu đạt điều kiện")
        st.dataframe(
            filtered[["Mã", "Sàn", "Giá đóng cửa", "MOM14 (%)", "EMA100", "Khối lượng", "Ngày dữ liệu"]],
            use_container_width=True, hide_index=True
        )
        st.download_button(
            "Tải danh sách CSV", filtered.to_csv(index=False).encode("utf-8-sig"),
            "co_phieu_dat_bo_loc.csv", "text/csv"
        )

    with tab_chart:
        instruments = st.session_state.get("vnstock_instruments")
        
        chart_days = st.session_state.get("vnstock_days", days)
        available = filtered["Mã"].tolist() or result["Mã"].tolist()
        selected = st.selectbox("Chọn mã cổ phiếu", available, key="amibroker_symbol")
        start = (date.today() - timedelta(days=chart_days)).isoformat()
        try:
            chart = add_indicators(fetch_daily_quotes(selected, start, date.today().isoformat()))
            chart = chart.dropna(subset=["date", "open", "high", "low", "close"])
            if chart.empty:
                st.warning("Chưa có dữ liệu OHLC hợp lệ cho mã này.")
            else:
                last = chart.iloc[-1]
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Giá đóng cửa", f"{last['close']:,.2f}")
                p2.metric("MOM14", f"{last['MOM14']:.2f}%" if pd.notna(last["MOM14"]) else "—")
                p3.metric("RSI14", f"{last['RSI14']:.1f}" if pd.notna(last["RSI14"]) else "—")
                p4.metric("Khối lượng", f"{last['volume']:,.0f}")
                fig = make_subplots(
                    rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                    row_heights=[0.62, 0.18, 0.20],
                    specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}]]
                )
                fig.add_trace(go.Candlestick(
                    x=chart["date"], open=chart["open"], high=chart["high"],
                    low=chart["low"], close=chart["close"], name="Giá"
                ), row=1, col=1)
                for col, label in [("EMA20", "EMA20"), ("EMA50", "EMA50"), ("EMA100", "EMA100")]:
                    fig.add_trace(go.Scatter(x=chart["date"], y=chart[col], mode="lines", name=label), row=1, col=1)
                fig.add_trace(go.Bar(x=chart["date"], y=chart["volume"], name="Khối lượng"), row=2, col=1)
                fig.add_trace(go.Scatter(x=chart["date"], y=chart["RSI14"], name="RSI14"), row=3, col=1)
                fig.add_hline(y=70, line_dash="dot", row=3, col=1)
                fig.add_hline(y=30, line_dash="dot", row=3, col=1)
                fig.update_layout(
                    height=820, template="plotly_dark", xaxis_rangeslider_visible=False,
                    margin=dict(l=10, r=10, t=35, b=10), legend=dict(orientation="h", y=1.02),
                    hovermode="x unified"
                )
                fig.update_yaxes(title_text="Giá", row=1, col=1)
                fig.update_yaxes(title_text="KL", row=2, col=1)
                fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
                st.plotly_chart(fig, use_container_width=True)
                macd_fig = go.Figure()
                macd_fig.add_trace(go.Bar(x=chart["date"], y=chart["MACD_HIST"], name="MACD Histogram"))
                macd_fig.add_trace(go.Scatter(x=chart["date"], y=chart["MACD"], name="MACD"))
                macd_fig.add_trace(go.Scatter(x=chart["date"], y=chart["MACD_SIGNAL"], name="Signal"))
                macd_fig.update_layout(height=260, template="plotly_dark", margin=dict(l=10,r=10,t=20,b=10), hovermode="x unified")
                st.plotly_chart(macd_fig, use_container_width=True)
                st.dataframe(chart.tail(30).sort_values("date", ascending=False), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Không tải được biểu đồ {selected}: {exc}")

    with tab_all:
        st.subheader("Bảng dữ liệu toàn thị trường")
        st.dataframe(result, use_container_width=True, hide_index=True)
        st.download_button(
            "Tải toàn bộ kết quả quét CSV", result.to_csv(index=False).encode("utf-8-sig"),
            "ket_qua_quet_thi_truong.csv", "text/csv"
        )
        if stats and stats.get("errors"):
            with st.expander(f"Lỗi ở {len(stats['errors'])} mã"):
                st.code("\n".join(stats["errors"][:100]))
