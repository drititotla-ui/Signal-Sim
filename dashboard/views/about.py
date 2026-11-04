"""
About Page View for SIGNALSIM-INDIA.

Documents project background, research motivations, software architecture stack,
and source repository information.
"""

import streamlit as st
from dashboard.common import clean_html, render_brand_header


def render_about():
    render_brand_header("About")

    st.markdown(clean_html("""
    <div class="section-header">
        <div class="section-tag">Platform Overview</div>
        <h2 class="section-title">About SIGNALSIM-INDIA</h2>
        <div class="section-subtitle">Evaluating intelligent traffic signal control heuristics on authentic Indian urban intersection dynamics.</div>
    </div>
    """), unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown(clean_html("""
        <div class="its-card" style="margin-bottom:1.5rem;">
            <h4>Project Motivation & Research Context</h4>
            <p>
                Urban intersections in developing countries face unique mobility challenges that differ substantially from
                the assumptions embedded in conventional traffic engineering software:
            </p>
            <ul>
                <li><strong>Left-Hand Traffic (LHT) Dynamics:</strong> Most international traffic control research assumes Right-Hand Traffic (RHT). In LHT corridors, right-turning vehicles represent the primary conflict stream, crossing opposing high-speed through traffic.</li>
                <li><strong>Non-Lane-Based Mixed Traffic:</strong> Two-wheelers and auto-rickshaws frequently filter laterally between larger passenger vehicles, forming wide queues that discharge with high initial saturation rates.</li>
                <li><strong>Adaptive vs Static Trade-offs:</strong> Fixed-time signal controllers remain widespread due to simplicity, but cause substantial unnecessary idling. This project benchmarks modern adaptive algorithms (such as Max-Pressure queue differential heuristics) under rigorous multi-seed experimental conditions.</li>
            </ul>
        </div>
        """), unsafe_allow_html=True)

    with col_right:
        st.markdown(clean_html("""
        <div class="its-card" style="margin-bottom:1.5rem;">
            <h4>Core Technology Stack</h4>
            <table class="its-table">
                <tbody>
                    <tr>
                        <td><strong>Micro-Simulator</strong></td>
                        <td>Eclipse SUMO 1.27.0</td>
                    </tr>
                    <tr>
                        <td><strong>Control Interface</strong></td>
                        <td>TraCI (Python 3.12)</td>
                    </tr>
                    <tr>
                        <td><strong>Frontend Web</strong></td>
                        <td>Streamlit 1.66.1 (Multipage)</td>
                    </tr>
                    <tr>
                        <td><strong>Visualization</strong></td>
                        <td>Altair 6.3.0 (Responsive theme)</td>
                    </tr>
                    <tr>
                        <td><strong>Data Pipeline</strong></td>
                        <td>Pandas & NumPy</td>
                    </tr>
                    <tr>
                        <td><strong>Configuration</strong></td>
                        <td>PyYAML (YAML-driven schemas)</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """), unsafe_allow_html=True)

        st.markdown(clean_html("""
        <div class="its-card">
            <h4>Open Source & Reproducibility</h4>
            <p>
                All network source definitions, scenario specifications, route generation scripts, controller adapters,
                and benchmark validation results are managed in our GitHub repository:
            </p>
            <div style="margin-top:1rem; text-align:center;">
                <a class="brand-github-link" href="https://github.com/drititotla-ui/Signal-Sim" target="_blank" rel="noopener noreferrer" style="display:inline-flex; padding:0.65rem 1.25rem; font-size:0.95rem;">
                    <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                    </svg>
                    github.com/drititotla-ui/Signal-Sim
                </a>
            </div>
            <p style="font-size:0.8rem; color:#64748B; margin-top:1rem; text-align:center;">
                Licensed under MIT / Academic Research License.
            </p>
        </div>
        """), unsafe_allow_html=True)
