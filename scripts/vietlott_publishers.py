"""Cross-check recent draw cards from two result publishers."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

PAGES = {
    "POWER535": ("lotto535", "lotto-535"),
    "MEGA645": ("mega", "mega-6-45"),
    "POWER655": ("power", "power-655"),
}


def read_cards(url):
    with urlopen(url, timeout=12) as response:
        html = response.read().decode("utf-8")
    cards = {}
    if url.startswith("https://xsmn.net/"):
        for card in re.findall(r'<article class="vk [^"]*">(.*?)</article>', html, re.S):
            heading = re.search(r'/ngay-(\d{2})-(\d{2})-(\d{4})">Vé [^<]* kỳ (\d+)</a>', card)
            balls = re.search(r'<ol class="vk-o"[^>]*>(.*?)</ol>', card, re.S)
            if heading and balls:
                d, m, y, number = heading.groups()
                cards[int(number)] = (f"{y}-{m}-{d}", list(map(int, re.findall(r'<li[^>]*>(\d+)</li>', balls[1]))))
    else:
        for number, d, m, y, balls in re.findall(
            r'<div class="title_tt">Kỳ vé #(\d+)\s*\|[^<]*?(\d{2})/(\d{2})/(\d{4})[^<]*</div>\s*'
            r'<div class="box_ketqua">(.*?)</div>', html, re.S
        ):
            cards[int(number)] = (f"{y}-{m}-{d}", list(map(int, re.findall(r'<span class="ball [^"]*">(\d+)</span>', balls))))
    return cards


def extend_archive(game, payload, archive, validate, today):
    if game not in PAGES:
        return payload
    rows = {int(row["id"]): row for row in map(json.loads, payload.splitlines())}
    original = set(rows)
    if archive.exists():
        for line in archive.read_bytes().splitlines():
            saved = json.loads(line)
            key = int(saved["id"])
            if saved.get("data_source") == "secondary_cross_check" and key in rows:
                if any(saved[field] != rows[key][field] for field in ("date", "result")):
                    raise ValueError(f"{game} draw {key}: upstream disagrees with archived result")
            if key not in rows:
                if saved.get("data_source") != "secondary_cross_check":
                    raise ValueError(f"{game}: upstream lost archived draw {key}")
                if key <= max(original):
                    raise ValueError(f"{game}: upstream missing interior draw {key}")
                rows[key] = saved

    left, right = PAGES[game]
    urls = [f"https://xsmn.net/kqxs{left}", f"https://www.ketquadientoan.com/ket-qua-xo-so-dien-toan-{right}.html"]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(read_cards, urls)
    except (OSError, UnicodeError) as err:
        print(f"{game}: publisher unavailable: {err}", flush=True)
    else:
        latest = max(rows)
        for key in sorted(first.keys() & second.keys()):
            if key <= latest:
                continue
            day, balls = first[key]
            if key != latest + 1 or first[key] != second[key]:
                break
            if not rows[latest]["date"][:10] <= day <= today.isoformat() or validate(game, balls):
                break
            if game == "POWER655" and len(balls) != 7:
                break
            rows[key] = {"date": day, "id": f"{key:05d}", "result": balls,
                         "data_source": "secondary_cross_check", "source_urls": urls}
            latest = key
    # Preserve the upstream representation and all validated historical rows.
    extra = [rows[key] for key in sorted(rows.keys() - original)]
    if not extra:
        return payload
    return payload.rstrip(b"\n") + b"\n" + b"".join(
        (json.dumps(row, separators=(",", ":")) + "\n").encode() for row in extra
    )
