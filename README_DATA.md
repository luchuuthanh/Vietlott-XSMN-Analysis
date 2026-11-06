# Bộ dữ liệu XSMN 5 năm (bản canonical)

## Phạm vi
- Khoảng dữ liệu: 2021-11-05 đến 2026-11-05.
- Phạm vi địa lý: 21 đài/tỉnh thành miền Nam.
- Cấu trúc kết quả: 9 giải mỗi đài.
- Số dòng dữ liệu được khai báo: 103.356.
- Trạng thái metadata tại thời điểm đóng gói: PASS.

## Thành phần
- `data/xsmn_5y_canonical.csv`: dữ liệu chuẩn để phân tích và backtest.
- `data/xsmn_5y_canonical.json`: metadata, trạng thái và nguồn dữ liệu.
- `SHA256SUMS.txt`: mã SHA-256 để kiểm tra tính toàn vẹn của hai tệp dữ liệu.

## Quy tắc sử dụng
1. Đọc metadata và chỉ sử dụng khi `status = PASS`.
2. Không chỉnh sửa trực tiếp hai tệp canonical trong quá trình phân tích.
3. Mọi bước chuẩn hóa hoặc thử nghiệm phải tạo bản sao riêng.
4. Khi cập nhật dữ liệu hằng ngày, chỉ thay thế bản canonical sau khi toàn bộ kiểm tra đạt PASS.
5. Các kết quả backtest phải ghi rõ khoảng thời gian, số kỳ, tỉnh và phương pháp; không diễn giải thống kê lịch sử thành cam kết dự đoán.

## Kiểm tra
Chạy `python scripts/package_xsmn_data.py`. Script sẽ kiểm tra số dòng CSV so với metadata, tạo SHA-256 và đóng gói ZIP.
