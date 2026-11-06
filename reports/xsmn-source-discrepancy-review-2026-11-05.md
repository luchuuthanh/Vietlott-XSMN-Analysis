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


## Recent 402-day cross-check corrections — 2026-11-06 (verified)

The two station-day mismatches are separate from the 66 historical archive-vs-383.im overlap groups above. Both are now resolved against multiple published tables, and the Vĩnh Long item is supported by a report of the issuer's formal correction.

1. **2026-08-29 Long An, G2 — confirmed 79719.** The normalized 383 supplement currently contains 76719, while the full draw table contains 79719. The result 79719 is independently listed by xskt.com.vn, Minh Ngọc, Minh Chính, XS.com.vn, Xổ Số Ngày Nay, and other result pages. Sources: https://xskt.com.vn/xsla/ngay-29-8-2026 ; https://www.minhngoc.net/ket-qua-xo-so/mien-nam/long-an/29-08-2026.html ; https://www.minhchinh.com/dai-ly-ve-so-long-an/29-08-2026.html ; https://xs.com.vn/xsla-ngay-29-8-2026.html ; https://xosongaynay.com/xo-so-long-an . **Correct value: 79719.**
2. **2026-10-23 Vĩnh Long, G4 — confirmed 87962.** The normalized 383 supplement contains 87992, and several early result pages repeated 87992. However, the issuer's correction was reported by Tuổi Trẻ: the original 87992 was wrong because the person drawing the number held the wrong number board; the supervisory council's signed record was 87962, and the Vĩnh Long Lottery Company formally corrected the result to 87962. xskt.com.vn and other updated tables also show 87962. Source reporting the issuer's correction: https://tuoitre.vn/vu-nham-ket-qua-xo-so-vinh-long-nhung-van-de-phap-ly-dat-ra-20261106141008842.htm (alternate syndicated URL captured in search: https://waf-user-app.vngcloud.vn/vu-nham-ket-qua-xo-so-vinh-long-nhung-van-de-phap-ly-dat-ra-100261026141008842.htm). Updated result table: https://xskt.com.vn/xsvl/ngay-23-10-2026 . **Correct value: 87962.**

**Required data corrections:** change Long An 2026-08-29 G2 from 76719 to 79719; change Vĩnh Long 2026-10-23 G4 item from 87992 to 87962. The user's earlier image was not accessible in the current file search, but the second correction is independently resolved by the issuer's formal correction as reported above. Preserve the original raw supplement as an immutable source snapshot and write corrected values into a reconciled/canonical layer with provenance; do not overwrite raw source evidence. Re-run the 402-day row-level comparison after applying these two corrections. Keep this QA scope separate from the 66 historical overlap discrepancies.


## Independent supplement verification — 2026-11-06 (PASS)

A complete row-level comparison of the 383.im supplement against the parsed XoSoTin daily result tables completed successfully in workflow run 42149973415.

- Window: 2026-07-01 through 2026-11-05.
- Dates requested: 128.
- Expected station-days: 402.
- Station-days parsed and compared: 402 / 402.
- Exact station-day matches: 402 / 402.
- Mismatching station-days: 0.
- Missing source station-days: 0.
- Prize-count mismatches: 0.
- Matching prize numbers: 7,236 / 7,236.
- Result: PASS.

The saved source HTML confirms the daily result table was parsed (including the Vĩnh Long 23/10/2026 table, where G4 contains 87962). The normalized artifact also contains Long An 29/08/2026 G2 = 79719 and Vĩnh Long 23/10/2026 G4 = 87962. This confirms the current supplement snapshot, not every historical API snapshot.

Artifact: https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42149973415/artifacts/13471308178
Workflow run: https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42149973415

The independent source is a secondary published results site, not an official issuer certification. The workflow has now been updated to use the verified parser (verify_xsmn_supplement_sources_v2.py) and retain the correction/reconciliation step for subsequent runs.
