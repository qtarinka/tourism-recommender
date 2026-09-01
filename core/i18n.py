"""
Minimal i18n layer for the Streamlit UI.

Usage:
    from core.i18n import t
    st.title(t("app_title"))

The active language is read from st.session_state["lang"] (set by the
language switcher in the sidebar). Falls back to Polish if unset, since
that's the thesis's home market.
"""
import streamlit as st

LANGUAGES = {"pl": "Polski", "en": "English"}

STRINGS = {
    "app_title": {
        "pl": "System Wspomagania Decyzji w Turystyce Wyjazdowej",
        "en": "Outbound Tourism Decision Support System",
    },
    "app_subtitle": {
        "pl": "Porównaj kierunki i otrzymaj rekomendację dopasowaną do Twoich preferencji.",
        "en": "Compare destinations and get a recommendation matched to your preferences.",
    },
    "nav_recommendation": {"pl": "Rekomendacja", "en": "Recommendation"},
    "nav_comparison": {"pl": "Porównanie", "en": "Comparison"},
    "nav_admin": {"pl": "Panel administratora", "en": "Admin panel"},
    "form_header": {"pl": "Twoje preferencje", "en": "Your preferences"},
    "form_intro": {
        "pl": "Odpowiedz na 4 krótkie pytania, a algorytm oceni 20 kierunków pod kątem Twoich preferencji.",
        "en": "Answer 4 quick questions and the algorithm will score all 20 destinations against your preferences.",
    },
    "form_trip_length": {"pl": "Długość wyjazdu (dni)", "en": "Trip length (days)"},
    "form_travel_month": {"pl": "Miesiąc wyjazdu", "en": "Travel month"},
    "form_org_style": {"pl": "Styl organizacji", "en": "Organization style"},
    "form_org_organized": {"pl": "Zorganizowany", "en": "Organized"},
    "form_org_individual": {"pl": "Indywidualny", "en": "Individual"},
    "form_risk": {"pl": "Poziom akceptowanego ryzyka", "en": "Risk tolerance"},
    "form_risk_low": {"pl": "Niski", "en": "Low"},
    "form_risk_medium": {"pl": "Średni", "en": "Medium"},
    "form_risk_high": {"pl": "Wysoki", "en": "High"},
    "form_submit": {"pl": "Pokaż rekomendacje", "en": "Show recommendations"},
    "results_header": {"pl": "Ranking rekomendacji", "en": "Recommendation ranking"},
    "results_score": {"pl": "Punktacja", "en": "Score"},
    "results_empty": {
        "pl": "Ustaw preferencje i kliknij przycisk, aby zobaczyć rekomendacje.",
        "en": "Set your preferences and click the button to see recommendations.",
    },
    "compare_header": {"pl": "Porównywarka kierunków", "en": "Destination comparison"},
    "compare_select": {"pl": "Wybierz kierunki do porównania", "en": "Select destinations to compare"},
    "col_destination": {"pl": "Kierunek", "en": "Destination"},
    "col_region": {"pl": "Region", "en": "Region"},
    "col_currency": {"pl": "Waluta", "en": "Currency"},
    "col_rate": {"pl": "Kurs (PLN)", "en": "Rate (PLN)"},
    "col_avg_stay": {"pl": "Śr. długość pobytu (dni)", "en": "Avg. stay length (days)"},
    "col_msz_level": {"pl": "Poziom ostrzeżenia MSZ", "en": "MSZ warning level"},
    "col_msz_message": {"pl": "Komunikat MSZ", "en": "MSZ advisory"},
    "col_seasonal_risk": {"pl": "Ryzyko sezonowe w wybranym miesiącu", "en": "Seasonal risk in selected month"},
    "col_none": {"pl": "brak", "en": "none"},
    "info_header": {"pl": "Dane kontekstowe", "en": "Contextual data"},
    "msz_info_header": {"pl": "Czym jest ostrzeżenie MSZ?", "en": "What is an MSZ warning?"},
    "msz_info_caption": {
        "pl": "MSZ (Ministerstwo Spraw Zagranicznych) publikuje ostrzeżenia dla podróżujących "
              "Polaków w 4-stopniowej skali: 1 — zachowaj zwykłą ostrożność (brak nadzwyczajnych "
              "zagrożeń), 2 — zachowaj szczególną ostrożność, 3 — nie podróżuj, 4 — natychmiast "
              "opuść dany kraj. Poziom 1 to normalny, bezpieczny stan — nie oznacza braku danych.",
        "en": "MSZ (Poland's Ministry of Foreign Affairs) publishes travel advisories for Polish "
              "citizens on a 4-level scale: 1 — exercise normal precautions (no special threats), "
              "2 — exercise increased caution, 3 — do not travel, 4 — leave the country "
              "immediately. Level 1 is the normal, safe baseline — it doesn't mean missing data.",
    },
    "bi_header": {"pl": "Pulpit Power BI", "en": "Power BI dashboard"},
    "bi_link_caption": {
        "pl": "Pełny interaktywny raport Power BI (statystyki GUS) jest dostępny pod poniższym "
              "linkiem — otwiera się w nowej karcie i wymaga zalogowania do Power BI.",
        "en": "The full interactive Power BI report (GUS statistics) is available at the link "
              "below — opens in a new tab and requires signing in to Power BI.",
    },
    "bi_open_link": {"pl": "Otwórz pulpit Power BI", "en": "Open Power BI dashboard"},
    "bi_missing": {
        "pl": "Pulpit Power BI nie jest jeszcze skonfigurowany. Ustaw POWERBI_REPORT_URL w pliku .env.",
        "en": "The Power BI dashboard isn't configured yet. Set POWERBI_REPORT_URL in your .env file.",
    },
    "admin_login_header": {"pl": "Logowanie administratora", "en": "Administrator login"},
    "admin_password": {"pl": "Hasło", "en": "Password"},
    "admin_login_btn": {"pl": "Zaloguj", "en": "Log in"},
    "admin_login_error": {"pl": "Nieprawidłowe hasło.", "en": "Incorrect password."},
    "admin_risks_header": {"pl": "Zarządzanie ryzykami sezonowymi", "en": "Manage seasonal risks"},
    "admin_add_risk": {"pl": "Dodaj ryzyko", "en": "Add risk"},
    "admin_delete": {"pl": "Usuń", "en": "Delete"},
    "admin_saved": {"pl": "Zapisano zmiany.", "en": "Changes saved."},
    "admin_logout": {"pl": "Wyloguj", "en": "Log out"},
    "footer_last_refresh": {"pl": "Ostatnia aktualizacja danych", "en": "Data last refreshed"},
    "footer_never": {"pl": "nigdy (uruchom scheduler.py)", "en": "never (run scheduler.py)"},
    "gallery_header": {"pl": "Poznaj kierunki", "en": "Explore the destinations"},
    "gallery_intro": {
        "pl": "Kliknij kierunek, aby zobaczyć więcej zdjęć jego najpopularniejszych atrakcji.",
        "en": "Click a destination to see more photos of its most popular sights.",
    },
    "gallery_expand": {"pl": "Zobacz więcej zdjęć", "en": "See more photos"},
    "photo_credit_prefix": {"pl": "Zdjęcie", "en": "Photo"},
    "photo_via_wikipedia": {"pl": "Wikipedia", "en": "Wikipedia"},
    "about_header": {"pl": "Jak to działa?", "en": "How this works"},
    "about_text": {
        "pl": "Wskazujesz preferencje → algorytm porównuje je z danymi 20 kierunków → każdy "
              "kierunek dostaje od 0 do 3 punktów za: dopasowanie długości pobytu, brak "
              "podwyższonego ryzyka sezonowego w wybranym miesiącu oraz akceptowalny poziom "
              "ostrzeżenia MSZ. Wyniki są posortowane malejąco po punktacji.",
        "en": "You set your preferences → the algorithm compares them against data for 20 "
              "destinations → each destination scores 0-3 points for: matching your trip length, "
              "no elevated seasonal risk in your travel month, and an acceptable MSZ warning "
              "level. Results are sorted highest score first.",
    },
}


def t(key: str) -> str:
    lang = st.session_state.get("lang", "pl")
    entry = STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry.get("pl", key))


def month_name(month: int) -> str:
    lang = st.session_state.get("lang", "pl")
    names_pl = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
                "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    names_en = ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]
    names = names_pl if lang == "pl" else names_en
    return names[month - 1]
