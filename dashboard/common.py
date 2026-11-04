"""
Common Utilities, Navigation Registry, and Shared Caches for SIGNALSIM-INDIA Dashboard.
"""

import base64
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.dashboard import DashboardService

BASELINE_DEMAND_VPH = 600

# Global registry of st.Page objects populated by app.py
PAGES: Dict[str, Any] = {}


def clean_html(s: str) -> str:
    """
    Strips leading whitespace from every line of an HTML snippet.
    Guarantees CommonMark never interprets any line as an indented code block (Bug A).
    """
    return "\n".join(line.strip() for line in s.strip().splitlines() if line.strip())


def register_pages(pages_map: Dict[str, Any]) -> None:
    """Registers st.Page objects into the central registry for navigation."""
    PAGES.update(pages_map)


def switch_to_page(page_name: str) -> None:
    """
    Safely navigates to a registered st.Page object.
    Resolves StreamlitPageNotFoundError by passing the registered Page instance.
    """
    if page_name in PAGES and hasattr(st, "switch_page"):
        st.switch_page(PAGES[page_name])


@st.cache_resource
def get_service() -> DashboardService:
    """Initializes and caches the DashboardService instance."""
    return DashboardService(ROOT_DIR / "results" / "summaries" / "master_summary.csv")


@st.cache_data
def get_scenario_metadata() -> Dict[str, Dict[str, Any]]:
    """
    Loads locked scenario configurations dynamically from configs/experiment.yaml.
    Baseline demand: 600 vehicles/hour/approach.
    S1 = 0.50x = 300 vph/approach
    S2 = 0.75x = 450 vph/approach
    S3 = 1.00x = 600 vph/approach
    S4 = 1.25x = 750 vph/approach
    """
    try:
        from src.experiments.config_loader import ExperimentConfig
        cfg = ExperimentConfig.load(ROOT_DIR / "configs" / "experiment.yaml")
        scenarios_data = {}
        for sid in ["S1", "S2", "S3", "S4"]:
            if sid in cfg.scenarios:
                s = cfg.scenarios[sid]
                mult = float(s.demand_multiplier)
                vph = int(round(mult * BASELINE_DEMAND_VPH))
                scenarios_data[sid] = {
                    "id": s.id,
                    "name": s.name,
                    "multiplier": mult,
                    "vph": vph,
                    "regime": s.regime,
                    "label": f"{s.id} — {s.name} ({mult:.2f}× multiplier, {vph} vph/approach)",
                }
        if len(scenarios_data) == 4:
            return scenarios_data
    except Exception:
        pass

    # Exact locked experimental configuration fallback
    return {
        "S1": {"id": "S1", "name": "Unsaturated / Off-Peak Flow", "multiplier": 0.50, "vph": 300, "label": "S1 — Unsaturated / Off-Peak Flow (0.50× multiplier, 300 vph/approach)"},
        "S2": {"id": "S2", "name": "Moderate / Medium Flow", "multiplier": 0.75, "vph": 450, "label": "S2 — Moderate / Medium Flow (0.75× multiplier, 450 vph/approach)"},
        "S3": {"id": "S3", "name": "Nominal Baseline Capacity", "multiplier": 1.00, "vph": 600, "label": "S3 — Nominal Baseline Capacity (1.00× multiplier, 600 vph/approach)"},
        "S4": {"id": "S4", "name": "Oversaturated / Peak Congestion", "multiplier": 1.25, "vph": 750, "label": "S4 — Oversaturated / Peak Congestion (1.25× multiplier, 750 vph/approach)"},
    }


def render_brand_header(current_page: str = ""):
    """
    Renders top branding bar with logo, research badge, theme toggle, and repository link.
    Guarantees no raw HTML is rendered into the Markdown AST by avoiding leading whitespace.
    """
    logo_file = Path(__file__).resolve().parent / "assets" / "logo.png"

    current_theme = st.session_state.get("theme", "dark")
    is_dark = (current_theme == "dark")

    # Logo markup: rendered inside a dedicated branded container
    logo_markup = ""
    if logo_file.is_file():
        try:
            b64 = base64.b64encode(logo_file.read_bytes()).decode("utf-8")
            pill_border = "#1E293B" if is_dark else "#CBD5E1"
            pill_shadow = "none" if is_dark else "0 1px 3px rgba(0,0,0,0.06)"
            logo_markup = (
                f'<div style="background:#FFFFFF; border-radius:8px; padding:3px 10px; '
                f'display:inline-flex; align-items:center; border:1px solid {pill_border}; '
                f'box-shadow:{pill_shadow};">'
                f'<img src="data:image/png;base64,{b64}" height="34" '
                f'style="display:block; object-fit:contain;" alt="SignalSim-India Logo" />'
                f'</div>'
            )
        except Exception:
            logo_markup = (
                '<div style="font-size:1.2rem; font-weight:800; color:'
                + ('#F8FAFC' if is_dark else '#0F172A')
                + ';">SignalSim<span style="color:#14B8A6;">-INDIA</span></div>'
            )
    else:
        logo_markup = (
            '<div style="font-size:1.2rem; font-weight:800; color:'
            + ('#F8FAFC' if is_dark else '#0F172A')
            + ';">SignalSim<span style="color:#14B8A6;">-INDIA</span></div>'
        )

    # 3-column top branding bar with vertical centering
    col_brand, col_theme, col_gh = st.columns([5, 2, 2], vertical_alignment="center")

    with col_brand:
        brand_html = (
            f'<div style="display:flex; align-items:center; gap:12px; margin-bottom:0.75rem;">'
            f'{logo_markup}'
            f'<span class="brand-badge">LHT ITS Research • SUMO 1.27.0</span>'
            f'</div>'
        )
        st.markdown(brand_html, unsafe_allow_html=True)

    with col_theme:
        # Segmented control for Light / Dark mode
        theme_options = ["🌙 Dark", "☀️ Light"]
        default_index = 0 if is_dark else 1
        selected_theme_icon = st.segmented_control(
            "Theme Mode",
            options=theme_options,
            default=theme_options[default_index],
            key=f"theme_selector_{current_page}",
            label_visibility="collapsed",
        )
        target_theme = "dark" if (selected_theme_icon == "🌙 Dark") else "light"
        if target_theme != current_theme:
            st.session_state["theme"] = target_theme
            st.rerun()

    with col_gh:
        st.link_button(
            "GitHub Repository",
            "https://github.com/drititotla-ui/Signal-Sim",
            icon=":material/code:",
            use_container_width=True,
        )
