"""
Recommendation scoring algorithm.

Score = trip_length_match + seasonal_risk_match + msz_status_match
Each term contributes 0 or 1 point (max score = 3), matching the thesis's
simple, transparent point-based model (chapter 4.4). Budget, currency and
organization style are deliberately excluded from the score -- they are
context for the user's decision, not scored criteria (same treatment the
thesis specifies for currency/organization style; see docs for rationale).
"""
from dataclasses import dataclass
from typing import Optional

from core.db import Destination

TRIP_LENGTH_TOLERANCE_DAYS = 2

RISK_TOLERANCE_TO_MSZ_MAX = {"low": 1, "medium": 2, "high": 3}
RISK_TOLERANCE_TO_SEASONAL_MAX = {"low": 1, "medium": 2, "high": 3}


@dataclass
class ScoredDestination:
    destination: Destination
    score: int
    trip_length_match: bool
    seasonal_risk_match: bool
    msz_status_match: bool
    active_seasonal_risks: list
    current_msz_level: Optional[int]


def score_destination(destination: Destination, trip_length_days: int, travel_month: int,
                       risk_tolerance: str) -> ScoredDestination:
    stat = destination.gus_stats
    avg_stay = stat.avg_stay_length_days if stat else trip_length_days
    trip_length_match = abs(trip_length_days - avg_stay) <= TRIP_LENGTH_TOLERANCE_DAYS

    month_risks = [r for r in destination.seasonal_risks if r.month == travel_month]
    seasonal_max = RISK_TOLERANCE_TO_SEASONAL_MAX[risk_tolerance]
    seasonal_risk_match = all(r.severity <= seasonal_max for r in month_risks)

    current_level = max((w.level for w in destination.msz_warnings), default=1)
    msz_max = RISK_TOLERANCE_TO_MSZ_MAX[risk_tolerance]
    msz_status_match = current_level <= msz_max

    score = int(trip_length_match) + int(seasonal_risk_match) + int(msz_status_match)

    return ScoredDestination(
        destination=destination,
        score=score,
        trip_length_match=trip_length_match,
        seasonal_risk_match=seasonal_risk_match,
        msz_status_match=msz_status_match,
        active_seasonal_risks=month_risks,
        current_msz_level=current_level,
    )


def rank_destinations(destinations, trip_length_days: int, travel_month: int,
                       risk_tolerance: str) -> list:
    scored = [
        score_destination(d, trip_length_days, travel_month, risk_tolerance)
        for d in destinations if d.is_active
    ]
    scored.sort(key=lambda s: (-s.score, s.destination.name_en))
    return scored
