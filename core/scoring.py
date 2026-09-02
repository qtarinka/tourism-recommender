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


MATCH_LEVEL_BY_SCORE = {3: "excellent", 2: "very_good", 1: "good", 0: "limited"}


@dataclass
class ScoredDestination:
    destination: Destination
    score: int
    trip_length_match: bool
    seasonal_risk_match: bool
    msz_status_match: bool
    active_seasonal_risks: list
    current_msz_level: Optional[int]

    @property
    def match_level(self) -> str:
        """A human-facing match tier ('excellent'..'limited') instead of a
        bare score -- callers look this up in core.i18n for the actual
        label text, keeping this module free of any UI/language concern."""
        return MATCH_LEVEL_BY_SCORE[self.score]

    def explanation_items(self):
        """Returns (matched: bool, positive_i18n_key, negative_i18n_key)
        for each of the 3 scored criteria, in the same order they're
        summed for `score`. Callers pick positive/negative text based on
        `matched` -- this keeps the *reasoning* (which criteria, in what
        order) in one place shared by every UI surface that explains a
        recommendation, rather than each screen re-deriving it."""
        return [
            (self.trip_length_match, "explain_trip_length_pos", "explain_trip_length_neg"),
            (self.seasonal_risk_match, "explain_seasonal_pos", "explain_seasonal_neg"),
            (self.msz_status_match, "explain_msz_pos", "explain_msz_neg"),
        ]


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
    """Scores and ranks the given destinations against one shared set of
    criteria. This is the single scoring/ranking entry point for both
    "recommendation mode" (called with all destinations) and "comparison
    mode" (called with only the user's selected destinations) -- there is
    deliberately no separate comparison algorithm; comparison is just this
    same function called with a smaller candidate list, per the unified
    decision-support design (see docs/DEVELOPMENT_DOCUMENTATION.md)."""
    scored = [
        score_destination(d, trip_length_days, travel_month, risk_tolerance)
        for d in destinations if d.is_active
    ]
    scored.sort(key=lambda s: (-s.score, s.destination.name_en))
    return scored


def low_risk_months(destination: Destination, max_severity: int = 1) -> list:
    """Months (1-12) with no recorded seasonal risk above `max_severity`
    for this destination, derived from the same `seasonal_risks` data the
    scoring above uses -- an honest, data-backed answer to "when's a good
    time to go", not a fabricated climate/season judgement. A destination
    with no seasonal_risks rows at all returns all 12 months; callers
    should phrase that as "nothing on record" rather than "guaranteed
    perfect," since an empty risk list only means nothing was entered,
    not that nothing could happen."""
    risky_months = {r.month for r in destination.seasonal_risks if r.severity > max_severity}
    return [m for m in range(1, 13) if m not in risky_months]
