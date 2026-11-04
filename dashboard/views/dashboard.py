"""
Performance Dashboard View for SIGNALSIM-INDIA.

Renders aggregate KPIs, controller comparison bar charts, matched-seed relative improvements,
and verified run-level records from DashboardService.
"""

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.common import (
    clean_html,
    get_scenario_metadata,
    get_service,
    render_brand_header,
)


def render_dashboard():
    render_brand_header("Dashboard")
    service = get_service()
    scenario_meta = get_scenario_metadata()

    st.markdown(clean_html("""
    <div class="section-header">
        <div class="section-tag">Empirical Results</div>
        <h2 class="section-title">Controller Performance & Benchmark Dashboard</h2>
        <div class="section-subtitle">Comparative evaluation of adaptive heuristics versus static baselines across traffic demand tiers.</div>
    </div>
    """), unsafe_allow_html=True)

    try:
        raw_df = service.load_data(refresh=False)
        kpis = service.get_overview_kpis()
        status_info = service.get_benchmark_status()
        has_data = not raw_df.empty
    except Exception:
        raw_df = pd.DataFrame()
        kpis = {}
        status_info = {"is_partial": True, "successful_runs": 0, "total_expected_runs": 40}
        has_data = False

    if not has_data:
        st.info("No benchmark results found. Run experiments via `experiments/run_experiments.py` to populate data.")
        return

    # Partial Benchmark Notice
    if status_info.get("is_partial", True):
        succ_runs = status_info.get("successful_runs", 0)
        exp_runs = status_info.get("total_expected_runs", 40)
        rate = status_info.get("completion_rate_pct", 0.0)
        st.markdown(clean_html(f"""
        <div class="banner-partial-dark">
            <strong>⚠️ Partial Benchmark Dataset Active:</strong> Displaying verified results for <strong>{succ_runs} of {exp_runs}</strong> planned runs ({rate}% completion). Single-seed and partial results illustrate initial controller trends and must not be interpreted as final multi-seed statistical conclusions.
        </div>
        """), unsafe_allow_html=True)
    else:
        st.markdown(clean_html("""
        <div class="banner-complete-dark">
            <strong>✓ Full Benchmark Suite Complete:</strong> All 40 standard evaluation runs have completed successfully across all four scenarios and evaluation seeds.
        </div>
        """), unsafe_allow_html=True)

    # 5 KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        mtt = kpis.get("mean_travel_time")
        val = f"{mtt:.2f} s" if pd.notna(mtt) else "—"
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">Avg Travel Time</div>
            <div class="kpi-value-dark kpi-value-teal">{val}</div>
            <div class="kpi-subtext-dark">Door-to-door duration</div>
        </div>
        """), unsafe_allow_html=True)

    with col2:
        mwt = kpis.get("mean_waiting_time")
        val = f"{mwt:.2f} s" if pd.notna(mwt) else "—"
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">Avg Waiting Time</div>
            <div class="kpi-value-dark">{val}</div>
            <div class="kpi-subtext-dark">Speed &lt; 0.1 m/s at stopline</div>
        </div>
        """), unsafe_allow_html=True)

    with col3:
        mtl = kpis.get("mean_time_loss")
        val = f"{mtl:.2f} s" if pd.notna(mtl) else "—"
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">Avg Time Loss</div>
            <div class="kpi-value-dark">{val}</div>
            <div class="kpi-subtext-dark">Delay vs free-flow speed</div>
        </div>
        """), unsafe_allow_html=True)

    with col4:
        tp = kpis.get("mean_throughput_vph")
        val = f"{int(tp)} veh/h" if pd.notna(tp) else "—"
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">Throughput</div>
            <div class="kpi-value-dark kpi-value-teal">{val}</div>
            <div class="kpi-subtext-dark">Hourly completed vehicles</div>
        </div>
        """), unsafe_allow_html=True)

    with col5:
        rate = status_info.get("completion_rate_pct", 0.0)
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark kpi-card-peach">
            <div class="kpi-label-dark">Completion</div>
            <div class="kpi-value-dark kpi-value-peach">{rate:.1f}%</div>
            <div class="kpi-subtext-dark">{status_info.get('successful_runs', 0)} / {status_info.get('total_expected_runs', 40)} runs</div>
        </div>
        """), unsafe_allow_html=True)

    st.write("")
    st.write("")

    # Comparative Exploration Section
    st.markdown(clean_html("""
    <div class="section-header">
        <div class="section-tag">Direct Evaluation</div>
        <h3 class="section-title" style="font-size:1.5rem;">Fixed-Time Baseline vs. Max-Pressure Adaptive</h3>
        <div class="section-subtitle">Evaluating relative performance under identical seed demand realizations.</div>
    </div>
    """), unsafe_allow_html=True)

    metric_options = {
        "mean_travel_time": "Average Travel Time (s) [Lower is Better]",
        "mean_waiting_time": "Average Waiting Time (s) [Lower is Better]",
        "mean_time_loss": "Average Time Loss (s) [Lower is Better]",
        "throughput_vph": "Intersection Throughput (veh/h) [Higher is Better]",
    }

    col_m, col_sc = st.columns([2, 1])
    with col_m:
        selected_metric_key = st.selectbox(
            "Select Evaluation Metric:",
            options=list(metric_options.keys()),
            format_func=lambda k: metric_options[k],
            index=0,
        )
    with col_sc:
        available_scenarios = service.get_available_scenarios()
        scenario_filter = st.selectbox(
            "Filter Traffic Demand Scenario:",
            options=["All Available Scenarios"] + available_scenarios,
            index=0,
        )

    sc_param = None if scenario_filter == "All Available Scenarios" else scenario_filter
    comp_df = service.get_controller_comparison(
        candidate_controller="max_pressure",
        baseline_controller="fixed_time",
        scenario=sc_param,
        by_seed=True,
    )

    if not comp_df.empty:
        col_chart, col_details = st.columns([3, 2])

        with col_chart:
            chart_records = []
            for _, r in comp_df.iterrows():
                chart_records.append({
                    "Scenario": r["scenario_id"],
                    "Controller": "Fixed-Time (Baseline)",
                    "Value": r[f"{selected_metric_key}_baseline"],
                })
                chart_records.append({
                    "Scenario": r["scenario_id"],
                    "Controller": "Max-Pressure (Candidate)",
                    "Value": r[f"{selected_metric_key}_candidate"],
                })
            chart_data = pd.DataFrame(chart_records)

            current_theme = st.session_state.get("theme", "dark")
            is_dark = (current_theme == "dark")
            axis_color = "#94A3B8" if is_dark else "#475569"
            title_color = "#F8FAFC" if is_dark else "#0F172A"
            grid_color = "#1E293B" if is_dark else "#E2E8F0"
            baseline_color = "#334155" if is_dark else "#64748B"
            candidate_color = "#14B8A6" if is_dark else "#0D9488"
            card_title_color = "#F8FAFC" if is_dark else "#0F172A"
            card_body_color = "#94A3B8" if is_dark else "#475569"

            chart = (
                alt.Chart(chart_data)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("Controller:N", title=None, axis=alt.Axis(labels=True, labelColor=axis_color)),
                    y=alt.Y(
                        "Value:Q",
                        title=metric_options[selected_metric_key].split(" [")[0],
                        axis=alt.Axis(labelColor=axis_color, titleColor=title_color, gridColor=grid_color),
                    ),
                    color=alt.Color(
                        "Controller:N",
                        scale=alt.Scale(
                            domain=["Fixed-Time (Baseline)", "Max-Pressure (Candidate)"],
                            range=[baseline_color, candidate_color],
                        ),
                        legend=alt.Legend(orient="top", title=None, labelColor=title_color),
                    ),
                    column=alt.Column("Scenario:N", title=None, header=alt.Header(labelColor=title_color)),
                    tooltip=["Scenario", "Controller", alt.Tooltip("Value:Q", format=".2f")],
                )
                .properties(height=320, background="transparent")
                .configure_view(stroke=None)
            )
            st.altair_chart(chart, use_container_width=True)

        with col_details:
            st.markdown("##### Matched-Seed Relative Improvements")
            for _, r in comp_df.iterrows():
                sc_id = r["scenario_id"]
                seed_val = r["seed"]
                pct_imp = r[f"{selected_metric_key}_pct_improvement"]
                b_val = r[f"{selected_metric_key}_baseline"]
                c_val = r[f"{selected_metric_key}_candidate"]

                is_better = pct_imp > 0 if pd.notna(pct_imp) else False
                pill_class = "pill-improvement-pos" if is_better else "pill-improvement-neg"
                sign = "+" if (pct_imp and pct_imp > 0) else ""

                sc_meta_item = scenario_meta.get(sc_id, {})
                sc_name = sc_meta_item.get("name", sc_id)
                sc_mult = sc_meta_item.get("multiplier", 0.0)
                sc_vph = sc_meta_item.get("vph", 0)

                st.markdown(clean_html(f"""
                <div class="its-card" style="margin-bottom:0.75rem; padding:1.25rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                        <span style="font-weight:700; color:{card_title_color}; font-size:1rem;">Scenario {sc_id} (Seed {seed_val})</span>
                        <span class="{pill_class}">{sign}{pct_imp:.2f}%</span>
                    </div>
                    <div style="font-size:0.8rem; color:#64748B; margin-bottom:0.5rem;">
                        {sc_name} ({sc_mult:.2f}× = {sc_vph} vph/approach)
                    </div>
                    <div style="font-size:0.88rem; color:{card_body_color};">
                        Fixed-Time Baseline: <strong style="color:{card_title_color};">{b_val:.2f}</strong> → Max-Pressure: <strong style="color:{candidate_color};">{c_val:.2f}</strong>
                    </div>
                </div>
                """), unsafe_allow_html=True)

            unexecuted = [s for s in ["S1", "S2", "S3", "S4"] if s not in available_scenarios]
            if unexecuted:
                unexec_str = ", ".join([f"{s} ({scenario_meta[s]['multiplier']:.2f}× = {scenario_meta[s]['vph']} vph)" for s in unexecuted if s in scenario_meta])
                st.caption(f"Scenarios awaiting benchmark execution: {unexec_str}.")
    else:
        st.info("No matched runs found for the chosen scenario selection.")

    st.write("")
    st.write("")

    # Raw Run Results Explorer
    with st.expander("🔍 View Raw Run-Level Experimental Records"):
        run_records_df = service.get_run_level_results()
        if not run_records_df.empty:
            display_cols = [
                "run_id", "controller_id", "scenario_id", "seed", "status",
                "mean_travel_time", "mean_waiting_time", "mean_time_loss",
                "throughput_vph", "completed_vehicles",
            ]
            cols = [c for c in display_cols if c in run_records_df.columns]
            st.dataframe(run_records_df[cols], use_container_width=True)
        else:
            st.caption("No run records available.")
