"""
Custom CSS injected once at the top of app.py. Kept separate from app.py
so the page logic isn't buried under a wall of CSS. Complements the color
tokens set in .streamlit/config.toml (which control Streamlit's own
native widget theming) with the layout/animation polish Streamlit's
theme system can't reach: card shadows, hover lift, the hero banner, and
photo placeholders.
"""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Poppins', sans-serif; }

/* ---- hero banner ---- */
.hero-banner {
    position: relative;
    border-radius: 18px;
    overflow: hidden;
    height: 260px;
    margin-bottom: 1.75rem;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    box-shadow: 0 10px 30px rgba(0,0,0,0.18);
}
.hero-banner .hero-tile {
    background-size: cover;
    background-position: center;
    filter: saturate(1.05);
}
.hero-banner .hero-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(20,20,30,0.15) 0%, rgba(15,15,25,0.75) 100%);
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 1.5rem 2rem;
}
.hero-overlay h1 {
    color: #fff;
    margin: 0;
    font-size: 2.1rem;
    text-shadow: 0 2px 10px rgba(0,0,0,0.4);
}
.hero-overlay p {
    color: #f0f0f0;
    margin: 0.35rem 0 0 0;
    font-size: 1.02rem;
    text-shadow: 0 1px 6px rgba(0,0,0,0.4);
}

/* ---- destination cards ---- */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    border-radius: 14px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 22px rgba(0,0,0,0.12);
}

/* ---- images (fixed height + cover-crop so grid/card rows line up
   evenly regardless of each landmark photo's native aspect ratio) ---- */
[data-testid="stImage"] img {
    border-radius: 12px;
    object-fit: cover;
    width: 100%;
    height: 150px;
}

/* ---- photo placeholder (shown when a live photo can't be fetched) ---- */
.photo-placeholder {
    height: 140px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 0.5rem;
    color: #fff;
    font-weight: 600;
    font-family: 'Poppins', sans-serif;
    background: linear-gradient(135deg, #ff9966, #ff5e62 60%, #6a5af9);
}

/* ---- score badge pills ---- */
.badge-row span.pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    background: #eafaf1;
    color: #157347;
    font-size: 0.82rem;
    margin: 2px 4px 2px 0;
}

/* ---- gallery grid caption (rendered ABOVE its photo, as a header --
   avoids reading as the caption for the row below it) ---- */
.gallery-caption {
    font-size: 0.9rem;
    font-weight: 700;
    text-align: center;
    margin: 1.1rem 0 0.4rem 0;
}

/* ---- sidebar: warm gradient backdrop + a distinct "form card" header
   so the preferences panel reads as one cohesive module, not a stack of
   default widgets ---- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFF6F0 0%, #F7F3EE 55%, #FFF1EA 100%);
}
.pref-card-header {
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    font-size: 1.15rem;
    margin: 0.4rem 0 0.1rem 0;
}

/* ---- segmented controls: rounder pills with a touch more presence ---- */
[data-testid="stSegmentedControl"] button {
    border-radius: 999px !important;
}

/* ---- expander used for the multi-photo "explore" gallery: subtle
   hover affordance so it reads as clickable ---- */
[data-testid="stExpander"] summary {
    border-radius: 10px;
    transition: background 0.15s ease;
}
[data-testid="stExpander"] summary:hover {
    background: rgba(255, 94, 77, 0.08);
}

/* ---- gentle entrance animation on the main content so the page feels
   alive on load/tab-switch rather than static ---- */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
[data-testid="stMainBlockContainer"] {
    animation: fadeInUp 0.35s ease-out;
}
</style>
"""
