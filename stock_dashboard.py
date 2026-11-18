"""Vietnam stock scanner using Vnstock data sources with VCI/KBS fallback."""
from __future__ import annotations

from datetime import date, timedelta
import os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

EXCHANGES = {"HOSE", "HNX", "UPCOM"}
DATA_SOURCES = ("vci", "kbs")
_VNSTOCK_AUTH_READY = False

class MarketDataError(RuntimeError):
    pass

def _vnstock_classes():
    global _VNSTOCK_AUTH_READY
    try:
        import vnstock
        from vnstock import Listing, Quote
        api_key = os.getenv("VNSTOCK_API_KEY", "").strip()
        if api_key and not _VNSTOCK_AUTH_READY:
            vnstock.login(api_key)
            _VNSTOCK_AUTH_READY = True
        return Listing, Quote
    except Exception as exc:
        raise MarketDataError(
            "Không nạp được Vnstock. Hãy kiểm tra gói vnstock trong requirements.txt "
            "và khởi động lại ứng dụng. Chi tiết: " + str(exc)
        ) from exc

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_instruments() -> pd.DataFrame:
    """Build HOSE/HNX/UPCOM universe from Cophieu68 public listings."""
    from cophieu68_import import fetch_cophieu68_listing
    try:
        return fetch_cophieu68_listing()
    except Exception as exc:
        raise MarketDataError(f"Không lấy được danh sách mã từ Cophieu68: {exc}") from exc

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
def fetch_daily_quotes(symbol: str, start_date: str, end_date: str, interval: str = "1D") -> pd.DataFrame:
    _, Quote = _vnstock_classes()
    errors = []
    for source in DATA_SOURCES:
        try:
            raw = Quote(source=source, symbol=symbol).history(start=start_date, end=end_date, interval=interval)
            df = _normalize_quotes(raw)
            if not df.empty:
                return df
            errors.append(f"{source}: không có dữ liệu")
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    raise MarketDataError(f"Không tải được lịch sử {symbol}. " + " | ".join(errors))

@st.cache_data(ttl=900, show_spinner=False)
def fetch_chart_quotes(symbol: str, start_date: str, end_date: str, interval: str = "1D") -> tuple[pd.DataFrame, str]:
    """Use public Cophieu68 daily history first; use Vnstock for intraday candles."""
    if interval == "1D":
        try:
            from cophieu68_import import fetch_cophieu68_history
            history = fetch_cophieu68_history(symbol, max_pages=30)
            history = history.rename(columns={"date": "date"})
            history["date"] = pd.to_datetime(history["date"], errors="coerce")
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            history = history[(history["date"] >= start) & (history["date"] <= end)]
            normalized = _normalize_quotes(history)
            if len(normalized) >= 20:
                return normalized, "Cophieu68 · dữ liệu ngày"
        except Exception as exc:
            cp68_error = str(exc)
        else:
            cp68_error = "Cophieu68 trả về không đủ dữ liệu"
    else:
        cp68_error = "Cophieu68 chỉ dùng cho biểu đồ ngày 1D"
    try:
        return fetch_daily_quotes(symbol, start_date, end_date, interval), "Vnstock VCI/KBS"
    except Exception as exc:
        raise MarketDataError(f"Cophieu68: {cp68_error}. Vnstock: {exc}") from exc

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["EMA20"] = out["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    out["EMA50"] = out["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    out["EMA100"] = out["close"].ewm(span=100, adjust=False, min_periods=100).mean()
    # FireAnt Mom: length 10, source Close; value is a price difference, not a percentage.
    out["MOM10"] = out["close"] - out["close"].shift(10)
    # ROC14 is percentage change from 14 trading sessions earlier.
    out["ROC14"] = (out["close"] / out["close"].shift(14) - 1) * 100
    out["VOL20"] = out["volume"].rolling(20, min_periods=20).mean()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    out["RSI14"] = 100 - (100 / (1 + rs))
    out.loc[(loss == 0) & (gain > 0), "RSI14"] = 100
    out.loc[(loss == 0) & (gain == 0), "RSI14"] = 50
    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_SIGNAL"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_HIST"] = out["MACD"] - out["MACD_SIGNAL"]
    return out

# Deliberately not cached: scan_market updates a live Streamlit progress element.
def _scan_market_uncached_v2(instruments: pd.DataFrame, lookback_days: int = 260) -> tuple[pd.DataFrame, dict]:
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    end = date.today().isoformat()
    rows, errors = [], []
    symbols = instruments.to_dict("records")
    for i, item in enumerate(symbols):
        symbol = item["symbol"]
        try:
            hist = add_indicators(fetch_daily_quotes(symbol, start, end))
            valid = hist.dropna(subset=["EMA100", "MOM10", "ROC14", "VOL20"])
            if not valid.empty:
                last = valid.iloc[-1]
                rows.append({
                    "Mã": symbol, "Sàn": item.get("exchange", ""),
                    "Giá đóng cửa": last["close"], "EMA100": last["EMA100"],
                    "MOM10 (FireAnt)": last["MOM10"], "ROC14 (%)": last["ROC14"], "Khối lượng": last["volume"],
                    "KLGD TB20": last["VOL20"], "Ngày dữ liệu": last["date"],
                    "Đạt ROC14": bool(last["ROC14"] >= 4),
                    "Đạt EMA100": bool(last["close"] >= last["EMA100"]),
                    "Đạt MOM10": bool(last["MOM10"] >= 4),
                    "Đạt bộ lọc": bool(last["MOM10"] >= 4 and last["ROC14"] >= 4 and last["close"] >= last["EMA100"]),
                })
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["Đạt bộ lọc", "ROC14 (%)"], ascending=[False, False]).reset_index(drop=True)
    return result, {"scanned": len(symbols), "success": len(rows), "errors": errors}

def load_saved_market_scan() -> tuple[pd.DataFrame | None, dict | None]:
    """Load the latest automated Cophieu68 scan committed by GitHub Actions."""
    from pathlib import Path
    path = Path(__file__).resolve().parent / "stocklab_market_all.csv"
    passed_path = Path(__file__).resolve().parent / "stocklab_market_passed.csv"
    if not path.exists():
        return None, None
    try:
        raw = pd.read_csv(path)
        required = {"symbol", "exchange", "date", "close", "EMA100", "MOM10", "ROC14", "VOL20"}
        if raw.empty or not required.issubset(raw.columns):
            raise ValueError("CSV thiếu cột bắt buộc hoặc không có dữ liệu")
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
        for col in ("close", "EMA100", "MOM10", "ROC14", "VOL20"):
            raw[col] = pd.to_numeric(raw[col], errors="coerce")
        raw = raw.dropna(subset=["symbol", "date", "close", "EMA100", "MOM10", "ROC14", "VOL20"])
        if raw.empty:
            raise ValueError("Không còn dòng OHLCV hợp lệ sau khi chuẩn hóa")
        result = pd.DataFrame({
            "Mã": raw["symbol"].astype(str).str.upper(),
            "Sàn": raw["exchange"].astype(str).str.upper(),
            "Giá đóng cửa": raw["close"],
            "EMA100": raw["EMA100"],
            "MOM10 (FireAnt)": raw["MOM10"],
            "ROC14 (%)": raw["ROC14"],
            "Khối lượng": pd.to_numeric(raw["volume"], errors="coerce") if "volume" in raw.columns else pd.NA,
            "KLGD TB20": raw["VOL20"],
            "Ngày dữ liệu": raw["date"],
        })
        updated = str(raw["updated_at_utc"].iloc[0]) if "updated_at_utc" in raw.columns else "không rõ"
        passed_count = None
        if passed_path.exists():
            passed = pd.read_csv(passed_path)
            passed_count = len(passed)
        stats = {
            "scanned": len(raw), "success": len(raw), "total": len(raw),
            "complete": True, "errors": [], "source": "GitHub Actions · Cophieu68",
            "updated_at_utc": updated, "saved_passed_count": passed_count,
        }
        return result, stats
    except Exception as exc:
        raise MarketDataError(f"Không đọc được bản quét tự động ({path.name}): {exc}") from exc


def render_stock_dashboard():
    st.header("📈 STOCKLAB VIỆT NAM")
    st.caption("Bảng giá · Bộ lọc cổ phiếu · Biểu đồ nến · EMA · RSI · MACD · Khối lượng")

    st.caption("Dữ liệu từ Vnstock (VCI/KBS). Có thể chạy chế độ Khách; đặt VNSTOCK_API_KEY trong Secrets để dùng hạn mức tài khoản Cộng đồng.")

    left, right = st.columns([1, 1])
    with left:
        days = st.selectbox("Số ngày lịch sử", [260, 365, 520, 730], index=1)
    with right:
        min_volume = st.number_input("Khối lượng tối thiểu (cổ phiếu)", min_value=0, value=50000, step=10000)
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        mom_floor = st.number_input("ROC14 tối thiểu (%)", value=4.0, step=0.5)
    with filter_col2:
        mom10_floor = st.number_input("MOM10 tối thiểu (giá)", value=4.0, step=0.5)
    require_ema = st.checkbox("Chỉ lấy giá đóng cửa ≥ EMA100", value=True)
    st.caption("Dữ liệu thị trường được cập nhật tự động từ Cophieu68. Nút bên dưới chỉ nạp lại bản quét đầy đủ, không gọi Vnstock hàng loạt.")

    scan_col, reset_col = st.columns([3, 1])
    with reset_col:
        if st.button("Xóa kết quả", use_container_width=True):
            for key in ("vnstock_scan_offset", "vnstock_scan_all", "vnstock_scan", "vnstock_scan_stats", "vnstock_instruments", "vnstock_days"):
                st.session_state.pop(key, None)
            st.rerun()
    with scan_col:
        scan_clicked = st.button("🔄 Cập nhật dữ liệu và quét thị trường", type="primary", use_container_width=True)
    if scan_clicked:
        try:
            # Prefer the complete scheduled Cophieu68 snapshot. Do not start
            # hundreds of Vnstock requests from a mobile button: that quickly
            # exhausts the per-minute quota and leaves a misleading partial scan.
            saved_result, saved_stats = load_saved_market_scan()
            if saved_result is None or saved_result.empty:
                raise MarketDataError(
                    "Chưa có dữ liệu quét tự động. Hãy chờ GitHub Actions cập nhật dữ liệu thị trường."
                )
            for key in (
                "vnstock_scan_offset", "vnstock_scan_all", "vnstock_scan",
                "vnstock_scan_stats", "vnstock_scan_config", "vnstock_instruments",
                "vnstock_days", "vnstock_scan_source",
            ):
                st.session_state.pop(key, None)
            st.session_state["vnstock_scan"] = saved_result
            st.session_state["vnstock_scan_all"] = saved_result
            st.session_state["vnstock_scan_stats"] = saved_stats
            st.session_state["vnstock_scan_source"] = "automatic"
            st.success(
                f"Đã nạp dữ liệu quét tự động: {len(saved_result):,} mã có dữ liệu. "
                "Không gọi Vnstock hàng loạt nên không tiêu hao hạn mức API."
            )
        except Exception as exc:
            st.error(f"Không thể nạp dữ liệu quét tự động: {exc}")
            st.stop()

    result = st.session_state.get("vnstock_scan")
    stats = st.session_state.get("vnstock_scan_stats")
    if result is None or result.empty:
        try:
            result, stats = load_saved_market_scan()
            if result is not None:
                st.session_state["vnstock_scan"] = result
                st.session_state["vnstock_scan_stats"] = stats
                st.session_state["vnstock_scan_all"] = result
                st.session_state["vnstock_scan_source"] = "automatic"
        except MarketDataError as exc:
            st.warning(str(exc))
    if result is None or result.empty:
        st.info("Chưa có bản quét tự động. Workflow GitHub Actions sẽ cập nhật theo lịch ngày giao dịch; mày cũng có thể nhấn nút cập nhật để quét thủ công.")
        from cophieu68_import import render_cophieu68_import
        render_cophieu68_import()
        return

    if stats and stats.get("source"):
        st.success(
            f"Bản quét tự động: {stats['success']:,}/{stats['total']:,} mã có dữ liệu · "
            f"{stats.get('saved_passed_count', '—')} mã đạt bộ lọc mặc định · "
            f"cập nhật UTC: {stats.get('updated_at_utc', 'không rõ')}"
        )

    result = result.copy()
    result["Đạt ROC14"] = result["ROC14 (%)"] >= mom_floor
    result["Đạt MOM10"] = result["MOM10 (FireAnt)"] >= mom10_floor
    result["Đạt EMA100"] = result["Giá đóng cửa"] >= result["EMA100"]
    result["Đạt khối lượng"] = result["KLGD TB20"] >= min_volume
    # Two independent momentum screens; share only volume and optional EMA constraints.
    common_pass = result["Đạt khối lượng"]
    if require_ema:
        common_pass = common_pass & result["Đạt EMA100"]
    result["Đạt MOM10 filter"] = result["Đạt MOM10"] & common_pass
    result["Đạt ROC14 filter"] = result["Đạt ROC14"] & common_pass
    filtered_mom10 = result[result["Đạt MOM10 filter"]].copy().sort_values("MOM10 (FireAnt)", ascending=False).reset_index(drop=True)
    filtered_roc14 = result[result["Đạt ROC14 filter"]].copy().sort_values("ROC14 (%)", ascending=False).reset_index(drop=True)
    filtered = result[common_pass].copy()

    if stats:
        a, b, c = st.columns(3)
        a.metric("Mã đã quét", f"{stats['scanned']:,}", help=f"Tổng danh sách: {stats.get('total', stats['scanned']):,}")
        b.metric("Mã có dữ liệu", f"{stats['success']:,}")
        c.metric("Mã đạt bộ lọc", f"{len(filtered):,}")
        if stats.get("complete") and not stats.get("source"):
            st.success("Đã quét hết danh sách mã hiện tại.")
        else:
            remaining = max(0, stats.get("total", stats["scanned"]) - stats["scanned"])
            st.info(f"Còn {remaining:,} mã chưa quét. Nhấn nút cập nhật để tiếp tục lượt kế tiếp.")
        if stats.get("errors"):
            with st.expander(f"Lỗi dữ liệu trong các lượt quét ({len(stats['errors'])})"):
                st.write(stats["errors"][-50:])

    tab_scan, tab_chart, tab_all = st.tabs(["🔎 Bộ lọc cổ phiếu", "📊 Biểu đồ kỹ thuật", "📋 Toàn bộ thị trường"])
    with tab_scan:
        mom_tab, roc_tab = st.tabs(["MOM10 ≥ ngưỡng", "ROC14 ≥ ngưỡng"])
        with mom_tab:
            st.subheader("Danh sách MOM10 độc lập · FireAnt Length 10, Close")
            st.caption("Không yêu cầu ROC14 đạt ngưỡng. Vẫn áp dụng khối lượng tối thiểu và EMA100 nếu bật.")
            st.metric("Số mã đạt MOM10", f"{len(filtered_mom10):,}")
            st.dataframe(filtered_mom10[["Mã", "Sàn", "Giá đóng cửa", "MOM10 (FireAnt)", "ROC14 (%)", "EMA100", "Khối lượng", "KLGD TB20", "Ngày dữ liệu"]], use_container_width=True, hide_index=True)
            st.download_button("Tải CSV MOM10", filtered_mom10.to_csv(index=False).encode("utf-8-sig"), "co_phieu_MOM10_dat_nguong.csv", "text/csv")
        with roc_tab:
            st.subheader("Danh sách ROC14 độc lập · phần trăm thay đổi 14 phiên")
            st.caption("Không yêu cầu MOM10 đạt ngưỡng. Vẫn áp dụng khối lượng tối thiểu và EMA100 nếu bật.")
            st.metric("Số mã đạt ROC14", f"{len(filtered_roc14):,}")
            st.dataframe(filtered_roc14[["Mã", "Sàn", "Giá đóng cửa", "MOM10 (FireAnt)", "ROC14 (%)", "EMA100", "Khối lượng", "KLGD TB20", "Ngày dữ liệu"]], use_container_width=True, hide_index=True)
            st.download_button("Tải CSV ROC14", filtered_roc14.to_csv(index=False).encode("utf-8-sig"), "co_phieu_ROC14_dat_nguong.csv", "text/csv")

    with tab_chart:
        instruments = st.session_state.get("vnstock_instruments")
        
        chart_days = st.session_state.get("vnstock_days", days)
        # Text entry works better than a long native selectbox on mobile.
        symbols_text = st.text_input(
            "Nhập mã cổ phiếu",
            value="AAM",
            placeholder="Ví dụ: FPT, AAM, AAA",
            help="Có thể nhập nhiều mã, ngăn cách bằng dấu phẩy hoặc dấu chấm phẩy.",
            key="stocklab_chart_symbols",
        )
        chart_symbols = []
        for item in symbols_text.replace(";", ",").split(","):
            symbol = item.strip().upper()
            if symbol and symbol not in chart_symbols:
                chart_symbols.append(symbol)
        selected = chart_symbols[0] if chart_symbols else "AAM"
        st.caption("Biểu đồ hiển thị mã đầu tiên. Các mã đã nhập sẽ được đối chiếu trong bảng bên dưới.")
        try:
            # Keep H1 unavailable until the D1 chart is fully validated in the live app.
            timeframe = "1D"
            st.caption("Đang hoàn thiện và kiểm thử biểu đồ D1. Khung H1 sẽ được mở sau.")
            effective_days = chart_days
            start = (date.today() - timedelta(days=effective_days)).isoformat()
            raw_chart, chart_source = fetch_chart_quotes(selected, start, date.today().isoformat(), interval=timeframe)
            st.caption(f"Nguồn dữ liệu biểu đồ: {chart_source}. Bộ lọc khối lượng dùng bình quân 20 phiên.")
            chart = add_indicators(raw_chart)
            chart = chart.dropna(subset=["date", "open", "high", "low", "close"])
            if chart.empty:
                st.warning("Chưa có dữ liệu OHLC hợp lệ cho mã này.")
            else:
                last = chart.iloc[-1]
                p1, p2, p3, p4, p5 = st.columns(5)
                p1.metric("Giá đóng cửa", f"{last['close']:,.2f}")
                p2.metric("MOM10 (FireAnt)", f"{last['MOM10']:.2f}" if pd.notna(last["MOM10"]) else "—")
                p3.metric("ROC14", f"{last['ROC14']:.2f}%" if pd.notna(last["ROC14"]) else "—")
                p4.metric("RSI14", f"{last['RSI14']:.1f}" if pd.notna(last["RSI14"]) else "—")
                p5.metric("Khối lượng", f"{last['volume']:,.0f}")
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
                # Mobile-friendly interaction: pan/zoom without accidental selection overlays.
                # Unified hover exposes all indicator values for the same trading session.
                fig.update_layout(
                    title=f"{selected} · {timeframe}", height=820, template="plotly_dark",
                    margin=dict(l=10, r=10, t=48, b=12),
                    legend=dict(orientation="h", y=1.02, x=0),
                    hovermode="x", dragmode="pan", uirevision=f"stocklab-{selected}-{timeframe}",
                    hoverlabel=dict(namelength=-1),
                )
                fig.update_xaxes(rangeslider_visible=False, showspikes=True, spikemode="across",
                                 spikesnap="cursor", showline=True)
                fig.update_yaxes(title_text="Giá", row=1, col=1, automargin=True)
                fig.update_yaxes(title_text="KL", row=2, col=1, automargin=True)
                fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1, automargin=True)
                st.plotly_chart(
                    fig, use_container_width=True,
                    config={"responsive": True, "scrollZoom": True, "displayModeBar": True,
                            "doubleClick": "reset", "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
                    key=f"stocklab_chart_{selected}_{timeframe}",
                )

                # Reliable touch-friendly alternative to hover: choose a trading
                # session and read its complete OHLCV + indicator values below.
                chart_dates = chart["date"].dt.strftime("%d/%m/%Y").tolist()
                unique_dates = list(dict.fromkeys(reversed(chart_dates)))
                chosen_date = st.selectbox(
                    "Chọn phiên để xem chi tiết (dùng được trên điện thoại)",
                    unique_dates, index=0, key=f"stocklab_detail_date_{selected}",
                )
                detail = chart.loc[chart["date"].dt.strftime("%d/%m/%Y") == chosen_date].iloc[-1]
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Mở cửa", f"{detail['open']:,.2f}")
                d2.metric("Cao nhất", f"{detail['high']:,.2f}")
                d3.metric("Thấp nhất", f"{detail['low']:,.2f}")
                d4.metric("Đóng cửa", f"{detail['close']:,.2f}")
                e1, e2, e3, e4 = st.columns(4)
                e1.metric("EMA20", f"{detail['EMA20']:,.2f}" if pd.notna(detail["EMA20"]) else "—")
                e2.metric("EMA50", f"{detail['EMA50']:,.2f}" if pd.notna(detail["EMA50"]) else "—")
                e3.metric("EMA100", f"{detail['EMA100']:,.2f}" if pd.notna(detail["EMA100"]) else "—")
                e4.metric("RSI14", f"{detail['RSI14']:.2f}" if pd.notna(detail["RSI14"]) else "—")
                st.caption(f"Khối lượng phiên {chosen_date}: {detail['volume']:,.0f} cổ phiếu")
                macd_fig = go.Figure()
                macd_fig.add_trace(go.Bar(x=chart["date"], y=chart["MACD_HIST"], name="MACD Histogram"))
                macd_fig.add_trace(go.Scatter(x=chart["date"], y=chart["MACD"], name="MACD"))
                macd_fig.add_trace(go.Scatter(x=chart["date"], y=chart["MACD_SIGNAL"], name="Signal"))
                macd_fig.update_layout(height=260, template="plotly_dark", margin=dict(l=10,r=10,t=20,b=10), hovermode="x unified")
                st.plotly_chart(macd_fig, use_container_width=True)
                st.dataframe(chart.tail(30).sort_values("date", ascending=False), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Không tải được biểu đồ {selected}: {exc}")

        st.subheader("Đối chiếu các mã đã nhập")
        if not chart_symbols:
            st.info("Nhập ít nhất một mã cổ phiếu để xem đối chiếu.")
        else:
            comparison = result[result["Mã"].astype(str).str.upper().isin(chart_symbols)].copy()
            if comparison.empty:
                st.warning("Chưa có dữ liệu quét cho các mã vừa nhập. Kiểm tra lại mã hoặc cập nhật dữ liệu thị trường.")
            else:
                order = {symbol: index for index, symbol in enumerate(chart_symbols)}
                comparison["_order"] = comparison["Mã"].map(order)
                comparison = comparison.sort_values("_order").drop(columns=["_order"])
                st.dataframe(
                    comparison[["Mã", "Sàn", "Giá đóng cửa", "ROC14 (%)", "EMA100", "Khối lượng", "KLGD TB20", "Ngày dữ liệu"]],
                    use_container_width=True,
                    hide_index=True,
                )
            missing_symbols = [symbol for symbol in chart_symbols if symbol not in set(comparison["Mã"].astype(str).str.upper())]
            if missing_symbols:
                st.caption("Chưa có dữ liệu đối chiếu cho: " + ", ".join(missing_symbols))

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

    from cophieu68_import import render_cophieu68_import
    render_cophieu68_import()
