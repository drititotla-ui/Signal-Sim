"""
Home Page View for SIGNALSIM-INDIA.

Provides high-level project narrative, intelligent transportation systems (ITS) context,
Left-Hand Traffic (LHT) challenges, and platform orientation.
"""

import streamlit as st
from dashboard.common import clean_html, render_brand_header, switch_to_page


def render_home():
    render_brand_header("Home")

    hero_html = clean_html("""
    <div class="hero-its">
        <span class="hero-tag">Adaptive Traffic Signal Research Platform</span>
        <h1 class="hero-title-dark">SIGNALSIM-INDIA</h1>
        <div class="hero-subtitle-dark">Smart Traffic. Smarter Decisions.</div>
        <p class="hero-desc-dark">
            An open experimental platform evaluating decentralized adaptive traffic control heuristics
            and reinforcement learning against classical static baselines under genuine Left-Hand Traffic (LHT)
            rules for mixed, heterogeneous Indian urban intersections.
        </p>
    </div>
    """)
    st.markdown(hero_html, unsafe_allow_html=True)

    # Navigation Call-To-Action Cards
    col_nav1, col_nav2, col_nav3 = st.columns(3)

    with col_nav1:
        st.markdown(clean_html("""
        <div class="its-card">
            <h4>📊 Performance Dashboard</h4>
            <p>Explore comparative benchmark results, delay reductions, and throughput metrics across verified simulation runs.</p>
        </div>
        """), unsafe_allow_html=True)
        if st.button("Open Dashboard →", key="btn_to_dash", use_container_width=True):
            switch_to_page("dashboard")

    with col_nav2:
        st.markdown(clean_html("""
        <div class="its-card">
            <h4>🚦 Simulation Control</h4>
            <p>Inspect controller implementations, configure demand regimes (S1–S4), and execute local SUMO micro-simulations.</p>
        </div>
        """), unsafe_allow_html=True)
        if st.button("Explore Simulation →", key="btn_to_sim", use_container_width=True):
            switch_to_page("simulation")

    with col_nav3:
        st.markdown(clean_html("""
        <div class="its-card">
            <h4>📐 Methodology & Metrics</h4>
            <p>Review the formal experimental protocol, TripInfo metric derivations, and cohort classification standards.</p>
        </div>
        """), unsafe_allow_html=True)
        if st.button("View Methodology →", key="btn_to_meth", use_container_width=True):
            switch_to_page("methodology")

    st.write("")
    st.write("")

    # Narrative Columns: The Traffic Challenge & Controllers
    col_problem, col_controllers = st.columns(2)

    with col_problem:
        st.markdown(clean_html("""
        <div class="its-card">
            <div class="section-tag">Urban Mobility Challenge</div>
            <h3>The Urban Intersection Bottleneck</h3>
            <p>
                Conventional urban traffic lights operate on rigid, pre-programmed fixed-time signal cycles.
                These static plans are derived from historical peak-hour averages and cannot adapt to instantaneous
                traffic surges, directional imbalances, or stochastic queuing dynamics.
            </p>
            <p>
                In Indian urban centers, this problem is compounded by <strong>heterogeneous vehicle mixes</strong>
                (two-wheelers, auto-rickshaws, cars, buses, and commercial vehicles) and <strong>non-lane-based driving</strong>.
                Vehicles filter and occupy space laterally rather than adhering to rigid lane markings.
            </p>
            <p>
                Under <strong>Left-Hand Traffic (LHT)</strong> rules, right-turning movements cross opposing arterial
                traffic, while left turns operate as filter streams. Evaluating signal controllers requires an
                accurate geometric representation of these crossing conflicts.
            </p>
        </div>
        """), unsafe_allow_html=True)

    with col_controllers:
        st.markdown(clean_html("""
        <div class="its-card">
            <div class="section-tag">Evaluated Algorithms</div>
            <h3>Signal Control Strategies</h3>
            <p>
                <strong>1. Fixed-Time Baseline (Static):</strong><br>
                Operates on a classical 68-second static cycle with 30s green phases separated by 3s yellow and
                clearance intervals. Serves as the experimental benchmark representing typical Indian urban infrastructure.
            </p>
            <p>
                <strong>2. Max-Pressure Control (Decentralized Heuristic):</strong><br>
                Dynamically balances upstream incoming queues against downstream available capacities every 10 seconds.
                Greedily prioritizes phases with the highest network pressure without requiring origin-destination matrix predictions.
            </p>
            <p>
                <strong>3. Deep Reinforcement Learning (PPO — Coming Soon):</strong><br>
                Proximal Policy Optimization policy trained on queue states and sublane occupancy metrics.
                Currently in development and evaluation staging.
            </p>
        </div>
        """), unsafe_allow_html=True)
