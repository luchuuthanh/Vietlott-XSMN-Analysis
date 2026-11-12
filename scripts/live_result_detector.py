"""Conservative OCR-based observations from visible draw frames.

Large numeric tokens are treated as candidates only; a number enters the live
observation sequence after repeated agreement across consecutive frames.
"""
from __future__ import annotations

import re
from collections import deque


def parse_large_numeric_tokens(data, image_width: int, image_height: int, universe: int):
    """Extract large, readable 1- or 2-digit tokens likely printed on a draw ball."""
    found = []
    texts = data.get("text", [])
    confs = data.get("conf", [])
    heights = data.get("height", [])
    widths = data.get("width", [])
    lefts = data.get("left", [])
    tops = data.get("top", [])
    for i, raw in enumerate(texts):
        token = re.sub(r"[^0-9]", "", str(raw))
        if not token or len(token) > 2:
            continue
        try:
            number = int(token)
            confidence = float(confs[i])
            height = int(heights[i])
            width = int(widths[i])
            left = int(lefts[i])
            top = int(tops[i])
        except (ValueError, TypeError, IndexError):
            continue
        if not (1 <= number <= universe):
            continue
        # Filter small captions, clocks and interface labels. A ball number should
        # occupy a substantial part of the frame.
        if height < max(22, int(image_height * 0.055)):
            continue
        if width < max(12, int(image_width * 0.012)):
            continue
        if confidence < 55:
            continue
        found.append({
            "number": number,
            "ocr_token": str(raw),
            "confidence": round(confidence, 1),
            "bbox": [left, top, width, height],
        })
    return found


def consensus_events(frame_rows, min_hits: int = 2, window_frames: int = 5):
    """Promote a candidate only after repeated agreement in a short frame window."""
    recent = deque(maxlen=window_frames)
    events = []
    last_emitted = None
    for row in frame_rows:
        recent.append(row)
        counts = {}
        best = {}
        for item in recent:
            for candidate in item.get("numeric_candidates", []):
                number = candidate["number"]
                counts[number] = counts.get(number, 0) + 1
                if number not in best or candidate.get("confidence", 0) > best[number].get("confidence", 0):
                    best[number] = candidate
        confirmed = [
            number for number, hits in counts.items()
            if hits >= min_hits
        ]
        if not confirmed:
            continue
        confirmed.sort(key=lambda number: (counts[number], best[number].get("confidence", 0)), reverse=True)
        chosen = confirmed[0]
        if chosen == last_emitted:
            continue
        if events and any(e["number"] == chosen for e in events):
            last_emitted = chosen
            continue
        event = {
            "number": chosen,
            "first_seen_elapsed_seconds": row.get("elapsed_seconds"),
            "frame_hits_in_window": counts[chosen],
            "best_ocr_confidence": best[chosen].get("confidence"),
            "status": "OCR_consensus_candidate_not_officially_verified",
        }
        events.append(event)
        last_emitted = chosen
    return events


def classify_sequence(events, game: str):
    """Label sequence positions without claiming an official result."""
    output = []
    for index, event in enumerate(events):
        item = dict(event)
        if index < 6:
            item["position"] = f"main_{index + 1}"
        elif game == "POWER655" and index == 6:
            item["position"] = "possible_special"
        else:
            item["position"] = "extra_or_false_positive"
        output.append(item)
    return output
