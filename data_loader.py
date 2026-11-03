"""Đọc và chuẩn hóa CSV người dùng cung cấp."""
import pandas as pd

VIETLOTT_REQUIRED = ["date", "game", "draw_id", "n1", "n2", "n3", "n4", "n5", "n6"]

def load_vietlott(file):
    df = pd.read_csv(file)
    missing = [c for c in VIETLOTT_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError("Thiếu cột: " + ", ".join(missing))
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
    for c in VIETLOTT_REQUIRED[3:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=VIETLOTT_REQUIRED).copy()
    df["game"] = df["game"].astype(str).str.upper().str.strip()
    return df.sort_values(["game", "date", "draw_id"]).reset_index(drop=True)

def load_xsmn(file):
    df = pd.read_csv(file, dtype={"number": str})
    required = ["date", "province", "prize", "number"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Thiếu cột: " + ", ".join(missing))
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["province"] = df["province"].astype(str).str.strip()
    df["prize"] = df["prize"].astype(str).str.strip()
    df["number"] = df["number"].astype(str).str.replace(r"\\D", "", regex=True).str.zfill(2)
    df = df.dropna(subset=["date"])
    df = df[df["number"].str.len().between(2, 6)]
    df["last2"] = df["number"].str[-2:].astype(int)
    return df.sort_values(["date", "province", "prize"]).reset_index(drop=True)
