# Vietlott & XSMN Analysis

Hệ thống phân tích thống kê kết quả Vietlott và xổ số miền Nam (XSMN).

## Mục tiêu
- Nhập dữ liệu lịch sử từ CSV.
- Chuẩn hóa và kiểm tra dữ liệu trước khi phân tích.
- Thống kê tần suất, số lâu chưa xuất hiện, chẵn/lẻ, tổng, khoảng cách (delta), cặp và bộ số.
- Phân tích riêng Power 6/55, Mega 6/45 và XSMN.
- Xuất bảng kết quả CSV để kiểm tra và lưu trữ.

> Lưu ý: Thống kê quá khứ không dự đoán chắc chắn kết quả tương lai. Các bộ số gợi ý chỉ mang tính tham khảo.

## Chạy ứng dụng
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Dữ liệu
Đưa CSV vào thư mục `data/` hoặc tải trực tiếp trong giao diện. Xem `data/template.csv` để biết định dạng mẫu.

## Nguyên tắc dữ liệu
Không tự tạo hoặc suy diễn kỳ quay còn thiếu. Luôn ghi rõ nguồn, ngày cập nhật và số kỳ đã nạp.
