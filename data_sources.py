"""Load the repository's audited Vietlott snapshots, including the Mega 6/45 historical backfill."""
import json
import requests
import pandas as pd
import streamlit as st

RAW = "https://raw.githubusercontent.com/luchuuthanh/Vietlott-XSMN-Analysis/main/data/vietlott/{file}"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_vietlott(game):
    key = {"POWER655": "power655.jsonl", "MEGA645": "power645.jsonl"}.get(str(game).upper())
    if not key:
        raise ValueError("Chỉ hỗ trợ POWER655 và MEGA645.")
    response = requests.get(RAW.format(file=key), timeout=30)
    response.raise_for_status()
    records = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    rows = []
    for item in records:
        nums = item.get("result") or item.get("numbers") or item.get("winning_numbers")
        if isinstance(nums, str):
            nums = [int(x) for x in nums.replace(",", " ").split() if x.isdigit()]
        if not isinstance(nums, list) or len(nums) < 6:
            continue
        main = [int(x) for x in nums[:6]]
        universe = 55 if str(game).upper() == "POWER655" else 45
        if len(set(main)) != 6 or any(n < 1 or n > universe for n in main):
            continue
        # POWER655's seventh value is NOT a seventh main number. It is drawn
        # separately from the 49 remaining balls and is only used for Jackpot 2.
        special = None
        if str(game).upper() == "POWER655" and len(nums) > 6:
            try:
                candidate = int(nums[6])
                if 1 <= candidate <= 55 and candidate not in main:
                    special = candidate
            except (TypeError, ValueError):
                pass
        rows.append({
            "date": item.get("date"),
            "game": str(game).upper(),
            "draw_id": item.get("id", ""),
            "n1": main[0], "n2": main[1], "n3": main[2],
            "n4": main[3], "n5": main[4], "n6": main[5],
            "special": special if str(game).upper() == "POWER655" else None
        })
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Nguồn trả về dữ liệu nhưng không nhận diện được cấu trúc kỳ quay.")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df
