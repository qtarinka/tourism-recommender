"""
Real user accounts via streamlit-authenticator (bcrypt-hashed passwords, a
signed re-auth cookie). A login is required to use the app at all -- see
docs/DEVELOPMENT_DOCUMENTATION.md §9's "Mandatory login" subsection for
why this replaced the original opt-in design.

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

from core.db import User, UserFavorite, UserLoginLog

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


def grant_admin_if_code_matches(session, username: str, entered_code: str) -> bool:
    """Called right after persist_new_user(), with whatever the registrant
    typed into the optional "admin code" field -- admin status is decided
    at registration time (per the requirement that it be "verified in the
    login or signup stage"), against the same shared ADMIN_PASSWORD secret
    the old, now-removed in-app admin password prompt used, so it carries
    no less security than before, just at a different point in the flow.
    A blank/non-matching code leaves the new account as an ordinary user --
    this never raises or blocks registration either way. Returns whether
    admin was granted, so the caller can show an appropriate message."""
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
    if not entered_code or entered_code != admin_password:
        return False
    user = session.query(User).filter_by(username=username).first()
    if user is None:
        return False
    user.is_admin = True
    session.commit()
    return True


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


def set_user_blocked(session, user_id: int, blocked: bool):
    user = session.get(User, user_id)
    if user is None:
        return
    user.is_blocked = blocked
    session.commit()


def list_all_users_with_stats(session):
    """One row per user for the admin panel's user-management table:
    the User row itself, its favorites count, and its most recent login
    timestamp (None if it's never actually completed a login -- e.g. a
    freshly registered account). A plain Python loop over a handful of
    users rather than a JOIN/aggregate query -- this app's scale (a
    handful of accounts) doesn't warrant the extra query complexity."""
    users = session.query(User).order_by(User.created_at.desc()).all()
    rows = []
    for user in users:
        fav_count = session.query(UserFavorite).filter_by(user_id=user.user_id).count()
        last_login = (
            session.query(UserLoginLog)
            .filter_by(user_id=user.user_id)
            .order_by(UserLoginLog.logged_in_at.desc())
            .first()
        )
        rows.append({
            "user": user,
            "favorites_count": fav_count,
            "last_login_at": last_login.logged_in_at if last_login else None,
        })
    return rows


def get_recent_login_log(session, limit: int = 50):
    """Most recent successful logins across all users, newest first, for
    the admin panel's activity view. Returns (username, logged_in_at)
    pairs rather than raw UserLoginLog rows so the caller doesn't need a
    second query per row to resolve the username."""
    rows = (
        session.query(UserLoginLog, User.username)
        .join(User, User.user_id == UserLoginLog.user_id)
        .order_by(UserLoginLog.logged_in_at.desc())
        .limit(limit)
        .all()
    )
    return [(username, log.logged_in_at) for log, username in rows]


def sync_session_with_auth(session, authenticator: stauth.Authenticate):
    """Runs once per script rerun, before any tab renders. On the run
    where a login is first detected (via the interactive form OR the
    re-auth cookie -- either way authentication_status flips to True),
    this is the single place that reacts to it:
      - blocked accounts are force-logged-out immediately, before any
        gated content below this call ever renders, with a flag set so
        app.py can show why;
      - a UserLoginLog row is recorded (once per browser session, not
        once per rerun -- see the "synced_for" marker below);
      - st.session_state["is_admin"] is loaded from the DB;
      - st.session_state["favorites"] (the set every card/strip reads
        and writes, unchanged) is replaced with that user's DB-persisted
        favorites.
    On the run where a logout is detected, all of the above resets back
    to an anonymous session. The "synced_for" marker (rather than
    re-querying on *every* run) is what makes this "once per login/logout
    transition" instead of "once per interaction" -- without it, an
    in-session Favorite toggle (which writes straight to the DB via
    toggle_favorite) would be immediately overwritten by a reload of
    what's already there, and login events would be logged on every
    single click instead of once per session."""
    username = st.session_state.get("username") if st.session_state.get("authentication_status") else None
    if st.session_state.get("auth_synced_for") == username:
        return

    if username:
        user = session.query(User).filter_by(username=username).first()
        if user and user.is_blocked:
            st.session_state["authentication_status"] = None
            st.session_state["username"] = None
            st.session_state["name"] = None
            st.session_state["account_blocked"] = True
            st.session_state["auth_synced_for"] = None
            # Without this, the re-auth cookie (if the block happened via
            # the cookie path rather than an interactive login) would just
            # log the same account back in on the very next rerun.
            authenticator.cookie_controller.delete_cookie()
            return
        session.add(UserLoginLog(user_id=user.user_id))
        session.commit()
        st.session_state["is_admin"] = bool(user.is_admin) if user else False
        st.session_state["favorites"] = load_user_favorites(session, username)
    else:
        st.session_state["is_admin"] = False
        st.session_state["favorites"] = set()
    st.session_state["auth_synced_for"] = username
