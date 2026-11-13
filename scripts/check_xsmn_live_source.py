"""Run the production XSMN live parser against the real upstream source."""
from __future__ import annotations

import sys
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xsmn_live import fetch_live_xsmn, fetch_live_xsmn_partial, EXPECTED

frame, source_url = fetch_live_xsmn()
dates = sorted(set(frame["date"].astype(str)))
stations = sorted(set(frame["province"].astype(str)))
print(f"SOURCE_URL={source_url}")
print(f"DRAW_DATES={dates}")
print(f"STATIONS={stations}")
for station, group in frame.groupby("province"):
    counts = group["prize"].value_counts().to_dict()
    assert len(group) == 18, f"{station}: expected 18 rows, got {len(group)}"
    assert counts == EXPECTED, f"{station}: unexpected prize structure {counts}"
    print(f"PASS station={station} rows={len(group)} prize_counts={counts}")
for station, group in frame.groupby("province"):
    special = group.loc[group["prize"] == "ĐB", "number"].astype(str).tolist()
    print(f"TOP_PRIZE station={station} numbers={special}")
print(f"PASS live_source rows={len(frame)} date={dates[0]}")

# Exercise the partial feed used as the app's issuer fallback.
partial_frame, partial_url = fetch_live_xsmn_partial()
partial_dates = set(pd.to_datetime(partial_frame["date"], errors="coerce").dt.date.astype(str))
assert partial_dates == {dates[0]}, f"Fallback feed date mismatch: {partial_dates}"
partial_vl = partial_frame[partial_frame["province"].astype(str).map(lambda value: value.strip().casefold()) == "vĩnh long"]
assert not partial_vl.empty, "Fallback feed did not return Vĩnh Long"
print(f"PASS fallback_source={partial_url} VinhLong_partial_rows={len(partial_vl)} date={dates[0]}")
