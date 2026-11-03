import streamlit as st
import pandas as pd
from analytics import frequency_table, gap_table, pair_table, draw_metrics, score_candidates
from data_loader import load_vietlott, load_xsmn
from generator import make_sets
from data_sources import fetch_vietlott

st.set_page_config(page_title="Vietlott & XSMN Lab", page_icon="📊", layout="wide")
st.title("📊 VIETLOTT & XSMN ANALYSIS LAB")
st.caption("Phân tích Vietlott, XSMN và cổ phiếu Việt Nam.")

with st.sidebar:
    st.header("Nguồn dữ liệu")
    mode = st.radio("Chọn hệ thống", ["Vietlott", "XSMN"])
    upload = st.file_uploader("Tải CSV lịch sử", type=["csv"])
    st.divider()
    st.caption("Mẫu CSV nằm trong thư mục data/ của repository.")

if mode == "Chứng khoán Việt Nam":
    from stock_dashboard import render_stock_dashboard
    render_stock_dashboard()
    st.stop()

if upload is None and mode == "XSMN":
    st.info("XSMN: hiện cần tải CSV kết quả theo mẫu data/xsmn_template.csv. Kết nối nguồn tự động cho XSMN đang được hoàn thiện.")
    st.stop()

try:
    if mode == "Vietlott":
        raw = load_vietlott(upload) if upload is not None else pd.concat([fetch_vietlott("POWER655"), fetch_vietlott("MEGA645")], ignore_index=True)
        games = sorted(raw["game"].unique().tolist())
        selected = st.sidebar.selectbox("Loại vé", games)
        data = raw[raw["game"] == selected].copy()
        cols = ["n1","n2","n3","n4","n5","n6"]
        universe = 55 if "655" in selected else 45 if "645" in selected else max(45, int(data[cols].max().max()))
        recent_n = st.slider("Số kỳ gần nhất đưa vào thống kê", 10, max(10, len(data)), min(200, max(10,len(data))))
        subset = data.tail(recent_n)
        draws = subset[cols].astype(int).values.tolist()
        flat = [n for d in draws for n in d]
        freq = frequency_table(flat, universe)
        gaps = gap_table(draws, universe)
        st.subheader(f"Phân tích {selected}")
        st.caption(f"Phạm vi dữ liệu: {data['date'].min():%d/%m/%Y} – {data['date'].max():%d/%m/%Y}")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Số kỳ đã nạp",f"{len(data):,}")
        c2.metric("Kỳ đang phân tích",f"{len(subset):,}")
        c3.metric("Số lớn nhất",universe)
        c4.metric("Kỳ mới nhất",str(data.iloc[-1]["draw_id"]))
        t1,t2,t3,t4,t5=st.tabs(["Tần suất & gan","Cặp số","Cấu trúc kỳ quay","Bộ số tham khảo","Dữ liệu"])
        with t1:
            a,b=st.columns(2)
            with a:
                st.markdown("**Tần suất cao nhất**")
                st.dataframe(freq.head(20),use_container_width=True,hide_index=True)
            with b:
                st.markdown("**Số lâu chưa xuất hiện**")
                st.dataframe(gaps.head(20),use_container_width=True,hide_index=True)
            st.bar_chart(freq.set_index("Số")["Số lần"])
            if "special" in subset.columns:
                special = pd.to_numeric(subset["special"], errors="coerce").dropna().astype(int)
                if not special.empty:
                    st.markdown("**Thống kê số đặc biệt (nếu có)**")
                    special_freq = special.value_counts().rename_axis("Số đặc biệt").reset_index(name="Số lần")
                    st.dataframe(special_freq, use_container_width=True, hide_index=True)
        with t2:
            st.dataframe(pair_table(draws,30),use_container_width=True,hide_index=True)
        with t3:
            metrics=draw_metrics(draws)
            st.dataframe(metrics.tail(100).iloc[::-1],use_container_width=True,hide_index=True)
            st.bar_chart(metrics.set_index("Kỳ")[["Tổng","Delta"]])
        with t4:
            ranked=score_candidates(freq,gaps,universe,universe)
            st.caption("Điểm là công thức xếp hạng thống kê nội bộ, không phải xác suất trúng.")
            st.dataframe(ranked.head(20),use_container_width=True,hide_index=True)
            n=st.selectbox("Số lượng số mỗi bộ",[6,7,8],index=0)
            k=st.slider("Số bộ muốn tạo",1,10,5)
            sets=make_sets(ranked,count=n,sets=k)
            st.dataframe(pd.DataFrame(sets),use_container_width=True,hide_index=True)
            if sets:
                st.download_button("Tải bộ số CSV",pd.DataFrame(sets).to_csv(index=False).encode("utf-8-sig"),"bo_so_tham_khao.csv","text/csv")
        with t5:
            st.dataframe(data.sort_values("date",ascending=False),use_container_width=True,hide_index=True)
            st.download_button("Tải dữ liệu đã chuẩn hóa",data.to_csv(index=False).encode("utf-8-sig"),"vietlott_clean.csv","text/csv")
    else:
        raw=load_xsmn(upload)
        provinces=sorted(raw["province"].unique().tolist())
        province=st.sidebar.selectbox("Tỉnh",provinces)
        data=raw[raw["province"]==province].copy()
        dates=sorted(data["date"].dropna().unique())
        recent_n=st.slider("Số ngày/kỳ gần nhất",10,max(10,len(dates)),min(90,max(10,len(dates))))
        chosen_dates=set(dates[-recent_n:])
        subset=data[data["date"].isin(chosen_dates)].copy()
        draws=subset.groupby("date")["last2"].apply(list).tolist()
        flat=subset["last2"].astype(int).tolist()
        freq=frequency_table(flat,99,start=0)
        gaps=gap_table(draws,99,start=0)
        c1,c2,c3=st.columns(3)
        c1.metric("Tỉnh đã chọn",province)
        c2.metric("Ngày có dữ liệu",len(dates))
        c3.metric("Số kết quả",len(subset))
        t1,t2,t3=st.tabs(["Lô tô 2 số","Theo giải","Dữ liệu"])
        with t1:
            a,b=st.columns(2)
            with a: st.dataframe(freq.head(20),use_container_width=True,hide_index=True)
            with b: st.dataframe(gaps.head(20),use_container_width=True,hide_index=True)
            st.bar_chart(freq.set_index("Số")["Số lần"])
            st.caption("Gan tính theo số ngày/kỳ có dữ liệu của tỉnh đã chọn, không phải số ngày lịch.")
        with t2:
            by_prize=subset.groupby("prize")["number"].count().sort_values(ascending=False).rename("Số kết quả")
            st.dataframe(by_prize,use_container_width=True)
        with t3:
            st.dataframe(data.sort_values(["date","prize"],ascending=[False,True]),use_container_width=True,hide_index=True)
            st.download_button("Tải dữ liệu tỉnh CSV",data.to_csv(index=False).encode("utf-8-sig"),"xsmn_clean.csv","text/csv")
except Exception as exc:
    st.error(f"Không đọc được dữ liệu: {exc}")
    st.info("Kiểm tra tên cột và định dạng theo hai tệp mẫu CSV trong thư mục data/.")
