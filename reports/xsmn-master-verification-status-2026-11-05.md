# XSMN master verification status — 2026-11-05

## Dataset rebuilt successfully
The GitHub Actions pipeline rebuilt the five-year normalized dataset successfully:
- Window: 2021-11-05 through 2026-11-05
- Normalized rows: 103,356
- Historical archive rows: 96,120
- 383.im supplement rows: 7,236
- Supplement window: 2026-07-01 through 2026-11-05
- Supplement draw dates: 128
- Provinces: 21
- Station-day pairs: 402
- Structural validation: no missing scheduled dates, no unexpected dates, no missing station-days, no unexpected station-days, no duplicate rows, and no validation errors.

The 383.im supplement remains a separate third-party source. Structural validation does not verify that its winning numbers are correct.

## Automated independent cross-check attempt
Added:
- `scripts/verify_xsmn_supplement_sources.py`
- `.github/workflows/xsmn-independent-crosscheck.yml`

The workflow successfully rebuilt and normalized the dataset, but the first independent source adapter did not work: XSKT.net returned HTML that the parser could not read in GitHub Actions. The audit therefore compared **0 of 402** station-days. This is a source-access/parser blocker, not evidence that the supplement is correct or incorrect. Do not count this run as an independent verification pass.

Runs:
- Initial URL-format attempt: https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42061025008
- Corrected month URL attempt: https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42061106116
- Parser diagnostic attempt: https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42061223346

Artifact from latest attempt:
https://github.com/luchuuthanh/Vietlott-XSMN-Analysis/actions/runs/42061223346/artifacts/13431712887

## Reconciliation of earlier manual reports
Earlier date-batch reports are not a reliable master ledger because they overlap in calendar coverage and some totals were inconsistent. The 2026-09-15 to 2026-09-20 report was corrected from 18/324 to 19 station-days / 342 result rows. Do not add all prior report counts together to claim a global verified total.

The 2026-09-05 to 2026-09-14 batch report records 31 station-days / 558 rows compared. The 2026-09-15 to 2026-09-20 report records 19 station-days / 342 rows. Other manually reported date batches should be treated as provisional until a single deduplicated row-level ledger is rebuilt.

## Current truthful status
- Dataset structurally rebuilt: PASS.
- Supplement size: 7,236 rows / 402 station-days.
- Automated independent comparison: BLOCKED; 0/402 compared in the latest run.
- Official issuer certification: not obtained.
- Do not merge the supplement into the historical archive as verified data.
- Next engineering step: replace the XSKT.net requests adapter with a source that is programmatically accessible and parseable in CI; add fixture-based parser tests, then rerun the complete 402-station-day comparison and reconcile all prior manual checks against the same row-level ledger.
