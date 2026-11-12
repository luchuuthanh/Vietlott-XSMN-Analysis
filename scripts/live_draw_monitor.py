#!/usr/bin/env python3
"""Capture and index public Vietlott Mega 6/45 / Power 6/55 live-draw evidence.

This stores timestamped sampled frames and OCR observations, not a full re-hosted
broadcast. A SHA-256 digest is recorded for every sampled frame. A digest proves
the saved sample has not changed since capture; it does not certify the source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

try:
    import yt_dlp
except Exception:
    yt_dlp = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from live_result_detector import parse_large_numeric_tokens, consensus_events, classify_sequence
except Exception:
    parse_large_numeric_tokens = None
    consensus_events = None
    classify_sequence = None

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "data" / "live_evidence"
INDEX_PATH = EVIDENCE_ROOT / "sessions.jsonl"
OFFICIAL_HOME = "https://vietlott.vn/"
OFFICIAL_LIVE = "https://vietlott.vn/vi/trung-thuong/truc-tiep-quay-so-mo-thuong"
OFFICIAL_VIDEO_LIST = "https://vietlott.vn/vi/trung-thuong/danh-sach-video-quay-so-mo-thuong-645"
DRAW_MINUTES = 30
SAMPLE_SECONDS = 2
USER_AGENT = "Mozilla/5.0 (compatible; VietlottLiveEvidenceMonitor/1.0)"


def now_vn() -> datetime:
    return datetime.now(TZ)


def game_for_date(day):
    # Python weekday: Monday=0. Mega: Wed/Fri/Sun. Power: Tue/Thu/Sat.
    if day.weekday() in (1, 3, 5):
        return "POWER655"
    if day.weekday() in (2, 4, 6):
        return "MEGA645"
    return None


def game_label(game):
    return "Power 6/55" if game == "POWER655" else "Mega 6/45"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def youtube_urls_from_html(html: str):
    urls = set()
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(["iframe", "a", "source"]):
        raw = node.get("src") or node.get("href") or ""
        if "youtube.com" in raw or "youtube-nocookie.com" in raw or "youtu.be" in raw:
            urls.add(raw.replace("&amp;", "&"))
    for match in re.findall(r"https?[^\"'\s<>]*(?:youtube\.com|youtu\.be)[^\"'\s<>]*", html):
        urls.add(match.replace("&amp;", "&"))
    return sorted(urls)


def fetch_html(url: str):
    response = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def discover_official_candidates(game: str):
    """Find embeds/live links exposed by Vietlott pages; never search unofficial channels."""
    candidates = []
    notes = []
    pages = [
        OFFICIAL_LIVE + ("?game=Mega645" if game == "MEGA645" else "?game=Power655"),
        OFFICIAL_HOME,
        OFFICIAL_VIDEO_LIST,
        "https://www.facebook.com/vietlott.vn/",
    ]
    for page in pages:
        try:
            html = fetch_html(page)
            found = youtube_urls_from_html(html)
            candidates.extend(found)
            notes.append({"page": page, "status": "ok", "youtube_links_found": len(found)})
            # Official website may expose a channel link; /live is checked by yt-dlp below.
            for url in found:
                if re.search(r"youtube(?:-nocookie)?\.com/(?:@[^/?]+|channel/[^/?]+|user/[^/?]+|c/[^/?]+)/?$", url):
                    candidates.append(url.rstrip("/") + "/live")
        except Exception as exc:
            notes.append({"page": page, "status": "unavailable", "error": str(exc)[:300]})
    # Prefer explicit live pages and embeds, de-duplicate without losing order.
    ordered = []
    seen = set()
    for url in candidates:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered, notes


def extract_live_info(url: str):
    if yt_dlp is None:
        raise RuntimeError("Thiếu yt-dlp; hãy cài requirements.txt.")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 20,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Nguồn không trả về metadata video.")
    if info.get("is_live") is not True:
        raise RuntimeError("Nguồn tìm thấy không được xác nhận đang phát trực tiếp.")
    formats = info.get("formats") or []
    usable = [
        item for item in formats
        if item.get("url") and (
            "m3u8" in str(item.get("protocol", "")) or
            item.get("vcodec") not in (None, "none")
        )
    ]
    if usable:
        usable.sort(key=lambda x: (x.get("height") or 0, x.get("tbr") or 0))
        chosen = usable[-1]
        stream_url = chosen["url"]
        headers = chosen.get("http_headers") or info.get("http_headers") or {}
    else:
        stream_url = info.get("url")
        headers = info.get("http_headers") or {}
    if not stream_url:
        raise RuntimeError("Không lấy được địa chỉ luồng phát.")
    return {
        "page_url": url,
        "stream_url": stream_url,
        "headers": headers,
        "video_id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "is_live": True,
    }


def resolve_source(game: str, explicit_url: str | None):
    manual = explicit_url or os.getenv("VIETLOTT_LIVE_URL", "").strip()
    candidates = [manual] if manual else discover_official_candidates(game)[0]
    discovery_notes = []
    for candidate in candidates:
        try:
            info = extract_live_info(candidate)
            info["source_mode"] = "manual_url" if manual else "official_site_discovery"
            info["discovery_notes"] = discovery_notes
            return info
        except Exception as exc:
            discovery_notes.append({"candidate": candidate, "error": str(exc)[:300]})
    # Preserve page discovery failures in the evidence report.
    if not manual:
        _, page_notes = discover_official_candidates(game)
        discovery_notes.extend(page_notes)
    raise RuntimeError("Không tìm thấy luồng trực tiếp đã xác minh. " + json.dumps(discovery_notes, ensure_ascii=False)[:2500])


def wait_until_draw_start():
    start = now_vn().replace(hour=18, minute=0, second=0, microsecond=0)
    if now_vn() < start:
        delay = (start - now_vn()).total_seconds()
        print(f"Chờ đến 18:00 giờ Việt Nam ({int(delay)} giây).", flush=True)
        time.sleep(max(0, delay))


def ffmpeg_capture(source, output_dir: Path, duration: int):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Không tìm thấy ffmpeg.")
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = source.get("headers") or {}
    header_text = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-rw_timeout", "20000000"]
    if header_text:
        command += ["-headers", header_text]
    command += [
        "-i", source["stream_url"],
        "-t", str(max(1, duration)),
        "-vf", f"fps=1/{SAMPLE_SECONDS},scale='min(1280,iw)':-2",
        "-q:v", "4",
        str(output_dir / "frame_%05d.jpg"),
    ]
    print("Bắt đầu lấy khung hình từ luồng trực tiếp.", flush=True)
    result = subprocess.run(command, capture_output=True, text=True, timeout=duration + 180)
    frames = sorted(output_dir.glob("frame_*.jpg"))
    if result.returncode != 0 and not frames:
        raise RuntimeError((result.stderr or "ffmpeg capture failed")[-2500:])
    if result.returncode != 0 and frames:
        print("Luồng kết thúc hoặc gián đoạn sớm; giữ lại các khung hình đã thu được.", flush=True)
    return frames


def ocr_text(image_path: Path, universe: int):
    if pytesseract is None:
        return "", "ocr_library_missing", []
    try:
        image = Image.open(image_path).convert("RGB")
        text = pytesseract.image_to_string(image, lang="vie+eng", config="--psm 6")
        data = pytesseract.image_to_data(
            image, lang="eng", config="--psm 11", output_type=pytesseract.Output.DICT
        )
        candidates = (
            parse_large_numeric_tokens(data, image.width, image.height, universe)
            if parse_large_numeric_tokens else []
        )
        return " ".join(text.split()), "ok", candidates
    except Exception as exc:
        return "", "ocr_error:" + str(exc)[:120], []


def is_candidate(text: str):
    normalized = text.upper().replace(" ", "")
    has_vali_code = bool(re.search(r"VA[-_:]?[1-4]", normalized))
    keywords = any(word in normalized for word in ("NIÊMPHONG", "NIEMPHONG", "VALI", "BÓNG", "BONG", "CHỌN", "CHON"))
    has_serial = bool(re.search(r"\b\d{5,8}\b", text))
    return has_vali_code or keywords or has_serial, has_vali_code


def make_contact_sheet(items, output_path: Path):
    if not items:
        return None
    thumb_w, thumb_h, label_h = 320, 180, 34
    columns = 3
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(items):
        image = Image.open(item["path"]).convert("RGB")
        image.thumbnail((thumb_w, thumb_h))
        x = (index % columns) * thumb_w
        y = (index // columns) * (thumb_h + label_h)
        sheet.paste(image, (x, y))
        label = f"{item['elapsed_seconds']}s | {item['ocr_text'][:34].encode('ascii', 'replace').decode()}"
        draw.text((x + 4, y + thumb_h + 3), label, fill="black")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=82, optimize=True)
    return output_path


def load_expected_draw_id(game: str, draw_date: str):
    """Only estimate the next ID when the local result snapshot is fresh."""
    manifest = ROOT / "data" / "vietlott" / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        game_data = data["games"][game]
        latest_date = datetime.strptime(game_data["latest_date"], "%Y-%m-%d").date()
        target_date = datetime.strptime(draw_date, "%Y-%m-%d").date()
        if (target_date - latest_date).days > 4 or target_date < latest_date:
            return None
        latest = int(game_data["latest_draw_id"])
        return f"{latest + 1:05d}"
    except Exception:
        return None


def capture(game: str, explicit_url: str | None, duration_override: int | None = None):
    started = now_vn()
    draw_date = started.date().isoformat()
    session_id = f"{draw_date}_{game.lower()}"
    session_dir = EVIDENCE_ROOT / "sessions" / game / draw_date
    session_dir.mkdir(parents=True, exist_ok=True)
    # Full 5-second samples are retained in the Actions artifact, not committed to Git.
    temp_dir = ROOT / "artifacts" / "live_evidence" / game / draw_date / "all_sampled_frames"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    draw_start = started.replace(hour=18, minute=0, second=0, microsecond=0)
    draw_end = draw_start + timedelta(minutes=DRAW_MINUTES)
    remaining = int((draw_end - now_vn()).total_seconds())
    duration = max(1, min(duration_override or DRAW_MINUTES, remaining))
    report = {
        "session_id": session_id,
        "game": game,
        "game_label": game_label(game),
        "draw_date": draw_date,
        "expected_draw_id": load_expected_draw_id(game, draw_date),
        "scheduled_start_vn": draw_start.isoformat(),
        "scheduled_end_vn": draw_end.isoformat(),
        "capture_started_vn": started.isoformat(),
        "status": "starting",
        "sample_interval_seconds": SAMPLE_SECONDS,
        "evidence_note": "Khung hình trích từ nguồn phát công khai; SHA-256 chỉ chứng minh tệp mẫu không bị thay đổi sau khi lưu, không thay thế biên bản chính thức của Vietlott.",
        "actions_run_url": os.getenv("GITHUB_RUN_URL", ""),
    }
    try:
        source = resolve_source(game, explicit_url)
        report["source"] = {
            "page_url": source["page_url"],
            "video_id": source.get("video_id"),
            "title": source.get("title"),
            "channel": source.get("channel"),
            "source_mode": source.get("source_mode"),
            "is_live_confirmed_by_extractor": True,
            "discovery_notes": source.get("discovery_notes", []),
        }
        if "facebook.com" in source["page_url"]:
            # Vietlott's Facebook live is a short preview, not the full 30-minute broadcast.
            duration = min(duration, 300)
            report["facebook_preview_limited_to_seconds"] = duration
        report["capture_duration_seconds"] = duration
        frames = ffmpeg_capture(source, temp_dir, duration)
        if not frames:
            raise RuntimeError("Luồng đã mở nhưng không trích xuất được khung hình.")
        saved_items = []
        frame_rows = []
        ocr_states = {}
        universe = 55 if game == "POWER655" else 45
        for index, frame in enumerate(frames):
            elapsed = index * SAMPLE_SECONDS
            text, ocr_state, numeric_candidates = ocr_text(frame, universe)
            ocr_states[ocr_state] = ocr_states.get(ocr_state, 0) + 1
            candidate, has_va_code = is_candidate(text)
            # Keep a visual baseline every 30 seconds, denser in the first 2 minutes.
            baseline = (elapsed <= 120 and elapsed % 10 == 0) or (elapsed > 120 and elapsed % 30 == 0)
            keep = candidate or baseline
            digest = sha256_file(frame)
            saved_name = None
            if keep:
                saved_name = f"evidence_{elapsed:04d}s_{'candidate' if candidate else 'sample'}.jpg"
                target = session_dir / saved_name
                shutil.copy2(frame, target)
                saved_items.append({
                    "path": target,
                    "elapsed_seconds": elapsed,
                    "ocr_text": text,
                })
            frame_rows.append({
                "frame_index": index,
                "elapsed_seconds": elapsed,
                "sha256": digest,
                "ocr_text": text,
                "ocr_status": ocr_state,
                "candidate": candidate,
                "va_code_detected_by_ocr": has_va_code,
                "numeric_candidates": numeric_candidates,
                "saved_file": saved_name,
            })
        live_events = (
            classify_sequence(consensus_events(frame_rows), game)
            if consensus_events and classify_sequence else []
        )
        live_observations_path = session_dir / "live_observations.json"
        write_json(live_observations_path, {
            "session_id": session_id,
            "game": game,
            "source_url": source.get("page_url"),
            "observations": live_events,
            "warning": "OCR consensus candidates observed on livestream; not yet official Vietlott-confirmed results. Inspect linked evidence frames before relying on them."
        })
        frames_log = session_dir / "frames_ocr.jsonl"
        frames_log.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in frame_rows), encoding="utf-8")
        sheet_path = make_contact_sheet(saved_items, session_dir / "contact_sheet.jpg")
        report.update({
            "status": (
                "partial_capture"
                if (
                    "facebook.com" in (source.get("page_url") or "")
                    or max(0, (len(frames) - 1) * SAMPLE_SECONDS) < DRAW_MINUTES * 60 - 60
                )
                else "captured"
            ),
            "all_sampled_frames_artifact_path": str(temp_dir.relative_to(ROOT)),
            "capture_finished_vn": now_vn().isoformat(),
            "sampled_frame_count": len(frames),
            "live_observation_count": len(live_events),
            "live_observations": live_events,
            "live_observations_file": str(live_observations_path.relative_to(ROOT)),
            "observed_main_numbers": [item["number"] for item in live_events if item["position"].startswith("main_")],
            "observed_possible_special": next((item["number"] for item in live_events if item["position"] == "possible_special"), None),
            "actual_sampled_span_seconds": max(0, (len(frames) - 1) * SAMPLE_SECONDS),
            "partial_capture": (
                "facebook.com" in (source.get("page_url") or "")
                or max(0, (len(frames) - 1) * SAMPLE_SECONDS) < DRAW_MINUTES * 60 - 60
            ),
            "capture_note": (
                "Đây là livestream xem trước trên Facebook (tối đa khoảng 5 phút), không phải bản phát đủ 30 phút."
                if "facebook.com" in (source.get("page_url") or "") else
                (
                    "Nguồn phát kết thúc/gián đoạn trước thời lượng dự kiến; vẫn giữ các khung hình đã lấy."
                    if max(0, (len(frames) - 1) * SAMPLE_SECONDS) < DRAW_MINUTES * 60 - 60
                    else "Đã lấy mẫu gần hết thời lượng phiên dự kiến."
                )
            ),
            "saved_frame_count": len(saved_items),
            "ocr_status_counts": ocr_states,
            "va_code_candidate_count": sum(1 for row in frame_rows if row["va_code_detected_by_ocr"]),
            "keyword_candidate_count": sum(1 for row in frame_rows if row["candidate"]),
            "contact_sheet": str(sheet_path.relative_to(ROOT)) if sheet_path else None,
            "frames_log": str(frames_log.relative_to(ROOT)),
            "evidence_files": [
                {"file": str(item["path"].relative_to(ROOT)), "sha256": sha256_file(item["path"]),
                 "elapsed_seconds": item["elapsed_seconds"]}
                for item in saved_items
            ],
            "source_stream_hash": None,
            "interpretation": "OCR chỉ gợi ý khung hình cần xem lại. Mã vali chỉ được xác nhận sau khi người kiểm tra nhìn rõ nhãn VA trong ảnh/video.",
        })
    except Exception as exc:
        report.update({
            "status": "capture_failed",
            "capture_finished_vn": now_vn().isoformat(),
            "error": str(exc)[:4000],
        })
    finally:
        # Keep all raw sampled frames for the Actions artifact on success.
        # Remove partial frames after a failed capture.
        if temp_dir.exists() and report.get("status") not in ("captured", "partial_capture"):
            shutil.rmtree(temp_dir, ignore_errors=True)
    write_json(session_dir / "session.json", report)
    append_jsonl(INDEX_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", choices=["AUTO", "MEGA645", "POWER655"], default="AUTO")
    parser.add_argument("--date", help="Ngày quay YYYY-MM-DD; mặc định ngày Việt Nam hiện tại.")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--duration", type=int, default=None)
    parser.add_argument("--wait", action="store_true", help="Chờ đến 18:00 giờ Việt Nam trước khi dò luồng.")
    args = parser.parse_args()
    if args.date:
        draw_day = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        draw_day = now_vn().date()
    game = game_for_date(draw_day) if args.game == "AUTO" else args.game
    if not game:
        print("Hôm nay không có lịch quay Mega 6/45 hoặc Power 6/55.")
        return 0
    if args.wait:
        wait_until_draw_start()
    if now_vn().hour >= 18:
        remaining = int(((now_vn().replace(hour=18, minute=30, second=0, microsecond=0)) - now_vn()).total_seconds())
        if remaining <= 0:
            print("Đã qua khung giờ quay 18:00–18:30; không ghi nhận luồng cũ.")
            return 0
    report = capture(game, args.source_url.strip() or None, args.duration)
    return 0 if report["status"] == "captured" else 2


if __name__ == "__main__":
    sys.exit(main())
