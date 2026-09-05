"""
Landmark photo lookup, plus a short country summary, via Wikipedia's
public MediaWiki Action API (no API key, no account, no signup -- unlike
a stock-photo API this needed nothing from the user to wire up). Used to
show each destination's most recognizable tourist landmarks and a
genuinely sourced "general information" blurb throughout the app --
multiple curated sights per destination, not just one, viewable directly
in the app rather than sending the user to Wikipedia to see more.

Uses action=query&prop=pageimages with an explicit pithumbsize rather
than the simpler REST /page/summary endpoint, because Wikimedia's image
CDN rejects a thumbnail URL whose embedded width was hand-edited after
the fact (verified: swapping "330px-" for "640px-" in a REST summary's
thumbnail URL gets a 400 from upload.wikimedia.org -- the width has to
be requested from the API itself so the CDN's cache key matches).

Images are hotlinked from Wikimedia's CDN (never downloaded/stored in
this repo) and are almost all CC BY-SA or public domain on Commons -- the
attribution caption rendered under each photo (see `app.py`'s
`render_photo`) satisfies CC BY-SA's attribution requirement. If
Wikipedia is unreachable, rate-limited, or a page has no thumbnail, the
lookup functions skip/omit that entry and callers fall back to a plain
gradient placeholder rather than a broken image.
"""
import requests
import streamlit as st

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
_THUMB_WIDTH = 640

# destination name_en -> a short list of well-known landmarks' exact English
# Wikipedia page titles, picked for name recognition (specific famous sights,
# not just "country skyline"). First entry is the "primary" one used on the
# hero banner, recommendation cards, and comparison strip; all of them are
# shown together in the destination gallery.
LANDMARKS = {
    "Czechia": ["Charles Bridge", "Prague Castle", "Old Town Square, Prague"],
    "Austria": ["Schönbrunn Palace", "Hallstatt", "St. Stephen's Cathedral, Vienna"],
    "Germany": ["Neuschwanstein Castle", "Brandenburg Gate", "Cologne Cathedral"],
    "Croatia": ["Dubrovnik", "Plitvice Lakes National Park", "Diocletian's Palace"],
    "Italy": ["Colosseum", "Venice", "Trevi Fountain"],
    "Spain": ["Sagrada Família", "Alhambra", "Park Güell"],
    "Greece": ["Acropolis of Athens", "Santorini", "Meteora"],
    "France": ["Eiffel Tower", "Louvre", "Mont Saint-Michel"],
    "Hungary": ["Hungarian Parliament Building", "Fisherman's Bastion", "Chain Bridge, Budapest"],
    "Slovakia": ["Bratislava Castle", "Spiš Castle", "Devín Castle"],
    "Slovenia": ["Lake Bled", "Ljubljana Castle", "Postojna Cave"],
    "Portugal": ["Belém Tower", "Pena Palace", "Dom Luís I Bridge"],
    "Netherlands": ["Keukenhof", "Anne Frank House", "Kinderdijk"],
    "Bulgaria": ["Rila Monastery", "Alexander Nevsky Cathedral", "Nesebar"],
    "Cyprus": ["Kourion", "Paphos", "Troodos Mountains"],
    "Malta": ["Valletta", "Mdina", "Blue Lagoon, Comino"],
    "United Kingdom": ["Tower Bridge", "Big Ben", "Stonehenge"],
    "Egypt": ["Great Sphinx of Giza", "Great Pyramid of Giza", "Karnak Temple"],
    "Tunisia": ["Amphitheatre of El Jem", "Medina of Tunis", "Sidi Bou Said"],
    "Turkey": ["Hagia Sophia", "Cappadocia", "Pamukkale"],
}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def _fetch_page_image(title: str, width: int = _THUMB_WIDTH):
    """Raises on any network failure/non-200 instead of returning None,
    so st.cache_data never caches a transient failure (a timeout or a
    momentary rate-limit) as a permanent "no image" for 24h -- only a
    genuine successful response gets cached. Callers must catch."""
    resp = requests.get(
        WIKI_API_URL,
        params={
            "action": "query", "titles": title, "prop": "pageimages|info",
            "inprop": "url", "pithumbsize": width, "format": "json", "redirects": 1,
        },
        headers={"User-Agent": "tourism-recommender-thesis-app/1.0 (educational project)"},
        timeout=6,
    )
    resp.raise_for_status()
    return resp.json()


def _lookup(title: str):
    try:
        data = _fetch_page_image(title)
    except requests.RequestException:
        return None
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), None)
    if not page or "thumbnail" not in page:
        return None
    return {
        "image_url": page["thumbnail"]["source"],
        "title": title,
        "page_url": page.get("fullurl"),
    }


def get_landmark_image(destination_name_en: str):
    """Returns {"image_url", "title", "page_url"} for the destination's
    primary landmark, or None if unavailable (unmapped destination,
    offline/rate-limited right now, or the Wikipedia page genuinely has
    no thumbnail)."""
    titles = LANDMARKS.get(destination_name_en)
    if not titles:
        return None
    return _lookup(titles[0])


def get_destination_photos(destination_name_en: str, limit: int = 3):
    """Returns a list of image dicts (see get_landmark_image) for all of
    the destination's curated landmarks, skipping any that fail to load.
    May return fewer than `limit` (or an empty list) if some/all lookups
    fail -- callers should handle a short or empty list gracefully."""
    titles = LANDMARKS.get(destination_name_en, [])[:limit]
    photos = [_lookup(title) for title in titles]
    return [p for p in photos if p is not None]


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def _fetch_country_extract(country_name: str, lang: str = "en"):
    """Same failure-doesn't-cache contract as _fetch_page_image (see its
    docstring) -- raises rather than returning None on network failure.
    `lang` selects which language Wikipedia to query ("en"/"pl"); it's part
    of st.cache_data's argument-based cache key, so the English and Polish
    extracts for the same country are cached independently."""
    resp = requests.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query", "titles": country_name, "prop": "extracts|info",
            "inprop": "url", "exintro": 1, "explaintext": 1, "exsentences": 3,
            "format": "json", "redirects": 1,
        },
        headers={"User-Agent": "tourism-recommender-thesis-app/1.0 (educational project)"},
        timeout=6,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_summary(country_name: str, lang: str):
    try:
        data = _fetch_country_extract(country_name, lang)
    except requests.RequestException:
        return None
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), None)
    extract = (page or {}).get("extract", "").strip()
    if not page or not extract:
        return None
    return {"extract": extract, "page_url": page.get("fullurl")}


def get_country_summary(country_name_en: str, country_name_pl: str = None, lang: str = "en"):
    """Returns {"extract", "page_url"} -- a short (~3 sentence), genuinely
    sourced intro paragraph about the country from Wikipedia's own lead
    section, or None if unavailable. Used for the destination detail
    view's "General information" section: real, attributable content
    rather than an invented country description.

    Follows the same _en/_pl selection convention used throughout the app:
    when `lang` is "pl" and a Polish title is given, the Polish Wikipedia
    is queried first so this section switches with the rest of the UI.
    Falls back to the English Wikipedia (and the English title) if no
    Polish article exists, or its extract comes back empty, so a missing
    Polish source never leaves the section blank -- it just shows the
    English summary instead."""
    if lang == "pl" and country_name_pl:
        summary = _extract_summary(country_name_pl, "pl")
        if summary:
            return summary
    return _extract_summary(country_name_en, "en")
