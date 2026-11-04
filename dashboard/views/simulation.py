"""
Simulation Control View for SIGNALSIM-INDIA.

Provides interactive execution staging and genuine local SUMO micro-simulation runs
via experiments/run_experiments.py for Fixed-Time and Max-Pressure controllers
across configured demand tiers (S1–S4) and random seeds.
"""

from pathlib import Path
import textwrap
import streamlit as st

from dashboard.common import (
    get_scenario_metadata,
    render_brand_header,
)
from dashboard.simulation_runner import (
    check_prerequisites,
    run_single_simulation,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def render_simulation():
    render_brand_header("Simulation")
    scenario_meta = get_scenario_metadata()

    st.markdown(textwrap.dedent("""
    <div class="section-header">
        <div class="section-tag">Interactive Execution</div>
        <h2 class="section-title">Traffic Simulation Execution Panel</h2>
        <div class="section-subtitle">Configure, stage, and execute micro-simulation runs on the verified Left-Hand Traffic SUMO network.</div>
    </div>
    """).strip(), unsafe_allow_html=True)

    # Local Host Execution Notice
    st.info(
        "ℹ️ **Local Host Execution Notice:** Simulations execute locally using the SUMO installation "
        "and Python environment on the machine hosting the Streamlit application. A remote web deployment "
        "cannot launch SUMO on an arbitrary visitor's machine without a local runner agent."
    )

    # Controller Status Table
    st.markdown(textwrap.dedent("""
    <div class="its-card" style="margin-bottom:1.5rem;">
        <h4>Controller Development & Operational Status</h4>
        <table class="its-table">
            <thead>
                <tr>
                    <th>Controller</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Evaluation Readiness</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Fixed-Time</strong></td>
                    <td>Static Cycle (68s)</td>
                    <td><span style="color:#2DD4BF; font-weight:700;">✓ Operational Baseline</span></td>
                    <td>Ready for execution & benchmark evaluation</td>
                </tr>
                <tr>
                    <td><strong>Max-Pressure</strong></td>
                    <td>Queue Heuristic (10s)</td>
                    <td><span style="color:#2DD4BF; font-weight:700;">✓ Operational Baseline</span></td>
                    <td>Ready for execution & benchmark evaluation</td>
                </tr>
                <tr>
                    <td><strong>PPO V6 Policy</strong></td>
                    <td>Deep Reinforcement Learning</td>
                    <td><span style="color:#2DD4BF; font-weight:700;">✓ Operational RL Candidate</span></td>
                    <td>Ready for execution & benchmark evaluation (stochastic inference)</td>
                </tr>
            </tbody>
        </table>
    </div>
    """).strip(), unsafe_allow_html=True)

    # Simulation Controls Card
    st.markdown(textwrap.dedent("""
    <div class="its-card" style="margin-bottom:1.5rem;">
        <h4>Simulation Run Configuration</h4>
    """).strip(), unsafe_allow_html=True)

    col_ctrl, col_scen, col_seed = st.columns(3)

    controller_map = {
        "Fixed-Time Baseline (fixed_time)": "fixed_time",
        "Max-Pressure Adaptive (max_pressure)": "max_pressure",
        "PPO V6 RL Policy (ppo_v6)": "ppo_v6",
    }

    with col_ctrl:
        selected_ctrl_label = st.selectbox(
            "Select Controller:",
            options=list(controller_map.keys()),
            index=0,
            help="Select the operational traffic signal controller: Fixed-Time, Max-Pressure, or PPO V6 (stochastic).",
        )
        selected_controller_id = controller_map[selected_ctrl_label]
        st.markdown(textwrap.dedent("""
        <div style="font-size:0.8rem; color:#2DD4BF; margin-top:0.35rem; font-weight:600;">
            • PPO V6 Policy: Operational RL model loaded from models/ppo_v6_model.zip (stochastic inference)
        </div>
        """).strip(), unsafe_allow_html=True)

    scenario_labels = {
        sid: scenario_meta[sid]["label"]
        for sid in ["S1", "S2", "S3", "S4"]
        if sid in scenario_meta
    }
    label_to_sid = {v: k for k, v in scenario_labels.items()}

    with col_scen:
        selected_scen_label = st.selectbox(
            "Select Traffic Scenario:",
            options=list(scenario_labels.values()),
            index=0,
            help="Locked demand tiers based on 600 vph/approach baseline design capacity.",
        )
        selected_scenario_id = label_to_sid.get(selected_scen_label, "S1")

    with col_seed:
        selected_seed = st.selectbox(
            "Select Evaluation Seed:",
            options=[42, 101, 202, 303, 404],
            index=0,
            help="Evaluation seeds configured for reproducible benchmark simulation.",
        )

    enable_gui = st.checkbox(
        "Launch with SUMO Graphical Interface (sumo-gui)",
        value=False,
        help="Optional: Open visual SUMO-GUI window during execution. Defaults to headless for fast execution.",
    )

    st.write("")
    btn_run = st.button("Run Simulation", type="primary", use_container_width=True)

    # Execution Area
    if btn_run:
        # Check if another run is active
        if st.session_state.get("sim_running", False):
            st.warning("A simulation run is already in progress. Please wait for it to complete.")
        else:
            st.session_state["sim_running"] = True
            planned_run_id = f"{selected_controller_id}_{selected_scenario_id}_seed{selected_seed}"
            gui_msg = " (GUI mode)" if enable_gui else ""

            with st.spinner(f"Executing SUMO simulation: {planned_run_id}{gui_msg} ... (Estimated: ~20-30s)"):
                result = run_single_simulation(
                    controller_id=selected_controller_id,
                    scenario_id=selected_scenario_id,
                    seed=selected_seed,
                    gui=enable_gui,
                )

            st.session_state["sim_running"] = False

            # Invalidate caches to refresh all dashboard views
            st.cache_resource.clear()
            st.cache_data.clear()

            if result.success:
                st.markdown(textwrap.dedent(f"""
                <div class="banner-complete-dark" style="margin-top:1.25rem;">
                    <strong>✓ Simulation Completed Successfully!</strong><br>
                    <strong>Run ID:</strong> <code>{result.run_id}</code> |
                    <strong>Duration:</strong> {result.wall_clock_seconds:.1f}s wall-clock time.<br>
                    Benchmark records have been updated and synced to the Master Summary.
                </div>
                """).strip(), unsafe_allow_html=True)

                # Show KPI metrics from the executed run
                metrics = result.metrics
                if metrics:
                    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
                    with col_kpi1:
                        st.metric("Completed Vehicles", f"{metrics.get('completed_vehicles', '—')}")
                    with col_kpi2:
                        st.metric("Throughput", f"{metrics.get('throughput_vph', '—')} veh/h")
                    with col_kpi3:
                        st.metric("Avg Waiting Time", f"{metrics.get('mean_waiting_time', '—')} s")
                    with col_kpi4:
                        st.metric("Avg Travel Time", f"{metrics.get('mean_travel_time', '—')} s")

                with st.expander("📄 View SUMO Execution Output Log"):
                    if result.stdout:
                        st.text(result.stdout)
                    if result.stderr:
                        st.code(result.stderr, language="text")
            else:
                st.markdown(textwrap.dedent(f"""
                <div class="banner-partial-dark" style="margin-top:1.25rem;">
                    <strong>❌ Simulation Execution Failed:</strong><br>
                    {result.error_message}
                </div>
                """).strip(), unsafe_allow_html=True)
                if result.stdout or result.stderr:
                    with st.expander("View Error Diagnostics"):
                        if result.stdout:
                            st.text(result.stdout)
                        if result.stderr:
                            st.code(result.stderr, language="text")
    else:
        st.markdown(textwrap.dedent(f"""
        <div class="sim-info-box" style="margin-top:0.5rem; padding:0.85rem; border-radius:8px; border:1px dashed var(--border-color, #334155); text-align:center; font-size:0.85rem;">
            Ready to configure. Selected: <code>{selected_controller_id}</code> on <code>{selected_scenario_id}</code> (Seed {selected_seed}). Click above to launch.
        </div>
        """).strip(), unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Runtime Parameters & Environment Constants Card
    st.markdown(textwrap.dedent("""
    <div class="its-card">
        <h4>Runtime Parameters & Environment Constants</h4>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:1rem; margin-top:0.75rem;">
            <div>
                <span style="font-size:0.78rem; color:#64748B; text-transform:uppercase; font-weight:700;">Intersection ID</span><br>
                <strong>J2 (LHT 4-Arm Node)</strong>
            </div>
            <div>
                <span style="font-size:0.78rem; color:#64748B; text-transform:uppercase; font-weight:700;">Simulation Horizon</span><br>
                <strong>5,100 s (1.42 hrs)</strong>
            </div>
            <div>
                <span style="font-size:0.78rem; color:#64748B; text-transform:uppercase; font-weight:700;">Simulation Step</span><br>
                <strong>0.10 seconds</strong>
            </div>
            <div>
                <span style="font-size:0.78rem; color:#64748B; text-transform:uppercase; font-weight:700;">Decision Interval</span><br>
                <strong>10.0 seconds</strong>
            </div>
            <div>
                <span style="font-size:0.78rem; color:#64748B; text-transform:uppercase; font-weight:700;">Sublane Resolution</span><br>
                <strong style="color:#2DD4BF;">0.50 meters</strong>
            </div>
            <div>
                <span style="font-size:0.78rem; color:#64748B; text-transform:uppercase; font-weight:700;">Warm-up / Eval / Drain</span><br>
                <strong>600s / 3,600s / 900s</strong>
            </div>
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)
