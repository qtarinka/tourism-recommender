"""
Optional, real user accounts via streamlit-authenticator (bcrypt-hashed
passwords, a signed re-auth cookie) layered on top of -- not replacing --
the session-only Favorites the app already has for anonymous users. Every
core feature (recommendations, comparison, exploring destinations) works
with zero account, per the original decision not to make login mandatory;
this only adds persistence for whoever opts in.

Credentials live in our own `users` table (core/db.py) rather than
streamlit-authenticator's usual YAML/JSON config file. Streamlit reruns
the whole script on every interaction, so nothing here can rely on
in-memory state surviving between runs -- the `credentials` dict handed
to `Authenticate()` is rebuilt from the DB fresh on every single run
(cheap at this app's scale), and a newly registered user is written to
the DB immediately so the next rerun's rebuilt dict includes them. This
is streamlit-authenticator's own documented pattern for a DB-backed
credential store, not a workaround.
"""
import os

import streamlit as st
import streamlit_authenticator as stauth

from core.db import User, UserFavorite

COOKIE_NAME = "tourism_app_auth"

# streamlit-authenticator's widgets take their own field-label overrides
# (separate from this app's core.i18n) -- defined here since they're
# tightly coupled to this exact library's expected dict keys, not general
# app content.
LOGIN_FIELDS = {
    "pl": {"Form name": "Logowanie", "Username": "Nazwa użytkownika", "Password": "Hasło", "Login": "Zaloguj"},
    "en": {"Form name": "Login", "Username": "Username", "Password": "Password", "Login": "Login"},
}
REGISTER_FIELDS = {
    "pl": {
        "Form name": "Rejestracja", "First name": "Imię", "Last name": "Nazwisko",
        "Email": "E-mail", "Username": "Nazwa użytkownika", "Password": "Hasło",
        "Repeat password": "Powtórz hasło", "Register": "Zarejestruj się",
    },
    "en": {
        "Form name": "Register", "First name": "First name", "Last name": "Last name",
        "Email": "Email", "Username": "Username", "Password": "Password",
        "Repeat password": "Repeat password", "Register": "Register",
    },
}


def login_fields(lang: str) -> dict:
    return LOGIN_FIELDS.get(lang, LOGIN_FIELDS["en"])


def register_fields(lang: str) -> dict:
    return REGISTER_FIELDS.get(lang, REGISTER_FIELDS["en"])


def _build_credentials(session) -> dict:
    users = session.query(User).all()
    return {
        "usernames": {
            u.username: {"email": u.email or "", "name": u.name, "password": u.password_hash}
            for u in users
        }
    }


def get_authenticator(session) -> stauth.Authenticate:
    """A fresh Authenticate object per script run, built from the current
    DB contents. auto_hash=False because every password_hash in the DB
    was already hashed by streamlit-authenticator itself at registration
    time (see persist_new_user) -- nothing here is ever plaintext."""
    cookie_key = os.environ.get("AUTH_COOKIE_KEY", "")
    if not cookie_key:
        raise RuntimeError(
            "AUTH_COOKIE_KEY is not set in .env -- required to sign the login cookie. "
            "See .env.example."
        )
    return stauth.Authenticate(
        _build_credentials(session),
        cookie_name=COOKIE_NAME,
        cookie_key=cookie_key,
        cookie_expiry_days=30,
        auto_hash=False,
    )


def persist_new_user(session, authenticator: stauth.Authenticate, username: str, name: str):
    """Call right after a successful authenticator.register_user() --
    reads the (already-hashed) new user's password back out of the
    authenticator's in-memory credentials and writes a row to the `users`
    table, which is what makes the registration durable across the next
    script rerun (the in-memory credentials dict itself is thrown away
    every rerun).

    `name` must be the full name returned by register_user() itself
    (its third return value, "first last") -- the credentials dict only
    stores first_name/last_name separately, never a combined "name" key,
    so reading record.get("name") back out always silently misses and
    falls back to the username instead.

    Verified by hitting a real AttributeError in the browser: the
    credentials dict lives on `authentication_controller.authentication_model`,
    one level deeper than the more obvious-looking
    `authentication_controller.credentials`."""
    record = authenticator.authentication_controller.authentication_model.credentials["usernames"][username]
    session.add(User(
        username=username,
        name=name or username,
        email=record.get("email") or None,
        password_hash=record["password"],
    ))
    session.commit()


RESET_PASSWORD_FIELDS = {
    "pl": {
        "Form name": "Zmień hasło", "Current password": "Obecne hasło",
        "New password": "Nowe hasło", "Repeat password": "Powtórz nowe hasło",
        "Reset": "Zmień hasło",
    },
    "en": {
        "Form name": "Change password", "Current password": "Current password",
        "New password": "New password", "Repeat password": "Repeat new password",
        "Reset": "Change password",
    },
}


def reset_password_fields(lang: str) -> dict:
    return RESET_PASSWORD_FIELDS.get(lang, RESET_PASSWORD_FIELDS["en"])


def update_profile(session, username: str, name: str, email: str):
    """Directly updates the `users` row's name/email -- unlike password
    changes, these aren't security-sensitive credentials, so this bypasses
    streamlit-authenticator's own update_user_details() widget (which only
    updates one field at a time via a dropdown) in favor of a single
    combined form in app.py's profile dialog. Caller is responsible for
    also updating st.session_state["name"]/["email"] afterward so the
    already-rendered "Zalogowano jako" banner reflects the change without
    needing a fresh login."""
    user = session.query(User).filter_by(username=username).first()
    if user is None:
        return
    user.name = name
    user.email = email or None
    session.commit()


def persist_password_change(session, authenticator: stauth.Authenticate, username: str):
    """Call right after a successful authenticator.reset_password() --
    same read-back-and-write pattern as persist_new_user(), for the same
    reason: reset_password() only updates the in-memory credentials dict
    (rebuilt fresh from `users` every rerun, see get_authenticator), and
    never touches the DB itself."""
    record = authenticator.authentication_controller.authentication_model.credentials["usernames"][username]
    user = session.query(User).filter_by(username=username).first()
    if user is None:
        return
    user.password_hash = record["password"]
    session.commit()


def get_user_id(session, username: str):
    user = session.query(User).filter_by(username=username).first()
    return user.user_id if user else None


def load_user_favorites(session, username: str) -> set:
    user_id = get_user_id(session, username)
    if user_id is None:
        return set()
    rows = session.query(UserFavorite.destination_id).filter_by(user_id=user_id).all()
    return {r[0] for r in rows}


def add_db_favorite(session, username: str, destination_id: int):
    user_id = get_user_id(session, username)
    if user_id is None:
        return
    exists = session.query(UserFavorite).filter_by(
        user_id=user_id, destination_id=destination_id).first()
    if not exists:
        session.add(UserFavorite(user_id=user_id, destination_id=destination_id))
        session.commit()


def remove_db_favorite(session, username: str, destination_id: int):
    user_id = get_user_id(session, username)
    if user_id is None:
        return
    session.query(UserFavorite).filter_by(
        user_id=user_id, destination_id=destination_id).delete()
    session.commit()


def sync_favorites_with_auth(session):
    """Runs once per script rerun, before any tab renders. Keeps
    st.session_state["favorites"] (the single set every card/strip
    already reads and writes, unchanged) in step with login state:
    on the run where a login is first detected, replaces it with that
    user's persisted favorites from the DB; on the run where a logout is
    detected, clears it back to an empty anonymous session. Uses a
    separate "synced_for" marker rather than re-loading from the DB on
    *every* run so that in-session toggles (which also write straight to
    the DB via toggle_favorite) aren't immediately overwritten by a
    reload of what's already there."""
    username = st.session_state.get("username") if st.session_state.get("authentication_status") else None
    if st.session_state.get("auth_synced_for") != username:
        st.session_state["favorites"] = load_user_favorites(session, username) if username else set()
        st.session_state["auth_synced_for"] = username
