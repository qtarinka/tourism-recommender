"""
ETL entrypoint: `python scheduler.py`

Runs one refresh cycle (NBP currency rates, MSZ warnings best-effort) and
exits. Matches the thesis's "harmonogram zadań" (task scheduler) design:
this script does the work, and unattended refresh is achieved by
scheduling it externally (Windows Task Scheduler / cron), not by an
in-process long-running loop. See docs/DEVELOPMENT_DOCUMENTATION.md for
a ready-to-use Task Scheduler command.
"""
from dotenv import load_dotenv

# Must run before importing core.db: it reads DATABASE_URL at *import*
# time (module-level `create_engine(...)`). Without this, scheduler.py
# would silently fall back to SQLite regardless of what .env says --
# exactly the bug that shipped here initially (see
# docs/DEVELOPMENT_DOCUMENTATION.md).
load_dotenv()

from core.db import init_db, get_session
from core.seed_data import seed_if_empty
from core.etl import run_all

if __name__ == "__main__":
    init_db()
    session = get_session()
    seeded = seed_if_empty(session)
    session.close()
    if seeded:
        print("Database was empty -- seeded with reference destination data.")

    run_all()
