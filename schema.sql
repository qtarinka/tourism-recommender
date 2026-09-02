-- PostgreSQL DDL matching core/db.py's SQLAlchemy models.
-- Only needed if DATABASE_URL is pointed at a real PostgreSQL server
-- (see .env.example) -- the app auto-creates this schema on SQLite by
-- default via Base.metadata.create_all(), so running this file by hand
-- is optional unless you want a real Postgres instance per the thesis.

CREATE TABLE destinations (
    destination_id     SERIAL PRIMARY KEY,
    name_en             VARCHAR(80) NOT NULL,
    name_pl             VARCHAR(80) NOT NULL,
    country_en          VARCHAR(80) NOT NULL,
    country_pl          VARCHAR(80) NOT NULL,
    region              VARCHAR(20) NOT NULL CHECK (region IN ('europe', 'non_europe')),
    currency_code       CHAR(3) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE gus_tourism_stats (
    stat_id                SERIAL PRIMARY KEY,
    destination_id         INTEGER NOT NULL REFERENCES destinations(destination_id) ON DELETE CASCADE,
    organized_share_pct    NUMERIC(5,2) NOT NULL,
    individual_share_pct   NUMERIC(5,2) NOT NULL,
    avg_stay_length_days   NUMERIC(5,2) NOT NULL,
    year                   INTEGER NOT NULL
);

CREATE TABLE msz_safety_warnings (
    warning_id      SERIAL PRIMARY KEY,
    destination_id  INTEGER NOT NULL REFERENCES destinations(destination_id) ON DELETE CASCADE,
    level           SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 4),
    message_pl      TEXT NOT NULL,
    message_en      TEXT NOT NULL,
    source_url      VARCHAR(300),
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE seasonal_risks (
    risk_id         SERIAL PRIMARY KEY,
    destination_id  INTEGER NOT NULL REFERENCES destinations(destination_id) ON DELETE CASCADE,
    month           SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    risk_type_en    VARCHAR(80) NOT NULL,
    risk_type_pl    VARCHAR(80) NOT NULL,
    severity        SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 3),
    description_en  TEXT,
    description_pl  TEXT
);

CREATE TABLE currency_rates (
    rate_id         SERIAL PRIMARY KEY,
    destination_id  INTEGER NOT NULL REFERENCES destinations(destination_id) ON DELETE CASCADE,
    rate_to_pln     NUMERIC(10,4) NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Optional user accounts (core/auth.py). Registering is never required
-- for the app's core features -- only for persisting Favorites across
-- sessions/devices instead of the session-only default.
CREATE TABLE users (
    user_id         SERIAL PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(200),
    password_hash   VARCHAR(200) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_favorites (
    favorite_id     SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    destination_id  INTEGER NOT NULL REFERENCES destinations(destination_id) ON DELETE CASCADE,
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, destination_id)
);

CREATE INDEX idx_gus_stats_destination ON gus_tourism_stats(destination_id);
CREATE INDEX idx_msz_warnings_destination ON msz_safety_warnings(destination_id);
CREATE INDEX idx_seasonal_risks_destination_month ON seasonal_risks(destination_id, month);
CREATE INDEX idx_currency_rates_destination ON currency_rates(destination_id);
CREATE INDEX idx_user_favorites_user ON user_favorites(user_id);
