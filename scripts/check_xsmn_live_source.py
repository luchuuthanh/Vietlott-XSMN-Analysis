"""Run the production XSMN live parser against the real upstream source."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xsmn_live import fetch_live_xsmn, EXPECTED

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
