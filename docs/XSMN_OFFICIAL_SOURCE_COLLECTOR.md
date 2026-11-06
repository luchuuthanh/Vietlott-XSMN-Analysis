# XSMN daily result feed and validation

## Primary daily source
The project already has a direct-access third-party result feed:
- Regional history: https://api.383.im/lottery/region/mn.json
- Live endpoint: https://api.383.im/lottery/live.json
The daily GitHub Actions validation runs at **16:35 Vietnam time**, after the result feed is normally available around 16:20. It fetches the regional feed and checks that the latest date is today's date. A stale feed fails closed and is not accepted as a daily update.

## What the daily validation checks
- Continuous calendar dates from 2026-07-01 through the latest feed date.
- Expected station schedule and all 21 station identifiers.
- All nine prize classes and expected number counts / digit lengths.
- Missing or unexpected draw dates and station-days.
- Duplicate rows and documented correction rules, with audit evidence.
- Preserves the API response and generated validation report as a 90-day workflow artifact.

## Data integrity boundary
383.im is a third-party feed, not an official lottery issuer. Passing structural validation means the feed is complete and internally consistent for the checked period; it does not by itself prove every winning number is correct.
The daily workflow currently **validates and archives evidence as an artifact**. It does not yet write into or overwrite the five-year canonical dataset. Canonical integration must remain a separate, guarded step after the daily artifact is checked. The historical 66 discrepancy groups are already reviewed and are not reopened by this daily workflow.

## Optional issuer websites
The separate `XSMN issuer websites — optional manual evidence capture` workflow is manual-only. It is a secondary evidence route, not the daily primary feed.
