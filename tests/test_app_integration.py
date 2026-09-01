"""
Integration smoke tests using Streamlit's built-in AppTest harness
(streamlit.testing.v1) -- runs the real app script headlessly and lets
us assert on the rendered widget tree, closer to a real browser session
than pure unit tests.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_runs_without_exceptions():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception


def _all_markdown_html(at):
    """The hero banner is raw HTML via st.markdown, not st.title, so
    AppTest's `.title` accessor won't see it -- search markdown blocks."""
    return "\n".join(el.value for el in at.markdown)


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
    assert len(at.tabs) == 5
