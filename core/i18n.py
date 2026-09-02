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
        "pl": "Jedne kryteria podróży. Ranking kierunków lub porównanie wybranych — Ty decydujesz.",
        "en": "One set of travel criteria. A full ranking or a comparison of your picks — your call.",
    },
    "nav_results": {"pl": "Wyniki", "en": "Results"},
    "nav_explore": {"pl": "Poznaj kierunki", "en": "Explore destinations"},
    "nav_admin": {"pl": "Panel administratora", "en": "Admin panel"},
    "nav_account": {"pl": "Konto", "en": "Account"},

    # --- unified criteria form (sidebar) -----------------------------
    "form_header": {"pl": "Twoje kryteria podróży", "en": "Your travel criteria"},
    "form_intro": {
        "pl": "Wypełnij raz — zostaw pole kierunków puste, aby zobaczyć ranking wszystkich "
              "20 kierunków, albo wybierz konkretne, aby je porównać.",
        "en": "Fill this in once — leave destinations empty to rank all 20, or pick specific "
              "ones to compare them.",
    },
    "form_trip_length": {"pl": "Długość wyjazdu (dni)", "en": "Trip length (days)"},
    "form_travellers": {"pl": "Liczba podróżnych", "en": "Number of travellers"},
    "form_travel_month": {"pl": "Miesiąc wyjazdu", "en": "Travel month"},
    "form_org_style": {"pl": "Styl organizacji", "en": "Organization style"},
    "form_org_organized": {"pl": "Zorganizowany", "en": "Organized"},
    "form_org_individual": {"pl": "Indywidualny", "en": "Individual"},
    "form_risk": {"pl": "Poziom akceptowanego ryzyka", "en": "Risk tolerance"},
    "form_risk_low": {"pl": "Niski", "en": "Low"},
    "form_risk_medium": {"pl": "Średni", "en": "Medium"},
    "form_risk_high": {"pl": "Wysoki", "en": "High"},
    "form_destinations": {"pl": "Kierunki do rozważenia (opcjonalnie)", "en": "Destinations to consider (optional)"},
    "form_destinations_help": {
        "pl": "Puste = ranking wszystkich kierunków. Wybrane = porównanie tylko tych kierunków.",
        "en": "Empty = rank all destinations. Selected = compare only those destinations.",
    },
    "form_submit": {"pl": "Znajdź kierunki", "en": "Find destinations"},

    # --- unified results -----------------------------------------------
    "results_header_recommendation": {"pl": "Ranking rekomendacji", "en": "Recommendation ranking"},
    "results_header_comparison": {"pl": "Porównanie wybranych kierunków", "en": "Comparison of selected destinations"},
    "results_mode_caption_recommendation": {
        "pl": "Wszystkie 20 kierunków ocenione względem Twoich kryteriów, od najlepiej dopasowanego.",
        "en": "All 20 destinations scored against your criteria, best match first.",
    },
    "results_mode_caption_comparison": {
        "pl": "Tylko wybrane przez Ciebie kierunki, ocenione względem tych samych kryteriów.",
        "en": "Only the destinations you picked, scored against the same criteria.",
    },
    "results_score": {"pl": "Punktacja", "en": "Score"},
    "results_score_of": {"pl": "{score}/3 kryteriów", "en": "{score}/3 criteria"},
    "results_empty": {
        "pl": "Ustaw kryteria w panelu bocznym i kliknij „Znajdź kierunki”, aby zobaczyć wyniki.",
        "en": "Set your criteria in the sidebar and click “Find destinations” to see results.",
    },
    "results_no_selected_destinations": {
        "pl": "Wybrane kierunki nie zostały znalezione — spróbuj ponownie.",
        "en": "The destinations you selected couldn't be found — try again.",
    },
    "card_view_details": {"pl": "🔍 Zobacz szczegóły", "en": "🔍 View details"},

    "match_excellent": {"pl": "Doskonałe dopasowanie", "en": "Excellent match"},
    "match_very_good": {"pl": "Bardzo dobre dopasowanie", "en": "Very good match"},
    "match_good": {"pl": "Dobre dopasowanie", "en": "Good match"},
    "match_limited": {"pl": "Słabe dopasowanie", "en": "Limited match"},

    "explain_header": {"pl": "Dlaczego ten kierunek?", "en": "Why this destination?"},
    "explain_trip_length_pos": {
        "pl": "Planowana długość wyjazdu dobrze pasuje do tego kierunku.",
        "en": "Your planned trip length is a good fit for this destination.",
    },
    "explain_trip_length_neg": {
        "pl": "Planowana długość wyjazdu może nie być optymalna dla tego kierunku.",
        "en": "Your planned trip length may be less suitable for this destination.",
    },
    "explain_seasonal_pos": {
        "pl": "Wybrany okres podróży wiąże się z niskim lub akceptowalnym ryzykiem sezonowym.",
        "en": "Your selected travel period has low or acceptable seasonal risk.",
    },
    "explain_seasonal_neg": {
        "pl": "Wybrany miesiąc może wiązać się z podwyższonym ryzykiem sezonowym.",
        "en": "Your selected month may involve elevated seasonal risk.",
    },
    "explain_msz_pos": {
        "pl": "Aktualny poziom ostrzeżenia MSZ jest akceptowalny przy Twoim poziomie ryzyka.",
        "en": "The current MSZ warning level is acceptable for your risk tolerance.",
    },
    "explain_msz_neg": {
        "pl": "Aktualny poziom ostrzeżenia MSZ przekracza Twój akceptowalny poziom ryzyka.",
        "en": "The current MSZ warning level exceeds your acceptable risk tolerance.",
    },

    "favorite_add": {"pl": "☆ Zapisz", "en": "☆ Save"},
    "favorite_remove": {"pl": "★ Zapisano", "en": "★ Saved"},
    "favorites_header": {"pl": "Twoje zapisane kierunki", "en": "Your saved destinations"},
    "favorites_note": {
        "pl": "Zapisane kierunki są przechowywane tylko w tej sesji przeglądarki — nie wymaga to "
              "konta i nic nie jest zapisywane na stałe. Zobacz „Jak to działa” po informacje o "
              "kontach użytkownika.",
        "en": "Saved destinations are kept only for this browser session — no account needed, "
              "nothing is stored permanently. See “How this works” for notes on user accounts.",
    },

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

    # --- explore destinations -----------------------------------------
    "gallery_header": {"pl": "Poznaj kierunki", "en": "Explore the destinations"},
    "gallery_intro": {
        "pl": "Przeglądaj, szukaj i odkrywaj wszystkie 20 kierunków. Kliknij kartę, aby zobaczyć "
              "zdjęcia i szczegóły — bez rozwijania strony w dół.",
        "en": "Browse, search, and discover all 20 destinations. Click a card to see photos and "
              "details — without the page expanding downward.",
    },
    "explore_search_placeholder": {"pl": "Szukaj kierunku...", "en": "Search destinations..."},
    "explore_region_all": {"pl": "Wszystkie regiony", "en": "All regions"},
    "explore_region_europe": {"pl": "Europa", "en": "Europe"},
    "explore_region_non_europe": {"pl": "Poza Europą", "en": "Non-Europe"},
    "explore_no_results": {"pl": "Brak kierunków pasujących do wyszukiwania.", "en": "No destinations match your search."},
    "explore_open": {"pl": "🖼️ Zdjęcia i szczegóły", "en": "🖼️ Photos & details"},
    "explore_add_to_compare": {"pl": "➕ Do porównania", "en": "➕ Add to compare"},
    "explore_added_to_compare": {
        "pl": "Dodano {name} do kierunków w panelu bocznym — kliknij „Znajdź kierunki”, aby zobaczyć wynik.",
        "en": "Added {name} to the destinations in the sidebar — click “Find destinations” to see the result.",
    },

    "photo_credit_prefix": {"pl": "Zdjęcie", "en": "Photo"},
    "photo_via_wikipedia": {"pl": "Wikipedia", "en": "Wikipedia"},

    # --- destination detail dialog --------------------------------------
    "detail_dialog_title": {"pl": "Szczegóły kierunku", "en": "Destination details"},
    "detail_close": {"pl": "Zamknij", "en": "Close"},
    "detail_photos_header": {"pl": "Zdjęcia", "en": "Photos"},
    "detail_photo_counter": {"pl": "Zdjęcie {i} z {n}", "en": "Photo {i} of {n}"},
    "detail_photo_none": {"pl": "Brak dostępnych zdjęć dla tego kierunku.", "en": "No photos available for this destination."},
    "detail_general_info_header": {"pl": "Ogólne informacje", "en": "General information"},
    "detail_general_info_missing": {
        "pl": "Ogólne informacje o tym kierunku są obecnie niedostępne.",
        "en": "General information for this destination isn't available right now.",
    },
    "detail_read_more": {"pl": "Czytaj więcej na Wikipedii", "en": "Read more on Wikipedia"},
    "detail_currency_header": {"pl": "Waluta i kurs", "en": "Currency & exchange rate"},
    "detail_msz_header": {"pl": "Ostrzeżenie MSZ dla tego kierunku", "en": "MSZ warning for this destination"},
    "detail_seasonal_header": {"pl": "Ryzyka sezonowe w ciągu roku", "en": "Seasonal risks through the year"},
    "detail_seasonal_none": {
        "pl": "Brak odnotowanych ryzyk sezonowych dla tego kierunku w naszej bazie.",
        "en": "No seasonal risks recorded for this destination in our data.",
    },
    "detail_recommended_period_header": {"pl": "Zalecany okres podróży", "en": "Recommended travel period"},
    "detail_recommended_period_all_clear": {
        "pl": "Na podstawie naszych danych: brak odnotowanych podwyższonych ryzyk sezonowych w "
              "żadnym miesiącu dla tego kierunku.",
        "en": "Based on our data: no elevated seasonal risk recorded for any month for this destination.",
    },
    "detail_recommended_period_avoid": {
        "pl": "Na podstawie naszych danych warto zachować szczególną ostrożność w: {months}.",
        "en": "Based on our data, worth extra caution in: {months}.",
    },
    "detail_travellers_note": {
        "pl": "Liczba podróżnych z Twoich kryteriów: {n}. Obecnie nie wpływa to na wynik "
              "dopasowania — w tej wersji aplikacji nie ma danych o kosztach na osobę.",
        "en": "Number of travellers from your criteria: {n}. This doesn't currently affect the "
              "match score — this version of the app has no per-person cost data.",
    },
    "detail_not_covered_header": {"pl": "Czego tu nie znajdziesz", "en": "What's not covered here"},
    "detail_not_covered": {
        "pl": "Klimat, wymogi wjazdowe i szczegóły dotyczące transportu nie są obecnie częścią "
              "zestawu danych tej aplikacji — nie chcemy zgadywać zamiast podawać sprawdzone dane.",
        "en": "Climate, entry requirements, and transport/accessibility details aren't currently "
              "part of this app's dataset — we'd rather leave them out than guess.",
    },

    "about_header": {"pl": "Jak to działa?", "en": "How this works"},
    "about_text": {
        "pl": "Ustawiasz kryteria podróży raz → algorytm ocenia względem nich kierunki → każdy "
              "kierunek dostaje od 0 do 3 punktów za: dopasowanie długości pobytu, brak "
              "podwyższonego ryzyka sezonowego w wybranym miesiącu oraz akceptowalny poziom "
              "ostrzeżenia MSZ. Jeśli nie wybierzesz konkretnych kierunków, oceniane jest "
              "wszystkich 20 (tryb rekomendacji). Jeśli wybierzesz kierunki, oceniane są tylko "
              "one, tymi samymi kryteriami (tryb porównania) — to dokładnie ten sam mechanizm, "
              "różni się tylko liczba ocenianych kierunków. Wyniki są posortowane malejąco po "
              "punktacji i opisane słownie, nie tylko liczbą.",
        "en": "You set your travel criteria once → the algorithm scores destinations against "
              "them → each destination scores 0-3 points for: matching your trip length, no "
              "elevated seasonal risk in your travel month, and an acceptable MSZ warning level. "
              "Leave destinations unselected and all 20 are scored (recommendation mode); select "
              "specific ones and only those are scored, with the exact same criteria (comparison "
              "mode) — it's the same mechanism either way, just a different candidate list. "
              "Results are sorted highest score first and explained in words, not just a number.",
    },
    "about_accounts_header": {"pl": "Konta użytkowników i zapisywanie wyników", "en": "User accounts & saving results"},
    "about_accounts_text": {
        "pl": "Konto jest całkowicie opcjonalne — rekomendacje, porównania i eksploracja "
              "kierunków działają bez logowania, a przycisk „Zapisz” zawsze zapisuje wybór "
              "przynajmniej w bieżącej sesji przeglądarki. Jeśli założysz konto w zakładce "
              "„Konto”, Twoje zapisane kierunki są dodatkowo zapisywane w bazie danych i wracają "
              "przy kolejnej wizycie (nawet po zamknięciu przeglądarki) — hasła są haszowane "
              "(bcrypt), a logowanie działa przez podpisany plik cookie. Bez konta zapisane "
              "kierunki znikają po zamknięciu karty przeglądarki.",
        "en": "An account is entirely optional — recommendations, comparisons, and exploring "
              "destinations all work without logging in, and the “Save” button always keeps your "
              "pick for at least the current browser session. If you create an account in the "
              "“Account” tab, your saved destinations are additionally stored in the database and "
              "come back on your next visit (even after closing the browser) — passwords are "
              "hashed (bcrypt) and login works via a signed cookie. Without an account, saved "
              "destinations disappear when you close the browser tab.",
    },
    "account_not_logged_in_intro": {
        "pl": "Zaloguj się, aby Twoje zapisane kierunki wracały przy kolejnej wizycie. Bez "
              "konta „Zapisz” nadal działa, ale tylko w tej sesji przeglądarki.",
        "en": "Log in so your saved destinations come back on your next visit. Without an "
              "account, “Save” still works, just only for this browser session.",
    },
    "account_sidebar_prompt": {"pl": "Zaloguj się / Zarejestruj się", "en": "Log in / Register"},
    "account_use_sidebar": {
        "pl": "Użyj panelu „👤 Zaloguj się / Zarejestruj się” w lewym pasku bocznym, aby się "
              "zalogować lub założyć konto.",
        "en": "Use the “👤 Log in / Register” panel in the left sidebar to log in or create an account.",
    },
    "account_login_tab": {"pl": "Zaloguj się", "en": "Log in"},
    "account_register_tab": {"pl": "Zarejestruj się", "en": "Register"},
    "account_login_error": {"pl": "Nieprawidłowa nazwa użytkownika lub hasło.", "en": "Incorrect username or password."},
    "account_register_success": {
        "pl": "Konto utworzone. Przejdź do zakładki „Zaloguj się”, aby się zalogować.",
        "en": "Account created. Switch to the “Log in” tab to sign in.",
    },
    "account_register_error": {"pl": "Nie udało się utworzyć konta: {error}", "en": "Couldn't create the account: {error}"},
    "account_logged_in_as": {"pl": "Zalogowano jako **{name}** (@{username})", "en": "Logged in as **{name}** (@{username})"},
    "account_logout": {"pl": "Wyloguj", "en": "Log out"},
    "account_favorites_header": {"pl": "Twoje zapisane kierunki", "en": "Your saved destinations"},
    "account_favorites_persisted_note": {
        "pl": "Te kierunki są zapisane na Twoim koncie i będą tu czekać przy następnej wizycie.",
        "en": "These are saved to your account and will be here on your next visit.",
    },
    "account_favorites_empty": {
        "pl": "Nie masz jeszcze żadnych zapisanych kierunków. Kliknij „☆ Zapisz” przy dowolnym "
              "kierunku w zakładce Wyniki lub Poznaj kierunki.",
        "en": "You haven't saved any destinations yet. Click “☆ Save” on any destination in the "
              "Results or Explore tab.",
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
