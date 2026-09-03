from unittest.mock import patch, MagicMock

import requests

from core import etl
from core.db import Destination, CurrencyRate


def _fake_response(mid):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"rates": [{"mid": mid}]}
    return resp


def test_fetch_nbp_rate_uses_table_a_when_available():
    with patch("core.etl.requests.get", return_value=_fake_response(4.32)) as mock_get:
        rate = etl.fetch_nbp_rate("EUR")
    assert rate == 4.32
    assert mock_get.call_args[0][0].endswith("/a/eur/?format=json")


def test_fetch_nbp_rate_falls_back_to_table_b():
    responses = [MagicMock(status_code=404), _fake_response(0.65)]

    def side_effect(url, timeout=10):
        return responses.pop(0)

    with patch("core.etl.requests.get", side_effect=side_effect):
        rate = etl.fetch_nbp_rate("EGP")
    assert rate == 0.65


def test_fetch_nbp_rate_returns_none_when_unreachable():
    with patch("core.etl.requests.get", side_effect=requests.exceptions.ConnectionError("boom")):
        rate = etl.fetch_nbp_rate("XYZ")
    assert rate is None


def test_fetch_nbp_rate_pln_shortcircuits_without_network_call():
    with patch("core.etl.requests.get") as mock_get:
        rate = etl.fetch_nbp_rate("PLN")
    assert rate == 1.0
    mock_get.assert_not_called()


def test_refresh_msz_warnings_skips_when_url_unset():
    with patch.object(etl, "MSZ_RSS_URL", ""):
        # Should return immediately without touching the database or network.
        etl.refresh_msz_warnings()


def test_refresh_currency_rates_inserts_new_row_each_run_not_updates(db_session):
    """Historical trend data (for Power BI) requires every ETL run to add
    a new row rather than overwrite the previous one -- this is the
    behavior that was requested and changed; regression-guard it
    directly rather than relying on it being implied by other tests."""
    dest = Destination(name_en="Testland", name_pl="Testlandia", country_en="Testland",
                        country_pl="Testlandia", region="europe", currency_code="EUR")
    db_session.add(dest)
    db_session.commit()
    db_session.refresh(dest)

    with patch.object(etl, "get_session", return_value=db_session), \
         patch.object(etl, "fetch_nbp_rate", return_value=4.30):
        etl.refresh_currency_rates()
    with patch.object(etl, "get_session", return_value=db_session), \
         patch.object(etl, "fetch_nbp_rate", return_value=4.35):
        etl.refresh_currency_rates()

    rows = db_session.query(CurrencyRate).filter_by(destination_id=dest.destination_id).all()
    assert len(rows) == 2
    assert {r.rate_to_pln for r in rows} == {4.30, 4.35}
