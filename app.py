import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="Vietlott & XSMN Analysis", page_icon="📊", layout="wide")
st.title("📊 Hệ thống phân tích Vietlott & XSMN")
st.caption("Phân tích thống kê dữ liệu lịch sử — không đảm bảo dự đoán kết quả.")

REQUIRED = ["date", "game", "draw_id", "n1", "n2", "n3", "n4", "n5", "n6"]

def load_data(uploaded):
    if uploaded is not None:
        return pd.read_csv(uploaded)
    path = Path("data/history.csv")
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=REQUIRED)

uploaded = st.sidebar.file_uploader("Tải dữ liệu CSV", type=["csv"])
df = load_data(uploaded)
if df.empty:
    st.info("Chưa có dữ liệu lịch sử. Hãy tải tệp CSV theo mẫu trong thư mục data/template.csv.")
    st.stop()

missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error("Thiếu cột bắt buộc: " + ", ".join(missing))
    st.stop()

df["date"] = pd.to_datetime(df["date"], errors="coerce")
for c in REQUIRED[3:]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["date", "game", "draw_id"] + REQUIRED[3:]).copy()
game = st.sidebar.selectbox("Loại xổ số", sorted(df["game"].astype(str).unique()))
data = df[df["game"].astype(str) == game].sort_values("date").reset_index(drop=True)
if data.empty:
    st.warning("Không có dữ liệu cho loại xổ số đã chọn.")
    st.stop()

number_cols = REQUIRED[3:]
numbers = data[number_cols].astype(int)
flat = numbers.to_numpy().ravel()
max_n = int(flat.max()) if len(flat) else 55
freq = pd.Series(flat).value_counts().reindex(range(1, max_n + 1), fill_value=0)
last_seen = {}
for n in range(1, max_n + 1):
    hits = np.where((numbers == n).any(axis=1))[0]
    last_seen[n] = len(data) - 1 - hits[-1] if len(hits) else len(data)

c1, c2, c3 = st.columns(3)
c1.metric("Số kỳ dữ liệu", f"{len(data):,}")
c2.metric("Ngày mới nhất", data["date"].max().strftime("%d/%m/%Y"))
c3.metric("Số lượng số khác nhau", f"{len(set(flat)):,}")

st.subheader("Tần suất xuất hiện")
freq_df = pd.DataFrame({"Số": freq.index, "Lần xuất hiện": freq.values})
st.bar_chart(freq_df.set_index("Số"))
st.dataframe(freq_df.sort_values(["Lần xuất hiện", "Số"], ascending=[False, True]), use_container_width=True)

st.subheader("Số lâu chưa xuất hiện")
gap_df = pd.DataFrame({"Số": list(last_seen), "Số kỳ vắng": list(last_seen.values())})
st.dataframe(gap_df.sort_values(["Số kỳ vắng", "Số"], ascending=[False, True]), use_container_width=True)

st.subheader("Phân tích từng kỳ")
analysis = data.copy()
analysis["Tổng"] = numbers.sum(axis=1)
analysis["Chẵn"] = (numbers % 2 == 0).sum(axis=1)
analysis["Lẻ"] = 6 - analysis["Chẵn"]
analysis["Delta"] = numbers.max(axis=1) - numbers.min(axis=1)
st.dataframe(analysis.sort_values("date", ascending=False), use_container_width=True)

st.download_button("Tải bảng tần suất CSV", freq_df.to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"{game.lower()}_frequency.csv", mime="text/csv")
