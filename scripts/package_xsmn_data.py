from __future__ import annotations
import csv
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CSV_FILE = DATA / "xsmn_5y_canonical.csv"
META_FILE = DATA / "xsmn_5y_canonical.json"
OUT_DIR = ROOT / "dist"
ZIP_FILE = OUT_DIR / "XSMN_5Y_DATA.zip"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> None:
    if not CSV_FILE.is_file() or not META_FILE.is_file():
        raise SystemExit("Missing canonical CSV or metadata JSON")
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    if meta.get("status") != "PASS":
        raise SystemExit("Canonical metadata status is not PASS")
    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("CSV header is missing")
        rows = sum(1 for _ in reader)
    expected = int(meta["rows"])
    if rows != expected:
        raise SystemExit(f"CSV row mismatch: expected {expected}, got {rows}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checksum = (
        f"{sha256(CSV_FILE)}  data/xsmn_5y_canonical.csv\n"
        f"{sha256(META_FILE)}  data/xsmn_5y_canonical.json\n"
    )
    sums_file = OUT_DIR / "SHA256SUMS.txt"
    sums_file.write_text(checksum, encoding="utf-8")
    files = [
        (CSV_FILE, "data/xsmn_5y_canonical.csv"),
        (META_FILE, "data/xsmn_5y_canonical.json"),
        (ROOT / "README_DATA.md", "README_DATA.md"),
        (sums_file, "SHA256SUMS.txt"),
    ]
    with zipfile.ZipFile(ZIP_FILE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path, archive_name in files:
            z.write(path, archive_name)
    print(f"PASS: {rows} data rows; {len(files)} files packaged; {ZIP_FILE.stat().st_size} bytes")
    print(checksum, end="")

if __name__ == "__main__":
    main()
