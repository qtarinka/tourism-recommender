"""
Static reference data: the 20-destination dictionary (17 European + 3
non-European, per thesis 3.1), baseline GUS-style tourism stats, and a
handful of illustrative seasonal risks that the admin can extend via the
admin panel.

GUS's public BDL API does not expose the specific "organized vs individual
trips by destination country" breakdown the thesis describes, so the
organized_share_pct/individual_share_pct figures are seeded reference
values, not a live GUS feed -- documented as a scope decision in
docs/DEVELOPMENT_DOCUMENTATION.md. The DB still stores them (matches the
thesis's chapter 4.1 data model exactly), but as of this revision they are
NOT displayed anywhere in the UI (removed on request -- a seeded stat
presented as if it were a live one was misleading). NBP currency rates and
MSZ warnings ARE fetched live by core/etl.py.

avg_daily_cost_pln was removed entirely (model, seed data, UI) on request --
see docs/DEVELOPMENT_DOCUMENTATION.md for the full history of that field.
"""
from core.db import Destination, GusTourismStat, SeasonalRisk, MszSafetyWarning, CurrencyRate

# (name_en, name_pl, country_en, country_pl, region, currency,
#  organized_share_pct, avg_stay_length_days)
_DESTINATIONS = [
    ("Czechia", "Czechy", "Czechia", "Czechy", "europe", "CZK", 18, 4.5),
    ("Austria", "Austria", "Austria", "Austria", "europe", "EUR", 25, 6.0),
    ("Germany", "Niemcy", "Germany", "Niemcy", "europe", "EUR", 15, 4.0),
    ("Croatia", "Chorwacja", "Croatia", "Chorwacja", "europe", "EUR", 22, 8.0),
    ("Italy", "Włochy", "Italy", "Włochy", "europe", "EUR", 35, 7.0),
    ("Spain", "Hiszpania", "Spain", "Hiszpania", "europe", "EUR", 40, 8.0),
    ("Greece", "Grecja", "Greece", "Grecja", "europe", "EUR", 45, 9.0),
    ("France", "Francja", "France", "Francja", "europe", "EUR", 30, 6.5),
    ("Hungary", "Węgry", "Hungary", "Węgry", "europe", "HUF", 20, 4.0),
    ("Slovakia", "Słowacja", "Slovakia", "Słowacja", "europe", "EUR", 15, 4.5),
    ("Slovenia", "Słowenia", "Slovenia", "Słowenia", "europe", "EUR", 24, 6.0),
    ("Portugal", "Portugalia", "Portugal", "Portugalia", "europe", "EUR", 38, 8.5),
    ("Netherlands", "Holandia", "Netherlands", "Holandia", "europe", "EUR", 20, 4.0),
    ("Bulgaria", "Bułgaria", "Bulgaria", "Bułgaria", "europe", "BGN", 42, 8.0),
    ("Cyprus", "Cypr", "Cyprus", "Cypr", "europe", "EUR", 48, 9.5),
    ("Malta", "Malta", "Malta", "Malta", "europe", "EUR", 44, 7.0),
    ("United Kingdom", "Wielka Brytania", "United Kingdom", "Wielka Brytania", "europe", "GBP", 18, 5.0),
    ("Egypt", "Egipt", "Egypt", "Egipt", "non_europe", "EGP", 78, 8.0),
    ("Tunisia", "Tunezja", "Tunisia", "Tunezja", "non_europe", "TND", 74, 8.0),
    ("Turkey", "Turcja", "Turkey", "Turcja", "non_europe", "TRY", 70, 8.5),
]

# (destination name_en, month, risk_type_en, risk_type_pl, severity 1-3, description_en, description_pl)
_SEASONAL_RISKS = [
    ("Egypt", 7, "Extreme heat", "Ekstremalne upały", 3,
     "July temperatures often exceed 40C outside coastal resorts.",
     "Temperatury w lipcu poza kurortami nadmorskimi często przekraczają 40C."),
    ("Egypt", 8, "Extreme heat", "Ekstremalne upały", 3,
     "August is the peak of the summer heat wave season.",
     "Sierpień to szczyt sezonu fal upałów."),
    ("Turkey", 2, "Seismic activity", "Aktywność sejsmiczna", 2,
     "Elevated regional earthquake risk; monitor local advisories.",
     "Podwyższone regionalne ryzyko sejsmiczne; monitoruj lokalne ostrzeżenia."),
    ("Tunisia", 8, "Extreme heat", "Ekstremalne upały", 2,
     "Hot, dry conditions with occasional heatwaves.",
     "Gorące, suche warunki z okazjonalnymi falami upałów."),
    ("Austria", 1, "Avalanche risk", "Ryzyko lawinowe", 2,
     "Elevated avalanche risk in alpine regions during peak ski season.",
     "Podwyższone ryzyko lawinowe w regionach alpejskich w szczycie sezonu narciarskiego."),
    ("Greece", 7, "Wildfire risk", "Ryzyko pożarów", 2,
     "Dry summer conditions increase wildfire risk in rural/forested areas.",
     "Suche warunki letnie zwiększają ryzyko pożarów na terenach wiejskich i leśnych."),
    ("Croatia", 8, "Wildfire risk", "Ryzyko pożarów", 1,
     "Occasional wildfire risk along the Adriatic coast in late summer.",
     "Okazjonalne ryzyko pożarów wzdłuż wybrzeża Adriatyku pod koniec lata."),
]

# Seed-only fallback MSZ status: real MSZ advisories are written in terms of
# the traveler's own risk, not this app's internals -- an ETL implementation
# detail like "run scheduler.py" has no place in it. Level 1 in MSZ's real
# 4-level scale means "exercise normal precautions" (no special advisory in
# effect), which is exactly what an unfetched/no-warning destination means
# here too. ETL overwrites this with the real message once MSZ_RSS_URL is
# configured and reachable.
_DEFAULT_MSZ_MESSAGE_PL = "Zachowaj zwykłą ostrożność. Brak nadzwyczajnych ostrzeżeń dla tego kierunku."
_DEFAULT_MSZ_MESSAGE_EN = "Exercise normal precautions. No special advisories currently in effect for this destination."


def seed_if_empty(session):
    if session.query(Destination).count() > 0:
        return False

    by_name = {}
    for (name_en, name_pl, country_en, country_pl, region, currency,
         organized_pct, avg_stay) in _DESTINATIONS:
        dest = Destination(
            name_en=name_en, name_pl=name_pl,
            country_en=country_en, country_pl=country_pl,
            region=region, currency_code=currency,
            is_active=True,
        )
        session.add(dest)
        session.flush()
        by_name[name_en] = dest

        session.add(GusTourismStat(
            destination_id=dest.destination_id,
            organized_share_pct=organized_pct,
            individual_share_pct=100 - organized_pct,
            avg_stay_length_days=avg_stay,
            year=2025,
        ))
        session.add(MszSafetyWarning(
            destination_id=dest.destination_id,
            level=1,
            message_pl=_DEFAULT_MSZ_MESSAGE_PL,
            message_en=_DEFAULT_MSZ_MESSAGE_EN,
            source_url=None,
        ))
        session.add(CurrencyRate(
            destination_id=dest.destination_id,
            rate_to_pln=0.0,
        ))

    for (name_en, month, type_en, type_pl, severity, desc_en, desc_pl) in _SEASONAL_RISKS:
        dest = by_name[name_en]
        session.add(SeasonalRisk(
            destination_id=dest.destination_id,
            month=month,
            risk_type_en=type_en, risk_type_pl=type_pl,
            severity=severity,
            description_en=desc_en, description_pl=desc_pl,
        ))

    session.commit()
    return True
