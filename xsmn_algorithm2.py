"""Hidden cross-station consensus engine for XSMN Algorithm 2.

The UI receives only number bundles and the two station groups. Method votes,
station overlap and intermediate scores remain internal.
"""
from __future__ import annotations

from collections import Counter

from xsmn_hit_analysis import METHODS, _score_vector, build_scope_history


def build_algorithm2(frame, stations, scope, top_k=10, min_history=30):
    """Build per-station bundles using prior-only, prize-specific history.

    Each of the six existing ranking methods votes for its top_k numbers.
    The station bundle is the top_k numbers with the most method votes.
    A station is Priority when at least one of its bundle numbers is also
    selected by another station for this same prize; otherwise it is Review.
    """
    station_bundles = {}
    station_votes = {}
    for station in stations:
        history = build_scope_history(frame, station, scope)
        if len(history) < max(1, int(min_history)):
            continue
        votes = Counter()
        rank_total = Counter()
        for method in METHODS:
            scores = _score_vector(history, method)
            ordered = sorted(range(100), key=lambda n: (-scores[n], n))[:int(top_k)]
            for rank, number in enumerate(ordered, start=1):
                votes[number] += 1
                rank_total[number] += rank
        ordered_bundle = sorted(
            votes,
            key=lambda n: (-votes[n], rank_total[n] / votes[n], n),
        )[:int(top_k)]
        station_bundles[str(station)] = [f"{n:02d}" for n in ordered_bundle]
        station_votes[str(station)] = {f"{n:02d}": int(votes[n]) for n in ordered_bundle}

    station_support = Counter(
        number
        for bundle in station_bundles.values()
        for number in set(bundle)
    )
    priority, review = {}, {}
    for station, bundle in station_bundles.items():
        if any(station_support[number] >= 2 for number in bundle):
            priority[station] = bundle
        else:
            review[station] = bundle

    bold_numbers = {
        number for number, station_count in station_support.items()
        if station_count >= 2
    }
    return {
        "priority": priority,
        "review": review,
        "bold_numbers": bold_numbers,
        # Internal diagnostics are intentionally not rendered in the app.
        "method_votes": station_votes,
        "station_support": dict(station_support),
    }
