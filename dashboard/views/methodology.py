"""
Methodology and Experimental Protocol View for SIGNALSIM-INDIA.

Documents the formal benchmark specifications, locked traffic demand scenarios,
turning movement splits, controller state machines, and simulation parameters.
"""

import streamlit as st

from dashboard.common import (
    BASELINE_DEMAND_VPH,
    clean_html,
    get_scenario_metadata,
    render_brand_header,
)


def render_methodology():
    render_brand_header("Methodology")
    scenario_meta = get_scenario_metadata()

    st.markdown(clean_html("""
    <div class="section-header">
        <div class="section-tag">Experimental Protocol</div>
        <h2 class="section-title">Methodology & Experimental Standards</h2>
        <div class="section-subtitle">Locked experimental parameters, signal timing logic, and demand configurations defining the evaluation benchmark.</div>
    </div>
    """), unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(clean_html(f"""
        <div class="its-card" style="margin-bottom:1.5rem;">
            <h4>🚦 Traffic Demand Regimes (S1–S4)</h4>
            <p style="font-size:0.88rem; color:#64748B; margin-bottom:0.75rem;">
                <strong>Baseline Design Demand:</strong> {BASELINE_DEMAND_VPH} vehicles/hour/approach (nominal 100% capacity).
            </p>
            <table class="its-table">
                <thead>
                    <tr>
                        <th>Scenario</th>
                        <th>Multiplier</th>
                        <th>Volume / Arm</th>
                        <th>Regime Classification</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>S1</strong></td>
                        <td>0.50×</td>
                        <td><strong>300 veh/h</strong></td>
                        <td>Unsaturated / Off-Peak Flow</td>
                    </tr>
                    <tr>
                        <td><strong>S2</strong></td>
                        <td>0.75×</td>
                        <td><strong>450 veh/h</strong></td>
                        <td>Moderate / Medium Flow</td>
                    </tr>
                    <tr>
                        <td><strong>S3</strong></td>
                        <td>1.00×</td>
                        <td><strong>600 veh/h</strong></td>
                        <td>Nominal Baseline Capacity</td>
                    </tr>
                    <tr>
                        <td><strong>S4</strong></td>
                        <td>1.25×</td>
                        <td><strong>750 veh/h</strong></td>
                        <td>Oversaturated / Peak Congestion</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """), unsafe_allow_html=True)

        st.markdown(clean_html("""
        <div class="its-card">
            <h4>🔄 Turning Movement Proportions</h4>
            <p>
                In Left-Hand Traffic (LHT), turning movements have asymmetric conflict profiles:
            </p>
            <ul>
                <li><strong>Left Turns (20%):</strong> Filter / unobstructed turn directly entering the near curb lane without conflicting with oncoming streams.</li>
                <li><strong>Through / Straight (60%):</strong> Primary arterial volume traversing directly across the intersection core.</li>
                <li><strong>Right Turns (20%):</strong> Crosses opposing straight traffic into internal junction waiting areas (<code>cont="1"</code>).</li>
            </ul>
            <p style="font-size:0.85rem; color:#64748B; margin-top:0.5rem;">
                <em>These proportions are applied uniformly across all four incoming arms (-E1 North, -E2 East, -E3 South, -E4 West).</em>
            </p>
        </div>
        """), unsafe_allow_html=True)

    with col2:
        st.markdown(clean_html("""
        <div class="its-card" style="margin-bottom:1.5rem;">
            <h4>⏱️ Simulation Timeline & Cohorts</h4>
            <p>
                To eliminate initialization bias and truncation artifacts, each run follows a 5,100-second timeline:
            </p>
            <table class="its-table">
                <thead>
                    <tr>
                        <th>Phase</th>
                        <th>Time Interval</th>
                        <th>Duration</th>
                        <th>Cohort Treatment</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Warm-up</strong></td>
                        <td>[0, 600s)</td>
                        <td>600s (10 min)</td>
                        <td>Excluded from KPIs</td>
                    </tr>
                    <tr>
                        <td><strong>Evaluation</strong></td>
                        <td>[600, 4200s)</td>
                        <td>3600s (60 min)</td>
                        <td><strong>Official KPI Cohort</strong></td>
                    </tr>
                    <tr>
                        <td><strong>Drain</strong></td>
                        <td>[4200, 5100s]</td>
                        <td>900s (15 min)</td>
                        <td>Zero new vehicle departures</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """), unsafe_allow_html=True)

        st.markdown(clean_html("""
        <div class="its-card">
            <h4>🎲 Evaluation Seeds & Reproducibility</h4>
            <p>
                Every scenario is evaluated under five pre-agreed pseudo-random seeds:
            </p>
            <div style="display:flex; gap:0.5rem; margin: 0.75rem 0;">
                <code>42 (Reference)</code>
                <code>101</code>
                <code>202</code>
                <code>303</code>
                <code>404</code>
            </div>
            <p style="font-size:0.85rem;">
                Controllers are benchmarked using <strong>matched seeds</strong>: Fixed-Time on Seed 42 is paired strictly with Max-Pressure on Seed 42. This controls for stochastic variation in vehicle arrival intervals.
            </p>
        </div>
        """), unsafe_allow_html=True)

    st.write("")
    st.write("")

    # Controller State Machine Details
    st.markdown(clean_html("""
    <div class="its-card">
        <h4>⚙️ Traffic Light Control Specifications (Node J2)</h4>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:1.25rem; margin-top:1rem;">
            <div class="its-subcard">
                <h5 style="color:#2DD4BF; margin-bottom:0.5rem;">Fixed-Time Controller</h5>
                <p style="font-size:0.85rem;">
                    • <strong>Cycle Length:</strong> 68.0 seconds<br>
                    • <strong>Phase 0 (East-West Green):</strong> 30.0s (<code>GGGGgrrrrrGGGGgrrrrr</code>)<br>
                    • <strong>Phase 1 (East-West Yellow):</strong> 3.0s (<code>yyyyyrrrrryyyyyrrrrr</code>)<br>
                    • <strong>Phase 2 (All-Red Clearance):</strong> 1.0s (<code>rrrrrrrrrrrrrrrrrrrr</code>)<br>
                    • <strong>Phase 3 (North-South Green):</strong> 30.0s (<code>rrrrrGGGGgrrrrrGGGGg</code>)<br>
                    • <strong>Phase 4 (North-South Yellow):</strong> 3.0s (<code>rrrrryyyyyrrrrryyyyy</code>)<br>
                    • <strong>Phase 5 (All-Red Clearance):</strong> 1.0s (<code>rrrrrrrrrrrrrrrrrrrr</code>)
                </p>
            </div>
            <div class="its-subcard">
                <h5 style="color:#14B8A6; margin-bottom:0.5rem;">Max-Pressure Adaptive</h5>
                <p style="font-size:0.85rem;">
                    • <strong>Decision Interval:</strong> 10.0 seconds<br>
                    • <strong>State Evaluation:</strong> Calculates upstream queue (halting vehicles) minus downstream occupancy per movement.<br>
                    • <strong>Min Green Constraint:</strong> 10.0s minimum holding time.<br>
                    • <strong>Yellow Interval:</strong> 3.0s clearance before red.<br>
                    • <strong>All-Red Clearance:</strong> 1.0s baseline (3.0s safety margin).
                </p>
            </div>
            <div class="its-subcard">
                <h5 style="color:#A855F7; margin-bottom:0.5rem;">PPO V6 Reinforcement Learning</h5>
                <p style="font-size:0.85rem;">
                    • <strong>Policy Type:</strong> Actor-Critic PPO target-phase policy (`MlpPolicy`).<br>
                    • <strong>Action Space:</strong> Discrete target phase selection (0: EW Green, 1: NS Green).<br>
                    • <strong>Current Status:</strong> <span style="color:#2DD4BF; font-weight:700;">✓ Verified Pilot Checkpoint</span>.<br>
                    • <strong>Inference Mode:</strong> Evaluated under reproducible stochastic inference with closed switch loophole penalties.
                </p>
            </div>
        </div>
    </div>
    """), unsafe_allow_html=True)
