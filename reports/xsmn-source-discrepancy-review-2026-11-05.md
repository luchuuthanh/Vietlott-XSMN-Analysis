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
- 2025-06-28: https://xskt.net/xsmn/06-2025
- 2025-06-28: https://kqxsmn.net/xsmn/06-2025.html
- 2025-06-28: https://www.minhngoc.net.vn/ket-qua-xo-so/28-06-2025.html
- 2025-08-23: https://www.minhngoc.net.vn/ket-qua-xo-so/mien-nam/binh-phuoc/23-08-2025.html
- 2025-08-23: https://xskt.com.vn/xsmn/ngay-23-8-2025
- 2025-08-23: https://ketqua.vn/xsmn/23-08-2025
- 2026-05-02: https://www.minhngoc.net.vn/free/ket-qua-xo-so/mien-nam/02-05-2026.html
- 2026-05-02: https://xosominhngoc.com/ket-qua-xo-so/mien-nam/02-05-2026.html
- 2026-05-02: https://quetkqxs.com/xsmn/02-05-2026
- 2026-05-02: https://xosonay.com/xsmn/02-05-2026/

## Remaining limitation

This is a targeted independent cross-check of all dates/groups flagged by the two-source comparison. It is not a complete official certification of every row in the five-year dataset. The 383.im supplement (2026-07-01 onward) has passed structural and schedule checks but still needs independent row-level verification before being labelled fully official.


## Row-level review update — 2026-11-06

The current five-year archive audit artifact was downloaded and the archive rows for all flagged date/province pairs were inspected. A reproducible builder has been added at `scripts/build_xsmn_66_discrepancy_ledger.py`; the archive-audit workflow now generates:
- `xsmn_audit/xsmn_66_discrepancy_ledger.csv` — one row per flagged prize group, including archived prize values and source URLs.
- `xsmn_audit/xsmn_66_discrepancy_ledger.json` — row-count and provenance summary.

The ledger is deliberately explicit that the historical 383.im overlap payload is not present in the current audit artifact. Therefore it cannot reconstruct the exact old 383.im value for each row; the previously documented 66-difference count remains based on the earlier archive/API comparison. The ledger records the archive values and their corroboration from published secondary result tables, without pretending to have retained the missing raw API values.

### Confirmed evidence details
- 2024-11-15 Trà Vinh: Minh Ngọc and xskt.com.vn both publish DB 084786.
- 2025-06-28: xskt.com.vn, xskt.net, and xs.com.vn publish the same full four-station table, including all prize groups DB–G7.
- 2025-08-23 Bình Phước: xskt.com.vn and Minh Ngọc both publish G4 number 79028.
- 2026-05-02: xskt.com.vn, Minh Ngọc, Xổ Số Nay, xskt.net, and other result pages publish the same four-station table, including all prize groups DB–G7.

These are corroborating secondary result pages. Their common upstream data ownership has not been established, and no official issuer certification has been obtained. The archive remains unchanged; no historical archive values are overwritten.
