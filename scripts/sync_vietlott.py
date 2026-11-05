#!/usr/bin/env python3
"""Daily mirror and integrity audit for all seven Vietlott datasets.

The upstream project publishes NDJSON collected from Vietlott result pages.
This script never fabricates missing draws: it downloads a complete snapshot,
validates every record, and writes an audit manifest alongside the raw files.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "vietlott"
MANIFEST = DATA_DIR / "manifest.json"
BASE = "https://raw.githubusercontent.com/vietvudanh/vietlott-data/main/data/"

GAMES = {
    "POWER655": ("power655.jsonl", "power655.jsonl"),
    "MEGA645": ("power645.jsonl", "power645.jsonl"),
    "POWER535": ("power535.jsonl", "power535.jsonl"),
    "KENO": ("keno.jsonl", "keno.jsonl"),
    "MAX3D": ("3d.jsonl", "3d.jsonl"),
    "MAX3DPRO": ("3d_pro.jsonl", "3d_pro.jsonl"),
    "BINGO18": ("bingo18.jsonl", "bingo18.jsonl"),
}

def fetch(url: str, attempts: int = 4) -> bytes:
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Vietlott-Analysis-Lab/1.0 (+daily-data-audit)"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                payload = response.read()
                if not payload:
                    raise RuntimeError("empty response")
                return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Download failed after {attempts} attempts: {url}: {last_error}")

def as_int_list(value):
    if not isinstance(value, list):
        return None
    if any(isinstance(x, bool) or not isinstance(x, int) for x in value):
        return None
    return value

def three_digit_values(value):
    found = []
    if isinstance(value, str) and re.fullmatch(r"\d{3}", value):
        found.append(value)
    elif isinstance(value, list):
        for item in value:
            found.extend(three_digit_values(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(three_digit_values(item))
    return found

def validate_result(game: str, result) -> str | None:
    if game in {"POWER655", "MEGA645", "POWER535", "KENO", "BINGO18"}:
        nums = as_int_list(result)
        if nums is None:
            return "result must be an integer array"
        if game == "POWER655":
            if len(nums) not in (6, 7) or len(set(nums[:6])) != 6 or any(n < 1 or n > 55 for n in nums):
                return "Power 6/55 expects 6 distinct main numbers in 1..55 and an optional 7th bonus number"
        elif game == "MEGA645":
            if len(nums) != 6 or len(set(nums)) != 6 or any(n < 1 or n > 45 for n in nums):
                return "Mega 6/45 expects 6 distinct numbers in 1..45"
        elif game == "POWER535":
            if len(nums) != 6 or len(set(nums[:5])) != 5 or any(n < 1 or n > 35 for n in nums[:5]):
                return "Power 5/35 expects 5 distinct main numbers in 1..35 plus a special number"
        elif game == "KENO":
            if len(nums) != 20 or len(set(nums)) != 20 or any(n < 1 or n > 80 for n in nums):
                return "Keno expects 20 distinct numbers in 1..80"
        elif game == "BINGO18":
            if len(nums) != 3 or any(n < 1 or n > 6 for n in nums):
                return "Bingo18 expects 3 dice values in 1..6"
        return None

    if game in {"MAX3D", "MAX3DPRO"}:
        if not isinstance(result, dict):
            return "Max 3D result must be an object grouped by prize tier"
        values = three_digit_values(result)
        if len(values) < 20:
            return f"Max 3D expects at least 20 three-digit prize values; found {len(values)}"
        return None
    return f"unsupported game: {game}"

def audit_payload(game: str, payload: bytes) -> dict:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"{game}: file is not UTF-8: {exc}") from exc

    records = []
    errors = []
    seen_ids = set()
    seen_date_ids = set()
    id_numbers = set()
    missing_bonus_count = 0
    id_order_anomalies = []
    previous_numeric_id = None
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(item, dict):
            errors.append(f"line {line_no}: record is not an object")
            continue
        draw_id = str(item.get("id", "")).strip()
        raw_date = str(item.get("date", "")).strip()
        result = item.get("result")
        if not draw_id:
            errors.append(f"line {line_no}: missing draw id")
            continue
        try:
            parsed_date = date.fromisoformat(raw_date[:10])
        except ValueError:
            errors.append(f"line {line_no}: invalid date {raw_date!r}")
            continue
        result_error = validate_result(game, result)
        if result_error:
            errors.append(f"line {line_no}, draw {draw_id}: {result_error}")
            continue
        if draw_id in seen_ids:
            errors.append(f"duplicate draw id: {draw_id}")
            continue
        key = (raw_date[:10], draw_id)
        if key in seen_date_ids:
            errors.append(f"duplicate date/id: {key}")
            continue
        seen_ids.add(draw_id)
        seen_date_ids.add(key)
        if game == "POWER655" and isinstance(result, list) and len(result) == 6:
            missing_bonus_count += 1
        if draw_id.isdigit():
            numeric_id = int(draw_id)
            id_numbers.add(numeric_id)
            if previous_numeric_id is not None and numeric_id <= previous_numeric_id:
                id_order_anomalies.append({
                    "line": line_no, "previous_id": str(previous_numeric_id),
                    "current_id": draw_id, "date": parsed_date.isoformat()
                })
            previous_numeric_id = numeric_id
        records.append((parsed_date, draw_id))

    if not records:
        errors.append("no valid records")
    if errors:
        raise RuntimeError(f"{game}: validation failed ({len(errors)} issue(s)); first issues: " + " | ".join(errors[:8]))

    numeric_ids = sorted(id_numbers)
    gaps = []
    if len(numeric_ids) > 1:
        for left, right in zip(numeric_ids, numeric_ids[1:]):
            if right - left > 1:
                gaps.append({"after": str(left), "before": str(right), "missing_count": right-left-1})
                if len(gaps) >= 100:
                    break

    dates = [x[0] for x in records]
    return {
        "records": len(records),
        "first_date": min(dates).isoformat(),
        "latest_date": max(dates).isoformat(),
        "first_draw_id": records[dates.index(min(dates))][1],
        "latest_draw_id": records[dates.index(max(dates))][1],
        "numeric_id_count": len(numeric_ids),
        "numeric_id_gaps": gaps,
        "id_order_anomalies": id_order_anomalies[:20],
        "id_order_anomaly_count": len(id_order_anomalies),
        "missing_bonus_count": missing_bonus_count,
        "numeric_id_gap_count_sampled": len(gaps),
        "sha256": None,
    }

def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_repository": "https://github.com/vietvudanh/vietlott-data",
        "source_note": "Third-party mirror stating that results are collected from vietlott.vn; cross-check important records against official Vietlott publications.",
        "games": {},
        "status": "ok",
    }
    staged = []
    failures = []
    for game, (filename, remote_name) in GAMES.items():
        url = BASE + remote_name
        print(f"Downloading {game}: {url}", flush=True)
        try:
            payload = fetch(url)
            summary = audit_payload(game, payload)
            summary["sha256"] = hashlib.sha256(payload).hexdigest()
            summary["bytes"] = len(payload)
            summary["source_url"] = url
            summary["numeric_id_gaps"] = summary["numeric_id_gaps"][:20]
            warnings = []
            if summary["numeric_id_gap_count_sampled"]:
                warnings.append("Numeric draw-id gaps detected")
            if summary["id_order_anomaly_count"]:
                warnings.append("Draw IDs are not in ascending source order")
            if summary["missing_bonus_count"]:
                warnings.append(f"{summary['missing_bonus_count']} Power 6/55 record(s) have no special number")
            if warnings:
                summary["warning"] = "; ".join(warnings) + ". Inspect source history before treating archive as complete."
                manifest["status"] = "warning"
            manifest["games"][game] = summary
            staged.append((DATA_DIR / filename, payload))
            print(
                f"OK {game}: {summary['records']:,} records; "
                f"{summary['first_date']} -> {summary['latest_date']}; "
                f"ID gaps(sample)={summary['numeric_id_gap_count_sampled']}",
                flush=True,
            )
        except Exception as exc:
            failures.append(f"{game}: {exc}")
            print(f"ERROR {game}: {exc}", file=sys.stderr, flush=True)

    if failures:
        manifest["status"] = "failed"
        manifest["errors"] = failures
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError("One or more game datasets failed; existing data snapshots were not replaced. " + " | ".join(failures))

    # Replace snapshots only after all seven downloads have passed validation.
    for path, payload in staged:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(payload)
        os.replace(tmp, path)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"All {len(GAMES)} datasets validated. Manifest: {MANIFEST}", flush=True)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(1)
