"""
Streamlit entrypoint: `streamlit run app.py`

Tourism outbound-trip decision support system (thesis chapters 3-7
implementation) with an added English/Polish language switcher, real
destination photography, and a visual redesign beyond the thesis's scope.
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
from core.scoring import rank_destinations
from core.images import get_landmark_image, get_destination_photos
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

# --- sidebar: language + preferences form ------------------------------
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

    submitted = st.button(f"🔎 {t('form_submit')}", type="primary", use_container_width=True)

session = get_session()
all_destinations = session.query(Destination).all()

_HERO_LANDMARK_DESTINATIONS = ["France", "Italy", "Greece", "Egypt"]


def destination_name(dest):
    return dest.name_pl if st.session_state["lang"] == "pl" else dest.name_en


def _photo_credit(img):
    credit = f"{t('photo_credit_prefix')}: {img['title']}"
    if img.get("page_url"):
        credit = f"{credit} — [{t('photo_via_wikipedia')}]({img['page_url']})"
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


render_hero()

tab_reco, tab_compare, tab_info, tab_about, tab_admin = st.tabs([
    f"🏆 {t('nav_recommendation')}", f"⚖️ {t('nav_comparison')}", f"📊 {t('info_header')}",
    f"ℹ️ {t('about_header')}", f"🔐 {t('nav_admin')}",
])


# --- Recommendation tab --------------------------------------------------
with tab_reco:
    if not submitted:
        st.info(t("results_empty"))
    else:
        st.subheader(t("results_header"))
        ranked = rank_destinations(all_destinations, trip_length_days, travel_month, risk_tolerance)

        for scored in ranked:
            dest = scored.destination
            with st.container(border=True):
                col_photo, col_info, col_score = st.columns([1.3, 3.2, 1])
                with col_photo:
                    render_photo(dest)
                with col_info:
                    st.markdown(f"### {destination_name(dest)}")
                    badges = []
                    if scored.trip_length_match:
                        badges.append("✅ " + t("form_trip_length"))
                    if scored.seasonal_risk_match:
                        badges.append("✅ " + t("col_seasonal_risk"))
                    if scored.msz_status_match:
                        badges.append("✅ " + t("col_msz_level"))
                    st.write(" · ".join(badges) if badges else "—")
                with col_score:
                    st.metric(t("results_score"), f"{scored.score} / 3")

# --- Comparison tab --------------------------------------------------
with tab_compare:
    st.subheader(t("compare_header"))
    options = {destination_name(d): d.destination_id for d in all_destinations}
    chosen_names = st.multiselect(t("compare_select"), options=list(options.keys()))

    if chosen_names:
        photo_cols = st.columns(len(chosen_names))
        for col, name in zip(photo_cols, chosen_names):
            with col:
                st.markdown(f'<div class="gallery-caption">{name}</div>', unsafe_allow_html=True)
                render_photo(session.get(Destination, options[name]), height_px=110)

        st.caption(f"ℹ️ {t('msz_info_caption')}")

        rows = []
        for name in chosen_names:
            dest = session.get(Destination, options[name])
            month_risks = [r for r in dest.seasonal_risks if r.month == travel_month]
            risk_text = ", ".join(
                (r.risk_type_pl if st.session_state["lang"] == "pl" else r.risk_type_en)
                for r in month_risks
            ) or t("col_none")
            msz_level = max((w.level for w in dest.msz_warnings), default=1)
            msz_message = dest.msz_warnings[-1].message_pl if st.session_state["lang"] == "pl" else (
                dest.msz_warnings[-1].message_en if dest.msz_warnings else "")
            rows.append({
                t("col_destination"): name,
                t("col_region"): dest.region,
                t("col_currency"): dest.currency_code,
                t("col_rate"): round(dest.currency_rate.rate_to_pln, 4) if dest.currency_rate else None,
                t("col_avg_stay"): dest.gus_stats.avg_stay_length_days if dest.gus_stats else None,
                t("col_msz_level"): msz_level,
                t("col_msz_message"): msz_message,
                t("col_seasonal_risk"): risk_text,
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

# --- Info / context tab --------------------------------------------------
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

    st.subheader(t("gallery_header"))
    st.caption(t("gallery_intro"))
    gallery_cols = st.columns(4)
    for idx, dest in enumerate(sorted(all_destinations, key=destination_name)):
        with gallery_cols[idx % 4]:
            st.markdown(f'<div class="gallery-caption">{destination_name(dest)}</div>', unsafe_allow_html=True)
            render_photo(dest, height_px=120)
            # Genuinely lazy: an st.expander's body runs on every rerun
            # regardless of whether it's visually open, so fetching all
            # 20 destinations' extra photos would mean ~60 Wikipedia
            # calls on every single interaction anywhere in the app.
            # A session_state toggle only fetches once actually clicked.
            show_key = f"show_photos_{dest.destination_id}"
            if st.button(f"📷 {t('gallery_expand')}", key=f"btn_{dest.destination_id}",
                         use_container_width=True):
                st.session_state[show_key] = not st.session_state.get(show_key, False)
            if st.session_state.get(show_key):
                photos = get_destination_photos(dest.name_en)
                if not photos:
                    st.caption(t("col_none"))
                for photo in photos:
                    st.image(photo["image_url"], use_container_width=True)
                    st.caption(_photo_credit(photo))

# --- About / how it works tab --------------------------------------------------
with tab_about:
    st.subheader(t("about_header"))
    st.write(t("about_text"))

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
