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

# Must run before importing core.db: it reads DATABASE_URL at *import*
# time (module-level `create_engine(...)`), so .env has to be loaded
# first or that read sees an unset var even though .env defines it.
load_dotenv()

from core.db import init_db, get_session, Destination, SeasonalRisk
from core.seed_data import seed_if_empty
from core.i18n import t, month_name, LANGUAGES
from core.scoring import rank_destinations, low_risk_months
from core.images import get_landmark_image, get_destination_photos, get_country_summary
from core.theme import CUSTOM_CSS

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
    if dest_id in favs:
        favs.discard(dest_id)
    else:
        favs.add(dest_id)


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

    submitted = st.button(f"🔎 {t('form_submit')}", type="primary", use_container_width=True)
    if submitted:
        st.session_state["search_done"] = True

render_hero()

tab_results, tab_explore, tab_info, tab_about, tab_admin = st.tabs([
    f"🏆 {t('nav_results')}", f"🧭 {t('nav_explore')}", f"📊 {t('info_header')}",
    f"ℹ️ {t('about_header')}", f"🔐 {t('nav_admin')}",
])


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
    summary = get_country_summary(dest.name_en)
    if summary:
        st.write(summary["extract"])
        if summary.get("page_url"):
            st.markdown(f"[{t('detail_read_more')}]({summary['page_url']})")
    else:
        st.caption(t("detail_general_info_missing"))

    st.markdown(f'<div class="detail-section-header">💱 {t("detail_currency_header")}</div>', unsafe_allow_html=True)
    rate = dest.currency_rate.rate_to_pln if dest.currency_rate else None
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


def render_favorites_strip():
    favorites = st.session_state["favorites"]
    if not favorites:
        return
    fav_destinations = sorted(
        (d for d in all_destinations if d.destination_id in favorites), key=destination_name,
    )
    with st.expander(f"⭐ {t('favorites_header')} ({len(fav_destinations)})", expanded=False):
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
            rate = dest.currency_rate.rate_to_pln if dest.currency_rate else None
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


# --- Results tab: recommendation OR comparison, same rendering ----------
with tab_results:
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
with tab_explore:
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
with tab_info:
    st.subheader(t("msz_info_header"))
    st.caption(t("msz_info_caption"))

    st.subheader(t("bi_header"))
    st.caption(t("bi_link_caption"))
    report_url = os.environ.get("POWERBI_REPORT_URL", "")
    if report_url:
        st.link_button(f"📊 {t('bi_open_link')}", report_url)
    else:
        st.warning(t("bi_missing"))

# --- About / how it works tab --------------------------------------------------
with tab_about:
    st.subheader(t("about_header"))
    st.write(t("about_text"))
    st.subheader(t("about_accounts_header"))
    st.write(t("about_accounts_text"))

# --- Admin tab --------------------------------------------------
with tab_admin:
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
    if not st.session_state.get("is_admin"):
        st.subheader(t("admin_login_header"))
        pw = st.text_input(t("admin_password"), type="password")
        if st.button(t("admin_login_btn")):
            if pw == admin_password:
                st.session_state["is_admin"] = True
                st.rerun()
            else:
                st.error(t("admin_login_error"))
    else:
        st.subheader(t("admin_risks_header"))
        if st.button(t("admin_logout")):
            st.session_state["is_admin"] = False
            st.rerun()

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
rates_fetched = [d.currency_rate.fetched_at for d in all_destinations
                  if d.currency_rate and d.currency_rate.rate_to_pln]
last_refresh = max(rates_fetched) if rates_fetched else None
st.divider()
st.caption(f"{t('footer_last_refresh')}: {last_refresh if last_refresh else t('footer_never')}")

session.close()
