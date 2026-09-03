"""
Database layer.

Defaults to a local SQLite file (data/app.db) so the app runs with zero
external setup. Set DATABASE_URL (e.g. postgresql+psycopg2://user:pass@host/db)
to point at a real PostgreSQL server instead -- no code changes needed,
since all queries go through SQLAlchemy's ORM rather than raw SQL.
"""
import os
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime,
    ForeignKey, Boolean, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")
# `or` (not .get's default arg) so an empty DATABASE_URL= line in .env --
# a var that IS set, just to "" -- falls back to SQLite too, not just a
# truly-unset var.
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{os.path.abspath(DEFAULT_SQLITE_PATH)}"

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class Destination(Base):
    __tablename__ = "destinations"

    destination_id = Column(Integer, primary_key=True)
    name_en = Column(String(80), nullable=False)
    name_pl = Column(String(80), nullable=False)
    country_en = Column(String(80), nullable=False)
    country_pl = Column(String(80), nullable=False)
    region = Column(String(20), nullable=False)  # 'europe' | 'non_europe'
    currency_code = Column(String(3), nullable=False)  # ISO 4217
    is_active = Column(Boolean, default=True, nullable=False)

    gus_stats = relationship("GusTourismStat", back_populates="destination", uselist=False,
                              cascade="all, delete-orphan")
    msz_warnings = relationship("MszSafetyWarning", back_populates="destination",
                                 cascade="all, delete-orphan")
    seasonal_risks = relationship("SeasonalRisk", back_populates="destination",
                                   cascade="all, delete-orphan")
    # A list, not a single row: the scheduler (core/etl.py) inserts a new
    # CurrencyRate every ETL run rather than overwriting one, so historical
    # rate trends accumulate for Power BI. Nothing in this app should read
    # currency_rates directly to mean "the current rate" -- use
    # current_currency_rate below, which is the one actually meant for that.
    currency_rates = relationship("CurrencyRate", back_populates="destination",
                                   cascade="all, delete-orphan", order_by="CurrencyRate.fetched_at")

    @property
    def current_currency_rate(self):
        """Most recently fetched CurrencyRate row, or None if none exist
        yet. This is what every display of "the" exchange rate should
        read -- currency_rates itself is the full history, not a single
        current value."""
        return self.currency_rates[-1] if self.currency_rates else None


class GusTourismStat(Base):
    __tablename__ = "gus_tourism_stats"

    stat_id = Column(Integer, primary_key=True)
    destination_id = Column(Integer, ForeignKey("destinations.destination_id"), nullable=False)
    organized_share_pct = Column(Float, nullable=False)
    individual_share_pct = Column(Float, nullable=False)
    avg_stay_length_days = Column(Float, nullable=False)
    year = Column(Integer, nullable=False)

    destination = relationship("Destination", back_populates="gus_stats")


class MszSafetyWarning(Base):
    __tablename__ = "msz_safety_warnings"

    warning_id = Column(Integer, primary_key=True)
    destination_id = Column(Integer, ForeignKey("destinations.destination_id"), nullable=False)
    level = Column(Integer, nullable=False)  # 1-4, MSZ scale
    message_pl = Column(Text, nullable=False)
    message_en = Column(Text, nullable=False)
    source_url = Column(String(300), nullable=True)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    destination = relationship("Destination", back_populates="msz_warnings")


class SeasonalRisk(Base):
    __tablename__ = "seasonal_risks"

    risk_id = Column(Integer, primary_key=True)
    destination_id = Column(Integer, ForeignKey("destinations.destination_id"), nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    risk_type_en = Column(String(80), nullable=False)
    risk_type_pl = Column(String(80), nullable=False)
    severity = Column(Integer, nullable=False)  # 1 (low) - 3 (high)
    description_en = Column(Text, nullable=True)
    description_pl = Column(Text, nullable=True)

    destination = relationship("Destination", back_populates="seasonal_risks")


class CurrencyRate(Base):
    __tablename__ = "currency_rates"

    rate_id = Column(Integer, primary_key=True)
    destination_id = Column(Integer, ForeignKey("destinations.destination_id"), nullable=False)
    rate_to_pln = Column(Float, nullable=False)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    destination = relationship("Destination", back_populates="currency_rates")


class User(Base):
    """Accounts (core/auth.py) -- a login is required to use the app at
    all (see docs/DEVELOPMENT_DOCUMENTATION.md §9's "Mandatory login"
    subsection); registering also persists Favorites across sessions/
    devices. is_admin is granted at registration time via a matching
    admin code (see core.auth.grant_admin_if_code_matches), not editable
    by the user themselves; is_blocked lets an admin cut off a specific
    account's access without deleting their data."""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    email = Column(String(200), nullable=True)
    password_hash = Column(String(200), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    favorites = relationship("UserFavorite", back_populates="user", cascade="all, delete-orphan")
    login_events = relationship("UserLoginLog", back_populates="user", cascade="all, delete-orphan")


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    favorite_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    destination_id = Column(Integer, ForeignKey("destinations.destination_id"), nullable=False)
    saved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="favorites")
    destination = relationship("Destination")


class UserLoginLog(Base):
    """One row per successful login (recorded once per browser session,
    not once per script rerun -- see core.auth.sync_session_with_auth),
    for the admin panel's "user activity" view."""
    __tablename__ = "user_login_log"

    log_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    logged_in_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="login_events")


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DEFAULT_SQLITE_PATH)), exist_ok=True)
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
