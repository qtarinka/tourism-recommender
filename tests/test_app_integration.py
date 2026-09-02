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
    replacing the old separate recommendation/comparison forms."""
    with patch("core.images.requests.get", side_effect=_mock_wikipedia_get):
        at = AppTest.from_file(APP_PATH)
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
        at.run(timeout=30)

        at.sidebar.multiselect(key="destinations_multiselect").set_value(["Egipt"]).run(timeout=30)
        at.sidebar.button(key="find_destinations_btn").click().run(timeout=30)
        assert not at.exception
        html = _all_markdown_html(at)
        assert "Porównanie wybranych kierunków" in html
        assert "Egipt" in html
