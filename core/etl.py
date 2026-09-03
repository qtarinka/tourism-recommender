"""
ETL: refreshes currency_rates (live) and msz_safety_warnings (live, best-effort).

NBP exchange rates: uses the public NBP web API (api.nbp.pl), no auth
required. Table A covers most major currencies daily; a handful of less
common ones (e.g. EGP, TND) only appear in table B, so we try A then B.
This part is verified against NBP's documented, stable public API.

MSZ travel warnings: MSZ does not publish a documented, stable RSS/JSON
feed with a machine-readable 1-4 warning level. MSZ_RSS_URL is left
configurable via .env; if unset (the default) or unreachable, the ETL
run logs a message and leaves existing data untouched rather than
guessing at a feed structure that hasn't been verified. See
docs/DEVELOPMENT_DOCUMENTATION.md ("Known limitations") -- this is a
documented scope gap, not a bug.
"""
import logging
import os

import requests

from core.db import get_session, Destination, CurrencyRate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("etl")

NBP_BASE = "https://api.nbp.pl/api/exchangerates/rates"
MSZ_RSS_URL = os.environ.get("MSZ_RSS_URL", "")


def fetch_nbp_rate(currency_code: str):
    if currency_code.upper() == "PLN":
        return 1.0
    for table in ("a", "b"):
        url = f"{NBP_BASE}/{table}/{currency_code.lower()}/?format=json"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return float(data["rates"][0]["mid"])
        except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
            log.debug("NBP lookup failed for %s on table %s: %s", currency_code, table, exc)
    return None


def refresh_currency_rates():
    """Inserts a new CurrencyRate row per destination every run rather
    than updating one in place, so the table accumulates a genuine rate
    history over time (each row's fetched_at is one point in that
    history) instead of only ever holding the latest value. The app reads
    "the current rate" via Destination.current_currency_rate (the most
    recent row), not by assuming there's only one row -- see core/db.py."""
    session = get_session()
    try:
        destinations = session.query(Destination).all()
        codes = {d.currency_code for d in destinations}
        rate_by_code = {}
        for code in codes:
            rate = fetch_nbp_rate(code)
            if rate is not None:
                rate_by_code[code] = rate
                log.info("NBP rate for %s: %.4f PLN", code, rate)
            else:
                log.warning("Could not fetch NBP rate for %s; leaving previous value", code)

        inserted = 0
        for dest in destinations:
            rate = rate_by_code.get(dest.currency_code)
            if rate is None:
                continue
            session.add(CurrencyRate(destination_id=dest.destination_id, rate_to_pln=rate))
            inserted += 1
        session.commit()
        log.info("Currency rates: %d new historical rows inserted.", inserted)
    finally:
        session.close()


def refresh_msz_warnings():
    if not MSZ_RSS_URL:
        log.info("MSZ_RSS_URL not configured; skipping MSZ refresh (existing data kept).")
        return

    try:
        import feedparser
    except ImportError:
        log.warning("feedparser not installed; skipping MSZ refresh.")
        return

    try:
        feed = feedparser.parse(MSZ_RSS_URL)
    except Exception as exc:  # feedparser rarely raises, but network layers can
        log.warning("MSZ feed fetch failed: %s", exc)
        return

    if getattr(feed, "bozo", 0) and not feed.entries:
        log.warning("MSZ feed could not be parsed (bozo=%s); skipping.", feed.bozo_exception)
        return

    session = get_session()
    try:
        destinations = session.query(Destination).all()
        matched = 0
        for entry in feed.entries:
            title = (entry.get("title") or "").lower()
            for dest in destinations:
                if dest.country_pl.lower() in title:
                    # Feed doesn't expose a documented numeric level; default to
                    # "elevated attention" (2) whenever the country is mentioned
                    # at all, since presence in the feed implies an active advisory.
                    # Verify/refine against the real feed once MSZ_RSS_URL is set.
                    from core.db import MszSafetyWarning
                    warning = MszSafetyWarning(
                        destination_id=dest.destination_id,
                        level=2,
                        message_pl=entry.get("title", ""),
                        message_en=entry.get("title", ""),
                        source_url=entry.get("link"),
                    )
                    session.add(warning)
                    matched += 1
        session.commit()
        log.info("MSZ refresh matched %d advisory entries.", matched)
    finally:
        session.close()


def run_all():
    log.info("Starting ETL run.")
    refresh_currency_rates()
    refresh_msz_warnings()
    log.info("ETL run complete.")
