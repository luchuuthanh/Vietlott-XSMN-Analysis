# XSMN discrepancy resolution from user-supplied screenshots — 2026-11-06

## Purpose
Record two primary-source-result discrepancies found by the independent cross-check run `42146311263`. This report preserves the original supplement values and records the evidence supplied by the project owner. The screenshots are evidence supplied in the conversation; they are not independently fetched or cryptographically authenticated source captures.

## Resolved discrepancies

| Draw date | Province | Prize | Supplement value (previous) | Corrected value supported by screenshot | Evidence shown |
|---|---|---|---:|---:|---|
| 2026-08-29 | Long An | Second prize (Giải Nhì) | 76719 | **79719** | Screenshot of Google result text: “Kết quả xổ số Long An (XSLA) ngày 29/08/2026 từ VOH”, showing Giải Nhì 79719. |
| 2026-10-23 | Vĩnh Long | Fourth prize (Giải Tư) | 87992 | **87962** | Screenshot of Google result text naming Minh Ngọc and VOH, showing Giải Tư 87962 and an explicit note that the supervisory council corrected the number to 87962 instead of the earlier displayed 87992. |

## Audit treatment
- The two screenshot-supported values agree with the independent XoSoTin comparison values in cross-check run `42146311263`.
- The supplement values `76719` and `87992` must remain in the historical audit trail as the originally ingested values; do not silently overwrite provenance.
- For the canonical corrected dataset, use `79719` for Long An 2026-08-29 Giải Nhì and `87962` for Vĩnh Long 2026-10-23 Giải Tư, while retaining an explicit correction record linking each old and new value.
- Evidence provenance: user-supplied screenshots viewed in the ChatGPT conversation on 2026-11-06. The first screenshot displays a VOH result; the second displays Minh Ngọc and VOH result text and the correction note. Search-result screenshots are corroborating evidence, not official issuer certification.
- The two discrepancies are resolved for the purpose of this audit based on the supplied evidence. The broader five-year dataset still requires its remaining provenance and source-independence review.

## Related run
- Workflow: https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42146311263
- Previous automated comparison: 400 of 402 station-days matched; these were the only two station-day mismatches reported in that run.
