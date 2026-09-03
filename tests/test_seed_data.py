from core.db import Destination
from core.seed_data import seed_if_empty


def test_seed_populates_20_destinations_17_3_split(db_session):
    seeded = seed_if_empty(db_session)
    assert seeded is True

    destinations = db_session.query(Destination).all()
    assert len(destinations) == 20
    assert sum(1 for d in destinations if d.region == "europe") == 17
    assert sum(1 for d in destinations if d.region == "non_europe") == 3


def test_seed_is_idempotent(db_session):
    seed_if_empty(db_session)
    seeded_again = seed_if_empty(db_session)
    assert seeded_again is False
    assert db_session.query(Destination).count() == 20


def test_every_destination_has_gus_stats_and_msz_warning(db_session):
    seed_if_empty(db_session)
    for dest in db_session.query(Destination).all():
        assert dest.gus_stats is not None
        assert len(dest.msz_warnings) >= 1
        assert dest.current_currency_rate is not None
