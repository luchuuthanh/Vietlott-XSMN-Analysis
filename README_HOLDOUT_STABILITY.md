# XSMN — Độ ổn định theo năm và tỉnh trong holdout

Nguồn: tập dữ liệu canonical PASS 5 năm; đánh giá walk-forward trong giai đoạn holdout 2025-11-06 đến 2026-11-05. Mỗi dự đoán chỉ dùng các kỳ trước đó của chính tỉnh, tối thiểu 90 kỳ. Top-10 số trên không gian 00–99. Không điều chỉnh tham số bằng holdout.

## 1. Theo năm

| Năm trong holdout | Phương pháp đứng đầu | Chênh lệch so với kỳ vọng ngẫu nhiên (số / bộ 10) |
|---|---|---:|
| 2025 (06/11–31/12) | freq_365 | +0,0443 |
| 2026 (01/01–05/11) | blend | +0,0393 |

Thứ hạng thay đổi giữa hai đoạn thời gian, nên không có một phương pháp duy nhất dẫn đầu xuyên suốt. Đây chỉ là hai đoạn của cùng một năm holdout 365 ngày, không phải hai năm kiểm định độc lập.

## 2. Độ ổn định theo tỉnh

Số tỉnh mà phương pháp có chênh lệch dương so với mốc ngẫu nhiên, số lần xếp hạng 1 và số lần nằm trong top 3:

| Phương pháp | Tỉnh có chênh lệch dương / 21 | Xếp hạng 1 | Top 3 | Hạng trung bình |
|---|---:|---:|---:|---:|
| freq_30 | 11 | 4 | 13 | 3,00 |
| blend | 14 | 3 | 14 | 3,05 |
| freq_365 | 10 | 3 | 11 | 3,33 |
| freq_90 | 13 | 4 | 10 | 3,48 |
| ewma | 14 | 3 | 10 | 3,62 |
| gap | 9 | 4 | 7 | 4,19 |

**Cách đọc:** blend có chênh lệch dương ở nhiều tỉnh nhất, còn freq_30 có hạng trung bình tốt nhất. Hai kết quả này không đủ để khẳng định có lợi thế dự đoán; việc chọn người thắng theo từng tỉnh dễ bị nhiễu do số kỳ kiểm tra mỗi tỉnh còn ít và có nhiều phép so sánh đồng thời.

## 3. Phương pháp đứng đầu theo tỉnh

| Tỉnh/thành | Phương pháp có chênh lệch cao nhất | Chênh lệch / kỳ |
|---|---|---:|
| An Giang | gap | +0,1887 |
| Bạc Liêu | ewma | +0,2442 |
| Bến Tre | freq_90 | +0,2096 |
| Bình Dương | freq_365 | +0,3596 |
| Bình Phước | freq_365 | +0,3327 |
| Bình Thuận | ewma | +0,1736 |
| Cà Mau | gap | +0,0077 |
| Cần Thơ | blend | +0,0308 |
| Đà Lạt | freq_30 | +0,1808 |
| Đồng Nai | ewma | +0,0231 |
| Đồng Tháp | gap | +0,1942 |
| Hậu Giang | freq_30 | +0,2942 |
| Kiên Giang | freq_90 | +0,1692 |
| Long An | freq_90 | +0,1058 |
| Sóc Trăng | blend | +0,3000 |
| TP. HCM | blend | +0,1087 |
| Tây Ninh | gap | +0,0830 |
| Tiền Giang | freq_30 | +0,0712 |
| Trà Vinh | freq_30 | +0,2173 |
| Vĩnh Long | freq_365 | +0,3173 |
| Vũng Tàu | freq_90 | -0,0173 |

Đây là phương pháp đứng đầu *tương đối trong sáu phương pháp đã thử* tại từng tỉnh, không phải bằng chứng rằng phương pháp đó tốt hơn chọn ngẫu nhiên. Ví dụ Vũng Tàu: phương pháp đứng đầu vẫn thấp hơn mốc ngẫu nhiên.

## 4. Quyết định kỹ thuật

- Chưa đưa bất kỳ phương pháp nào thành công cụ dự đoán/đặt cược chính thức.
- Giữ nguyên cả sáu phương pháp như các bộ lọc phân tích lịch sử.
- Nếu tiếp tục nghiên cứu, cần mở rộng đánh giá trên các cửa sổ thời gian mới trong tương lai, đăng ký trước tiêu chí, dùng baseline ngẫu nhiên ghép cặp theo từng tỉnh-kỳ và hiệu chỉnh vấn đề nhiều phép thử.
- Không chọn cấu hình riêng cho từng tỉnh từ bảng này vì sẽ overfit.

## 5. Tệp dữ liệu

Workflow **XSMN strict final holdout** xuất:
- `final_holdout_by_year.csv`
- `final_holdout_by_province.csv`
- `final_holdout_overall.csv`
- `final_holdout_detail.csv`
- `final_holdout_report.json`

[Lần chạy GitHub Actions](https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42171336351)
