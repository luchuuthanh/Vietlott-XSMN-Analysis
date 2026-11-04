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


## Triển khai ứng dụng chứng khoán riêng (StockLab)

Có thể triển khai StockLab thành một ứng dụng Streamlit riêng, dùng chung repository nhưng không thay thế ứng dụng Vietlott/XSMN:

1. Mở https://share.streamlit.io/ và đăng nhập bằng GitHub có quyền truy cập repository.
2. Chọn **Create app** → **Yup, I have an app**.
3. Repository: `luchuuthanh/Vietlott-XSMN-Analysis`.
4. Branch: `main`.
5. Main file path: `stock_app.py`.
6. Custom subdomain: `stocklab-vn` (nếu còn khả dụng).
7. Chọn **Deploy**.

Streamlit sẽ tạo URL riêng theo subdomain được chọn. Nếu subdomain đã có người dùng, chọn tên khác. Ứng dụng chứng khoán dùng `stock_app.py`; ứng dụng cũ vẫn dùng `app.py`.

### Nguồn dữ liệu StockLab

StockLab dùng Vnstock 5.0.1. Cấu hình cài đặt nằm trong `requirements.txt`; bộ lấy dữ liệu thử VCI trước và KBS dự phòng. Khả năng truy cập và độ đầy đủ của dữ liệu phải được xác minh sau khi app khởi động trên Streamlit Cloud.
