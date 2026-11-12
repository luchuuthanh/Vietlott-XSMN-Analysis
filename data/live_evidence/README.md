# Vietlott Live Evidence Monitor

This feature monitors public live broadcasts for Mega 6/45 and Power 6/55.

## Schedule

- Mega 6/45: Wednesday, Friday, Sunday, 18:00–18:30 Vietnam time.
- Power 6/55: Tuesday, Thursday, Saturday, 18:00–18:30 Vietnam time.
- GitHub Actions is scheduled for 17:50 Vietnam time and waits until 18:00 before resolving the public stream.

## Evidence collection

The worker attempts to discover a currently-live stream from Vietlott's official live page, homepage embeds, and official-site-linked YouTube pages. It rejects a candidate unless the extractor confirms that it is live. A manual public source URL can be supplied when running the workflow manually.

During the 30-minute session it samples one frame every two seconds, computes SHA-256 for every sampled frame, runs Vietnamese/English OCR, and stores:
- session metadata (session.json);
- per-frame OCR, large-number candidates and hashes (frames_ocr.jsonl);
- an automatic live number-observation sequence in live_observations.json, requiring repeated OCR agreement across adjacent frames;
- a contact sheet of saved sample/candidate frames;
- all sampled frames (one every five seconds) in the GitHub Actions artifact, separate from the Git repository;
- individual frames selected as baseline samples or OCR candidates.

The dashboard is pages/8_Live_Evidence_Monitor.py.

## Important limits

- This is a public-stream evidence collector, not access to Vietlott's internal camera archive or official draw minutes.
- The worker does not infer a suitcase code from lottery results.
- Large visible number tokens are promoted to a live observation only after repeated OCR agreement across adjacent frames. The sequence is still an OCR observation, not an official result: verify each number against its evidence frame/video before using it as the factual basis.
- OCR output is only a clue. A human must visually confirm a readable VA label before the suitcase code is marked as identified.
- SHA-256 proves that a saved image file has not changed after capture; it does not independently authenticate the broadcast source or certify the draw.
- The official Facebook fanpage is checked as a fallback; Vietlott has said that Facebook live may cover only the first few minutes, so such a session is marked partial_capture when it ends early.
- If the official page blocks automated access, no live URL is exposed, or the stream cannot be confirmed as live, the session is recorded as capture_failed; no synthetic evidence is created.
- The full evidence bundle, including every sampled frame, is attached to the GitHub Actions run as an artifact for 90 days. Only selected frames and the session index are committed to data/live_evidence/.

## Run manually

GitHub → Actions → Vietlott live draw evidence → Run workflow.
Choose AUTO, MEGA645, or POWER655. Normally leave source_url empty so official-site discovery is attempted. If the official page publishes a different public live URL, it can be entered there.

## Source schedule reference

Vietlott's public broadcast is reported as running 18:00–18:30 on its website, official YouTube channel, and SCTV2. Mega runs Wednesday/Friday/Sunday; Power runs Tuesday/Thursday/Saturday. The Facebook live is reported to show only the first few minutes, so the worker prioritizes full-session sources.
