"""
Integration smoke tests using Streamlit's built-in AppTest harness
(streamlit.testing.v1) -- runs the real app script headlessly and lets
us assert on the rendered widget tree, closer to a real browser session
than pure unit tests.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def _mock_wikipedia_get(url, params=None, headers=None, timeout=None):
    """Fast, deterministic stand-in for live Wikipedia calls -- AppTest
    runs the real app.py script in-process, so patching core.images's
    requests.get affects it directly. Used for tests that don't care
    about actual photo/summary content, only that the app doesn't crash
    and renders the expected destination text -- avoids depending on
    live network speed/availability for CI-style runs."""
    from unittest.mock import MagicMock
    resp = MagicMock()
    resp.status_code = 200
    if params and params.get("prop") == "extracts|info":
        resp.json.return_value = {"query": {"pages": {"1": {
            "extract": "Test extract.", "fullurl": "https://en.wikipedia.org/wiki/Test",
        }}}}
    else:
        resp.json.return_value = {"query": {"pages": {"1": {
            "thumbnail": {"source": "https://upload.wikimedia.org/test.jpg"},
            "fullurl": "https://en.wikipedia.org/wiki/Test",
        }}}}
    return resp


def _login(at, username="apptest_user", name="AppTest User", email="apptest@example.com",
           is_admin=False):
    """Pre-seeds AppTest's session_state as an already-authenticated user,
    bypassing the real login form entirely. Safe to call before the first
    .run(): authenticator.login(location="unrendered")'s own cookie-check
    only runs when authentication_status isn't already truthy (see
    core/auth.py and the app.py comment on the LoginError fix), so setting
    it up front makes that bootstrap call a no-op instead of touching a
    real cookie or the DB. auth_synced_for is pre-set to the same username
    so sync_session_with_auth() doesn't issue a real (harmless, but
    pointless) DB lookup/write for a username that doesn't exist in
    whichever database this test run happens to be pointed at -- which
    also means is_admin has to be pre-seeded directly here rather than
    relying on that DB-backed sync to set it."""
    at.session_state["authentication_status"] = True
    at.session_state["username"] = username
    at.session_state["name"] = name
    at.session_state["email"] = email
    at.session_state["auth_synced_for"] = username
    at.session_state["is_admin"] = is_admin


def _st_element_exists(accessor, key):
    """AppTest's keyed accessors (e.g. at.sidebar.button(key=...)) raise
    KeyError rather than returning None when no such widget was rendered
    this run -- used to assert a widget is genuinely absent (e.g. the
    logged-out sidebar), not just empty/default-valued."""
    try:
        accessor(key=key)
        return True
    except KeyError:
        return False


def test_app_runs_without_exceptions():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception


def _all_markdown_html(at):
    """The hero banner is raw HTML via st.markdown, not st.title, so
    AppTest's `.title` accessor won't see it -- search markdown blocks.
    Also pulls in subheader/caption/text, since results/explore content
    uses those element types too, not just st.markdown."""
    parts = [el.value for el in at.markdown]
    parts += [el.value for el in at.subheader]
    parts += [el.value for el in at.caption]
    parts += [el.value for el in at.text]
    return "\n".join(parts)


def test_default_language_is_polish_and_switches_to_english():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert "System Wspomagania Decyzji" in _all_markdown_html(at)

    at.sidebar.selectbox[0].select("en").run(timeout=30)
    assert not at.exception
    assert "Outbound Tourism Decision Support" in _all_markdown_html(at)


def test_nav_offers_five_pages_and_admin_only_for_admins():
    """The main nav is a segmented control bound to main_nav, not st.tabs()
    (st.tabs() has no supported way to select a page from Python, which
    both "Find destinations" jumping to Results and hiding Admin from
    non-admins need). Five pages always; a sixth (Admin) only once
    is_admin is set."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception
    nav = at.segmented_control(key="main_nav")
    # .options holds the *labels* (format_func output), not the raw page
    # keys -- "Panel administratora" is the Admin page's Polish label.
    assert len(nav.options) == 5
    assert "Panel administratora" not in nav.options

    at2 = AppTest.from_file(APP_PATH)
    _login(at2, is_admin=True)
    at2.run(timeout=30)
    assert not at2.exception
    nav2 = at2.segmented_control(key="main_nav")
    assert len(nav2.options) == 6
    assert "Panel administratora" in nav2.options


def test_find_destinations_jumps_to_results_page():
    """Clicking "Find destinations" while on a different page navigates to
    Results, not just marks a search done that you'd only see by
    separately clicking over to Results yourself. Reported directly: "it
    doesnt show destination except you are in result page"."""
    with patch("core.images.requests.get", side_effect=_mock_wikipedia_get):
        at = AppTest.from_file(APP_PATH)
        _login(at)
        at.session_state["main_nav"] = "explore"
        at.run(timeout=30)
        assert at.session_state["main_nav"] == "explore"

        at.sidebar.button(key="find_destinations_btn").click().run(timeout=30)
        assert not at.exception
        assert at.session_state["main_nav"] == "results"
        assert "Ranking rekomendacji" in _all_markdown_html(at)


def test_unified_form_recommendation_mode_ranks_all_destinations():
    """No destinations selected -> recommendation mode: all 20 are
    scored and rendered. This is the single "Find destinations" flow
    replacing the old separate recommendation/comparison forms. Requires
    being logged in -- the whole app is now gated behind an account."""
    with patch("core.images.requests.get", side_effect=_mock_wikipedia_get):
        at = AppTest.from_file(APP_PATH)
        _login(at)
        at.run(timeout=30)
        assert at.sidebar.multiselect(key="destinations_multiselect").value == []

        at.sidebar.button(key="find_destinations_btn").click().run(timeout=30)
        assert not at.exception
        html = _all_markdown_html(at)
        assert "Ranking rekomendacji" in html
        # A known seeded destination should appear somewhere in the ranking.
        assert "Austria" in html


def test_unified_form_comparison_mode_ranks_only_selected_destinations():
    """Selecting destinations in the same sidebar form switches to
    comparison mode -- same button, same results renderer, only the
    candidate list differs (core.scoring.rank_destinations called with
    a smaller list rather than a separate comparison algorithm)."""
    with patch("core.images.requests.get", side_effect=_mock_wikipedia_get):
        at = AppTest.from_file(APP_PATH)
        _login(at)
        at.run(timeout=30)

        at.sidebar.multiselect(key="destinations_multiselect").set_value(["Egipt"]).run(timeout=30)
        at.sidebar.button(key="find_destinations_btn").click().run(timeout=30)
        assert not at.exception
        html = _all_markdown_html(at)
        assert "Porównanie wybranych kierunków" in html
        assert "Egipt" in html


def test_logged_out_sidebar_has_no_criteria_form():
    """The app requires a logged-in account to be used at all -- while
    logged out, the sidebar should contain only the language selector and
    the login/register widget, not the travel-criteria form (slider,
    multiselect, submit button)."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception
    assert not _st_element_exists(at.sidebar.multiselect, key="destinations_multiselect")
    assert not _st_element_exists(at.sidebar.button, key="find_destinations_btn")
    assert len(at.sidebar.slider) == 0  # the trip-length slider isn't rendered at all


def test_logged_out_pages_show_locked_message_not_real_content():
    """Results/Explore/Contextual data/Account all show the locked message
    instead of their real, interactive content when logged out -- "any
    clicks to result, data or explore can't work" without an account.
    Only one page's content renders at a time now (the nav is a plain
    Python if/elif on active_page, not st.tabs(), which used to render
    every tab's content simultaneously just CSS-hidden) so each gated page
    has to be selected and checked individually. Admin isn't included
    here: it's not even reachable via the nav while logged out (see
    test_nav_offers_five_pages_and_admin_only_for_admins). Only About
    stays unrestricted (see the separate test below)."""
    for page in ["results", "explore", "info", "account"]:
        at = AppTest.from_file(APP_PATH)
        at.session_state["main_nav"] = page
        at.run(timeout=30)
        assert not at.exception, f"page={page}"
        locked = [el.value for el in at.info if "Zaloguj się w panelu bocznym" in el.value]
        assert len(locked) == 1, f"page={page}"
    # None of Explore's search box should have rendered while on that page.
    at = AppTest.from_file(APP_PATH)
    at.session_state["main_nav"] = "explore"
    at.run(timeout=30)
    with pytest.raises(KeyError):
        at.text_input(key="explore_search")


def test_logged_in_shows_profile_button_and_full_sidebar():
    """Once authenticated, the sidebar carries the full criteria form and
    a "Profile" button appears above the hero banner."""
    at = AppTest.from_file(APP_PATH)
    _login(at)
    at.run(timeout=30)
    assert not at.exception
    assert at.sidebar.multiselect(key="destinations_multiselect") is not None
    assert at.sidebar.button(key="find_destinations_btn") is not None
    assert at.button(key="open_profile_btn") is not None


def test_about_page_accessible_without_login():
    """The About/"How it works" page is informational only (no interactive
    features), so it deliberately stays outside the login gate -- reachable
    from the nav (which is always shown, even logged out) and renders its
    real content rather than a locked message."""
    at = AppTest.from_file(APP_PATH)
    at.session_state["main_nav"] = "about"
    at.run(timeout=30)
    assert not at.exception
    assert "Jak to działa" in _all_markdown_html(at)
