"""Dashboard xem lại bằng chứng quay số trực tiếp Mega 6/45 và Power 6/55."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "data" / "live_evidence"
INDEX = EVIDENCE_ROOT / "sessions.jsonl"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

st.set_page_config(page_title="Vietlott Live Evidence", page_icon="📹", layout="wide")
st.title("📹 VIETLOTT LIVE EVIDENCE MONITOR")
st.caption("Theo dõi phiên Mega 6/45 và Power 6/55; lưu khung hình, OCR, thời điểm và mã SHA-256 để đối chiếu.")

c1, c2, c3 = st.columns(3)
c1.metric("Giờ Việt Nam", datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S"))
c2.metric("Mega 6/45", "18:00 · Thứ 4, 6, Chủ nhật")
c3.metric("Power 6/55", "18:00 · Thứ 3, 5, 7")

st.info(
    "Bộ ghi hình tự chạy bằng GitHub Actions lúc 17:50 giờ Việt Nam vào ngày có lịch quay. "
    "Nó dò luồng công khai, lấy mẫu khung hình 5 giây/lần trong phiên 18:00–18:30, "
    "chạy OCR và lưu ảnh chứng cứ. Nếu nguồn không mở hoặc không xác minh được đang phát trực tiếp, "
    "phiên được ghi là thất bại — phần mềm không tự tạo mã vali."
)

st.markdown("### Nguồn phát chính thức")
st.markdown(
    "- [Trang Vietlott](https://vietlott.vn/)\n"
    "- [Danh sách video quay số Mega 6/45](https://vietlott.vn/vi/trung-thuong/danh-sach-video-quay-so-mo-thuong-645)\n"
    "- [Bài giải thích về phát trực tiếp 18:00–18:30 trên website, YouTube và SCTV2](https://tuoitre.vn/nld/vi-sao-vietlott-khong-livestream-toan-bo-cac-phien-quay-so-mo-thuong-tren-mang-xa-hoi-196250714145608742.htm)"
)

records = []
if INDEX.exists():
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except Exception:
            continue

if not records:
    st.warning("Chưa có phiên ghi nhận nào. Phiên đầu tiên sẽ được tạo ở kỳ quay trực tiếp kế tiếp sau khi workflow chạy và tìm được nguồn.")
    st.stop()

records = sorted(records, key=lambda x: x.get("capture_started_vn", ""), reverse=True)
df = pd.DataFrame([{
    "Ngày": r.get("draw_date"),
    "Trò chơi": r.get("game_label", r.get("game")),
    "Kỳ dự kiến": r.get("expected_draw_id") or "Chưa đối chiếu",
    "Trạng thái": r.get("status"),
    "Khung hình": r.get("sampled_frame_count", 0),
    "Ảnh lưu": r.get("saved_frame_count", 0),
    "OCR thấy mã VA": r.get("va_code_candidate_count", 0),
    "Nguồn": (r.get("source") or {}).get("title") or (r.get("source") or {}).get("page_url") or "Không tìm thấy",
} for r in records])
st.markdown("### Nhật ký các phiên")
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("### Xem bằng chứng từng phiên")
options = [
    f"{r.get('draw_date')} · {r.get('game_label', r.get('game'))} · {r.get('status')}"
    for r in records
]
choice = st.selectbox("Chọn phiên", options)
selected = records[options.index(choice)]
a, b, c = st.columns(3)
a.metric("Trạng thái", selected.get("status", "—"))
b.metric("Số khung hình", selected.get("sampled_frame_count", 0))
c.metric("Khung hình OCR gợi ý mã VA", selected.get("va_code_candidate_count", 0))

st.write("**Nguồn:**", (selected.get("source") or {}).get("page_url", "Không có"))
st.write("**Tiêu đề luồng:**", (selected.get("source") or {}).get("title", "Không có"))
st.write("**Bắt đầu ghi:**", selected.get("capture_started_vn", "—"))
st.write("**Kết thúc ghi:**", selected.get("capture_finished_vn", "—"))
if selected.get("error"):
    st.error(selected["error"])
if selected.get("actions_run_url"):
    st.markdown(f"[Mở nhật ký GitHub Actions của phiên này]({selected['actions_run_url']})")

sheet = selected.get("contact_sheet")
if sheet:
    sheet_path = ROOT / sheet
    if sheet_path.exists():
        st.image(str(sheet_path), caption="Bảng liên hệ các khung hình được lưu — cần xem từng ảnh để xác nhận mã vali.")
    else:
        st.warning("Không tìm thấy ảnh contact sheet trong bản triển khai này.")

files = selected.get("evidence_files") or []
if files:
    st.markdown("**Ảnh chứng cứ riêng**")
    for item in files:
        path = ROOT / item["file"]
        if path.exists():
            with st.expander(f"{item.get('elapsed_seconds')} giây · SHA-256 {item.get('sha256','')[:16]}…"):
                st.image(str(path), use_container_width=True)
                st.code(item.get("sha256", ""), language="text")
else:
    st.caption("Phiên này chưa có ảnh mẫu được lưu.")

frames_log = selected.get("frames_log")
if frames_log:
    log_path = ROOT / frames_log
    if log_path.exists():
        st.download_button(
            "Tải nhật ký OCR từng khung hình",
            log_path.read_bytes(),
            file_name=f"{selected.get('session_id','session')}_frames_ocr.jsonl",
            mime="application/x-ndjson",
        )

st.caption(
    "Lưu ý chứng cứ: ảnh trích từ luồng công khai có thể hỗ trợ nhận diện và đối chiếu. "
    "SHA-256 giúp phát hiện ảnh bị thay đổi sau khi lưu; nó không chứng minh độc lập danh tính người phát, "
    "tính toàn vẹn của luồng gốc hay thay thế biên bản của Vietlott. Mã vali chỉ được kết luận khi nhãn VA "
    "hoặc hồ sơ tương ứng nhìn rõ và được người kiểm tra xác nhận."
)
