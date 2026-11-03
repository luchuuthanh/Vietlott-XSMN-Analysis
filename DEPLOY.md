# Hướng dẫn đưa ứng dụng lên mạng

## Cách nhanh: Streamlit Community Cloud
1. Đăng nhập Streamlit Community Cloud bằng tài khoản GitHub.
2. Chọn tạo app mới và chọn repository luchuuthanh/Vietlott-XSMN-Analysis.
3. Branch: main; Main file path: app.py.
4. Deploy và chờ cài các thư viện trong requirements.txt.
5. Mở đường dẫn ứng dụng được cấp; tải CSV lịch sử vào thanh bên để bắt đầu.

## Lưu ý dữ liệu
Ứng dụng hiện xử lý dữ liệu do người dùng tải lên. Chưa có kết nối nguồn dữ liệu chính thức tự động và chưa có kho lịch sử hoàn chỉnh trong repository. Cần kiểm tra nguồn, ngày cập nhật và tính đầy đủ trước khi dùng kết quả.

## Chạy kiểm thử
    pip install -r requirements.txt
    python -m unittest discover -s tests
