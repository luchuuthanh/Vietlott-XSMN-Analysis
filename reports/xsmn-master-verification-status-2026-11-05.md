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

## July 1–10 manual batch: current evidence status
- July 1, 2, 3 and 5: a new station-day ledger records 12 station-days / 216 prize entries manually compared with full-result secondary-source pages; 216/216 matched. See [manual ledger](xsmn-manual-verification-2026-07-01-02-03-05.md).
- July 4 and July 6–10: a previous report records 19 station-days / 342 entries as matching. See [previous report](xsmn-manual-comparison-2026-07-04-to-10.md). That report is a manual summary, not a machine-generated row-level evidence ledger; its source URLs and all individual comparisons still require a fresh audit before this batch can be marked fully audited.
- Therefore, do not claim the entire July 1–10 batch is fully audited yet. The strongest currently consolidated record is 216/558 entries in the new ledger; 342/558 remain to be re-audited and documented in a row-level ledger.

## 66 source discrepancies in the overlap
A discrepancy review report exists at [source discrepancy review](xsmn-source-discrepancy-review-2026-11-05.md). It records 66 differing prize groups between the archive and 383.im in their overlap and a secondary-source review. Keep original source values and provenance; do not silently overwrite one source with another. Recheck evidence before treating every one of the 66 as closed.

## Automated independent cross-check for 402 station-days
The current XoSoTin adapter in `scripts/verify_xsmn_supplement_sources_v2.py` is not working: GitHub Actions receives HTML pages but its parser does not recognize the result grid. Latest failed run:
https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42064345239

It parsed 0 of the 402 station-days. This is a parser/source-access blocker, not evidence that the 383.im data is correct or incorrect. Do not count this as a verification pass.

## Current truthful status
- Five-year dataset structural validation: PASS.
- July 1, 2, 3 and 5 manual ledger: 216/216 entries matched against cited secondary full-result pages.
- July 4 and July 6–10 manual report: provisional pending fresh audit and row-level ledger.
- 402-station-day automated independent comparison: BLOCKED; 0/402 parsed by current XoSoTin adapter.
- Official issuer certification: not obtained.
- Do not label the complete five-year dataset independently verified.

## Next work
1. Re-audit July 4 and July 6–10 against exact full-result pages; create a station-day/prize-level evidence ledger, correcting any bad URLs in the earlier summary.
2. Inspect raw XoSoTin HTML and build parser fixtures from saved pages before attempting the 402-day run again.
3. Reconcile the 66 discrepancy groups in one deduplicated ledger.
4. Maintain clear statuses: structurally valid, manually matched to secondary source, independently cross-checked, unresolved, and official certification (if ever obtained).
