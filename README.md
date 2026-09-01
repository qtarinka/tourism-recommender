# Tourism Outbound Trip Decision Support System

Streamlit implementation of the thesis "System Wspomagania Decyzji w
Turystyce Wyjazdowej Polaków" (chapters 3–7), with an added English/Polish
language switcher.

Quick start:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\streamlit run app.py
```

See `docs/DEVELOPMENT_DOCUMENTATION.md` for architecture, the scoring
algorithm, data model, ETL/scheduler setup, testing, and documented scope
decisions.
