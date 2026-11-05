"""Ứng dụng phân tích Vietlott độc lập."""
import streamlit as st
import pandas as pd
from analytics import frequency_table, gap_table, pair_table, draw_metrics, score_candidates
from data_loader import load_vietlott
from generator import make_sets
from data_sources import fetch_vietlott
from ticket_checker import expand_ticket, check_tickets, rolling_backtest

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
    t1, t2, t3, t4, t5, t6 = st.tabs(["Tần suất & gan", "Cặp số", "Cấu trúc kỳ quay", "Bộ số tham khảo", "Dữ liệu", "Dò vé & kiểm định"])
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
    with t6:
        if selected in {"POWER655", "MEGA645"}:
            st.markdown("### Bộ dò vé dùng chung")
            st.caption("Chọn Power 6/55 hoặc Mega 6/45 ở danh sách Loại vé phía trên. Bộ dò tự áp dụng đúng giới hạn số và luật giải của trò chơi đang chọn.")
            ticket_text = st.text_area(f"Các bộ vé {selected}", placeholder=("08 23 30 34 38 47\n01 12 20 30 40 55" if selected == "POWER655" else "03 12 20 30 38 45\n01 09 18 27 36 44"), height=110, key=f"shared_ticket_input_{selected}")
            draw_options = data.sort_values("date").reset_index(drop=True)
            draw_labels = [
                f"#{row.draw_id} · {row.date:%d/%m/%Y}"
                for row in draw_options.itertuples()
            ]
            selected_label = st.selectbox("Chọn kỳ quay để dò", draw_labels, index=len(draw_labels)-1)
            draw_index = draw_labels.index(selected_label)
            selected_draw = draw_options.iloc[draw_index]
            main_result = [int(selected_draw[f"n{i}"]) for i in range(1, 7)]
            special_value = pd.to_numeric(pd.Series([selected_draw.get("special")]), errors="coerce").iloc[0]
            special_result = None if pd.isna(special_value) else int(special_value)
            st.caption(
                f"Kết quả kỳ #{selected_draw['draw_id']}: "
                + " – ".join(f"{n:02d}" for n in main_result)
                + (f" | Đặc biệt: {special_result:02d}" if special_result is not None else " | Chưa có số đặc biệt")
            )
            if st.button("Dò các vé đã nhập", key="run_power655_ticket_check"):
                parsed = []
                errors = []
                for line_no, line in enumerate(ticket_text.splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        parsed.extend(expand_ticket(line.replace(",", " ").replace("-", " ").replace(";", " ").split(), universe=universe))
                    except ValueError as err:
                        errors.append(f"Dòng {line_no}: {err}")
                if errors:
                    for err in errors:
                        st.error(err)
                if parsed:
                    checked = check_tickets(parsed, main_result, special_result, game=selected)
                    st.dataframe(pd.DataFrame(checked), use_container_width=True, hide_index=True)
                    winners = sum(row["Mã giải"] != "NONE" for row in checked)
                    st.metric("Số vé có giải", f"{winners}/{len(checked)}")
            st.divider()
            st.markdown(f"### Kiểm định thuật toán {selected} theo kiểu cuốn chiếu")
            st.caption("Mỗi kỳ chỉ dùng dữ liệu các kỳ trước để tạo bộ số; sau đó mới đối chiếu với kỳ kế tiếp. Cách này tránh lấy dữ liệu tương lai để dự đoán quá khứ.")
            history_limit = st.slider("Số kỳ lịch sử dùng để tạo ứng viên", 100, min(1000, len(data)-1), min(200, len(data)-1), key="ticket_backtest_window")
            tickets_per_draw = st.slider("Số bộ tạo cho mỗi kỳ kiểm định", 1, 10, 5, key="ticket_backtest_count")
            if st.button("Chạy kiểm định thuật toán hiện tại", key="run_power655_backtest"):
                chronological = data.sort_values("date").reset_index(drop=True)
                draw_records = []
                for row in chronological.itertuples():
                    special_raw = getattr(row, "special", None)
                    special_num = None if pd.isna(special_raw) else int(special_raw)
                    draw_records.append({
                        "draw_id": str(row.draw_id),
                        "date": row.date.strftime("%Y-%m-%d"),
                        "main_numbers": [int(getattr(row, f"n{i}")) for i in range(1, 7)],
                        "special": special_num,
                    })
                def build_from_history(history):
                    history_draws = [item["main_numbers"] for item in history[-history_limit:]]
                    history_flat = [number for draw in history_draws for number in draw]
                    history_freq = frequency_table(history_flat, universe)
                    history_gaps = gap_table(history_draws, universe)
                    ranked_history = score_candidates(history_freq, history_gaps, universe, universe)
                    generated = make_sets(ranked_history, count=6, sets=tickets_per_draw)
                    return [
                        [int(value) for value in item["Bộ số"].split(" - ")]
                        for item in generated
                    ]
                with st.spinner("Đang chạy kiểm định ngoài mẫu trên lịch sử Power 6/55..."):
                    summary, detail = rolling_backtest(
                        draw_records, build_from_history,
                        min_history=history_limit, history_window=history_limit, game=selected
                    )
                st.caption(f"Đã kiểm định {summary['tested_draws']:,} kỳ, tổng {summary['total_tickets']:,} bộ vé.")
                summary_df = pd.DataFrame([
                    {"Hạng giải": ("Jackpot 1" if selected == "POWER655" else "Jackpot"), "Số lượt": summary["jackpot1"] + summary.get("jackpot", 0)},
                    {"Hạng giải": "Jackpot 2", "Số lượt": summary["jackpot2"]},
                    {"Hạng giải": "Giải nhất", "Số lượt": summary["first"]},
                    {"Hạng giải": "Giải nhì", "Số lượt": summary["second"]},
                    {"Hạng giải": "Giải ba", "Số lượt": summary["third"]},
                    {"Hạng giải": "Không trúng", "Số lượt": summary["no_prize"]},
                ])
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                st.dataframe(pd.DataFrame(detail).tail(100), use_container_width=True, hide_index=True)
                st.download_button(
                    "Tải kết quả kiểm định CSV",
                    pd.DataFrame(detail).to_csv(index=False).encode("utf-8-sig"),
                    "power655_rolling_backtest.csv", "text/csv"
                )
                st.warning("Kết quả kiểm định là phép đo lịch sử, không chứng minh thuật toán dự đoán được kết quả tương lai hoặc làm tăng xác suất trúng.")
except Exception as exc:
    st.error(f"Không đọc được dữ liệu Vietlott: {exc}")
    st.info("Kiểm tra kết nối nguồn dữ liệu hoặc định dạng theo data/vietlott_template.csv.")
