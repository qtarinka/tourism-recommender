from core.db import User, UserLoginLog
from core.auth import (
    get_user_id, load_user_favorites, add_db_favorite, remove_db_favorite,
    grant_admin_if_code_matches, set_user_blocked, list_all_users_with_stats,
    get_recent_login_log,
)


def _make_user(db_session, username="jkowalski"):
    user = User(username=username, name="Jan Kowalski", email="jan@example.com",
                password_hash="$2b$fakehash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_get_user_id_returns_none_for_unknown_username(db_session):
    assert get_user_id(db_session, "nobody") is None


def test_get_user_id_returns_correct_id(db_session):
    user = _make_user(db_session)
    assert get_user_id(db_session, "jkowalski") == user.user_id


def test_load_user_favorites_empty_for_unknown_username(db_session):
    assert load_user_favorites(db_session, "nobody") == set()


def test_add_and_load_db_favorite_round_trips(db_session):
    _make_user(db_session)
    add_db_favorite(db_session, "jkowalski", destination_id=1)
    add_db_favorite(db_session, "jkowalski", destination_id=2)
    assert load_user_favorites(db_session, "jkowalski") == {1, 2}


def test_add_db_favorite_is_idempotent(db_session):
    _make_user(db_session)
    add_db_favorite(db_session, "jkowalski", destination_id=1)
    add_db_favorite(db_session, "jkowalski", destination_id=1)
    assert load_user_favorites(db_session, "jkowalski") == {1}


def test_remove_db_favorite(db_session):
    _make_user(db_session)
    add_db_favorite(db_session, "jkowalski", destination_id=1)
    add_db_favorite(db_session, "jkowalski", destination_id=2)
    remove_db_favorite(db_session, "jkowalski", destination_id=1)
    assert load_user_favorites(db_session, "jkowalski") == {2}


def test_favorites_are_scoped_per_user(db_session):
    _make_user(db_session, username="alice")
    _make_user(db_session, username="bob")
    add_db_favorite(db_session, "alice", destination_id=1)
    add_db_favorite(db_session, "bob", destination_id=2)
    assert load_user_favorites(db_session, "alice") == {1}
    assert load_user_favorites(db_session, "bob") == {2}


def test_grant_admin_if_code_matches_correct_code(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
    user = _make_user(db_session)
    assert grant_admin_if_code_matches(db_session, "jkowalski", "secret123") is True
    db_session.refresh(user)
    assert user.is_admin is True


def test_grant_admin_if_code_matches_wrong_code(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
    user = _make_user(db_session)
    assert grant_admin_if_code_matches(db_session, "jkowalski", "wrong") is False
    db_session.refresh(user)
    assert user.is_admin is False


def test_grant_admin_if_code_matches_blank_code_does_not_grant(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
    user = _make_user(db_session)
    assert grant_admin_if_code_matches(db_session, "jkowalski", "") is False
    db_session.refresh(user)
    assert user.is_admin is False


def test_set_user_blocked_toggles_flag(db_session):
    user = _make_user(db_session)
    assert user.is_blocked is False
    set_user_blocked(db_session, user.user_id, True)
    db_session.refresh(user)
    assert user.is_blocked is True
    set_user_blocked(db_session, user.user_id, False)
    db_session.refresh(user)
    assert user.is_blocked is False


def test_list_all_users_with_stats_includes_favorites_count_and_last_login(db_session):
    user = _make_user(db_session)
    add_db_favorite(db_session, "jkowalski", destination_id=1)
    add_db_favorite(db_session, "jkowalski", destination_id=2)
    db_session.add(UserLoginLog(user_id=user.user_id))
    db_session.commit()

    rows = list_all_users_with_stats(db_session)
    assert len(rows) == 1
    assert rows[0]["user"].username == "jkowalski"
    assert rows[0]["favorites_count"] == 2
    assert rows[0]["last_login_at"] is not None


def test_list_all_users_with_stats_last_login_none_when_never_logged_in(db_session):
    _make_user(db_session)
    rows = list_all_users_with_stats(db_session)
    assert rows[0]["last_login_at"] is None


def test_get_recent_login_log_returns_username_and_timestamp_newest_first(db_session):
    from datetime import datetime, timezone
    alice = _make_user(db_session, username="alice")
    bob = _make_user(db_session, username="bob")
    # Explicit, clearly-ordered timestamps -- default=lambda: datetime.now(...)
    # on both rows created microseconds apart isn't a reliable enough gap
    # to assert ordering against.
    db_session.add(UserLoginLog(user_id=alice.user_id,
                                 logged_in_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db_session.add(UserLoginLog(user_id=bob.user_id,
                                 logged_in_at=datetime(2026, 1, 2, tzinfo=timezone.utc)))
    db_session.commit()

    log = get_recent_login_log(db_session)
    assert [username for username, _ in log] == ["bob", "alice"]
