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

## Automated independent cross-check: 402 station-days
Latest run:
https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42146311263

The UTF-8 parser now successfully parsed and compared all 402 station-days from 2026-07-01 through 2026-11-05:
- 402/402 station-days parsed and compared
- 400 station-days initially matched
- 2 station-days initially differed
- 0 station-days missing from the independent source
- 0 prize-count mismatches
- 7,228 of 7,236 numbers matched
- source errors: 0

The two initial differences have now been resolved using user-supplied screenshots:
1. 2026-08-29 Long An, Giải Nhì: corrected value **79719**; supplement had **76719**. The screenshot shows the VOH result with 79719.
2. 2026-10-23 Vĩnh Long, Giải Tư: corrected value **87962**; supplement had **87992**. The screenshot shows Minh Ngọc/VOH result text and explicitly notes the supervisory correction from 87992 to 87962.

See [user-supplied evidence resolution](xsmn-user-supplied-evidence-resolution-2026-11-06.md). The screenshots are corroborating evidence supplied in the conversation, not independently fetched or cryptographically authenticated captures. Keep original ingested values in the audit trail and apply corrections only with explicit provenance.

## Current truthful status
- Five-year dataset structural validation: PASS.
- July 1–10 manual comparison: 558/558 matched against displayed secondary-source result pages.
- Automated independent comparison: all 402 station-days parsed; two differences identified and now resolved by supplied screenshot evidence.
- Secondary-source agreement: 402/402 station-days accounted for after the two documented corrections; this does not establish official issuer certification.
- Official issuer certification: not obtained.
- Do not label the complete five-year dataset officially certified or independently verified in the strongest sense.

## Next work
1. Apply the two documented corrections to the canonical supplement/normalized dataset while retaining original values and an auditable correction log.
2. Rerun structural validation and independent comparison against the corrected dataset.
3. Reconcile the 66 historical overlap discrepancy groups in a deduplicated row-level ledger, checking each cited page and preserving both source values.
4. Keep statuses distinct: structurally valid, manually matched to secondary source, independently cross-checked, unresolved, and official certification (if ever obtained).
