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
Two non-overlapping ledgers now cover all 10 dates:
- [July 1, 2, 3 and 5 ledger](xsmn-manual-verification-2026-07-01-02-03-05.md): 12 station-days / 216 entries; 216/216 matched.
- [July 4 and July 6–10 ledger](xsmn-manual-verification-2026-07-04-06-07-08-09-10.md): 19 station-days / 342 entries; 342/342 matched.

Combined manual batch totals:
- 31 station-days
- 558 prize entries
- 558 entries matched against displayed full-result secondary-source pages
- 0 mismatches observed in this manual comparison

Limitations: the source pages are secondary result websites, not official issuer certification. The comparisons are manually recorded and are not yet a fully reproducible automated row-level parser run. Some dates have more than one corroborating page; ownership independence of every site has not been separately established. This result applies only to July 1–10, 2026.

## 66 source discrepancies in the overlap
A discrepancy review report exists at [source discrepancy review](xsmn-source-discrepancy-review-2026-11-05.md). It records 66 differing prize groups between the archive and 383.im in their overlap and a secondary-source review. Keep original source values and provenance; do not silently overwrite one source with another. Recheck evidence before treating every one of the 66 as closed.

## Automated independent cross-check for 402 station-days
The current XoSoTin adapter in `scripts/verify_xsmn_supplement_sources_v2.py` is not working: GitHub Actions receives HTML pages but its parser does not recognize the result grid. Latest failed run:
https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42064345239

It parsed 0 of the 402 station-days. This is a parser/source-access blocker, not evidence that the 383.im data is correct or incorrect. Do not count this as an automated verification pass.

## Current truthful status
- Five-year dataset structural validation: PASS.
- July 1–10 manual comparison: 558/558 matched against cited secondary result pages.
- 402-station-day automated independent comparison: BLOCKED; 0/402 parsed by current XoSoTin adapter.
- Official issuer certification: not obtained.
- Do not label the complete five-year dataset independently verified.

## Next work
1. Inspect raw XoSoTin HTML and build parser fixtures from saved pages before attempting the 402-day run again.
2. Reconcile the 66 discrepancy groups in one deduplicated ledger, checking the evidence and preserving both source values.
3. Maintain clear statuses: structurally valid, manually matched to secondary source, independently cross-checked, unresolved, and official certification (if ever obtained).
