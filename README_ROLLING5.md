# XSMN – kiểm định cửa sổ cuốn chiếu 5 kỳ

## Phạm vi
- Dữ liệu canonical 5 năm: 2021-11-05 đến 2026-11-05.
- 21 tỉnh/thành; mỗi tỉnh có chuỗi kỳ quay riêng.
- Với mỗi kỳ mục tiêu, chỉ dùng đúng 5 kỳ gần nhất trước kỳ đó để tạo dự đoán, rồi dịch cửa sổ một kỳ.
- 5,637 lượt tỉnh-kỳ được kiểm định; chấm riêng Top 5, Top 10 và Top 15.
- Đuôi 2 số là tập giá trị duy nhất trong toàn bộ giải của tỉnh ở kỳ đó.
- Baseline ngẫu nhiên được ghép theo từng lượt, chọn k số trong 00–99; kỳ vọng/phương sai theo phân phối siêu bội.
- CI 95% là xấp xỉ chuẩn ghép cặp cho chênh lệch hit so với ngẫu nhiên; p-value là xấp xỉ chuẩn một phía cho tổng hit.

## Phương pháp
- `freq5`: tần suất trong 5 kỳ.
- `gap5`: ưu tiên số vắng lâu trong cửa sổ.
- `recent5`: số gần đây được trọng số cao hơn (hệ số 0.7).
- `freq_gap5`: kết hợp tần suất và độ vắng.
- `cold5`: ưu tiên số ít xuất hiện.
- `freq3`: tần suất trong 3 kỳ cuối của cửa sổ.

## Kết quả Top 10
| Phương pháp | Tổng hit | Hit/kỳ | Ngẫu nhiên kỳ vọng/kỳ | Chênh lệch/kỳ | Lift | CI 95% | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| cold5 / gap5 | 9,381 | 1.6642 | 1.6560 | +0.0082 | 1.0049 | [-0.0213; +0.0377] | 0.292 |
| recent5 | 9,375 | 1.6631 | 1.6560 | +0.0071 | 1.0043 | [-0.0223; +0.0365] | 0.317 |
| freq_gap5 | 9,309 | 1.6514 | 1.6560 | -0.0046 | 0.9972 | [-0.0340; +0.0248] | 0.621 |
| freq5 | 9,306 | 1.6509 | 1.6560 | -0.0051 | 0.9969 | [-0.0345; +0.0242] | 0.634 |
| freq3 | 9,262 | 1.6431 | 1.6560 | -0.0129 | 0.9922 | [-0.0423; +0.0165] | 0.807 |

## Kết luận
- Cửa sổ 5 kỳ chưa cho thấy lợi thế dự báo đáng tin cậy so với chọn ngẫu nhiên.
- Cách tốt nhất Top 10 chỉ hơn kỳ vọng khoảng 0.008 hit mỗi lượt; CI chứa 0 và p-value lớn.
- `gap5` và `cold5` cho cùng kết quả trong cấu hình này; không xem là hai bằng chứng độc lập.
- Top 5 và Top 15 cũng không cho thấy bằng chứng thống kê rõ ràng; xem CSV kết quả để biết đầy đủ.
- Không dùng kết quả này để khẳng định số nào có xác suất trúng cao hơn. Bước tiếp theo đúng là khóa thuật toán và ghi dự đoán trước các kỳ tương lai.
