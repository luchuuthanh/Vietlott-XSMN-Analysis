# XSMN — Kiểm định holdout cuối cùng (1 năm)

## Mục tiêu và nguyên tắc

Bài kiểm định này tách riêng 365 ngày mới nhất của dữ liệu làm tập đánh giá cuối:
- **Giai đoạn holdout:** 2025-11-06 đến 2026-11-05.
- **Phạm vi:** 21 tỉnh/thành, 1.147 lượt tỉnh-kỳ được đánh giá.
- **Lịch sử tối thiểu:** 90 kỳ trước ngày dự đoán.
- **Mỗi phương pháp chọn:** 10 số trong 00–99.
- **Không điều chỉnh trọng số hoặc tham số bằng kết quả của giai đoạn holdout.**
- Mỗi lượt tỉnh-kỳ được so với 1.000 bộ chọn ngẫu nhiên top-10; seed cố định để có thể tái lập.

Các phương pháp: `freq_30`, `freq_90`, `freq_365`, `gap`, `ewma`, `blend`.

## Kết quả tổng hợp

| Phương pháp | Tổng số trúng | TB số trúng / 10 số | Kỳ vọng ngẫu nhiên | Chênh lệch / kỳ | CI bootstrap 95% | p Monte Carlo |
|---|---:|---:|---:|---:|---:|---:|
| freq_30 | 1.934 | 1,6861 | 1,6556 | +0,0305 | [-0,0366; +0,0974] | 0,1858 |
| freq_365 | 1.933 | 1,6853 | 1,6556 | +0,0296 | [-0,0360; +0,0945] | 0,1908 |
| blend | 1.929 | 1,6818 | 1,6556 | +0,0262 | [-0,0381; +0,0937] | 0,2178 |
| freq_90 | 1.914 | 1,6687 | 1,6556 | +0,0131 | [-0,0498; +0,0760] | 0,3427 |
| ewma | 1.910 | 1,6652 | 1,6556 | +0,0096 | [-0,0555; +0,0739] | 0,3876 |
| gap | 1.862 | 1,6234 | 1,6556 | -0,0323 | [-0,0970; +0,0343] | 0,8362 |

Monte Carlo random baseline có trung bình 1.898,56 lượt trúng tổng cộng, độ lệch chuẩn 37,77.

## Kết luận

1. `freq_30` đứng đầu trên holdout, nhưng chỉ hơn kỳ vọng ngẫu nhiên khoảng **0,0305 số trên mỗi bộ 10 số** — mức chênh lệch rất nhỏ.
2. **Cả sáu khoảng tin cậy 95% đều chứa 0**; không có phương pháp nào cho thấy lợi thế rõ ràng trong năm holdout.
3. Các p-value Monte Carlo đều lớn hơn 0,18; không có bằng chứng thống kê thuyết phục để bác bỏ giả thuyết chọn ngẫu nhiên.
4. Không nên kết luận `freq_30` là phương pháp dự đoán tốt nhất chỉ vì nó xếp đầu trong lần kiểm tra này.
5. Kết quả lịch sử không làm thay đổi tính ngẫu nhiên của xổ số và không phải khuyến nghị đặt cược.

## Tệp kết quả chi tiết

Workflow GitHub Actions tạo artifact `XSMN-FINAL-HOLDOUT-VALIDATION` gồm:
- `final_holdout_detail.csv`: từng tỉnh-kỳ và số trúng của sáu phương pháp.
- `final_holdout_overall.csv`: bảng tổng hợp và kiểm định Monte Carlo.
- `final_holdout_by_year.csv`: độ ổn định theo năm.
- `final_holdout_by_province.csv`: độ ổn định theo tỉnh.
- `final_holdout_report.json`: cấu hình và kết quả máy đọc được.

Chạy lại bằng GitHub Actions workflow **XSMN strict final holdout** hoặc:
```bash
python scripts/backtest_xsmn_final_holdout.py
```

Artifact của lần chạy hiện tại: [GitHub Actions run](https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42171336351).
