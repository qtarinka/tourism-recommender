# Development Documentation — Tourism Outbound Trip Decision Support System

This documents the actual implementation built from the thesis's "Dokumentacja
Implementacyjna" (chapters 3–7), plus features added beyond the original
scope: a runtime English/Polish language switch, and a visual redesign with
real destination landmark photos. Where the implementation deviates from
what the thesis chapters specify, it's called out explicitly below with the
reasoning, rather than silently diverging.

## 1. Scope recap (from the source thesis document)

- **Users**: individual tourists (get a scored recommendation + can compare
  destinations) and an admin (maintains the seasonal-risk reference data
  behind a password).
- **Core deliverable**: a scored recommendation across a fixed dictionary of
  20 destinations (17 European + 3 non-European), a side-by-side comparison
  view, and contextual data (NBP rates, MSZ warnings, GUS trip-organization
  stats), all inside a Streamlit app backed by a relational database.
- **Non-functional targets**: <2s response time, responsive UI, unattended
  ETL via a task scheduler, password-gated admin panel.

## 2. Architecture

```
tourism-recommender/
├── app.py                  # Streamlit entrypoint  (streamlit run app.py)
├── scheduler.py             # ETL entrypoint        (python scheduler.py)
├── schema.sql                # PostgreSQL DDL (parity reference; SQLite auto-creates the same schema)
├── requirements.txt
├── .env.example
├── .streamlit/config.toml     # Theme colors (native Streamlit widget theming)
├── core/
│   ├── db.py                 # SQLAlchemy models + engine (SQLite by default, Postgres via DATABASE_URL)
│   ├── seed_data.py           # 20-destination dictionary + reference GUS/seasonal-risk data
│   ├── scoring.py              # Scoring/ranking (shared by both modes) + match-level/explanation + low_risk_months
│   ├── etl.py                   # Live NBP rates + best-effort MSZ warnings refresh
│   ├── i18n.py                   # EN/PL string tables + t() helper
│   ├── images.py                  # Wikipedia landmark photos + country summary (hero, cards, gallery, detail dialog)
│   └── theme.py                    # Custom CSS (hero banner, card hover, carousel, photo placeholders)
├── tests/
│   ├── test_seed_data.py
│   ├── test_scoring.py
│   ├── test_etl.py
│   └── test_app_integration.py    # Streamlit AppTest-based smoke tests
└── docs/
    └── DEVELOPMENT_DOCUMENTATION.md  (this file)
```

**Stack**: Python 3.12, Streamlit, SQLAlchemy 2.x (ORM, not raw SQL — this is
what makes the SQLite/PostgreSQL swap a one-line config change), `requests`
for NBP, `feedparser` for the MSZ RSS feed, `python-dotenv` for config.

## 3. Deliberate deviations from the thesis spec (and why)

| Area | Thesis spec | What's implemented | Why |
|---|---|---|---|
| Database | PostgreSQL | **Real PostgreSQL** (matches the thesis exactly) — SQLite remains the zero-config fallback if `DATABASE_URL` is unset | Started on SQLite for a zero-install first pass, then switched to an actual local PostgreSQL 18 instance once requested — see §10a for exactly how. Same SQLAlchemy models either way, no code changes needed to switch. |
| GUS statistics | "GUS API" implied | **Seeded reference values** in `core/seed_data.py` | GUS's public BDL API doesn't expose the specific "organized vs. individual trips by destination country" breakdown the thesis describes at a queryable per-country level. Building a full scraper for a metric that isn't cleanly available wasn't worth the fragility; the numbers are illustrative and match the thesis's narrative (e.g. Egypt/Tunisia/Turkey skew organized, Czechia/Austria/Germany/Croatia skew individual). |
| MSZ warnings | "RSS feed, 4-level scale" | **Live fetch attempted, with a documented fallback** | I could not find a stable, documented MSZ RSS feed with a machine-readable 1–4 level during implementation (see `core/etl.py` docstring). `MSZ_RSS_URL` is left as a `.env` setting: if you find/confirm the real feed URL, set it and the ETL will parse it (matching by country name in the entry title, defaulting matched entries to level 2 pending real level data). If unset, existing/seed data is kept rather than the app pretending to have live data it doesn't. |
| Power BI | Embedded Power BI Service report via iframe | **A clickable "Open Power BI dashboard" link** (`POWERBI_REPORT_URL` in `.env`), not an iframe | See §6 for the full story — the university tenant blocks "Publish to web" (needs an admin), and true secure embedding needs an Azure app registration (real infra, out of scope). A direct link to the report works around both: opening it just requires being signed in to Power BI, which is fine for a personal thesis demo. |
| Budget input | A form input in the thesis, not part of the scoring formula | **Removed entirely** (DB column, seed data, UI) — on request | Was a filter on `avg_daily_cost_pln`, an estimate with no cited basis when first built. Rather than keep patching a field the user didn't want, it was removed end to end — no dead column, no dead seed values, no dead UI. |
| GUS organized-trip-share display | Chart/table of `organized_share_pct` | **Removed from the UI** — on request | The underlying `gus_tourism_stats.organized_share_pct`/`individual_share_pct` columns are kept (matches thesis chapter 4.1's data model, and still feeds the Power BI report), but no longer rendered anywhere in the Streamlit app — a seeded stat displayed like a live one was misleading. |
| MSZ advisory text | Real MSZ-style wording | **Rewritten to sound like an actual advisory**, not an app implementation note | The original seed fallback text read "No live data yet - run scheduler.py" — a dev-facing message a real user has no reason to see. Replaced with proper MSZ level-1 wording ("Exercise normal precautions..."), and a dedicated caption now explains what the 4-level MSZ scale actually means. |
| Language | Polish only (implied) | **EN/PL switcher in the sidebar** (`core/i18n.py`) | Requested addition beyond the thesis scope. |
| Destination photos | Not in scope | **Multiple real landmark photos per destination**, viewable in-app (`core/images.py`) | Requested addition — see §3b and §7. |

### 3a. `avg_daily_cost_pln` — history, now removed

This field went through two revisions before being removed entirely.
Originally it was a set of numbers estimated with no cited basis — a real
gap, not a rounding error. It was then rebuilt on an actual source
(MyFunkyTravel's backpacker country cost table, 16/20 destinations sourced
directly, 4 interpolated and flagged, converted USD→PLN at the live NBP
rate) and surfaced in the UI with a caption explaining the methodology.
Even sourced, though, it was still a coarse, illustrative estimate being
used to filter real recommendations — and once that was pointed out, the
right call was to remove it rather than keep refining a field that wasn't
wanted, rather than leave a half-used budget concept lying around the
codebase. It no longer exists anywhere: not in `core/db.py`'s model, not in
`core/seed_data.py`, not in `schema.sql`, not in the UI.

### 3b. `organized_share_pct` — kept in the data model, removed from the UI

This is the share of trips to a destination that are booked through a
travel agency/tour operator, as opposed to arranged independently — the
same distinction the thesis's GUS section describes. It's seeded reference
data inspired by that GUS statistic, not a live GUS API feed (GUS's public
BDL API doesn't expose this breakdown per destination country in a
queryable form). On request, this is no longer displayed anywhere in the
Streamlit app (previously a bar chart + a comparison-table column) — a
seeded stat presented like a live one was misleading. The underlying
`gus_tourism_stats.organized_share_pct`/`individual_share_pct` columns are
still there, still populated, and still match the thesis's chapter 4.1 data
model — they're what the actual Power BI report (§6) charts, which is now
the one place in the whole project this statistic is visible.

## 4. Scoring algorithm

```
Score = trip_length_match + seasonal_risk_match + msz_status_match   (0–3)
```

- `trip_length_match`: 1 if `|user.trip_length_days - destination.avg_stay_length_days| <= 2`, else 0.
- `seasonal_risk_match`: 1 if none of the destination's seasonal risks *for the
  selected travel month* exceed the user's risk tolerance (low→severity 1,
  medium→severity 2, high→severity 3), else 0.
- `msz_status_match`: 1 if the destination's current MSZ warning level is at
  or below the tolerance-mapped threshold (low→1, medium→2, high→3), else 0.

Currency rate and organization style are shown as context only and never
enter the score, matching the thesis's explicit statement that these two
inputs are decision context rather than scored criteria.

## 5. Data model

Five tables, matching the thesis's chapter 4.1 structure: `destinations`,
`gus_tourism_stats`, `msz_safety_warnings`, `seasonal_risks`,
`currency_rates` — all FK'd back to `destinations.destination_id`. See
`schema.sql` for the full DDL, or `core/db.py` for the SQLAlchemy source of
truth. User-facing text fields (destination/country names, risk types,
MSZ messages) carry parallel `_en`/`_pl` columns rather than a separate
translation table, since the dictionary is small and fixed-size (20 rows).

## 6. Power BI report setup (done — link-based, not embedded)

The thesis calls for embedding a real Power BI Service report. I can't
create the account, log in, or publish on the user's behalf (that needs
their personal Microsoft/university credentials) — so this was done as a
live collaborative session: I opened Power BI in a browser and drove the
report-building UI; the user handled every step that touched their login or
their account's permissions.

**What was actually built**: a report ("Gus_report") in the user's own
Power BI workspace. It went through two revisions:

1. **First pass (SQLite era)**: built from a one-time CSV export of
   `gus_tourism_stats`, uploaded via Power BI's "Upload a file" flow — a
   static snapshot with no ongoing connection to the app's database at all.
2. **Second pass (after switching to Postgres, §10a)**: rebuilt as a genuine
   **live connection**. Installed Power BI Desktop (via Microsoft Store —
   I can't drive its UI the way I could the browser-based Service, since
   it's a native app with no browser automation surface, so this leg was
   guided step-by-step from user-provided screenshots), connected directly
   to `localhost:5432` / `tourism_recommender` using Power BI's built-in
   PostgreSQL connector with the `tourism_app` role's credentials, loaded
   the `destinations` and `gus_tourism_stats` tables (Power BI auto-detected
   the `destination_id` relationship between them), rebuilt the same
   clustered-bar chart, then republished from Desktop to the **same
   workspace with the same report name** — Power BI offered to replace the
   existing report in place, which kept the exact same report URL/ID
   (`df1c2c08-79aa-4dbb-b094-5f7a511833b1`), so `POWERBI_REPORT_URL` in
   `.env` needed no changes. Verified afterward by reloading the report
   directly and re-clicking the app's link button — both show the
   Postgres-sourced chart. The chart is a clustered bar of
   `organized_share_pct` by `destination`, sorted descending — it
   reproduces the exact same "Egypt/Tunisia/Turkey skew organized" pattern
   the thesis describes in chapter 6.3.

**What "live" actually means here** — worth being precise about, since it's
a common point of confusion: Power BI **Desktop** refreshing (or
re-publishing) pulls current data straight from Postgres over
`localhost:5432` — genuinely live, no gateway needed, because Desktop runs
locally and can reach `localhost` directly. The **published Service copy**
(what the app's link button opens) is a snapshot as of whenever it was last
published from Desktop — visiting the link does *not* re-query Postgres on
page load. Getting the Service copy to auto-refresh on a schedule would
need an **On-premises Data Gateway** installed and registered with the
tenant (real infrastructure, not set up here — the only two things that are
editable in this whole system are seasonal risks via the admin panel, which
this chart doesn't even chart, so in practice this gap rarely matters). To
manually push a DB change through: refresh in Desktop, then re-publish
(same replace-in-place flow as above).

**Why it's a link, not an iframe** — two real walls, in order:
1. **"Publish to web (public)"** is disabled at the tenant level for this
   university's Power BI admin (a common institutional data-governance
   setting) — got "Contact your admin to enable embed code creation."
   Not something a student account can override.
2. **"Website or portal"** embed (the authenticated alternative) routes
   through Power BI **Embedded**'s developer playground, which needs an
   actual Azure AD app registration (client ID/secret, token generation) to
   produce a working embed — real infrastructure, not a form to fill in.
   Out of scope for what this needed to accomplish.

**The actual solution**: `app.py`'s Contextual data tab renders a
`st.link_button` pointed at `POWERBI_REPORT_URL` from `.env` — the report's
normal `app.powerbi.com/groups/.../reports/...` URL. Clicking it opens the
real, live, interactive report in a new tab. The only requirement is being
signed in to Power BI in that browser — true for the user running their own
local app, so this is a complete, working solution for the actual use case,
just not a same-page embed. If `POWERBI_REPORT_URL` is unset, the button is
replaced with a warning instead of showing nothing.

To point this at a different report later: open it in Power BI Service,
copy the URL from the address bar (or use Share → Copy link), and set
`POWERBI_REPORT_URL=<that URL>` in `.env`, then restart the app (env vars
are only read at process start).

## 7. Images & visual redesign

Beyond the thesis scope: a full visual pass plus real photos of each
destination's most recognizable landmark (Eiffel Tower for France, Colosseum
for Italy, etc. — full list in `core/images.py`'s `LANDMARKS` dict).

- **Source**: Wikipedia's public MediaWiki Action API
  (`action=query&prop=pageimages`) — no API key, no account, nothing for you
  to sign up for. Images are hotlinked from Wikimedia's CDN, never
  downloaded into this repo.
- **Licensing**: Commons images are almost all CC BY-SA or public domain.
  Every photo in the app renders an attribution caption underneath
  ("Zdjęcie: <landmark> — Wikipedia", linking to the source page) to satisfy
  CC BY-SA's attribution requirement. For a real public deployment, pulling
  the actual author/license per image from the Commons API would be more
  rigorous than this good-faith attribution — flagged honestly rather than
  overclaiming full compliance.
- **Caching**: `st.cache_data(ttl=24h)` avoids re-fetching the same
  landmark's metadata on every Streamlit rerun (which happens on every
  widget interaction). Failures (offline, rate-limited, timeout) are *not*
  cached — only genuine successes are — so a transient failure doesn't lock
  in a "no photo" result for 24 hours (see the bug log in §12).
- **Fallback**: if a photo can't be fetched, `render_photo()` in `app.py`
  shows a gradient placeholder with the destination's name instead of a
  broken image — used on the hero banner, recommendation cards, the
  comparison tab's photo strip, and the full 20-destination gallery in the
  Contextual data tab.
- **Theming**: `.streamlit/config.toml` sets Streamlit's native widget
  theme (a warm off-white/coral palette); `core/theme.py` adds the custom
  CSS Streamlit's theme system can't reach — the hero banner, card hover-lift
  effect, and fixed-height photo cropping so grid rows line up evenly
  despite each landmark photo having a different native aspect ratio.

## 8. Unified recommendation/comparison system (major restructuring)

This was the largest single change to the project: recommendation and
comparison used to be two separate tabs with separate UI (a card list vs.
a raw `st.dataframe` table) even though both called the same
`rank_destinations()` underneath. On request, they were unified into one
flow, one form, one results renderer — comparison is now explicitly *the
same recommendation system*, just given a smaller candidate list.

**What changed, concretely:**

- **One sidebar form, one button.** The old "Pokaż rekomendacje" button
  and the separate comparison-tab multiselect are gone. The sidebar now
  has a single "🗺️ Kierunki do rozważenia (opcjonalnie)" multiselect and a
  single "🔎 Znajdź kierunki" button. Mode is derived, not chosen: empty
  selection → recommendation mode (all 20 scored); non-empty → comparison
  mode (only the selected ones scored) — `core/scoring.py`'s
  `rank_destinations()` didn't need a single line changed; it already
  accepted an arbitrary candidate list. A new `core/scoring.py` test
  (`test_rank_destinations_with_a_single_candidate_is_comparison_mode`)
  makes this equivalence explicit.
- **One results renderer** (`render_result_card()` in `app.py`) draws
  every card in both modes — the header/caption text is the only thing
  that differs (`results_header_recommendation` vs.
  `results_header_comparison`). This directly eliminates the dead-button
  bug described in the request ("Show Recommendations" doing nothing
  while viewing a comparison) — there is structurally only one action to
  take now.
- **Plain-language match explanations** (`ScoredDestination.match_level`
  and `.explanation_items()` in `core/scoring.py`, new methods — the
  scoring math itself is untouched). Score 3/2/1/0 maps to a label
  ("Doskonałe/Bardzo dobre/Dobre/Słabe dopasowanie") plus 3 sentences,
  one per criterion, phrased positively or negatively depending on whether
  that criterion matched — e.g. "Wybrany okres podróży wiąże się z niskim
  lub akceptowalnym ryzykiem sezonowym" vs. "...może wiązać się z
  podwyższonym ryzykiem sezonowym." A card no longer shows an unexplained
  "3/3" with no context.
- **A shared destination detail dialog** (`_detail_dialog()`, opened via
  `open_detail()`), reachable from three places — a Results card's "🔍
  Zobacz szczegóły" button, the Favorites strip, and Explore Destinations
  — one component, three entry points, not three separate detail views.
  Contains: the match explanation (only when opened from a scored context;
  omitted when opened from Explore, since there's nothing to explain
  without criteria yet), a photo carousel, a genuinely-sourced "General
  information" blurb (see below), currency + live rate, the MSZ warning
  with its level explained, every seasonal risk on record for that
  destination (not just the selected month — reuses the previously-unused
  `SeasonalRisk.description_en/pl` columns), a "recommended travel period"
  derived from that same seasonal-risk data (`core.scoring.low_risk_months`),
  and an explicit "what's not covered" note (see below). This is the
  "Destination Ranking → Destination Details" step from the requested
  user flow.
- **"General information" is real, sourced content, not invented.**
  `core/images.py`'s new `get_country_summary()` pulls each country's own
  lead paragraph from Wikipedia (same API family as the landmark photos,
  same failure-doesn't-cache contract). The request listed several other
  detail-view fields — climate, entry requirements, transport/accessibility,
  "information particularly relevant to Polish travellers" — that this
  app has no real, verified data source for. Rather than fabricate them
  (the same call made earlier in this project for cost/GUS data), the
  dialog has an explicit "ℹ️ Czego tu nie znajdziesz" section naming
  exactly what's missing and why, instead of silently omitting them or
  making something up.
- **Explore Destinations redesigned**: search box + region filter
  (segmented control), and critically, clicking a destination no longer
  appends its extra photos inline below the card (the reported bug — the
  page kept growing downward and became disorganized). It opens the same
  shared detail dialog as a proper overlay instead. Each card also has an
  "➕ Do porównania" button that adds that destination to the sidebar's
  comparison selection — connecting Explore → Results per the requested
  flow, without needing to manually retype the name in the sidebar.
- **Session-only Favorites** (`st.session_state["favorites"]`, a plain
  set of destination IDs). A ☆/★ toggle appears on every card and inside
  the detail dialog; a "⭐ Twoje zapisane kierunki" strip appears at the
  top of the Results tab whenever it's non-empty. This is the "Save" part
  of the requested flow, implemented as simply as the requirement allows
  ("do not make login mandatory... without unnecessarily complicating").
  See the evaluation of full user accounts below.
- **User accounts: evaluated, not built** — at this point in the project —
  per the request to assess feasibility without forcing login onto the core
  features. The session-only Favorites above worked with no account. The
  About tab's "Konta użytkowników i zapisywanie wyników" section documented,
  in-app, what real cross-visit accounts would need: a `users` table,
  secure password storage, and foreign-keying saved items to an account
  — noting that the existing SQLAlchemy models already generalized to that
  without restructuring. They were, in fact, then actually built — see §9.

### Bugs found and fixed while building this

- **Markdown link syntax silently failing inside a raw HTML block.** The
  photo carousel's counter line was built as one `st.markdown(...,
  unsafe_allow_html=True)` call containing both a `<div>` wrapper and a
  `[text](url)` Markdown link inside it. Verified in the browser: it
  rendered as the literal text `[Wikipedia](https://...)` instead of a
  link — Markdown syntax embedded inside an explicit raw-HTML block
  doesn't get parsed. Fixed by adding `_photo_credit_html()`, which
  builds a real `<a href="...">` tag for exactly this one call site,
  while the existing `_photo_credit()` (used inside plain `st.caption`/
  `st.write` calls elsewhere, where Markdown parsing works normally) was
  left untouched.
- **The dialog closed itself the moment you used it.** The first version
  called `_detail_dialog(...)` directly from inside each trigger button's
  `if st.button(...):` block. That works for *opening* the dialog, but
  every control *inside* it (the carousel's prev/next buttons) needs its
  own `st.rerun()` to update — and on that fresh script run, the original
  trigger button is no longer "clicked" (Streamlit buttons only return
  `True` on the exact run they were pressed), so the dialog wasn't
  re-invoked and it just vanished. Caught immediately by clicking "▶" in
  the browser and watching the whole modal disappear instead of advancing
  to photo 2. Fixed by moving to persistent state: `open_detail()` sets
  `st.session_state["open_detail_id"]` (+ the scored object, if any) and
  reruns; a single dispatcher line (`if
  st.session_state.get("open_detail_id") is not None:
  _detail_dialog(...)`) re-invokes the dialog on *every* rerun for as
  long as that state is set, regardless of which button caused the rerun.
  Closing (via the dialog's own × or the in-dialog "Zamknij" button) clears
  that state through an `on_dismiss` callback so it doesn't just pop back
  open on the next unrelated interaction. Re-verified: prev/next now
  correctly keep the same destination's dialog open and just change the
  photo.
- **`StreamlitWidgetAlreadyInstantiatedError` from "➕ Do porównania".**
  The first version of this button wrote straight into
  `st.session_state["destinations_multiselect"]` — the sidebar's own
  multiselect widget key — then called `st.rerun()`. Streamlit rejects
  writing to a widget's session-state key on the same run where that
  widget already rendered (the sidebar always runs before the Explore tab
  further down the script), regardless of the pending rerun. Reproduced
  live in the browser (a full traceback rendered in the app). Fixed with
  a staging key: the button sets `st.session_state["pending_add_to_compare"]`
  instead; a small block near the very top of the script — before the
  sidebar creates the multiselect — checks for that pending value, merges
  it into the selection, and clears it. Re-verified: adding a destination
  from Explore now correctly shows up pre-selected in the sidebar with no
  error, and running the search from there produces the right comparison.
- Full test suite re-run after each of the three fixes above; all green.
  Two new AppTest integration tests
  (`test_unified_form_recommendation_mode_ranks_all_destinations`,
  `test_unified_form_comparison_mode_ranks_only_selected_destinations`)
  exercise the actual unified button + mode-switch end to end, mocking
  the Wikipedia network layer for speed/determinism rather than depending
  on live network performance (this machine was under heavy unrelated
  load from other running applications during this pass, which caused a
  couple of false-start timeouts before the mocking was added — logged
  here since it looked like a regression at first and wasn't one).

## 9. User accounts (optional, persistent favorites)

Built as a direct follow-up to §8's "evaluated, not built" note. Prompted by
the user asking, unprompted by any prior plan, whether a user-friendly web
app like this shouldn't have login/signup so users get their own experience
— the recommendation was real accounts backed by a `users` table with
favorites foreign-keyed to it, and the user approved building it. Accounts
stay fully optional: every core feature (recommendations, comparison,
exploring destinations) still works with zero account, per the original
constraint never to make login mandatory — the only thing an account adds
is having Favorites survive across visits/devices instead of vanishing the
moment the browser session ends.

**What was built:**

- **`users` and `user_favorites` tables** (`core/db.py`, DDL added to
  `schema.sql`), the latter cascade-deleted with its user and unique on
  `(user_id, destination_id)`.
- **`core/auth.py`** wraps `streamlit-authenticator` (bcrypt-hashed
  passwords, a signed re-auth cookie) over a DB-backed credential store: the
  `credentials` dict `Authenticate()` needs is rebuilt fresh from `users` on
  *every* script run rather than kept in memory, since Streamlit reruns the
  whole script on every interaction anyway — this is the library's own
  documented pattern for a non-file credential store, not a workaround.
  `sync_favorites_with_auth()` keeps the existing
  `st.session_state["favorites"]` set (unchanged, still what every card/
  strip reads) in step with login state: on the run a login is first
  detected it's replaced with that user's DB-persisted favorites; on logout
  it's cleared back to an empty anonymous session.
- **Sidebar-first placement.** The login/register widgets render inside an
  expander at the very top of the sidebar, above the criteria form —
  visible on first load in every tab, since the sidebar persists across
  tabs. (This wasn't the first placement — see the bug log below.) The
  Konto tab, once logged in, shows a favorites grid + logout; logged out,
  it just points at the sidebar rather than duplicating the form.

### Bugs found and fixed while building this

- **Wrong attribute path for reading back a just-registered user.** The
  first version of `persist_new_user()` read the new user's hashed password
  off `authenticator.authentication_controller.credentials`. Reproduced live
  in the browser as an `AttributeError` the moment registration was
  submitted: `'AuthenticationController' object has no attribute
  'credentials'`. Fixed by reading the library's source
  (`AuthenticationModel.__init__`) to find the real path — the credentials
  dict lives one level deeper, on
  `authentication_controller.authentication_model.credentials`.
- **Registered accounts silently got the username as their display name
  instead of their real name.** `persist_new_user()` read
  `record.get("name")` off the freshly-registered credentials record and
  fell back to the username when that key was missing — which it always
  was: `streamlit-authenticator` stores a new registrant's name as separate
  `first_name`/`last_name` keys, never a combined `name` key (confirmed by
  reading `AuthenticationModel._get_user_name()` and
  `AuthenticationController.register_user()`, whose actual return signature
  is `(email, username, "first last")`). Caught by registering a real test
  user end to end and checking the row that landed in Postgres directly —
  the sidebar showed no error, so this would have shipped silently. Fixed
  by taking the full name from `register_user()`'s own return value instead
  of trying to read it back out of the credentials dict.
- **Login/register UI not visible on the landing page — a direct user
  report** ("i dont see login/signup on the landing page"). The first
  version only put the login/register forms inside the Konto tab, requiring
  an extra click to discover. Fixed by moving them to the always-visible
  sidebar expander described above; verified visually via a fresh page load
  screenshot showing both forms rendered without any tab click.
- **A stale re-auth cookie crashed the entire app for that browser.**
  Surfaced by the user pasting a screenshot of an uncaught
  `streamlit_authenticator.utilities.exceptions.LoginError: User not
  authorized` traceback. Root cause, confirmed by reading
  `AuthenticationModel.login()`: the unattended
  `authenticator.login(location="unrendered")` bootstrap call (run on every
  script run, before any tab renders, to silently honor an existing re-auth
  cookie) *raises* rather than just treating the cookie as invalid when the
  cookie's username has no matching row in the credentials dict rebuilt
  from `users` — which happens any time an account is deleted (here, a test
  user cleaned up manually after end-to-end verification) while that
  browser still holds a valid cookie for it. Fixed by wrapping the
  bootstrap call in `try/except LoginError`, deleting the stale cookie via
  `authenticator.cookie_controller.delete_cookie()` and falling back to an
  anonymous session, instead of crashing every rerun until the cookie
  expires or is cleared by hand.
- Full end-to-end verification performed live in the browser after these
  fixes (not just the test suite): registered a fresh user via the sidebar
  → correct name confirmed in the `users` row via direct DB query →
  logged in → toggled a Favorite → confirmed it landed in `user_favorites`
  → logged out and back in → confirmed the Favorite was still marked saved
  (i.e. genuinely reloaded from the DB, not just left over in session
  state) → test user and its favorite deleted afterward, no leftover data.
  `tests/test_auth.py` (7 tests: round-trip, idempotency, per-user scoping,
  unknown-user handling for the DB helper functions) and two updated
  `test_app_integration.py` assertions (the sidebar's new widgets shifted
  the submit button's position, so it was given an explicit
  `key="find_destinations_btn"` and the affected tests switched from
  positional to keyed lookup) — full suite (32 tests) green after each fix.

## 10. Setup & running

```powershell
cd tourism-recommender
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # then edit ADMIN_PASSWORD at minimum
.\.venv\Scripts\streamlit run app.py
```

First run auto-creates and seeds the database (SQLite at `data/app.db` by
default) — no manual migration step needed for the default setup.

### 10a. Switching to PostgreSQL (what this project actually runs on)

This app currently runs against a real local PostgreSQL 18 instance, not
SQLite. To set that up from scratch:

1. Install PostgreSQL (the user did this manually via the official
   installer this round). Note the superuser password you set during
   install.
2. Create a dedicated role and database for the app — don't reuse the
   `postgres` superuser account directly:
   ```powershell
   $env:PGPASSWORD = "<your postgres superuser password>"
   $psql = "C:\Program Files\PostgreSQL\<version>\bin\psql.exe"
   & $psql -U postgres -h localhost -p 5432 -c "CREATE ROLE tourism_app WITH LOGIN PASSWORD 'tourism_app_pw';"
   & $psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE tourism_recommender OWNER tourism_app;"
   & $psql -U postgres -h localhost -p 5432 -d tourism_recommender -c "GRANT ALL PRIVILEGES ON SCHEMA public TO tourism_app;"
   ```
3. Set `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql+psycopg2://tourism_app:tourism_app_pw@localhost:5432/tourism_recommender
   ```
4. Run `python scheduler.py` (or start the app) — `init_db()` calls
   `Base.metadata.create_all(engine)`, which creates all 5 tables against
   Postgres automatically; no need to run `schema.sql` by hand unless you
   want to inspect/adjust the DDL first (it's kept as an exact parity
   reference). `seed_if_empty()` then populates the 20-destination
   dictionary the same way it does on SQLite.

**A note on `psql` output encoding**: on Windows, `psql`'s console output
may show mangled non-ASCII characters (e.g. table headers) in some
terminals — this is a client-side code-page display issue, not a data
problem; the actual stored data is correct UTF-8.

**Unrelated discovery worth knowing about**: while setting this up, we
found a pre-existing PostgreSQL 17 *data directory* at
`C:\Program Files\PostgreSQL\17\data` with real historical data (logs
from September 2025 through January 2026) but no server binaries, no
Windows service, and nothing running — looks like PostgreSQL was
uninstalled at some point without removing its data. That directory was
left completely untouched; this project's database lives in a fresh
PostgreSQL 18 instance instead. If that old data matters, it would need
its own investigation (what created it, whether it's recoverable) — out of
scope for this project.

**ETL / unattended refresh** (currency rates + best-effort MSZ warnings):

```powershell
.\.venv\Scripts\python scheduler.py
```

Register this as a Windows Task Scheduler action (rather than an in-process
loop) to match the thesis's "harmonogram zadań" design:

```
schtasks /create /tn "TourismAppETL" /tr "C:\path\to\.venv\Scripts\python.exe C:\path\to\scheduler.py" /sc daily /st 06:00
```

## 11. Testing

```powershell
.\.venv\Scripts\pytest -v
```

- `test_seed_data.py` — verifies the 20-destination / 17+3 split and that
  every destination has GUS stats, an MSZ warning row, and a currency rate row.
- `test_scoring.py` — trip-length tolerance boundaries, risk-tolerance
  mapping for both MSZ and seasonal risk, score = sum of the three
  components, and extreme inputs (365-day trip, max severity, max MSZ level)
  don't crash and correctly score 0.
- `test_etl.py` — NBP table-A/table-B fallback, unreachable-network handling,
  PLN short-circuit, and that an unset `MSZ_RSS_URL` is a safe no-op.
- `test_app_integration.py` — runs the real `app.py` headlessly via
  Streamlit's `AppTest` harness, asserts it renders without exceptions, that
  the language switch actually changes rendered text, and all 5 tabs render.

## 12. Verification performed during development

Beyond the automated suite, the running app was manually exercised end to
end in a real Chrome browser session against a fresh SQLite database:

- Recommendation form → ranking: submitting default preferences correctly
  scored and ranked Austria/Bulgaria/Croatia at 3/3.
- Language switch: toggling PL → EN in the sidebar re-rendered every label,
  the page title, destination names, and the footer, with no page reload.
- Comparison table: selecting Czechia + Egypt showed the expected contrast
  (18% vs. 78% organized-trip share), each column (currency, rate, avg. cost,
  avg. stay, MSZ level/message, seasonal risk) populated correctly.
- **Bug found and fixed**: the GUS bar chart (`st.bar_chart`) was initially
  fed a plain `{name: value}` dict, which Streamlit/Vega-Lite silently
  failed to render (console showed "Infinite extent" warnings, empty chart).
  Fixed by building a proper `pandas.DataFrame` indexed by destination name
  before charting (`app.py`, Contextual data tab). Re-verified visually —
  the chart now correctly shows Egypt/Tunisia/Turkey with the highest
  organized-trip share, matching the thesis's own stated findings (§6.3).
- Admin panel: password login, and a full add → verify → delete cycle on
  the seasonal-risks table, both confirmed against the live SQLite DB.
- ETL: `python scheduler.py` was run for real against the live NBP API —
  successfully fetched rates for all 20 destinations (including the table-A
  → table-B fallback for EGP and TND), and correctly logged a no-op skip
  for the MSZ refresh since `MSZ_RSS_URL` is unset by default.

### Second pass: images, redesign, and cost-data rework

- **Bug found and fixed — Wikimedia thumbnail 400s.** The first `core/images.py`
  used Wikipedia's REST `/page/summary` endpoint and hand-edited the returned
  thumbnail URL's embedded width (e.g. swapping `330px-` for `640px-`) to get
  a bigger image. Every single one of those requests came back `400 Bad
  Request` from `upload.wikimedia.org` — verified directly with `curl`-style
  requests outside the app. Root cause: the CDN validates the requested width
  against the API-issued cache key; a hand-edited width doesn't match it.
  Fixed by switching to the MediaWiki Action API
  (`action=query&prop=pageimages&pithumbsize=N`), which lets you request an
  exact size properly and returns a URL the CDN actually honors — confirmed
  working end to end (200, real image bytes) before wiring it into the app.
- **Bug found and fixed — failed fetches cached as permanent.** `st.cache_data`
  caches whatever a function returns, including `None` from a transient
  failure. The gallery's first live run (20 near-simultaneous requests) hit
  what looked like transient rate-limiting, and every destination's `None`
  result got cached for the full 24h TTL, leaving every photo on placeholders
  even after the network recovered. Fixed by having the cached inner function
  raise on failure instead of returning `None` — `st.cache_data` doesn't
  cache exceptions, so only genuine successes get cached and failures retry
  next call.
- **Bug found and fixed — `DATABASE_URL=` (empty) crashed the app.**
  `core/db.py` used `os.environ.get("DATABASE_URL", <sqlite default>)`,
  which only falls back when the var is *unset* — but the `.env` file sets
  it to `""`, a var that *is* set. Compounding this, `app.py` imported
  `core.db` (which reads that var at module-import time) *before* calling
  `load_dotenv()`, so it worked by accident on a cold process start (the var
  genuinely wasn't set yet) and only broke once Streamlit's dev-mode file
  watcher re-imported `core.db` later in the same process's life, after
  `load_dotenv()` had already populated `os.environ["DATABASE_URL"] = ""`.
  Fixed both: `load_dotenv()` now runs before any `core.*` import, and
  `core/db.py` uses `os.environ.get("DATABASE_URL") or <default>` so an
  empty value is treated the same as unset either way.
- **Bug found and fixed — gallery captions read as belonging to the wrong
  photo.** The destination-name label was rendered *below* each photo (as a
  caption). The data pairing was actually correct in code, but visually the
  name sat closer to the *next* row's photo than its own (Streamlit's
  per-element spacing), making the whole 20-photo gallery look mislabeled at
  a glance. Fixed by rendering the name *above* each photo as a header
  instead — removes the ambiguity entirely, verified visually row by row.
- Re-verified after all four fixes: hero banner, recommendation cards,
  comparison tab photo strip, and the full 20-photo gallery all render
  correctly, correctly attributed, correctly paired, in both languages.
- `avg_daily_cost_pln` was rebuilt from an actual cited source (see §3a)
  after the original placeholder values were correctly flagged as having no
  stated basis — before being removed entirely in the next revision.

### Third pass: removals, MSZ clarity, multi-photo, Power BI, form redesign

- **Bug found and fixed — lazy photo loading wasn't actually lazy.** The
  first version of the multi-photo "explore" gallery put
  `get_destination_photos(...)` inside an `st.expander`, assuming collapsed
  expanders don't execute their body. They do — Streamlit only hides the
  DOM, it doesn't skip the code. That meant every single script rerun
  (triggered by *any* widget interaction anywhere in the app) fired up to
  60 extra Wikipedia API calls for all 20 destinations' hidden photos, on
  top of the ~20 already needed for the visible cards. Caught by
  `test_app_runs_without_exceptions` timing out at 30s instead of its
  normal ~2-5s. Fixed by replacing the expander with a plain button that
  toggles an `st.session_state` flag, and only calling
  `get_destination_photos` when that flag is actually set — genuinely
  fetches only on click, verified by re-running the full suite (back to
  normal timing) and confirming the button correctly reveals 3 photos per
  destination in the browser.
- Verified the transient-failure/permanent-cache fix from the second pass
  is durable: reloaded the gallery cold, saw a handful of destinations on
  placeholders (real Wikipedia rate-limiting, not a bug — confirmed by
  calling `get_landmark_image` directly outside Streamlit and getting a
  correct result), reloaded again a few seconds later, all photos loaded.
- Confirmed in the browser: budget slider and its caption are fully gone
  from the sidebar; the GUS bar chart/caption and the comparison table's
  organized-share column are gone from their tabs; the MSZ explanation
  caption renders correctly in both Contextual data and Comparison tabs;
  the redesigned segmented-pill preference controls and gallery work in
  both languages; the "How it works" tab renders.
- Power BI: built and verified an actual live report in the user's real
  workspace (not a mock) — see §6 for the two blockers hit (tenant-disabled
  public publish, Embedded's Azure-registration requirement) and the
  link-based resolution. Confirmed the `st.link_button` opens the correct
  report URL in a new tab.

### Fourth pass: switching to real PostgreSQL

- **Bug found and fixed — `scheduler.py` silently never used Postgres.**
  After creating the dedicated `tourism_app` role/database and setting
  `DATABASE_URL` in `.env`, running `python scheduler.py` reported success
  ("Currency rates refreshed for 20 destinations") — but querying Postgres
  directly with `psql` showed zero tables. Root cause: unlike `app.py`
  (fixed for this exact class of bug earlier — see the second-pass bug
  log), `scheduler.py` never called `load_dotenv()` at all, so
  `core.db`'s module-level `os.environ.get("DATABASE_URL")` read nothing
  and silently fell back to SQLite — the script was refreshing the old
  SQLite file the whole time while claiming to work. Fixed by adding the
  same `load_dotenv()`-before-`core.db`-import pattern to `scheduler.py`.
  Re-ran it, got "Database was empty -- seeded with reference destination
  data" (the real tell that it was actually a fresh Postgres DB this time),
  then verified directly with `psql`: 5 tables, 20 destinations, live NBP
  rates, all correct.
- Verified the admin login and the full app UI load correctly against
  Postgres in the browser, and cross-checked `seasonal_risks` row count
  (7, matching the seed data) directly via `psql`.
- Full test suite re-run and still green — the test suite uses its own
  isolated in-memory SQLite fixture (`tests/conftest.py`), independent of
  `.env`'s `DATABASE_URL`, so switching the app's real database doesn't
  and shouldn't change test behavior.

### Fifth pass: unified recommendation/comparison restructuring

Full detail (what changed and all three bugs found/fixed) is in §8, kept
there rather than duplicated here since that section already tells the
story end to end. Summary: recommendation and comparison modes unified
into one form/button/results-renderer (verified both modes live in the
browser — an all-20 ranking and a single-destination comparison, both
showing the same plain-language match explanations); Explore
Destinations redesigned with search/filter and a shared detail dialog
replacing the old inline-expansion gallery (verified the reported bug —
photos appending below and pushing the page down — no longer happens);
session-only Favorites verified end to end (toggle → strip appears →
persists across tab switches). Three real bugs were found and fixed
during this pass by actually clicking through the feature rather than
just reading the code back: a Markdown-inside-raw-HTML link that
silently failed to render, a dialog that closed itself on its own
internal interactions, and a `StreamlitWidgetAlreadyInstantiatedError`
crash from the Explore→sidebar "add to compare" action.

## 13. Known limitations

- GUS figures (`organized_share_pct`/`individual_share_pct`) are seeded
  reference values, not a live feed (see §3b) — no longer shown in the
  Streamlit app itself, but still exist in the DB and feed the Power BI
  report.
- MSZ warning levels default to "2" for any live-matched entry until the
  real feed's level encoding is confirmed and `core/etl.py`'s parsing logic
  is refined against it (this only applies once `MSZ_RSS_URL` is actually
  set — the seed/fallback level-1 text is real MSZ wording, not a
  placeholder).
- Power BI is a link to the real report, not a same-page embed — see §6
  for exactly why, and what it would take to change that (a tenant admin
  enabling public publish, or an Azure app registration for secure
  embedding).
- Destination dictionary is a fixed set of 20 (matches thesis scope, chapter
  7.3's own stated limitation).
- Photos require internet access at runtime (Wikipedia API) and are not
  bundled with the app; offline, every photo falls back to the gradient
  placeholder rather than failing — by design, but worth knowing before a
  fully offline demo.
- The `tourism_app` PostgreSQL role's password (`tourism_app_pw`, set in
  `.env`'s `DATABASE_URL`) is a plain local-dev credential, not something
  hardened for any shared/production use — fine for localhost-only access
  as set up here, but change it if this database ever needs to be reachable
  from anywhere else.
- "Number of travellers" is captured in the unified form and shown back to
  the user inside the destination detail dialog, but does not currently
  affect the match score — there's no per-person/per-group cost data in
  this app (see §3a) to scale by. It's collected for context and future
  extensibility, not silently ignored without explanation.
- Favorites persist across visits only for a logged-in account (§9); an
  anonymous session's Favorites still live in `st.session_state` only and
  are lost when the browser session ends. This is by design, not a gap —
  accounts stay opt-in rather than mandatory.
- The destination detail dialog deliberately does not cover climate,
  entry requirements, or transport/accessibility — no verified data
  source for these was integrated, and the dialog says so explicitly
  rather than guessing (see §8).
- Streamlit does not preserve scroll position across a rerun (a platform
  limitation, not something this app controls) — closing the detail
  dialog returns you to the same tab and the same search results, but the
  page may have scrolled to the top rather than back to exactly where you
  were.
