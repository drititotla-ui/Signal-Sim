"""
Views package for SIGNALSIM-INDIA Multipage Streamlit Application.
"""

from dashboard.views.about import render_about
from dashboard.views.dashboard import render_dashboard
from dashboard.views.home import render_home
from dashboard.views.methodology import render_methodology
from dashboard.views.metrics import render_metrics
from dashboard.views.simulation import render_simulation

__all__ = [
    "render_home",
    "render_dashboard",
    "render_simulation",
    "render_metrics",
    "render_methodology",
    "render_about",
]
