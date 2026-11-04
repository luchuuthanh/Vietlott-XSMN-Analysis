# Bộ ứng dụng phân tích xổ số Việt Nam

Repository chứa hai ứng dụng Streamlit độc lập: Vietlott và XSMN. Mỗi ứng dụng có entrypoint, giao diện và URL triển khai riêng.

## Tính năng hiện có
- Đọc CSV, kiểm tra cột và chuẩn hóa dữ liệu.
- Vietlott: Power 6/55, Mega 6/45 hoặc game có cấu trúc 6 số.
- Tần suất, tỷ lệ, gan theo số kỳ, cặp số, tổng, chẵn/lẻ, Delta.
- XSMN: thống kê lô tô 2 số theo tỉnh, theo giải, tần suất và gan theo kỳ/ngày có dữ liệu.
- Xếp hạng ứng viên theo điểm thống kê và tạo bộ số tham khảo.
- Xuất CSV đã chuẩn hóa và bảng kết quả.

## Chạy trên máy
    pip install -r requirements.txt
    streamlit run app.py  # Vietlott

    streamlit run xsmn_app.py  # XSMN

## Tách ứng dụng và triển khai riêng

- **Vietlott:** entrypoint `app.py`. Ứng dụng cũ đang dùng `app.py` trên Streamlit Cloud sẽ chuyển sang giao diện Vietlott riêng sau khi Cloud tự redeploy.
- **XSMN:** entrypoint `xsmn_app.py`. Tạo một ứng dụng Streamlit Cloud mới từ cùng repository, branch `main`, chọn Main file path là `xsmn_app.py` để có URL riêng.
- Hai ứng dụng dùng chung module xử lý dữ liệu (`analytics.py`, `data_loader.py`) nhưng không còn chung màn hình hoặc menu chọn hệ thống.
- XSMN hiện nhận CSV lịch sử do người dùng tải lên; nguồn kết quả tự động chưa được kết nối.

## Định dạng dữ liệu

### Vietlott — data/vietlott_template.csv
Cột bắt buộc: date,game,draw_id,n1,n2,n3,n4,n5,n6. Cột special tùy chọn. Mỗi dòng là một kỳ quay; 6 số chính nằm ở n1–n6. Tên game khuyến nghị POWER655 hoặc MEGA645.

### XSMN — data/xsmn_template.csv
Cột bắt buộc: date,province,prize,number. Mỗi dòng là một kết quả giải của một tỉnh trong ngày. Ứng dụng lấy hai chữ số cuối để thống kê lô tô.

## Quan trọng
- Repository hiện chỉ có tệp mẫu, không có bộ dữ liệu lịch sử đầy đủ.
- Người dùng cần tải CSV lịch sử thực tế để phân tích. Không tự tạo kết quả còn thiếu.
- Điểm xếp hạng và bộ số tạo ra chỉ là thống kê tham khảo; xổ số có tính ngẫu nhiên và không thể bảo đảm trúng.

## StockLab Việt Nam

StockLab là màn hình riêng cho phân tích cổ phiếu Việt Nam, dùng chung repository nhưng không thay đổi luồng Vietlott/XSMN.

### Chạy StockLab
```bash
pip install -r requirements.txt
streamlit run stock_app.py
```

Có thể chạy từ `app.py` bằng cách chọn **Chứng khoán Việt Nam** ở thanh bên.

### Nguồn dữ liệu và hạn mức
- Dữ liệu qua Vnstock, tự thử VCI rồi KBS.
- Chạy không có khóa ở cấp Khách bị giới hạn lượt gọi; ứng dụng quét theo từng nhóm mã để giảm nguy cơ vượt hạn mức.
- Để tăng hạn mức, tạo khóa API Vnstock cấp Cộng đồng miễn phí và cấu hình biến môi trường `VNSTOCK_API_KEY`. Không ghi khóa vào mã nguồn hoặc commit Git.
- Trên Streamlit Community Cloud: mở ứng dụng → Settings → Secrets và thêm:
  ```toml
  VNSTOCK_API_KEY = "khoa_api_cua_ban"
  ```
- Bộ lọc mặc định: MOM14 từ 4%, giá đóng cửa trên EMA100, khối lượng tối thiểu 50.000 cổ phiếu. Có thể thay đổi các ngưỡng trong giao diện.
- Biểu đồ hỗ trợ 1D và 1H. Dữ liệu H1 có giới hạn lịch sử theo cấp tài khoản và nguồn dữ liệu.

### Triển khai Streamlit Cloud
Tạo ứng dụng mới từ repository này, chọn branch `main`, đặt **Main file path** là `stock_app.py`. Không dùng `app.py` làm entrypoint nếu muốn mở thẳng StockLab.
