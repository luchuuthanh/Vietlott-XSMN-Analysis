# XSMN source discrepancy review

Review date: 2026-11-05

## Decision

Keep the quarterly SQLite archive as the canonical source for the overlap period. Do not use the 383.im API values to overwrite it. The 383.im regional endpoint is suitable only as a separately validated supplement after the archive ends (2026-06-30), and remains third-party data.

## 66 discrepant prize groups reviewed

The overlap comparison found 66 prize groups whose sorted number sets differ between the archive and 383.im:

| Draw date | Province(s) | Groups | Independent cross-check |
|---|---|---:|---|
| 2024-11-15 | Tra Vinh | 1 | Minh Ngoc and xskt.com.vn show DB 084786, matching archive |
| 2025-06-28 | Binh Phuoc, Hau Giang, Long An, TP. HCM | 32 | xskt.com.vn, xskt.in.net, kqxsmn.net, Minh Ngoc show full draw tables matching archive |
| 2025-08-23 | Binh Phuoc | 1 | Minh Ngoc, xskt.com.vn, ketqua.vn show G4 79028, matching archive |
| 2026-05-02 | Binh Phuoc, Hau Giang, Long An, TP. HCM | 32 | Minh Ngoc, xosominhngoc.com, QuetKQXS, vesokethanh show full draw tables matching archive |

## Interpretation

- 2025-06-28 and 2026-05-02 have the same distinctive pattern across four stations: the 383.im values are shifted across adjacent prize categories, beginning at DB and propagating down to G7. Independent published result tables support the archive's prize assignments.
- 2024-11-15: archive DB 084786 is independently published for Tra Vinh; the API value 560920 is not supported by the cross-check.
- 2025-08-23: archive G4 contains 79028; the API has 79023. Multiple independent result pages support 79028.
- These are source-level errors in 383.im for the overlap dates, not reasons to edit the archive.

## Evidence URLs

- 2024-11-15 Tra Vinh: https://www.minhngoc.net.vn/ket-qua-xo-so/mien-nam/tra-vinh/15-11-2024.html
- 2024-11-15 regional table: https://ttttmb.xskt.com.vn/xsmn/ngay-15-11
- 2025-06-28: https://xskt.com.vn/xsmn/ngay-28-6-2025
- 2025-06-28: https://xskt.in.net/xsmn/28-06-2025.html
- 2025-06-28: https://kqxsmn.net/xsmn/06-2025.html
- 2025-06-28: https://www.minhngoc.net.vn/ket-qua-xo-so/28-06-2025.html
- 2025-08-23: https://www.minhngoc.net.vn/ket-qua-xo-so/mien-nam/binh-phuoc/23-08-2025.html
- 2025-08-23: https://xskt.com.vn/xsmn/ngay-23-8-2025
- 2025-08-23: https://ketqua.vn/xsmn/23-08-2025
- 2026-05-02: https://www.minhngoc.net.vn/free/ket-qua-xo-so/mien-nam/02-05-2026.html
- 2026-05-02: https://xosominhngoc.com/ket-qua-xo-so/mien-nam/02-05-2026.html
- 2026-05-02: https://quetkqxs.com/xsmn/02-05-2026
- 2026-05-02: https://vesokethanh.com.vn/ket-qua-xo-so/mien-nam/05-05-2026.html

## Remaining limitation

This is a targeted independent cross-check of all dates/groups flagged by the two-source comparison. It is not a complete official certification of every row in the five-year dataset. The 383.im supplement (2026-07-01 onward) has passed structural and schedule checks but still needs independent row-level verification before being labelled fully official.
