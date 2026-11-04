"""
Brand Styles, Color Palettes, and ITS Theme Definitions for SIGNALSIM-INDIA.

Provides dedicated, professionally designed CSS for both Dark Mode and Light Mode.
Neither theme is a simple inversion; each is crafted specifically for Intelligent
Transportation Systems (ITS) visualization, high readability, and WCAG AA contrast.
"""

# -----------------------------------------------------------------------------
# DARK THEME (Deep Navy / ITS Operations Center)
# -----------------------------------------------------------------------------
CUSTOM_DARK_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Global resets & typography */
html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: #0A0F1D !important;
    color: #F8FAFC !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* Hide Streamlit default clutter */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {
    background-color: #0A0F1D !important;
    border-bottom: 1px solid #1E293B !important;
}

/* Max container width & padding */
.block-container {
    padding-top: 5rem !important;
    padding-bottom: 4rem !important;
    max-width: 1200px !important;
}

@media (max-width: 992px) {
    .block-container {
        padding-top: 5.75rem !important;
    }
}

@media (max-width: 768px) {
    .block-container {
        padding-top: 6.5rem !important;
    }
}

@media (max-width: 480px) {
    .block-container {
        padding-top: 7.5rem !important;
    }
}

/* Streamlit Native Top Navigation Bar Styling */
[data-testid="stTopNav"] {
    background-color: #0A0F1D !important;
    border-bottom: 1px solid #1E293B !important;
    padding: 0.4rem 1rem !important;
}

[data-testid="stTopNav"] a, [data-testid="stTopNav"] button {
    color: #94A3B8 !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    transition: all 0.2s ease !important;
}

[data-testid="stTopNav"] a:hover, [data-testid="stTopNav"] button:hover {
    color: #2DD4BF !important;
}

[data-testid="stTopNav"] a[aria-current="page"], [data-testid="stTopNav"] button[aria-current="page"] {
    color: #14B8A6 !important;
    border-bottom: 2px solid #14B8A6 !important;
}

/* Top Branding Bar Container */
.brand-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 12px;
    padding: 0.65rem 1.25rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.brand-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background-color: rgba(20, 184, 166, 0.1);
    color: #2DD4BF;
    border: 1px solid rgba(20, 184, 166, 0.25);
    padding: 0.25rem 0.65rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

.brand-github-link {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background-color: #1E293B;
    color: #F8FAFC !important;
    border: 1px solid #334155;
    padding: 0.4rem 0.85rem;
    border-radius: 8px;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    text-decoration: none;
    transition: all 0.2s ease;
}

.brand-github-link:hover {
    background-color: #334155;
    border-color: #2DD4BF;
}

/* Section Headers */
.section-header {
    margin-bottom: 1.5rem;
}

.section-tag {
    color: #14B8A6;
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}

.section-title {
    font-size: 1.85rem;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.5px;
    line-height: 1.2;
    margin-bottom: 0.35rem;
}

.section-subtitle {
    font-size: 0.95rem;
    color: #94A3B8;
    line-height: 1.5;
}

/* ITS Cards */
.its-card {
    background-color: #131C31;
    border: 1px solid #1E293B;
    border-radius: 12px;
    padding: 1.35rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    transition: all 0.2s ease;
    height: 100%;
    display: flex;
    flex-direction: column;
}

.its-card:hover {
    border-color: #334155;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
}

.its-card h3, .its-card h4 {
    color: #F8FAFC;
    font-weight: 700;
    margin-bottom: 0.65rem;
}

.its-card p, .its-card li {
    color: #94A3B8;
    font-size: 0.90rem;
    line-height: 1.55;
}

.its-subcard {
    background-color: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 8px;
    padding: 1rem;
}

.its-subcard p {
    color: #94A3B8;
}

/* KPI Cards */
.kpi-card-dark {
    background-color: #131C31;
    border: 1px solid #1E293B;
    border-radius: 12px;
    padding: 1.35rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    height: 100%;
    position: relative;
    overflow: hidden;
}

.kpi-card-dark::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #14B8A6, #2DD4BF);
    opacity: 0.8;
}

.kpi-card-peach::before {
    background: linear-gradient(90deg, #FB7185, #F43F5E);
}

.kpi-label-dark {
    font-size: 0.78rem;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 0.45rem;
}

.kpi-value-dark {
    font-size: 2rem;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.5px;
    line-height: 1.1;
    margin-bottom: 0.3rem;
}

.kpi-value-teal {
    color: #2DD4BF;
}

.kpi-value-peach {
    color: #FB7185;
}

.kpi-subtext-dark {
    font-size: 0.80rem;
    color: #64748B;
}

/* Status Banners */
.banner-partial-dark {
    background-color: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-left: 4px solid #F59E0B;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 1.5rem;
    color: #FDE68A;
    font-size: 0.90rem;
    line-height: 1.5;
}

.banner-complete-dark {
    background-color: rgba(20, 184, 166, 0.08);
    border: 1px solid rgba(20, 184, 166, 0.3);
    border-left: 4px solid #14B8A6;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 1.5rem;
    color: #99F6E4;
    font-size: 0.90rem;
    line-height: 1.5;
}

/* Comparison Badges */
.pill-improvement-pos {
    background-color: rgba(20, 184, 166, 0.15);
    color: #2DD4BF;
    border: 1px solid rgba(20, 184, 166, 0.3);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.85rem;
}

.pill-improvement-neg {
    background-color: rgba(251, 113, 133, 0.15);
    color: #FB7185;
    border: 1px solid rgba(251, 113, 133, 0.3);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.85rem;
}

/* Hero Card (Home) */
.hero-its {
    background: linear-gradient(135deg, #131C31 0%, #0F172A 100%);
    border: 1px solid #1E293B;
    border-radius: 16px;
    padding: 2.75rem 2rem;
    margin-bottom: 2rem;
    text-align: center;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    position: relative;
    overflow: hidden;
}

.hero-its::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 20%;
    right: 20%;
    height: 1px;
    background: linear-gradient(90deg, transparent, #14B8A6, transparent);
}

.hero-tag {
    display: inline-block;
    background-color: rgba(20, 184, 166, 0.12);
    color: #2DD4BF;
    border: 1px solid rgba(20, 184, 166, 0.3);
    padding: 0.25rem 0.8rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    margin-bottom: 1rem;
}

.hero-title-dark {
    font-size: 2.75rem;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.7px;
    margin-bottom: 0.45rem;
}

.hero-subtitle-dark {
    font-size: 1.25rem;
    font-weight: 600;
    color: #14B8A6;
    margin-bottom: 1.1rem;
}

.hero-desc-dark {
    max-width: 720px;
    margin: 0 auto;
    font-size: 1.0rem;
    color: #94A3B8;
    line-height: 1.6;
}

/* Table styling */
.its-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.75rem;
    background-color: #131C31;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #1E293B;
}

.its-table th {
    background-color: #0F172A;
    color: #F8FAFC;
    font-weight: 700;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0.75rem 0.9rem;
    border-bottom: 1px solid #1E293B;
    text-align: left;
}

.its-table td {
    padding: 0.75rem 0.9rem;
    border-bottom: 1px solid #1E293B;
    color: #94A3B8;
    font-size: 0.88rem;
}

.its-table tr:hover {
    background-color: #1A243B;
}

/* Code blocks & tags */
code {
    background-color: #1E293B !important;
    color: #2DD4BF !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.84rem !important;
    padding: 0.2rem 0.45rem !important;
    border-radius: 4px !important;
}

/* Streamlit Widget dark styling overrides */
div[data-baseweb="select"] > div {
    background-color: #131C31 !important;
    border-color: #1E293B !important;
    color: #F8FAFC !important;
}

div[data-baseweb="select"] span {
    color: #F8FAFC !important;
}

button[kind="primary"] {
    background-color: #14B8A6 !important;
    color: #0A0F1D !important;
    font-weight: 700 !important;
    border: none !important;
    transition: all 0.2s ease !important;
}

button[kind="primary"]:hover {
    background-color: #2DD4BF !important;
    box-shadow: 0 4px 12px rgba(20, 184, 166, 0.3) !important;
}

/* Secondary Buttons */
button[kind="secondary"] {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
    border: 1px solid #334155 !important;
    transition: all 0.2s ease !important;
}

button[kind="secondary"]:hover {
    border-color: #14B8A6 !important;
    color: #2DD4BF !important;
}

/* Simulation Info Box */
.sim-info-box {
    background-color: transparent !important;
    border: 1px dashed #334155 !important;
    color: #94A3B8 !important;
}

/* Dark Mode Segmented Control */
[data-testid="stSegmentedControl"] {
    background-color: #0F172A !important;
    border: 1px solid #1E293B !important;
}

[data-testid="stSegmentedControl"] button {
    color: #94A3B8 !important;
}

[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background-color: #14B8A6 !important;
    color: #0A0F1D !important;
    font-weight: 700 !important;
}

</style>
"""

# -----------------------------------------------------------------------------
# LIGHT THEME (Clean Off-White / High-Contrast Crisp ITS Surface)
# -----------------------------------------------------------------------------
CUSTOM_LIGHT_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Global resets & typography */
html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* Ensure all typography is crisp, high-contrast navy/near-black across all pages */
.stApp p,
.stApp span,
.stApp label,
.stApp li,
.stApp td,
.stApp th,
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp h5,
.stApp h6,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] em,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h5,
[data-testid="stMarkdownContainer"] h6,
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"] p,
[data-testid="stRadio"] label,
[data-testid="stRadio"] span,
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] span,
[data-testid="stSelectbox"] label,
[data-testid="stSelectbox"] span,
[data-testid="stSelectbox"] div,
[data-testid="stMetricLabel"] p,
[data-testid="stMetricValue"] div,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p,
.stTabs [data-baseweb="tab"] {
    color: #0F172A !important;
}

/* Secondary Muted Body Text */
.section-subtitle,
.its-card p,
.its-card li,
.hero-desc-dark,
.sim-info-box,
.subtext-muted {
    color: #334155 !important;
}

.kpi-subtext-dark,
.kpi-label-dark {
    color: #475569 !important;
}


/* Hide Streamlit default clutter */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {
    background-color: #F8FAFC !important;
    border-bottom: 1px solid #E2E8F0 !important;
}

/* Max container width & padding */
.block-container {
    padding-top: 5rem !important;
    padding-bottom: 4rem !important;
    max-width: 1200px !important;
}

@media (max-width: 992px) {
    .block-container {
        padding-top: 5.75rem !important;
    }
}

@media (max-width: 768px) {
    .block-container {
        padding-top: 6.5rem !important;
    }
}

@media (max-width: 480px) {
    .block-container {
        padding-top: 7.5rem !important;
    }
}

/* Streamlit Native Top Navigation Bar Styling */
[data-testid="stTopNav"] {
    background-color: #FFFFFF !important;
    border-bottom: 1px solid #E2E8F0 !important;
    padding: 0.4rem 1rem !important;
}

[data-testid="stTopNav"] a, [data-testid="stTopNav"] button {
    color: #475569 !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    transition: all 0.2s ease !important;
}

[data-testid="stTopNav"] a:hover, [data-testid="stTopNav"] button:hover {
    color: #0D9488 !important;
}

[data-testid="stTopNav"] a[aria-current="page"], [data-testid="stTopNav"] button[aria-current="page"] {
    color: #0D9488 !important;
    border-bottom: 2px solid #0D9488 !important;
}

/* Top Branding Bar Container */
.brand-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 0.65rem 1.25rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.brand-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background-color: rgba(13, 148, 136, 0.1);
    color: #0D9488;
    border: 1px solid rgba(13, 148, 136, 0.25);
    padding: 0.25rem 0.65rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

.brand-github-link {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background-color: #F1F5F9;
    color: #0F172A !important;
    border: 1px solid #CBD5E1;
    padding: 0.4rem 0.85rem;
    border-radius: 8px;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    text-decoration: none;
    transition: all 0.2s ease;
}

.brand-github-link:hover {
    background-color: #E2E8F0;
    border-color: #0D9488;
}

/* Section Headers */
.section-header {
    margin-bottom: 1.5rem;
}

.section-tag {
    color: #0D9488;
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}

.section-title {
    font-size: 1.85rem;
    font-weight: 800;
    color: #0F172A;
    letter-spacing: -0.5px;
    line-height: 1.2;
    margin-bottom: 0.35rem;
}

.section-subtitle {
    font-size: 0.95rem;
    color: #475569;
    line-height: 1.5;
}

/* ITS Cards */
.its-card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1.35rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    transition: all 0.2s ease;
    height: 100%;
    display: flex;
    flex-direction: column;
}

.its-card:hover {
    border-color: #CBD5E1;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
}

.its-card h3, .its-card h4 {
    color: #0F172A;
    font-weight: 700;
    margin-bottom: 0.65rem;
}

.its-card p, .its-card li {
    color: #475569;
    font-size: 0.90rem;
    line-height: 1.55;
}

.its-subcard {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 1rem;
}

.its-subcard p {
    color: #475569;
}

/* KPI Cards */
.kpi-card-dark {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1.35rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    height: 100%;
    position: relative;
    overflow: hidden;
}

.kpi-card-dark::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #0D9488, #14B8A6);
    opacity: 0.9;
}

.kpi-card-peach::before {
    background: linear-gradient(90deg, #E11D48, #F43F5E);
}

.kpi-label-dark {
    font-size: 0.78rem;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 0.45rem;
}

.kpi-value-dark {
    font-size: 2rem;
    font-weight: 800;
    color: #0F172A;
    letter-spacing: -0.5px;
    line-height: 1.1;
    margin-bottom: 0.3rem;
}

.kpi-value-teal {
    color: #0D9488;
}

.kpi-value-peach {
    color: #E11D48;
}

.kpi-subtext-dark {
    font-size: 0.80rem;
    color: #64748B;
}

/* Status Banners */
.banner-partial-dark {
    background-color: #FEF3C7;
    border: 1px solid #FDE68A;
    border-left: 4px solid #D97706;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 1.5rem;
    color: #92400E;
    font-size: 0.90rem;
    line-height: 1.5;
}

.banner-complete-dark {
    background-color: #CCFBF1;
    border: 1px solid #99F6E4;
    border-left: 4px solid #0D9488;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 1.5rem;
    color: #115E59;
    font-size: 0.90rem;
    line-height: 1.5;
}

/* Comparison Badges */
.pill-improvement-pos {
    background-color: rgba(13, 148, 136, 0.12);
    color: #0D9488;
    border: 1px solid rgba(13, 148, 136, 0.3);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.85rem;
}

.pill-improvement-neg {
    background-color: rgba(225, 29, 72, 0.12);
    color: #E11D48;
    border: 1px solid rgba(225, 29, 72, 0.3);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.85rem;
}

/* Hero Card (Home) */
.hero-its {
    background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 2.75rem 2rem;
    margin-bottom: 2rem;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
    position: relative;
    overflow: hidden;
}

.hero-its::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 20%;
    right: 20%;
    height: 1px;
    background: linear-gradient(90deg, transparent, #0D9488, transparent);
}

.hero-tag {
    display: inline-block;
    background-color: rgba(13, 148, 136, 0.1);
    color: #0D9488;
    border: 1px solid rgba(13, 148, 136, 0.25);
    padding: 0.25rem 0.8rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    margin-bottom: 1rem;
}

.hero-title-dark {
    font-size: 2.75rem;
    font-weight: 800;
    color: #0F172A;
    letter-spacing: -0.7px;
    margin-bottom: 0.45rem;
}

.hero-subtitle-dark {
    font-size: 1.25rem;
    font-weight: 600;
    color: #0D9488;
    margin-bottom: 1.1rem;
}

.hero-desc-dark {
    max-width: 720px;
    margin: 0 auto;
    font-size: 1.0rem;
    color: #475569;
    line-height: 1.6;
}

/* Table styling */
.its-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.75rem;
    background-color: #FFFFFF;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #E2E8F0;
}

.its-table th {
    background-color: #F1F5F9;
    color: #0F172A;
    font-weight: 700;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0.75rem 0.9rem;
    border-bottom: 1px solid #E2E8F0;
    text-align: left;
}

.its-table td {
    padding: 0.75rem 0.9rem;
    border-bottom: 1px solid #E2E8F0;
    color: #334155;
    font-size: 0.88rem;
}

.its-table tr:hover {
    background-color: #F8FAFC;
}

/* Code blocks & tags */
code {
    background-color: #F1F5F9 !important;
    color: #0D9488 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.84rem !important;
    padding: 0.2rem 0.45rem !important;
    border-radius: 4px !important;
    border: 1px solid #E2E8F0 !important;
}

/* Streamlit Widget light styling overrides */
div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border-color: #CBD5E1 !important;
    color: #0F172A !important;
}

div[data-baseweb="select"] span {
    color: #0F172A !important;
}

button[kind="primary"] {
    background-color: #0D9488 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    border: none !important;
    transition: all 0.2s ease !important;
}

button[kind="primary"]:hover {
    background-color: #14B8A6 !important;
    box-shadow: 0 4px 12px rgba(13, 148, 136, 0.25) !important;
}

/* Secondary Buttons */
button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    transition: all 0.2s ease !important;
}

button[kind="secondary"]:hover {
    border-color: #0D9488 !important;
    color: #0D9488 !important;
}
/* Additional Light Mode Controls */
[data-testid="stSegmentedControl"] {
    background-color: #F1F5F9 !important;
    border: 1px solid #CBD5E1 !important;
}

[data-testid="stSegmentedControl"] button {
    color: #0F172A !important;
}

[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background-color: #0D9488 !important;
    color: #FFFFFF !important;
}

div[data-baseweb="popover"] div,
div[data-baseweb="menu"] div,
div[data-baseweb="menu"] li {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
}

.sim-info-box {
    background-color: #F8FAFC !important;
    border: 1px dashed #CBD5E1 !important;
    color: #334155 !important;
}
</style>
"""


def get_theme_css(theme: str = "dark") -> str:
    """Returns the custom CSS string corresponding to the active theme mode."""
    if theme == "light":
        return CUSTOM_LIGHT_THEME_CSS
    return CUSTOM_DARK_THEME_CSS
