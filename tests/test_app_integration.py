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


def _login(at, username="apptest_user", name="AppTest User", email="apptest@example.com"):
    """Pre-seeds AppTest's session_state as an already-authenticated user,
    bypassing the real login form entirely. Safe to call before the first
    .run(): authenticator.login(location="unrendered")'s own cookie-check
    only runs when authentication_status isn't already truthy (see
    core/auth.py and the app.py comment on the LoginError fix), so setting
    it up front makes that bootstrap call a no-op instead of touching a
    real cookie or the DB. auth_synced_for is pre-set to the same username
    so sync_favorites_with_auth() doesn't issue a real (harmless, but
    pointless) DB lookup for a username that doesn't exist in whichever
    database this test run happens to be pointed at."""
    at.session_state["authentication_status"] = True
    at.session_state["username"] = username
    at.session_state["name"] = name
    at.session_state["email"] = email
    at.session_state["auth_synced_for"] = username


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


def test_tabs_render_recommendation_comparison_info_about_admin():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception
    # 6 top-level tabs: Results, Explore, Contextual data, Account, About,
    # Admin. The sidebar's login/register widget toggles between the two
    # forms with a plain button rather than nested st.tabs (see app.py's
    # comment on why -- streamlit-authenticator's location="sidebar" bypasses
    # nested containers, so real st.tabs() there rendered both forms
    # unconditionally), so there's nothing left to flatten in from there.
    assert len(at.tabs) == 6


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


def test_logged_out_tabs_show_locked_message_not_real_content():
    """Results/Explore/Contextual data/Account/Admin all show the same
    locked message instead of their real, interactive content when logged
    out -- "any clicks to result, data or explore can't work" without an
    account. Only About stays unrestricted (see the separate test below)."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception
    locked_messages = [el.value for el in at.info if "Zaloguj się w panelu bocznym" in el.value]
    # Results, Explore, Contextual data, Account, Admin -- 5 gated tabs
    # (every tab except About, which is informational-only).
    assert len(locked_messages) == 5
    # None of Explore's search box or region filter should have rendered.
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


def test_about_tab_accessible_without_login():
    """The About/"How it works" tab is informational only (no interactive
    features), so it deliberately stays outside the login gate."""
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception
    # The tab's own header text should render regardless of login state.
    assert "Jak to działa" in _all_markdown_html(at)
