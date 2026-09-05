"""
Streamlit entrypoint: `streamlit run app.py`

Tourism outbound-trip decision support system (thesis chapters 3-7
implementation), restructured around one unified travel-criteria form:
leave destinations unselected for a full ranking (recommendation mode),
or pick specific ones to score only those (comparison mode). Both modes
share the same scoring/ranking call (core.scoring.rank_destinations) and
the same results UI -- comparison is not a separate system, it's the same
one given a smaller candidate list. See docs/DEVELOPMENT_DOCUMENTATION.md
for the full rationale behind this restructuring.
"""
import os

import streamlit as st
from dotenv import load_dotenv
from streamlit_authenticator.utilities.exceptions import LoginError

# Must run before importing core.db: it reads DATABASE_URL at *import*
# time (module-level `create_engine(...)`), so .env has to be loaded
# first or that read sees an unset var even though .env defines it.
load_dotenv()

# Streamlit Community Cloud has no .env file -- it injects config via
# st.secrets instead. Every config read in this codebase goes through
# plain os.environ.get(...) (DATABASE_URL, ADMIN_PASSWORD, etc.), so
# rather than rewriting every one of those call sites for a second config
# source, this copies whatever Streamlit Cloud put in st.secrets into
# os.environ once, at startup -- the existing os.environ.get(...) calls
# then work unchanged on both platforms. setdefault (not direct
# assignment) means a real local .env value always wins if both happen to
# be present. st.secrets raises when no secrets.toml exists at all, which
# is the normal case for local dev, so this is expected to no-op there.
try:
    for _secret_key, _secret_value in st.secrets.items():
        os.environ.setdefault(_secret_key, str(_secret_value))
except Exception:
    pass

from core.db import init_db, get_session, Destination, SeasonalRisk
from core.seed_data import seed_if_empty
from core.i18n import t, month_name, LANGUAGES
from core.scoring import rank_destinations, low_risk_months
from core.images import get_landmark_image, get_destination_photos, get_country_summary
from core.theme import CUSTOM_CSS
from core.auth import (
    get_authenticator, persist_new_user, sync_session_with_auth,
    add_db_favorite, remove_db_favorite, login_fields, register_fields,
    update_profile, persist_password_change, reset_password_fields,
    grant_admin_if_code_matches, set_user_blocked, list_all_users_with_stats,
    get_recent_login_log,
)

st.set_page_config(page_title="Tourism Decision Support", page_icon="\U0001F30D", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- bootstrap ---------------------------------------------------------
init_db()
_session = get_session()
seed_if_empty(_session)
_session.close()

if "lang" not in st.session_state:
    st.session_state["lang"] = "pl"
if "search_done" not in st.session_state:
    st.session_state["search_done"] = False
if "favorites" not in st.session_state:
    st.session_state["favorites"] = set()
if "open_detail_id" not in st.session_state:
    st.session_state["open_detail_id"] = None
if "open_detail_scored" not in st.session_state:
    st.session_state["open_detail_scored"] = None

# A destination added to the comparison selection from "Explore" (below)
# stages its name here rather than writing directly into
# st.session_state["destinations_multiselect"] -- Streamlit raises
# StreamlitWidgetAlreadyInstantiatedError if you set a widget's own
# session_state value on the same run where that widget already rendered
# (the sidebar, further down, always runs before the Explore tab that
# would otherwise try this). Applying the pending value here, before the
# sidebar creates the widget, avoids that entirely.
if "pending_add_to_compare" in st.session_state:
    _pending_name = st.session_state.pop("pending_add_to_compare")
    _current_selection = list(st.session_state.get("destinations_multiselect", []))
    if _pending_name not in _current_selection:
        _current_selection.append(_pending_name)
    st.session_state["destinations_multiselect"] = _current_selection

session = get_session()
all_destinations = session.query(Destination).all()

# Accounts (core/auth.py) -- a login is required to use the app at all
# (see docs/DEVELOPMENT_DOCUMENTATION.md §9's "Mandatory login"
# subsection). A fresh Authenticate object is built from the DB every run
# (Streamlit reruns the whole script on every interaction, so nothing can
# persist in memory between runs) and location="unrendered" here just
# silently checks the re-auth cookie / session state without drawing any
# widget -- the actual visible login/register form renders in the
# sidebar, further down, only when not already authenticated. This must
# run before any tab body (Results' Favorites strip, rendered further
# down, needs st.session_state["favorites"] already synced to the logged-
# in user; the nav itself needs st.session_state["is_admin"] synced to
# know whether to offer the Admin page at all).
authenticator = get_authenticator(session)
try:
    authenticator.login(location="unrendered")
except LoginError:
    # The browser's re-auth cookie names a username that no longer has a
    # matching row in `users` (e.g. the account was deleted, or this is a
    # stale cookie from before a DB reset). streamlit-authenticator raises
    # rather than just treating that as logged-out, and would otherwise
    # crash the whole app on every rerun for that browser until the cookie
    # expires or is cleared manually -- so drop it and continue anonymous.
    authenticator.cookie_controller.delete_cookie()
    st.session_state["authentication_status"] = None
sync_session_with_auth(session, authenticator)

_HERO_LANDMARK_DESTINATIONS = ["France", "Italy", "Greece", "Egypt"]


def destination_name(dest):
    return dest.name_pl if st.session_state["lang"] == "pl" else dest.name_en


def _photo_credit(img):
    """Markdown-syntax credit line -- for use inside st.caption/st.write,
    which parse Markdown normally."""
    credit = f"{t('photo_credit_prefix')}: {img['title']}"
    if img.get("page_url"):
        credit = f"{credit} — [{t('photo_via_wikipedia')}]({img['page_url']})"
    return credit


def _photo_credit_html(img):
    """Same credit line as an <a> tag instead of Markdown link syntax --
    for use inside a raw unsafe_allow_html block (e.g. the carousel
    counter), where embedded `[text](url)` Markdown does NOT get parsed
    into a link (verified: it rendered as literal bracket/paren text)."""
    credit = f"{t('photo_credit_prefix')}: {img['title']}"
    if img.get("page_url"):
        credit = f'{credit} — <a href="{img["page_url"]}" target="_blank">{t("photo_via_wikipedia")}</a>'
    return credit


def render_photo(dest, height_px: int = 160):
    """Renders a destination's landmark photo, or a gradient placeholder
    with its name if the photo can't be fetched (offline, rate-limited,
    or no thumbnail on the Wikipedia page)."""
    img = get_landmark_image(dest.name_en)
    if img:
        st.image(img["image_url"], use_container_width=True)
        st.caption(_photo_credit(img))
    else:
        st.markdown(
            f'<div class="photo-placeholder" style="height:{height_px}px">'
            f'{destination_name(dest)}</div>',
            unsafe_allow_html=True,
        )


def render_hero():
    tiles = ""
    for name_en in _HERO_LANDMARK_DESTINATIONS:
        img = get_landmark_image(name_en)
        url = img["image_url"] if img else ""
        style = f"background-image:url('{url}')" if url else "background:#555"
        tiles += f'<div class="hero-tile" style="{style}"></div>'
    st.markdown(
        f'<div class="hero-banner">{tiles}'
        f'<div class="hero-overlay"><h1>{t("app_title")}</h1><p>{t("app_subtitle")}</p></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def toggle_favorite(dest_id):
    favs = st.session_state["favorites"]
    username = st.session_state.get("username") if st.session_state.get("authentication_status") else None
    if dest_id in favs:
        favs.discard(dest_id)
        if username:
            remove_db_favorite(session, username, dest_id)
    else:
        favs.add(dest_id)
        if username:
            add_db_favorite(session, username, dest_id)


def open_detail(dest_id, scored=None):
    """Opens the destination detail dialog by setting persistent state and
    rerunning, rather than calling the @st.dialog function directly from
    inside a button handler. This matters: a button-guarded direct call
    (`if st.button(...): _detail_dialog(...)`) only re-opens the dialog on
    the exact rerun where that specific button was clicked -- any
    *internal* interaction inside the dialog (e.g. the carousel's
    prev/next buttons) triggers its own st.rerun(), which is a fresh
    script run where the original trigger button is no longer "clicked",
    so the dialog would immediately close instead of just updating its
    photo. Session-state-backed "is a dialog open, and for which
    destination" persists across those internal reruns correctly."""
    st.session_state["open_detail_id"] = dest_id
    st.session_state["open_detail_scored"] = scored
    st.rerun()


def _close_detail():
    st.session_state["open_detail_id"] = None
    st.session_state["open_detail_scored"] = None


def open_profile():
    """Same persistent-state-plus-rerun pattern as open_detail() above, for
    the same reason: the profile dialog's own internal interactions (saving
    the name/email form, submitting the password-change form) each trigger
    their own st.rerun(), which would immediately close a dialog that was
    only open because of an `if st.button(...):` guard around the trigger."""
    st.session_state["show_profile"] = True
    st.rerun()


def _close_profile():
    st.session_state["show_profile"] = False


def _require_login() -> bool:
    """Gate for every page except About and Admin: the app now requires a
    logged-in account to be used at all (not just to persist Favorites
    across visits, the original opt-in design -- see
    docs/DEVELOPMENT_DOCUMENTATION.md §9 vs. the later, stricter
    requirement this replaces it with). Shows a locked message and
    returns False when not authenticated, so callers can write
    `if active_page == "x": if _require_login(): <real content>`. Admin
    doesn't use this: it's gated on is_admin directly, and isn't even
    offered as a nav option unless that's already true."""
    if not st.session_state.get("authentication_status"):
        st.info(t("locked_feature_message"))
        return False
    return True


# --- sidebar: ONE unified travel-criteria form --------------------------
# Mode (recommendation vs comparison) is derived from whether the
# "destinations to consider" multiselect is empty -- there is no separate
# comparison form; this is deliberate (see requirement: comparison is an
# extended recommendation, not a parallel feature).
with st.sidebar:
    lang_choice = st.selectbox(
        "Język / Language", options=list(LANGUAGES.keys()),
        format_func=lambda code: LANGUAGES[code],
        index=list(LANGUAGES.keys()).index(st.session_state["lang"]),
    )
    st.session_state["lang"] = lang_choice

    # Account status/login -- placed at the very top of the sidebar (the
    # first thing rendered on load, in every tab) rather than tucked
    # inside the "Konto" tab alone, so it's actually visible without
    # having to go looking for it. The app now requires a logged-in account
    # to be used at all: the travel-criteria form below (and every other
    # feature) only renders once authenticated -- while logged out, this
    # login/register widget is the *only* thing in the sidebar.
    if st.session_state.get("authentication_status"):
        st.success(t("account_logged_in_as").format(
            name=st.session_state.get("name", ""), username=st.session_state.get("username", "")))
        authenticator.logout(t("account_logout"), location="sidebar", key="sidebar_logout_btn")
        st.divider()

        st.markdown(f'<div class="pref-card-header">🧭 {t("form_header")}</div>', unsafe_allow_html=True)
        st.caption(t("form_intro"))

        trip_length_days = st.slider(f"📅 {t('form_trip_length')}", min_value=2, max_value=21, value=7)
        travellers = st.number_input(f"👥 {t('form_travellers')}", min_value=1, max_value=10, value=2, step=1)
        st.session_state["current_travellers"] = travellers
        travel_month = st.selectbox(
            f"🗓️ {t('form_travel_month')}", options=list(range(1, 13)),
            format_func=month_name, index=6,
        )
        st.markdown(f"**🧳 {t('form_org_style')}**")
        org_style = st.segmented_control(
            t("form_org_style"), options=["organized", "individual"],
            format_func=lambda v: t("form_org_organized") if v == "organized" else t("form_org_individual"),
            default="organized", label_visibility="collapsed",
        ) or "organized"
        st.markdown(f"**⚠️ {t('form_risk')}**")
        risk_tolerance = st.segmented_control(
            t("form_risk"), options=["low", "medium", "high"],
            format_func=lambda v: {"low": t("form_risk_low"), "medium": t("form_risk_medium"),
                                    "high": t("form_risk_high")}[v],
            default="medium", label_visibility="collapsed",
        ) or "medium"

        _dest_name_options = sorted(destination_name(d) for d in all_destinations)
        chosen_names = st.multiselect(
            f"🗺️ {t('form_destinations')}", options=_dest_name_options, key="destinations_multiselect",
        )
        st.caption(t("form_destinations_help"))

        submitted = st.button(f"🔎 {t('form_submit')}", type="primary", use_container_width=True,
                               key="find_destinations_btn")
        if submitted:
            st.session_state["search_done"] = True
            # Jumps straight to the Results page on submit -- this runs
            # before main_nav's own widget is instantiated later in the
            # script (see the nav section below), so setting its
            # session_state value here is safe rather than hitting
            # StreamlitWidgetAlreadyInstantiatedError. Requested directly:
            # "the find destination button should be linked to result
            # page because right now it doesnt show destination except
            # you are in result page".
            st.session_state["main_nav"] = "results"
    else:
        if st.session_state.pop("account_blocked", False):
            st.error(t("account_blocked_message"))
        st.session_state.setdefault("auth_mode", "login")
        with st.expander(f"👤 {t('account_sidebar_prompt')}", expanded=True):
            # location="main" here (not "sidebar") is deliberate:
            # streamlit-authenticator's location="sidebar" calls st.sidebar.form()
            # internally, which targets the sidebar's top-level container directly
            # and ignores any *nested* container it's called from -- so with
            # location="sidebar", the login and register forms rendered
            # unconditionally, always both, regardless of being nested in this
            # expander or in tabs (confirmed by reading the library source after
            # a user report that the two forms weren't behaving like tabs at
            # all). Bare st.form() (location="main") respects the ambient `with`
            # container instead, so nesting one-at-a-time inside this expander
            # actually works.
            if st.session_state.pop("just_registered", False):
                if st.session_state.pop("just_registered_admin", False):
                    st.success(t("account_admin_granted"))
                else:
                    st.success(t("account_register_success"))

            if st.session_state["auth_mode"] == "login":
                authenticator.login(location="main", key="sidebar_login_form",
                                     fields=login_fields(st.session_state["lang"]))
                if st.session_state.get("authentication_status") is False:
                    st.error(t("account_login_error"))
                if st.button(t("account_switch_to_register"), key="switch_to_register_btn",
                             use_container_width=True):
                    st.session_state["auth_mode"] = "register"
                    st.rerun()
            else:
                try:
                    _, _sidebar_new_username, _sidebar_new_name = authenticator.register_user(
                        location="main", captcha=False, password_hint=False,
                        key="sidebar_register_form", fields=register_fields(st.session_state["lang"]),
                    )
                    # Outside register_user()'s own st.form() -- its public
                    # API renders a fixed set of fields with no hook to
                    # inject an extra one, so this is a separate widget
                    # collected independently and read at the same point
                    # register_user()'s submission is detected below.
                    # "Admin code" being verified "in the login or signup
                    # stage" (as requested) means here: matching it against
                    # ADMIN_PASSWORD grants is_admin permanently on the new
                    # account, so it's never asked again after this.
                    admin_code = st.text_input(
                        t("account_admin_code_label"), type="password",
                        key="sidebar_register_admin_code",
                    )
                    if _sidebar_new_username:
                        persist_new_user(session, authenticator, _sidebar_new_username, _sidebar_new_name)
                        granted = grant_admin_if_code_matches(session, _sidebar_new_username, admin_code)
                        st.session_state["auth_mode"] = "login"
                        st.session_state["just_registered"] = True
                        st.session_state["just_registered_admin"] = granted
                        st.rerun()
                except Exception as exc:
                    st.error(t("account_register_error").format(error=str(exc)))
                if st.button(t("account_switch_to_login"), key="switch_to_login_btn",
                             use_container_width=True):
                    st.session_state["auth_mode"] = "login"
                    st.rerun()
        st.divider()
        st.info(t("sidebar_login_required"))

# Fallbacks so the rest of the script has something to reference when
# logged out -- the values are never actually used for scoring, since
# tab_results (the only place that reads them) is itself gated by
# _require_login() and short-circuits before reaching this branch's data.
if not st.session_state.get("authentication_status"):
    trip_length_days = travel_month = risk_tolerance = None
    chosen_names = []

# Profile button, right-aligned above the hero banner -- the closest
# equivalent Streamlit layout offers to a "top right" nav element (the
# actual browser-chrome top-right corner is reserved for Streamlit's own
# Deploy/menu controls and isn't available to app code). Only shown once
# logged in, since there's no profile to view/edit otherwise.
if st.session_state.get("authentication_status"):
    _, _profile_btn_col = st.columns([6, 1])
    with _profile_btn_col:
        if st.button(f"👤 {t('nav_profile')}", key="open_profile_btn", use_container_width=True):
            open_profile()

render_hero()

# Page nav, as a segmented control bound to st.session_state["main_nav"]
# rather than st.tabs() -- st.tabs() has no supported way to select a tab
# from Python, which the "Find destinations" button above needs (it sets
# main_nav="results" before this widget is created each run, jumping the
# user to the Results page on submit) and which showing/hiding "Admin"
# based on account privilege also needs (a plain Python list, filtered
# before the widget is built, rather than trying to make one of several
# static st.tabs() panels invisible after the fact).
_NAV_ITEMS = [
    ("results", f"🏆 {t('nav_results')}"),
    ("explore", f"🧭 {t('nav_explore')}"),
    ("info", f"📊 {t('info_header')}"),
    ("account", f"👤 {t('nav_account')}"),
    ("about", f"ℹ️ {t('about_header')}"),
]
if st.session_state.get("is_admin"):
    _NAV_ITEMS.append(("admin", f"🔐 {t('nav_admin')}"))
_nav_keys = [key for key, _ in _NAV_ITEMS]
_nav_labels = dict(_NAV_ITEMS)

st.session_state.setdefault("main_nav", "results")
if st.session_state["main_nav"] not in _nav_keys:
    # E.g. an admin was viewing the Admin page and lost admin status
    # (or logged out) mid-session -- fall back rather than pointing at a
    # page that's no longer offered.
    st.session_state["main_nav"] = "results"

active_page = st.segmented_control(
    "nav", options=_nav_keys, format_func=lambda k: _nav_labels[k],
    label_visibility="collapsed", key="main_nav",
) or "results"
st.divider()


# --- destination detail dialog: shared by Results cards, the Favorites
# strip, and Explore Destinations -- one component, three entry points,
# per the "reuse instead of duplicating" requirement. -----------------
@st.dialog(t("detail_dialog_title"), width="large", on_dismiss=_close_detail)
def _detail_dialog(dest_id: int, scored):
    dest = session.get(Destination, dest_id)
    if dest is None:
        return
    lang = st.session_state["lang"]

    st.markdown(f"## {destination_name(dest)}")
    is_fav = dest_id in st.session_state["favorites"]
    if st.button(t("favorite_remove") if is_fav else t("favorite_add"), key=f"fav_dialog_{dest_id}"):
        toggle_favorite(dest_id)
        st.rerun()

    if scored is not None:
        st.markdown(f'<div class="detail-section-header">⭐ {t("explain_header")}</div>', unsafe_allow_html=True)
        st.markdown(f"**{t('match_' + scored.match_level)}** &nbsp;·&nbsp; "
                    f"{t('results_score_of').format(score=scored.score)}")
        for matched, pos_key, neg_key in scored.explanation_items():
            icon = "✅" if matched else "⚠️"
            st.write(f"{icon} {t(pos_key if matched else neg_key)}")

    st.markdown(f'<div class="detail-section-header">📷 {t("detail_photos_header")}</div>', unsafe_allow_html=True)
    photos = get_destination_photos(dest.name_en)
    if not photos:
        st.caption(t("detail_photo_none"))
    else:
        idx_key = f"carousel_idx_{dest_id}"
        idx = st.session_state.get(idx_key, 0) % len(photos)
        photo = photos[idx]
        st.markdown(f'<img src="{photo["image_url"]}" class="detail-carousel-img">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="detail-carousel-counter">'
            f'{t("detail_photo_counter").format(i=idx + 1, n=len(photos))} — {_photo_credit_html(photo)}'
            f'</div>', unsafe_allow_html=True,
        )
        nav_cols = st.columns([1, 1, 5])
        if nav_cols[0].button("◀", key=f"prev_{dest_id}", use_container_width=True, disabled=len(photos) < 2):
            st.session_state[idx_key] = (idx - 1) % len(photos)
            st.rerun()
        if nav_cols[1].button("▶", key=f"next_{dest_id}", use_container_width=True, disabled=len(photos) < 2):
            st.session_state[idx_key] = (idx + 1) % len(photos)
            st.rerun()

    st.markdown(f'<div class="detail-section-header">📖 {t("detail_general_info_header")}</div>', unsafe_allow_html=True)
    summary = get_country_summary(dest.name_en, dest.name_pl, lang)
    if summary:
        st.write(summary["extract"])
        if summary.get("page_url"):
            st.markdown(f"[{t('detail_read_more')}]({summary['page_url']})")
    else:
        st.caption(t("detail_general_info_missing"))

    st.markdown(f'<div class="detail-section-header">💱 {t("detail_currency_header")}</div>', unsafe_allow_html=True)
    rate = dest.current_currency_rate.rate_to_pln if dest.current_currency_rate else None
    rate_text = f" — 1 {dest.currency_code} ≈ {rate:.4f} PLN" if rate else ""
    st.write(f"{t('col_currency')}: {dest.currency_code}{rate_text}")

    st.markdown(f'<div class="detail-section-header">🛂 {t("detail_msz_header")}</div>', unsafe_allow_html=True)
    msz_level = max((w.level for w in dest.msz_warnings), default=1)
    msz_message = dest.msz_warnings[-1].message_pl if lang == "pl" else (
        dest.msz_warnings[-1].message_en if dest.msz_warnings else "")
    st.write(f"{t('col_msz_level')}: {msz_level}/4")
    st.caption(msz_message)
    with st.expander(t("msz_info_header")):
        st.caption(t("msz_info_caption"))

    st.markdown(f'<div class="detail-section-header">🌦️ {t("detail_seasonal_header")}</div>', unsafe_allow_html=True)
    risks = sorted(dest.seasonal_risks, key=lambda r: r.month)
    if not risks:
        st.caption(t("detail_seasonal_none"))
    else:
        for r in risks:
            risk_type = r.risk_type_pl if lang == "pl" else r.risk_type_en
            desc = (r.description_pl if lang == "pl" else r.description_en) or ""
            st.write(f"**{month_name(r.month)}** — {risk_type} ({r.severity}/3)")
            if desc:
                st.caption(desc)

    st.markdown(f'<div class="detail-section-header">🗓️ {t("detail_recommended_period_header")}</div>',
                unsafe_allow_html=True)
    ok_months = set(low_risk_months(dest, max_severity=1))
    risky_months = [m for m in range(1, 13) if m not in ok_months]
    if not risky_months:
        st.write(t("detail_recommended_period_all_clear"))
    else:
        st.write(t("detail_recommended_period_avoid").format(
            months=", ".join(month_name(m) for m in risky_months)))

    travellers_n = st.session_state.get("current_travellers")
    if travellers_n:
        st.caption(t("detail_travellers_note").format(n=travellers_n))

    st.markdown(f'<div class="detail-section-header">ℹ️ {t("detail_not_covered_header")}</div>',
                unsafe_allow_html=True)
    st.caption(t("detail_not_covered"))

    st.divider()
    if st.button(t("detail_close"), key=f"close_{dest_id}", use_container_width=True):
        _close_detail()
        st.rerun()


# The dialog only actually renders when this fires -- kept as persistent
# state (see open_detail()) rather than the more obvious-looking "call
# _detail_dialog() straight from inside each trigger button's if-block",
# because that pattern breaks as soon as anything *inside* the dialog
# (the carousel's own prev/next buttons) needs its own st.rerun().
if st.session_state.get("open_detail_id") is not None:
    _detail_dialog(st.session_state["open_detail_id"], st.session_state.get("open_detail_scored"))


@st.dialog(t("profile_dialog_title"), on_dismiss=_close_profile)
def _profile_dialog():
    username = st.session_state.get("username")
    st.caption(f"@{username}")

    if st.session_state.pop("profile_just_saved", False):
        st.success(t("profile_saved"))

    with st.form("profile_edit_form"):
        new_name = st.text_input(t("profile_name_label"), value=st.session_state.get("name", ""))
        new_email = st.text_input(t("profile_email_label"), value=st.session_state.get("email", ""))
        if st.form_submit_button(t("profile_save_btn"), type="primary", use_container_width=True):
            update_profile(session, username, new_name.strip(), new_email.strip())
            # st.session_state["name"] is also read by the sidebar's
            # "Zalogowano jako" banner, which renders *before* this dialog
            # in script order -- updating it here takes effect only on the
            # *next* rerun, not the one this form_submit_button triggers.
            # Rerunning immediately (with a one-shot flag for the success
            # message, since a plain st.success() here would be wiped out
            # by the rerun before ever being seen) makes the sidebar catch
            # up on the very same click instead of lagging one interaction
            # behind.
            st.session_state["name"] = new_name.strip()
            st.session_state["email"] = new_email.strip()
            st.session_state["profile_just_saved"] = True
            st.rerun()

    st.divider()
    # location="main" (not "sidebar") for the same reason as the sidebar's
    # login/register widgets -- this dialog isn't the sidebar at all, but
    # the lesson generalizes: location="sidebar" always targets the
    # sidebar's own top-level container regardless of where it's called
    # from, so it would render this form in the sidebar instead of here.
    try:
        if authenticator.reset_password(username, location="main", key="profile_reset_pw_form",
                                         fields=reset_password_fields(st.session_state["lang"])):
            persist_password_change(session, authenticator, username)
            st.success(t("profile_password_changed"))
    except Exception as exc:
        st.error(t("profile_password_error").format(error=str(exc)))


if st.session_state.get("show_profile"):
    _profile_dialog()


def render_favorites_strip():
    favorites = st.session_state["favorites"]
    if not favorites:
        return
    fav_destinations = sorted(
        (d for d in all_destinations if d.destination_id in favorites), key=destination_name,
    )
    with st.expander(f"⭐ {t('favorites_header')} ({len(fav_destinations)})", expanded=False):
        if st.session_state.get("authentication_status"):
            st.caption(t("account_favorites_persisted_note"))
        else:
            st.caption(t("favorites_note"))
        cols = st.columns(4)
        for idx, d in enumerate(fav_destinations):
            with cols[idx % 4]:
                render_photo(d, height_px=100)
                st.caption(destination_name(d))
                if st.button(t("card_view_details"), key=f"fav_view_{d.destination_id}",
                             use_container_width=True):
                    open_detail(d.destination_id, None)


def render_result_card(scored, mode: str):
    dest = scored.destination
    dest_id = dest.destination_id
    with st.container(border=True):
        col_photo, col_info, col_actions = st.columns([1.2, 3.3, 1])
        with col_photo:
            render_photo(dest)
        with col_info:
            st.markdown(f"### {destination_name(dest)}")
            st.markdown(f"**{t('match_' + scored.match_level)}** &nbsp;·&nbsp; "
                        f"{t('results_score_of').format(score=scored.score)}")
            for matched, pos_key, neg_key in scored.explanation_items():
                icon = "✅" if matched else "⚠️"
                st.caption(f"{icon} {t(pos_key if matched else neg_key)}")
            rate = dest.current_currency_rate.rate_to_pln if dest.current_currency_rate else None
            facts = f"💱 {dest.currency_code}" + (f" (1 ≈ {rate:.4f} PLN)" if rate else "")
            facts += f" &nbsp;·&nbsp; 🛂 MSZ {scored.current_msz_level}/4"
            st.markdown(f'<span style="font-size:0.85rem;color:#666">{facts}</span>', unsafe_allow_html=True)
        with col_actions:
            if st.button(t("card_view_details"), key=f"details_{mode}_{dest_id}", use_container_width=True):
                open_detail(dest_id, scored)
            is_fav = dest_id in st.session_state["favorites"]
            if st.button(t("favorite_remove") if is_fav else t("favorite_add"),
                         key=f"fav_{mode}_{dest_id}", use_container_width=True):
                toggle_favorite(dest_id)
                st.rerun()


# --- Results page: recommendation OR comparison, same rendering ----------
if active_page == "results":
    if _require_login():
        render_favorites_strip()

        if not st.session_state["search_done"]:
            st.info(t("results_empty"))
        else:
            mode = "comparison" if chosen_names else "recommendation"
            if mode == "comparison":
                name_to_dest = {destination_name(d): d for d in all_destinations}
                candidates = [name_to_dest[n] for n in chosen_names if n in name_to_dest]
            else:
                candidates = all_destinations

            ranked = rank_destinations(candidates, trip_length_days, travel_month, risk_tolerance)

            header_key = "results_header_comparison" if mode == "comparison" else "results_header_recommendation"
            caption_key = "results_mode_caption_comparison" if mode == "comparison" else "results_mode_caption_recommendation"
            st.subheader(t(header_key))
            st.caption(t(caption_key))

            if not ranked:
                st.warning(t("results_no_selected_destinations"))
            else:
                for scored in ranked:
                    render_result_card(scored, mode)

# --- Explore destinations: search/filter + click-through detail dialog --
if active_page == "explore":
    if _require_login():
        st.subheader(t("gallery_header"))
        st.caption(t("gallery_intro"))

        col_search, col_region = st.columns([3, 1])
        with col_search:
            search_query = st.text_input(
                t("explore_search_placeholder"), key="explore_search",
                label_visibility="collapsed", placeholder=t("explore_search_placeholder"),
            )
        with col_region:
            region_filter = st.segmented_control(
                "region", options=["all", "europe", "non_europe"],
                format_func=lambda v: {"all": t("explore_region_all"), "europe": t("explore_region_europe"),
                                        "non_europe": t("explore_region_non_europe")}[v],
                default="all", key="explore_region", label_visibility="collapsed",
            ) or "all"

        filtered = [d for d in all_destinations if region_filter == "all" or d.region == region_filter]
        if search_query.strip():
            q = search_query.strip().lower()
            filtered = [d for d in filtered if q in d.name_en.lower() or q in d.name_pl.lower()]
        filtered = sorted(filtered, key=destination_name)

        if not filtered:
            st.info(t("explore_no_results"))
        else:
            explore_cols = st.columns(4)
            for idx, dest in enumerate(filtered):
                with explore_cols[idx % 4]:
                    st.markdown(f'<div class="gallery-caption">{destination_name(dest)}</div>', unsafe_allow_html=True)
                    render_photo(dest, height_px=120)
                    if st.button(t("explore_open"), key=f"explore_open_{dest.destination_id}",
                                 use_container_width=True):
                        open_detail(dest.destination_id, None)
                    if st.button(t("explore_add_to_compare"), key=f"explore_add_{dest.destination_id}",
                                 use_container_width=True):
                        name = destination_name(dest)
                        st.session_state["pending_add_to_compare"] = name
                        st.toast(t("explore_added_to_compare").format(name=name))
                        st.rerun()

# --- Contextual data: MSZ explainer + Power BI link ----------------------
if active_page == "info":
    if _require_login():
        st.subheader(t("msz_info_header"))
        st.caption(t("msz_info_caption"))

        st.subheader(t("bi_header"))
        st.caption(t("bi_link_caption"))
        report_url = os.environ.get("POWERBI_REPORT_URL", "")
        if report_url:
            st.link_button(f"📊 {t('bi_open_link')}", report_url)
        else:
            st.warning(t("bi_missing"))

# --- Account: favorites list, persisted to the DB -----
if active_page == "account":
    if _require_login():
        st.subheader(t("account_favorites_header"))

        favorites = st.session_state["favorites"]
        if not favorites:
            st.info(t("account_favorites_empty"))
        else:
            st.caption(t("account_favorites_persisted_note"))
            fav_destinations = sorted(
                (d for d in all_destinations if d.destination_id in favorites), key=destination_name,
            )
            acct_cols = st.columns(4)
            for idx, d in enumerate(fav_destinations):
                with acct_cols[idx % 4]:
                    render_photo(d, height_px=100)
                    st.caption(destination_name(d))
                    if st.button(t("card_view_details"), key=f"acct_view_{d.destination_id}",
                                 use_container_width=True):
                        open_detail(d.destination_id, None)

# --- About / how it works page -- unrestricted, see _require_login() -----
if active_page == "about":
    st.subheader(t("about_header"))
    st.write(t("about_text"))
    st.subheader(t("about_accounts_header"))
    st.write(t("about_accounts_text"))

# --- Admin page: never offered in the nav (above) unless is_admin, but
# guarded again here too as defense in depth against a stale nav
# selection surviving a lost-admin/logout transition. Admin status itself
# is decided once, at registration (see the sidebar's admin-code field
# and core.auth.grant_admin_if_code_matches) -- not re-prompted here, per
# the requirement that it be "verified in the login or signup stage"
# rather than behind a separate in-app password gate. -------------------
if active_page == "admin" and st.session_state.get("is_admin"):
    st.subheader(t("admin_users_header"))
    st.caption(t("admin_users_blocked_note"))
    for row in list_all_users_with_stats(session):
        u = row["user"]
        with st.container(border=True):
            cols = st.columns([2, 2, 3, 2, 2, 2])
            cols[0].markdown(f"**@{u.username}**" + (" 🔐" if u.is_admin else ""))
            cols[1].write(u.name)
            cols[2].write(u.email or "—")
            cols[3].write(f"{t('admin_users_favorites')}: {row['favorites_count']}")
            last_login = row["last_login_at"].strftime("%Y-%m-%d %H:%M") if row["last_login_at"] \
                else t("admin_users_never_logged_in")
            cols[4].write(f"{t('admin_users_last_login')}: {last_login}")
            status = t("admin_users_status_blocked") if u.is_blocked else t("admin_users_status_active")
            cols[5].write(status)

            with st.expander(t("admin_users_edit_expander")):
                edit_name = st.text_input(t("profile_name_label"), value=u.name, key=f"admin_edit_name_{u.user_id}")
                edit_email = st.text_input(t("profile_email_label"), value=u.email or "",
                                            key=f"admin_edit_email_{u.user_id}")
                edit_cols = st.columns(2)
                if edit_cols[0].button(t("profile_save_btn"), key=f"admin_save_user_{u.user_id}",
                                        use_container_width=True):
                    update_profile(session, u.username, edit_name.strip(), edit_email.strip())
                    st.success(t("profile_saved"))
                    st.rerun()
                block_label = t("admin_users_unblock_btn") if u.is_blocked else t("admin_users_block_btn")
                if edit_cols[1].button(block_label, key=f"admin_block_user_{u.user_id}",
                                        use_container_width=True):
                    set_user_blocked(session, u.user_id, not u.is_blocked)
                    st.rerun()

    st.divider()
    st.subheader(t("admin_login_log_header"))
    login_log = get_recent_login_log(session, limit=50)
    if not login_log:
        st.caption(t("admin_login_log_empty"))
    else:
        for username, logged_in_at in login_log:
            st.caption(f"@{username} — {logged_in_at.strftime('%Y-%m-%d %H:%M:%S')}")

    st.divider()
    st.subheader(t("admin_risks_header"))
    risks = session.query(SeasonalRisk).all()
    for risk in risks:
        dest = session.get(Destination, risk.destination_id)
        cols = st.columns([3, 2, 3, 1, 1])
        cols[0].write(destination_name(dest))
        cols[1].write(month_name(risk.month))
        cols[2].write(risk.risk_type_pl if st.session_state["lang"] == "pl" else risk.risk_type_en)
        cols[3].write(risk.severity)
        if cols[4].button(t("admin_delete"), key=f"del_{risk.risk_id}"):
            session.delete(risk)
            session.commit()
            st.rerun()

    st.divider()
    st.markdown(f"**{t('admin_add_risk')}**")
    with st.form("add_risk_form", clear_on_submit=True):
        dest_options = {destination_name(d): d.destination_id for d in all_destinations}
        new_dest_name = st.selectbox(t("col_destination"), options=list(dest_options.keys()))
        new_month = st.selectbox(t("form_travel_month"), options=list(range(1, 13)),
                                  format_func=month_name)
        new_type = st.text_input(t("col_seasonal_risk"))
        new_severity = st.slider(t("results_score"), min_value=1, max_value=3, value=2)
        if st.form_submit_button(t("admin_add_risk")):
            session.add(SeasonalRisk(
                destination_id=dest_options[new_dest_name],
                month=new_month,
                risk_type_en=new_type, risk_type_pl=new_type,
                severity=new_severity,
            ))
            session.commit()
            st.success(t("admin_saved"))
            st.rerun()

# --- footer --------------------------------------------------
rates_fetched = [d.current_currency_rate.fetched_at for d in all_destinations
                  if d.current_currency_rate and d.current_currency_rate.rate_to_pln]
last_refresh = max(rates_fetched) if rates_fetched else None
st.divider()
st.caption(f"{t('footer_last_refresh')}: {last_refresh if last_refresh else t('footer_never')}")

session.close()
