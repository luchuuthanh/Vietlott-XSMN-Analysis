# XSMN master verification status — 2026-11-06

## Dataset rebuilt successfully
Latest normalized dataset artifact from workflow run 42064345239:
- Window: 2021-11-05 through 2026-11-05
- Normalized rows: 103,356
- Historical archive rows: 96,120
- 383.im supplement rows: 7,236
- Supplement window: 2026-07-01 through 2026-11-05
- Supplement draw dates: 128
- Provinces: 21
- Station-day pairs: 402
- Structural validation: no missing scheduled dates, no unexpected dates, no missing station-days, no unexpected station-days, no duplicate rows, and no validation errors.

The 383.im supplement remains a third-party source. Structural validation does not verify winning-number accuracy.

## July 1–10 manual batch: consolidated result
Two non-overlapping ledgers cover all 10 dates:
- [July 1, 2, 3 and 5 ledger](xsmn-manual-verification-2026-07-01-02-03-05.md): 12 station-days / 216 entries; 216/216 matched.
- [July 4 and July 6–10 ledger](xsmn-manual-verification-2026-07-04-06-07-08-09-10.md): 19 station-days / 342 entries; 342/342 matched.

Combined manual batch totals: 31 station-days, 558 prize entries, 558 matched, 0 mismatches observed. This applies only to July 1–10, 2026. The sources are secondary result websites, not official issuer certification; source ownership independence has not been established for every page.

## 66 source discrepancies in the historical overlap
See [source discrepancy review](xsmn-source-discrepancy-review-2026-11-05.md). It records 66 differing prize groups between the archive and 383.im in their overlap. Preserve original values and provenance; do not silently overwrite one source with another. Recheck evidence before treating every one as closed.

## Automated independent cross-check after corrections: 402 station-days

Latest completed run:
https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42146902836

The supplement validation, five-year normalization, and independent XoSoTin comparison all completed successfully:
- 402/402 station-days parsed and compared
- 402 station-days matched
- 0 mismatches
- 0 station-days missing from the independent source
- 0 prize-count mismatches
- 7,236/7,236 numbers matched
- source errors: 0

The two screenshot-supported corrections are now applied automatically by the supplement validation pipeline, with the original values retained in a separate correction audit log:
1. 2026-08-29 Long An, Giải Nhì: **76719 → 79719**.
2. 2026-10-23 Vĩnh Long, Giải Tư: **87992 → 87962**.

The rebuilt normalized dataset confirms both corrected values. Full five-year structural validation also passed:
- 103,356 rows: 96,120 archive + 7,236 supplement
- 1,827 calendar days, 21 provinces, 9 prize classes, 5,742 station-day pairs
- 0 missing calendar dates, 0 schedule mismatches, 0 duplicate keys, 0 validation errors.

The independent comparator uses XoSoTin, a secondary result source. A clean comparison is not official issuer certification and does not establish that every source is institutionally independent.

## Current truthful status
- Five-year dataset structural validation: PASS.
- July 1–10 manual comparison: 558/558 matched against displayed secondary-source result pages.
- Automated independent comparison after correction: 402/402 station-days and 7,236/7,236 numbers match XoSoTin; no missing station-days, mismatches, or source errors.
- The correction rules are part of the validation pipeline and are recorded in an audit JSON artifact; the original source values are preserved there.
- Secondary-source agreement does not establish official issuer certification.
- Official issuer certification: not obtained.
- Do not label the complete five-year dataset officially certified or independently verified in the strongest sense.

## Next work
1. Reconcile the 66 historical overlap discrepancy groups in a deduplicated row-level ledger, checking each cited page and preserving both source values.
2. Keep statuses distinct: structurally valid, manually matched to secondary source, independently cross-checked, unresolved, and official certification (if ever obtained).
