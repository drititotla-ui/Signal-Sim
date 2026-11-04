"""
SIGNALSIM-INDIA Multipage Web Application (M04.2.3).

Architecture:
- Native Streamlit multipage navigation via st.navigation and st.Page.
- Six distinct modular views: Home, Dashboard, Simulation, Metrics, Methodology, About.
- Integrated theme switcher supporting Dark Navy (#0A0F1D) and Clean Light (#F8FAFC).
- Global Page registry enabling seamless st.switch_page programmatic transitions.
"""

from pathlib import Path
import sys
import streamlit as st

# Ensure repository root is on sys.path for backend and view imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dashboard.common import PAGES, register_pages
from dashboard.styles import get_theme_css
from dashboard.views import (
    render_about,
    render_dashboard,
    render_home,
    render_methodology,
    render_metrics,
    render_simulation,
)

# Page configuration
st.set_page_config(
    page_title="SignalSim-India | Intelligent Traffic Simulation",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize theme state
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

# Apply active ITS theme styling
st.markdown(get_theme_css(st.session_state["theme"]), unsafe_allow_html=True)

# Define native multipage navigation structure
home_page = st.Page(
    render_home,
    title="Home",
    icon=":material/home:",
    url_path="home",
    default=True,
)

dashboard_page = st.Page(
    render_dashboard,
    title="Dashboard",
    icon=":material/dashboard:",
    url_path="dashboard",
)

simulation_page = st.Page(
    render_simulation,
    title="Simulation",
    icon=":material/play_circle:",
    url_path="simulation",
)

metrics_page = st.Page(
    render_metrics,
    title="Metrics",
    icon=":material/analytics:",
    url_path="metrics",
)

methodology_page = st.Page(
    render_methodology,
    title="Methodology",
    icon=":material/menu_book:",
    url_path="methodology",
)

about_page = st.Page(
    render_about,
    title="About",
    icon=":material/info:",
    url_path="about",
)

# Register pages in global dictionary for cross-page navigation
register_pages({
    "home": home_page,
    "dashboard": dashboard_page,
    "simulation": simulation_page,
    "metrics": metrics_page,
    "methodology": methodology_page,
    "about": about_page,
})

# Initialize navigation with horizontal top bar
pg = st.navigation(
    [
        home_page,
        dashboard_page,
        simulation_page,
        metrics_page,
        methodology_page,
        about_page,
    ],
    position="top",
)

# Execute the selected page
pg.run()
