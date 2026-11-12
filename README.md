# Bộ ứng dụng phân tích xổ số Việt Nam

Repository chứa hai ứng dụng Streamlit độc lập: Vietlott và XSMN. Mỗi ứng dụng có entrypoint, giao diện và URL triển khai riêng.

## Tính năng hiện có
- Đọc CSV, kiểm tra cột và chuẩn hóa dữ liệu.
- Vietlott: giao diện thống kê hiện hỗ trợ Power 6/55 và Mega 6/45.
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
- XSMN có bộ nạp kho SQLite lịch sử theo quý, mục tiêu 5 năm từ 04/11/2021; vẫn hỗ trợ CSV dự phòng. Ứng dụng hiển thị trạng thái từng quý, số kết quả và tỉnh tải được. Cần kiểm tra độ phủ và đối chiếu nguồn trước khi xác nhận đủ 5 năm.

## Định dạng dữ liệu

### Vietlott — data/vietlott_template.csv
Cột bắt buộc: date,game,draw_id,n1,n2,n3,n4,n5,n6. Cột special tùy chọn. Mỗi dòng là một kỳ quay; 6 số chính nằm ở n1–n6. Riêng POWER655, `special` là số được quay riêng sau 6 số chính từ 49 bóng còn lại, không phải số chính thứ bảy; chỉ dùng xét Jackpot 2 và thống kê riêng. POWER655 quay thứ Ba, thứ Năm, thứ Bảy lúc 18:00. Tên game khuyến nghị POWER655 hoặc MEGA645.

### XSMN — data/xsmn_template.csv
Cột bắt buộc: date,province,prize,number. Mỗi dòng là một kết quả giải của một tỉnh trong ngày. Ứng dụng lấy hai chữ số cuối để thống kê lô tô.

## Quan trọng
- Kho lịch sử Vietlott 6 game đã được đồng bộ tại `data/vietlott/`; trạng thái chất lượng và phạm vi dữ liệu nằm trong `data/vietlott/manifest.json`.
- Kho XSMN vẫn có quy trình nạp dữ liệu riêng; không suy diễn rằng dữ liệu XSMN đã hoàn chỉnh chỉ từ các tệp mẫu.
- Không tự tạo kết quả còn thiếu. Các bản ghi có cảnh báo phải được đối chiếu nguồn trước khi dùng.
- Điểm xếp hạng và bộ số tạo ra chỉ là thống kê tham khảo; xổ số có tính ngẫu nhiên và không thể bảo đảm trúng.


## XSMN: kiểm định kho lịch sử 5 năm

- Phạm vi audit mặc định: 05/11/2021 đến ngày chạy.
- Script: `python scripts/audit_xsmn_archive.py`.
- Workflow: `.github/workflows/xsmn-archive-audit.yml`, có chạy thủ công và lịch hằng tuần.
- Thử tải V1 trước, tự chuyển sang V2 nếu V1 thiếu hoặc không hợp lệ; kiểm tra SQLite `quick_check` và `foreign_key_check`.
- Artifact `xsmn-five-year-audit` gồm tổng quan, trạng thái từng quý, độ phủ tỉnh/ngày/giải, bản ghi trùng, số không hợp lệ và độ phủ 00–99 theo từng tỉnh.
- Báo cáo độ phủ là chỉ báo kiểm tra, chưa tự khẳng định kỳ quay/giải thiếu nếu chưa đối chiếu lịch quay và nguồn chính thức.

## Vietlott: kho dữ liệu đầy đủ và tự cập nhật hằng ngày

- Workflow `.github/workflows/vietlott-daily-sync.yml` chạy tự động mỗi ngày lúc **23:45 giờ Việt Nam** (16:45 UTC), đồng thời có thể chạy thủ công trong tab **Actions**.
- Script `scripts/sync_vietlott.py` đồng bộ 6 sản phẩm được chọn: Power 6/55, Mega 6/45, Lotto 5/35 (nguồn mirror dùng tên tệp power535), Max 3D, Max 3D Pro và Bingo18. Keno đã được loại khỏi phạm vi đồng bộ theo yêu cầu.
- Bản NDJSON được lưu tại `data/vietlott/`; `manifest.json` ghi số bản ghi, khoảng ngày, mã kỳ, SHA-256 và cảnh báo khoảng trống mã kỳ.
- Trước khi thay thế dữ liệu cũ, script tải và kiểm tra toàn bộ 6 tệp. Nếu một tệp lỗi hoặc sai cấu trúc, snapshot hiện tại không bị ghi đè.
- Nguồn đồng bộ là kho dữ liệu mở [vietvudanh/vietlott-data](https://github.com/vietvudanh/vietlott-data), công bố thu thập từ trang Vietlott. Đây là nguồn trung gian, không phải API chính thức; các kỳ quan trọng hoặc bất thường cần đối chiếu kết quả công bố trên vietlott.vn.
- Workflow không tự tạo kỳ còn thiếu. Mã kỳ bị khuyết, mã kỳ sai thứ tự, ngày quay lệch lịch thường lệ và số đặc biệt bị thiếu được ghi thành cảnh báo trong manifest và GitHub Actions Summary để rà soát.
- Snapshot đồng bộ lần đầu (05/11/2026): Power 6/55 1.419 kỳ; Mega 6/45 1.387 kỳ; Lotto 5/35 988 bản ghi; Max 3D 1.154 kỳ; Max 3D Pro 800 kỳ; Bingo18 98.799 kỳ.
- Lần rà soát đầu đã phát hiện bản ghi Power 6/55 ID 00944 ở ngày 23/09/2022 (lệch lịch quay thứ Ba/Thứ Năm/Thứ Bảy), chỉ có 6 số và làm thứ tự ID nhảy 00779 → 00944 → 00780. Max 3D có hai dòng năm 2025 bị đặt sau dữ liệu năm 2026; Bingo18 có khoảng trống và đảo thứ tự ID. Những điểm này đang được giữ nguyên và gắn cảnh báo, chưa tự ý sửa số liệu.
- Có thể chạy kiểm tra cục bộ: `python -m unittest discover -s tests` và đồng bộ: `python scripts/sync_vietlott.py`.

Lưu ý: kho dữ liệu có 6 sản phẩm được chọn không đồng nghĩa giao diện phân tích hiện tại đã hỗ trợ đầy đủ từng sản phẩm. Giao diện `app.py` hiện chỉ phân tích Power 6/55 và Mega 6/45; Bingo18, Lotto 5/35, Max 3D và Max 3D Pro cần bộ phân tích riêng theo đúng luật từng trò chơi.

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

## Power 6/55: bộ dò vé và kiểm định thuật toán

- Tab **Dò vé & kiểm định** là bộ dò dùng chung cho Power 6/55 và Mega 6/45: chọn loại trò chơi ở bộ lọc phía trên, nhập nhiều dòng vé, chọn kỳ quay và hệ thống tự áp dụng giới hạn số cùng luật giải tương ứng.
- Hỗ trợ vé 6 số; vé hệ thống 5 số (Power 6/55 tạo 50 tổ hợp, Mega 6/45 tạo 40 tổ hợp), Bao 7–15 và Bao 18 (mở rộng toàn bộ tổ hợp 6 số).
- Với Power 6/55, số đặc biệt được kiểm tra độc lập, chỉ dùng xét Jackpot 2; nếu thiếu dữ liệu, hệ thống đánh dấu chưa thể xác nhận Jackpot 2. Với Mega 6/45, không có số đặc biệt và bộ dò dùng đúng các hạng Jackpot, Giải nhất, Giải nhì, Giải ba.
- Bộ kiểm định thuật toán dùng rolling/out-of-sample: mỗi kỳ kiểm tra chỉ được tạo ứng viên từ các kỳ đứng trước, không sử dụng kết quả tương lai. Có thể xuất chi tiết CSV.
- Module lõi dùng chung: `ticket_checker.py`; kiểm thử: `tests/test_ticket_checker.py`.
- Quy tắc hạng giải theo Thể lệ Power 6/55 Vietlott: Jackpot 1 (6 số), Jackpot 2 (5 số + đặc biệt), Giải nhất (5 số), Giải nhì (4 số), Giải ba (3 số). Một vé chỉ nhận hạng giải cao nhất. Công cụ chỉ hỗ trợ đối chiếu tham khảo; vé hợp lệ và kết quả chính thức phải được Vietlott xác nhận.
- Rolling backtest đo hiệu quả lịch sử ngoài mẫu, không phải bằng chứng thuật toán dự đoán được tương lai hay làm tăng xác suất trúng.

## XSMN: thuật toán thống kê và backtest cuốn chiếu

- Module phân tích: `xsmn_algorithms.py`.
- Các phương pháp xếp hạng: tần suất 30/90/365 kỳ, độ gan, EWMA (giảm trọng số theo thời gian), mô hình kết hợp.
- Phân tích cặp số cùng xuất hiện, tổng, chẵn/lẻ và phân phối 00–99.
- Tab **Thuật toán** và **Backtest** trong `xsmn_app.py`.
- Backtest walk-forward: tại mỗi ngày kiểm tra, chỉ dùng dữ liệu có ngày nhỏ hơn ngày mục tiêu; không dùng kết quả tương lai.
- So sánh số lần trùng trong top-K với mức kỳ vọng ngẫu nhiên, xuất chi tiết từng ngày ra CSV.
- Kiểm thử tự động: `tests/test_xsmn_algorithms.py`, workflow `.github/workflows/xsmn-algorithms-tests.yml`.
- Điểm xếp hạng và kết quả backtest là thống kê quá khứ, không chứng minh khả năng dự đoán hoặc tăng xác suất trúng.


## Vietlott: giám sát trực tiếp và lưu bằng chứng vali bóng

- Trang Streamlit: pages/8_Live_Evidence_Monitor.py (tự xuất hiện trong menu ứng dụng Vietlott).
- Worker: scripts/live_draw_monitor.py.
- Workflow: .github/workflows/vietlott-live-evidence.yml.
- Tự chạy 17:50 giờ Việt Nam vào ngày quay; chờ 18:00 và lấy mẫu luồng công khai đến 18:30.
- Mega 6/45: thứ Tư, thứ Sáu, Chủ nhật. Power 6/55: thứ Ba, thứ Năm, thứ Bảy.
- Lấy một khung hình mỗi 5 giây; OCR tiếng Việt/Anh; ghi thời điểm, nội dung OCR và SHA-256 từng khung hình. Lưu contact sheet và các ảnh mẫu/ảnh OCR nghi vấn.
- Toàn bộ khung hình lấy mẫu mỗi 5 giây, nhật ký OCR và gói chứng cứ đính kèm GitHub Actions artifact 90 ngày; ảnh chọn lọc và nhật ký phiên được lưu trong data/live_evidence/.
- Chạy thủ công tại GitHub → Actions → Vietlott live draw evidence. Có thể nhập URL phát công khai nếu trang chính thức không tự lộ luồng.
- OCR chỉ gợi ý khung hình cần xem. Người kiểm tra phải nhìn rõ nhãn VA trước khi xác nhận mã vali. Không suy đoán mã vali từ kết quả số.
- Đây là bộ thu thập bằng chứng từ luồng công khai, không truy cập camera nội bộ hoặc biên bản mật của Vietlott. SHA-256 chứng minh tệp ảnh không bị thay đổi sau khi lưu, không tự chứng minh tính xác thực của luồng gốc.
- Hướng dẫn chi tiết: data/live_evidence/README.md.
