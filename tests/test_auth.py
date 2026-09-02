from core.db import User
from core.auth import (
    get_user_id, load_user_favorites, add_db_favorite, remove_db_favorite,
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
