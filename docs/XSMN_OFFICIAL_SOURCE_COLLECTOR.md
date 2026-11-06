# XSMN official source collector — phase 1

This workflow discovers and preserves result-notice pages and their original media from the Southern Lottery Council information portal:

- https://xsktmiennam.vn/
- Runs daily at 18:40 Vietnam time and can be run manually from GitHub Actions.
- Captures HTML, image/PDF-linked media where exposed as page images, SHA-256 hashes, source URLs, company-name hints and date hints.
- Stores the run as a 90-day GitHub Actions artifact.

## Data-integrity rule

This phase is **source discovery and evidence capture**, not yet a verified direct-company result feed. The Council portal is an information portal and is not the issuing company website itself. The collector does not OCR images or insert extracted values into the canonical five-year dataset. No result is accepted merely because a page title or image exists.

## Next implementation phase

For each of the 21 issuing companies, verify its own official domain and its result-publication path/API. Add a dedicated parser for each actual format (HTML, PDF or image), preserve the original response, and test the parsed nine prize groups against the issuer notice. Only after a source is confirmed as belonging to the issuer should its parsed results be eligible for the official-source comparison ledger.

The known direct issuer website confirmed in the current inventory is XSKT TP.HCM: https://www.xskthcm.com/. The Council portal is the discovery starting point for other issuer links and notices.
