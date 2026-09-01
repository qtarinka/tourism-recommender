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
    currency_rate = relationship("CurrencyRate", back_populates="destination", uselist=False,
                                  cascade="all, delete-orphan")


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

    destination = relationship("Destination", back_populates="currency_rate")


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DEFAULT_SQLITE_PATH)), exist_ok=True)
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
