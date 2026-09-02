from core.db import Destination, GusTourismStat, SeasonalRisk, MszSafetyWarning
from core.scoring import (
    score_destination, rank_destinations, low_risk_months, TRIP_LENGTH_TOLERANCE_DAYS,
)


def _make_destination(db_session, avg_stay=7.0, msz_level=1, risks=None):
    dest = Destination(
        name_en="Testland", name_pl="Testlandia", country_en="Testland", country_pl="Testlandia",
        region="europe", currency_code="EUR", is_active=True,
    )
    db_session.add(dest)
    db_session.flush()
    db_session.add(GusTourismStat(destination_id=dest.destination_id, organized_share_pct=30,
                                   individual_share_pct=70, avg_stay_length_days=avg_stay, year=2025))
    db_session.add(MszSafetyWarning(destination_id=dest.destination_id, level=msz_level,
                                     message_pl="x", message_en="x"))
    for month, severity in (risks or []):
        db_session.add(SeasonalRisk(destination_id=dest.destination_id, month=month,
                                     risk_type_en="t", risk_type_pl="t", severity=severity))
    db_session.commit()
    db_session.refresh(dest)
    return dest


def test_trip_length_match_within_tolerance(db_session):
    dest = _make_destination(db_session, avg_stay=7.0)
    scored = score_destination(dest, trip_length_days=7 + TRIP_LENGTH_TOLERANCE_DAYS,
                                travel_month=6, risk_tolerance="medium")
    assert scored.trip_length_match is True


def test_trip_length_match_outside_tolerance(db_session):
    dest = _make_destination(db_session, avg_stay=7.0)
    scored = score_destination(dest, trip_length_days=7 + TRIP_LENGTH_TOLERANCE_DAYS + 1,
                                travel_month=6, risk_tolerance="medium")
    assert scored.trip_length_match is False


def test_msz_status_match_respects_risk_tolerance(db_session):
    dest = _make_destination(db_session, msz_level=3)
    low = score_destination(dest, trip_length_days=7, travel_month=6, risk_tolerance="low")
    high = score_destination(dest, trip_length_days=7, travel_month=6, risk_tolerance="high")
    assert low.msz_status_match is False
    assert high.msz_status_match is True


def test_seasonal_risk_only_considers_selected_month(db_session):
    dest = _make_destination(db_session, risks=[(7, 3)])  # severe risk only in July
    june = score_destination(dest, trip_length_days=7, travel_month=6, risk_tolerance="low")
    july = score_destination(dest, trip_length_days=7, travel_month=7, risk_tolerance="low")
    assert june.seasonal_risk_match is True
    assert july.seasonal_risk_match is False


def test_score_is_sum_of_three_binary_components(db_session):
    dest = _make_destination(db_session, avg_stay=7.0, msz_level=1)
    scored = score_destination(dest, trip_length_days=7, travel_month=6, risk_tolerance="high")
    assert scored.score == 3
    assert scored.score == int(scored.trip_length_match) + int(scored.seasonal_risk_match) + int(scored.msz_status_match)


def test_extreme_inputs_do_not_crash(db_session):
    dest = _make_destination(db_session, avg_stay=1.0, msz_level=4, risks=[(1, 3)])
    scored = score_destination(dest, trip_length_days=365, travel_month=1, risk_tolerance="low")
    assert scored.score == 0


def test_rank_destinations_sorts_descending_and_skips_inactive(db_session):
    good = _make_destination(db_session, avg_stay=7.0, msz_level=1)
    bad = _make_destination(db_session, avg_stay=1.0, msz_level=4, risks=[(6, 3)])
    bad.is_active = False
    db_session.commit()

    ranked = rank_destinations([good, bad], trip_length_days=7, travel_month=6, risk_tolerance="low")
    assert len(ranked) == 1
    assert ranked[0].destination.destination_id == good.destination_id


def test_rank_destinations_with_a_single_candidate_is_comparison_mode(db_session):
    """Comparison mode is just rank_destinations() called with a smaller
    candidate list -- there is no separate comparison algorithm. This
    confirms scoring one destination behaves identically to scoring it
    within a larger set (same score_destination call underneath)."""
    only = _make_destination(db_session, avg_stay=7.0, msz_level=1)
    ranked = rank_destinations([only], trip_length_days=7, travel_month=6, risk_tolerance="high")
    direct = score_destination(only, trip_length_days=7, travel_month=6, risk_tolerance="high")
    assert len(ranked) == 1
    assert ranked[0].score == direct.score
    assert ranked[0].match_level == direct.match_level


def test_match_level_maps_score_to_tier(db_session):
    dest = _make_destination(db_session, avg_stay=7.0, msz_level=1)
    excellent = score_destination(dest, trip_length_days=7, travel_month=6, risk_tolerance="high")
    assert excellent.score == 3
    assert excellent.match_level == "excellent"

    limited = score_destination(dest, trip_length_days=200, travel_month=6, risk_tolerance="high")
    assert limited.score < 3
    assert limited.match_level != "excellent"


def test_explanation_items_align_with_match_booleans(db_session):
    dest = _make_destination(db_session, avg_stay=7.0, msz_level=1, risks=[(6, 3)])
    scored = score_destination(dest, trip_length_days=7, travel_month=6, risk_tolerance="low")
    items = scored.explanation_items()
    assert len(items) == 3
    matched_flags = [matched for matched, _, _ in items]
    assert matched_flags == [scored.trip_length_match, scored.seasonal_risk_match, scored.msz_status_match]
    for matched, pos_key, neg_key in items:
        assert pos_key.startswith("explain_")
        assert neg_key.startswith("explain_")


def test_low_risk_months_excludes_only_high_severity_months(db_session):
    dest = _make_destination(db_session, risks=[(7, 3), (8, 2), (1, 1)])
    ok = low_risk_months(dest, max_severity=1)
    assert 7 not in ok  # severity 3 > 1
    assert 8 not in ok  # severity 2 > 1
    assert 1 in ok      # severity 1 <= 1
    assert len(ok) == 10


def test_low_risk_months_all_months_when_no_risks_recorded(db_session):
    dest = _make_destination(db_session)
    assert low_risk_months(dest) == list(range(1, 13))
