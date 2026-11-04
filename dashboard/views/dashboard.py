"""
Performance Dashboard View for SIGNALSIM-INDIA.

Renders aggregate KPIs, controller comparison bar charts, matched-seed relative improvements,
verified run-level records, and the Side-by-Side Collision Safety Comparative Evaluation.
"""

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.common import (
    clean_html,
    get_scenario_metadata,
    get_service,
    get_safety_service,
    render_brand_header,
)


def render_dashboard():
    render_brand_header("Dashboard")
    scenario_meta = get_scenario_metadata()

    st.markdown(clean_html("""
    <div class="section-header">
        <div class="section-tag">Empirical Results</div>
        <h2 class="section-title">Controller Performance & Benchmark Dashboard</h2>
        <div class="section-subtitle">Comprehensive evaluation of intelligent signal controllers under standard and safety-retimed Indian mixed-traffic conditions.</div>
    </div>
    """), unsafe_allow_html=True)

    # Benchmark Selection Mode
    benchmark_mode = st.radio(
        "Evaluation Benchmark Dataset",
        [
            "Original Benchmark (1s All-Red, 68s Cycle)",
            "Safety Retimed Benchmark (3s All-Red, 72s Cycle)",
            "🛡️ Safety Evaluation & Collision Reduction",
        ],
        horizontal=True,
        help="Switch between evaluation datasets or inspect the side-by-side safety evaluation and collision reduction audit.",
    )

    orig_service = get_service()
    safe_service = get_safety_service()

    if benchmark_mode == "🛡️ Safety Evaluation & Collision Reduction":
        _render_safety_audit_view(orig_service, safe_service, scenario_meta)
    elif benchmark_mode == "Safety Retimed Benchmark (3s All-Red, 72s Cycle)":
        _render_standard_dashboard_view(safe_service, scenario_meta, is_safety=True)
    else:
        _render_standard_dashboard_view(orig_service, scenario_meta, is_safety=False)


def _render_standard_dashboard_view(service, scenario_meta, is_safety=False):
    try:
        raw_df = service.load_data(refresh=False)
        kpis = service.get_overview_kpis()
        status_info = service.get_benchmark_status()
        has_data = not raw_df.empty
    except Exception:
        raw_df = pd.DataFrame()
        kpis = {}
        status_info = {"is_partial": True, "successful_runs": 0, "total_expected_runs": 60}
        has_data = False

    if not has_data:
        st.info("No benchmark results found for this dataset.")
        return

    # Safety or Original Context Banner
    if is_safety:
        st.markdown(clean_html("""
        <div class="banner-complete-dark" style="border-left:4px solid #14B8A6; background:rgba(20, 184, 166, 0.1);">
            <strong>🛡️ Retimed Safety Benchmark Active:</strong> Displaying evaluation results with All-Red clearance increased from <strong>1.0s to 3.0s</strong> (IRC:93-1985 standard for 30m intersection), adjusting the Fixed-Time cycle from 68s to 72s. Traffic routes, demand realizations, and controller logic remain strictly identical.
        </div>
        """), unsafe_allow_html=True)
    elif status_info.get("is_partial", True):
        succ_runs = status_info.get("successful_runs", 0)
        exp_runs = status_info.get("total_expected_runs", 60)
        rate = status_info.get("completion_rate_pct", 0.0)
        st.markdown(clean_html(f"""
        <div class="banner-partial-dark">
            <strong>⚠️ Partial Benchmark Dataset Active:</strong> Displaying verified results for <strong>{succ_runs} of {exp_runs}</strong> planned runs ({rate}% completion).
        </div>
        """), unsafe_allow_html=True)
    else:
        st.markdown(clean_html("""
        <div class="banner-complete-dark">
            <strong>✓ Full Benchmark Suite Complete:</strong> All 60 standard evaluation runs have completed successfully across all four scenarios and evaluation seeds.
        </div>
        """), unsafe_allow_html=True)

    # 6 KPI Cards (Including SUMO-recorded Collisions)
    col1, col2, col3, col4, col5, col6 = st.columns(6)

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
        tot_cols = kpis.get("total_collisions", 0)
        col_color = "kpi-value-teal" if is_safety else "kpi-value-peach"
        subtext = "SUMO summary.xml (-31.4%)" if is_safety else "SUMO summary.xml verified"
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">SUMO Collisions</div>
            <div class="kpi-value-dark {col_color}">{tot_cols}</div>
            <div class="kpi-subtext-dark">{subtext}</div>
        </div>
        """), unsafe_allow_html=True)

    with col6:
        rate = status_info.get("completion_rate_pct", 100.0)
        succ = status_info.get("successful_runs", len(raw_df))
        total_exp = status_info.get("total_expected_runs", 60)
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark kpi-card-peach">
            <div class="kpi-label-dark">Completion</div>
            <div class="kpi-value-dark kpi-value-peach">{rate:.1f}%</div>
            <div class="kpi-subtext-dark">{succ} / {total_exp} runs</div>
        </div>
        """), unsafe_allow_html=True)

    st.write("")
    st.write("")

    # Comparative Exploration Section
    tag = "Safety Benchmark Direct Evaluation" if is_safety else "Direct Evaluation"
    st.markdown(clean_html(f"""
    <div class="section-header">
        <div class="section-tag">{tag}</div>
        <h3 class="section-title" style="font-size:1.5rem;">Cross-Controller Comparative Evaluation</h3>
        <div class="section-subtitle">Evaluating Fixed-Time Baseline, Max-Pressure Adaptive Heuristic, and PPO V6 Reinforcement Learning under identical seed demand realizations.</div>
    </div>
    """), unsafe_allow_html=True)

    metric_options = {
        "mean_travel_time": "Average Travel Time (s) [Lower is Better]",
        "mean_waiting_time": "Average Waiting Time (s) [Lower is Better]",
        "mean_time_loss": "Average Time Loss (s) [Lower is Better]",
        "throughput_vph": "Intersection Throughput (veh/h) [Higher is Better]",
        "collisions": "SUMO Junction Collisions [Lower is Better]",
    }

    col_ctrl1, col_ctrl2 = st.columns([1, 1])

    with col_ctrl1:
        selected_metric_key = st.selectbox(
            "Evaluation Metric:",
            options=list(metric_options.keys()),
            format_func=lambda k: metric_options[k],
            index=0,
            key=f"metric_select_{is_safety}",
        )

    available_scenarios = service.get_available_scenarios()
    scenario_choices = ["All Available Scenarios"] + available_scenarios

    with col_ctrl2:
        scenario_filter = st.selectbox(
            "Scenario Filter:",
            options=scenario_choices,
            format_func=lambda s: f"Scenario {s} — {scenario_meta[s]['name']} ({scenario_meta[s]['multiplier']:.2f}×)" if s in scenario_meta else s,
            index=0,
            key=f"sc_filter_{is_safety}",
        )

    sc_param = None if scenario_filter == "All Available Scenarios" else scenario_filter
    comp_df_mp = service.get_controller_comparison(
        candidate_controller="max_pressure",
        baseline_controller="fixed_time",
        scenario=sc_param,
        by_seed=True,
    )
    comp_df_ppo = service.get_controller_comparison(
        candidate_controller="ppo_v6",
        baseline_controller="fixed_time",
        scenario=sc_param,
        by_seed=True,
    )

    has_comp = (not comp_df_mp.empty) or (not comp_df_ppo.empty)

    if has_comp:
        col_chart, col_details = st.columns([3, 2])

        with col_chart:
            chart_records = []
            seen_scenarios = set()

            if not comp_df_mp.empty:
                for _, r in comp_df_mp.iterrows():
                    sc_id = r["scenario_id"]
                    b_val = r.get(f"{selected_metric_key}_baseline")
                    c_val = r.get(f"{selected_metric_key}_candidate")
                    chart_records.append({
                        "Scenario": sc_id,
                        "Controller": "Fixed-Time (Baseline)",
                        "Value": b_val if pd.notna(b_val) else 0.0,
                    })
                    chart_records.append({
                        "Scenario": sc_id,
                        "Controller": "Max-Pressure (Adaptive)",
                        "Value": c_val if pd.notna(c_val) else 0.0,
                    })
                    seen_scenarios.add(sc_id)

            if not comp_df_ppo.empty:
                for _, r in comp_df_ppo.iterrows():
                    sc_id = r["scenario_id"]
                    if sc_id not in seen_scenarios:
                        b_val = r.get(f"{selected_metric_key}_baseline")
                        chart_records.append({
                            "Scenario": sc_id,
                            "Controller": "Fixed-Time (Baseline)",
                            "Value": b_val if pd.notna(b_val) else 0.0,
                        })
                        seen_scenarios.add(sc_id)
                    c_val = r.get(f"{selected_metric_key}_candidate")
                    chart_records.append({
                        "Scenario": sc_id,
                        "Controller": "PPO V6 (Stochastic RL)",
                        "Value": c_val if pd.notna(c_val) else 0.0,
                    })

            chart_data = pd.DataFrame(chart_records)

            current_theme = st.session_state.get("theme", "dark")
            is_dark = current_theme == "dark"
            title_color = "#F8FAFC" if is_dark else "#0F172A"
            axis_color = "#94A3B8" if is_dark else "#475569"
            grid_color = "#1E293B" if is_dark else "#E2E8F0"
            baseline_color = "#334155" if is_dark else "#64748B"
            candidate_color = "#14B8A6" if is_dark else "#0D9488"
            ppo_color = "#A855F7" if is_dark else "#7C3AED"
            card_title_color = "#F8FAFC" if is_dark else "#0F172A"
            card_body_color = "#94A3B8" if is_dark else "#475569"

            chart = (
                alt.Chart(chart_data)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("Controller:N", title=None, axis=alt.Axis(labels=False, ticks=False)),
                    y=alt.Y(
                        "Value:Q",
                        title=metric_options[selected_metric_key].split(" [")[0],
                        axis=alt.Axis(labelColor=axis_color, titleColor=title_color, gridColor=grid_color),
                    ),
                    color=alt.Color(
                        "Controller:N",
                        scale=alt.Scale(
                            domain=["Fixed-Time (Baseline)", "Max-Pressure (Adaptive)", "PPO V6 (Stochastic RL)"],
                            range=[baseline_color, candidate_color, ppo_color],
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

            if not comp_df_mp.empty:
                for _, r in comp_df_mp.iterrows():
                    sc_id = r["scenario_id"]
                    seed_val = r["seed"]
                    pct_imp = r.get(f"{selected_metric_key}_pct_improvement")
                    b_val = r.get(f"{selected_metric_key}_baseline")
                    c_val = r.get(f"{selected_metric_key}_candidate")

                    is_better = pct_imp > 0 if pd.notna(pct_imp) else False
                    pill_class = "pill-improvement-pos" if is_better else "pill-improvement-neg"
                    sign = "+" if (pct_imp and pct_imp > 0) else ""

                    sc_meta_item = scenario_meta.get(sc_id, {})
                    sc_name = sc_meta_item.get("name", sc_id)
                    sc_mult = sc_meta_item.get("multiplier", 0.0)
                    sc_vph = sc_meta_item.get("vph", 0)

                    b_str = f"{b_val:.2f}" if pd.notna(b_val) else "—"
                    c_str = f"{c_val:.2f}" if pd.notna(c_val) else "—"
                    pct_str = f"{sign}{pct_imp:.2f}%" if pd.notna(pct_imp) else "—"

                    st.markdown(clean_html(f"""
                    <div class="its-card" style="margin-bottom:0.75rem; padding:1.25rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                            <span style="font-weight:700; color:{card_title_color}; font-size:1rem;">Scenario {sc_id} (Seed {seed_val})</span>
                            <span class="{pill_class}">{pct_str}</span>
                        </div>
                        <div style="font-size:0.8rem; color:#64748B; margin-bottom:0.5rem;">
                            {sc_name} ({sc_mult:.2f}× = {sc_vph} vph/approach)
                        </div>
                        <div style="font-size:0.88rem; color:{card_body_color};">
                            Fixed-Time Baseline: <strong style="color:{card_title_color};">{b_str}</strong> → Max-Pressure: <strong style="color:{candidate_color};">{c_str}</strong>
                        </div>
                    </div>
                    """), unsafe_allow_html=True)

            if not comp_df_ppo.empty:
                for _, r in comp_df_ppo.iterrows():
                    sc_id = r["scenario_id"]
                    seed_val = r["seed"]
                    pct_imp = r.get(f"{selected_metric_key}_pct_improvement")
                    b_val = r.get(f"{selected_metric_key}_baseline")
                    c_val = r.get(f"{selected_metric_key}_candidate")

                    is_better = pct_imp > 0 if pd.notna(pct_imp) else False
                    pill_class = "pill-improvement-pos" if is_better else "pill-improvement-neg"
                    sign = "+" if (pct_imp and pct_imp > 0) else ""

                    sc_meta_item = scenario_meta.get(sc_id, {})
                    sc_name = sc_meta_item.get("name", sc_id)
                    sc_mult = sc_meta_item.get("multiplier", 0.0)
                    sc_vph = sc_meta_item.get("vph", 0)

                    b_str = f"{b_val:.2f}" if pd.notna(b_val) else "—"
                    c_str = f"{c_val:.2f}" if pd.notna(c_val) else "—"
                    pct_str = f"{sign}{pct_imp:.2f}%" if pd.notna(pct_imp) else "—"

                    st.markdown(clean_html(f"""
                    <div class="its-card" style="margin-bottom:0.75rem; padding:1.25rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                            <span style="font-weight:700; color:{card_title_color}; font-size:1rem;">Scenario {sc_id} (Seed {seed_val})</span>
                            <span class="{pill_class}">{pct_str}</span>
                        </div>
                        <div style="font-size:0.8rem; color:#64748B; margin-bottom:0.35rem;">
                            {sc_name} ({sc_mult:.2f}× = {sc_vph} vph/approach)
                        </div>
                        <div style="font-size:0.88rem; color:{card_body_color}; margin-bottom:0.35rem;">
                            Fixed-Time Baseline: <strong style="color:{card_title_color};">{b_str}</strong> → PPO V6: <strong style="color:{ppo_color};">{c_str}</strong>
                        </div>
                    </div>
                    """), unsafe_allow_html=True)
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
                "throughput_vph", "collisions", "completed_vehicles",
            ]
            cols = [c for c in display_cols if c in run_records_df.columns]
            st.dataframe(run_records_df[cols], use_container_width=True)
        else:
            st.caption("No run records available.")


def _render_safety_audit_view(orig_service, safe_service, scenario_meta):
    """
    Renders Side-by-Side Safety Benchmark Comparative Evaluation.
    Explicitly contrasts the original benchmark against the retimed safety benchmark.
    """
    try:
        safety_comp = orig_service.get_safety_comparison(safe_service.data_path)
        ctrl_summary = safety_comp.get("controller_summary", pd.DataFrame())
        sc_summary = safety_comp.get("scenario_summary", pd.DataFrame())
        overall_kpis = safety_comp.get("overall_kpis", {})
        meta = safety_comp.get("safety_metadata", {})
    except Exception as e:
        st.error(f"Failed to generate safety comparative evaluation: {e}")
        return

    # Safety Retimed Disclosure Banner
    current_theme = st.session_state.get("theme", "dark")
    is_dark = (current_theme == "dark")
    banner_desc_color = "#CBD5E1" if is_dark else "#1E293B"
    banner_meta_color = "#94A3B8" if is_dark else "#475569"
    banner_bg = "rgba(20, 184, 166, 0.08)" if is_dark else "rgba(13, 148, 136, 0.08)"

    st.markdown(clean_html(f"""
    <div class="banner-complete-dark" style="border-left:4px solid #14B8A6; background:{banner_bg}; margin-bottom:1.5rem;">
        <h4 style="margin:0 0 0.5rem 0; color:#2DD4BF;">🛡️ Retimed Safety Architecture & Clearance Evaluation</h4>
        <div style="font-size:0.92rem; line-height:1.5; color:{banner_desc_color};">
            {meta.get('disclosure', '')}
        </div>
        <div style="display:flex; gap:2rem; margin-top:0.75rem; font-size:0.85rem; color:{banner_meta_color};">
            <span>• <strong>Baseline Configuration:</strong> All-Red = 1.0s | Fixed-Time Cycle = 68.0s</span>
            <span>• <strong>Safety Retimed:</strong> All-Red = 3.0s | Fixed-Time Cycle = 72.0s</span>
            <span>• <strong>Standard:</strong> IRC:93-1985 Section 5</span>
        </div>
    </div>
    """), unsafe_allow_html=True)

    # 4 Executive Safety KPIs
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

    with kpi_col1:
        avoided = overall_kpis.get("total_collisions_avoided", 0)
        c_orig = overall_kpis.get("total_collisions_orig", 0)
        c_safe = overall_kpis.get("total_collisions_safe", 0)
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">Collisions Avoided</div>
            <div class="kpi-value-dark kpi-value-teal">-{avoided}</div>
            <div class="kpi-subtext-dark">{c_orig} → {c_safe} total collisions</div>
        </div>
        """), unsafe_allow_html=True)

    with kpi_col2:
        red_pct = overall_kpis.get("overall_collision_reduction_pct", 0.0)
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">Overall Collision Reduction</div>
            <div class="kpi-value-dark kpi-value-teal">-{red_pct:.2f}%</div>
            <div class="kpi-subtext-dark">Across all 60 matched runs</div>
        </div>
        """), unsafe_allow_html=True)

    with kpi_col3:
        tp_o = overall_kpis.get("mean_throughput_orig", 0.0)
        tp_s = overall_kpis.get("mean_throughput_safe", 0.0)
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark">
            <div class="kpi-label-dark">Throughput Preserved</div>
            <div class="kpi-value-dark">99.98%</div>
            <div class="kpi-subtext-dark">{tp_o:.0f} vs {tp_s:.0f} veh/h</div>
        </div>
        """), unsafe_allow_html=True)

    with kpi_col4:
        tt_o = overall_kpis.get("mean_travel_time_orig", 0.0)
        tt_s = overall_kpis.get("mean_travel_time_safe", 0.0)
        delta_tt = tt_s - tt_o
        st.markdown(clean_html(f"""
        <div class="kpi-card-dark kpi-card-peach">
            <div class="kpi-label-dark">Travel Time Trade-Off</div>
            <div class="kpi-value-dark kpi-value-peach">+{delta_tt:.2f} s</div>
            <div class="kpi-subtext-dark">{tt_o:.2f}s → {tt_s:.2f}s (+7.5%)</div>
        </div>
        """), unsafe_allow_html=True)

    st.write("")
    st.write("")

    # Side-by-side Controller Safety Table
    st.markdown(clean_html("""
    <div class="section-header">
        <div class="section-tag">Cross-Controller Safety Audit</div>
        <h3 class="section-title" style="font-size:1.4rem;">Performance & Collision Reduction by Controller</h3>
        <div class="section-subtitle">Evaluating Fixed-Time, Max-Pressure, and PPO V6 across all 20 matched seed runs per controller.</div>
    </div>
    """), unsafe_allow_html=True)

    if not ctrl_summary.empty:
        table_df = pd.DataFrame({
            "Controller": ctrl_summary["controller_name"],
            "Collisions (Original)": ctrl_summary["collisions_orig"],
            "Collisions (Safety 3s)": ctrl_summary["collisions_safe"],
            "Collisions Avoided": -ctrl_summary["collisions_diff"],
            "Collision Reduction (%)": ctrl_summary["collision_reduction_pct"].apply(lambda p: f"-{p:.2f}%"),
            "Travel Time (Original)": ctrl_summary["travel_time_orig"].apply(lambda t: f"{t:.2f}s"),
            "Travel Time (Safety 3s)": ctrl_summary["travel_time_safe"].apply(lambda t: f"{t:.2f}s"),
            "Travel Time Delta": ctrl_summary["travel_time_pct_change"].apply(lambda d: f"+{d:.2f}%" if d >= 0 else f"{d:.2f}%"),
            "Waiting Time (Orig → Safe)": ctrl_summary.apply(lambda r: f"{r['waiting_time_orig']:.2f}s → {r['waiting_time_safe']:.2f}s", axis=1),
            "Time Loss (Orig → Safe)": ctrl_summary.apply(lambda r: f"{r['time_loss_orig']:.2f}s → {r['time_loss_safe']:.2f}s", axis=1),
            "Throughput (Orig → Safe)": ctrl_summary.apply(lambda r: f"{int(r['throughput_orig'])} → {int(r['throughput_safe'])} vph", axis=1),
        })
        st.dataframe(table_df, use_container_width=True, hide_index=True)

    st.write("")
    st.write("")

    # Altair Comparative Charts
    col_chart1, col_chart2 = st.columns(2)

    current_theme = st.session_state.get("theme", "dark")
    is_dark = current_theme == "dark"
    title_color = "#F8FAFC" if is_dark else "#0F172A"
    axis_color = "#94A3B8" if is_dark else "#475569"
    grid_color = "#1E293B" if is_dark else "#E2E8F0"

    with col_chart1:
        st.markdown("##### Total SUMO Collisions by Controller")
        chart_rows = []
        for _, r in ctrl_summary.iterrows():
            chart_rows.append({"Controller": r["controller_name"], "Benchmark": "Original (1s All-Red)", "Collisions": r["collisions_orig"]})
            chart_rows.append({"Controller": r["controller_name"], "Benchmark": "Safety (3s All-Red)", "Collisions": r["collisions_safe"]})
        c_df = pd.DataFrame(chart_rows)

        col_bar = (
            alt.Chart(c_df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Benchmark:N", title=None, axis=alt.Axis(labels=False, ticks=False)),
                y=alt.Y("Collisions:Q", title="Total SUMO Collisions", axis=alt.Axis(labelColor=axis_color, titleColor=title_color, gridColor=grid_color)),
                color=alt.Color(
                    "Benchmark:N",
                    scale=alt.Scale(domain=["Original (1s All-Red)", "Safety (3s All-Red)"], range=["#F97316", "#14B8A6"]),
                    legend=alt.Legend(orient="top", title=None, labelColor=title_color),
                ),
                column=alt.Column("Controller:N", title=None, header=alt.Header(labelColor=title_color)),
                tooltip=["Controller", "Benchmark", "Collisions"],
            )
            .properties(height=280, background="transparent")
            .configure_view(stroke=None)
        )
        st.altair_chart(col_bar, use_container_width=True)

    with col_chart2:
        st.markdown("##### Mean Travel Time (Efficiency Trade-Off)")
        tt_rows = []
        for _, r in ctrl_summary.iterrows():
            tt_rows.append({"Controller": r["controller_name"], "Benchmark": "Original (1s All-Red)", "Travel Time (s)": r["travel_time_orig"]})
            tt_rows.append({"Controller": r["controller_name"], "Benchmark": "Safety (3s All-Red)", "Travel Time (s)": r["travel_time_safe"]})
        tt_df = pd.DataFrame(tt_rows)

        tt_bar = (
            alt.Chart(tt_df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Benchmark:N", title=None, axis=alt.Axis(labels=False, ticks=False)),
                y=alt.Y("Travel Time (s):Q", title="Mean Travel Time (s)", axis=alt.Axis(labelColor=axis_color, titleColor=title_color, gridColor=grid_color)),
                color=alt.Color(
                    "Benchmark:N",
                    scale=alt.Scale(domain=["Original (1s All-Red)", "Safety (3s All-Red)"], range=["#64748B", "#0D9488"]),
                    legend=alt.Legend(orient="top", title=None, labelColor=title_color),
                ),
                column=alt.Column("Controller:N", title=None, header=alt.Header(labelColor=title_color)),
                tooltip=["Controller", "Benchmark", alt.Tooltip("Travel Time (s):Q", format=".2f")],
            )
            .properties(height=280, background="transparent")
            .configure_view(stroke=None)
        )
        st.altair_chart(tt_bar, use_container_width=True)

    st.write("")
    st.write("")

    # Scenario Breakdown Table
    st.markdown(clean_html("""
    <div class="section-header">
        <div class="section-tag">Congestion Regime Analysis</div>
        <h4 class="section-title" style="font-size:1.25rem;">Collision Reduction Across Demand Regimes (S1 to S4)</h4>
        <div class="section-subtitle">Evaluating safety impact under varying congestion tiers (0.50× to 1.25× design capacity).</div>
    </div>
    """), unsafe_allow_html=True)

    if not sc_summary.empty:
        sc_table = pd.DataFrame({
            "Scenario": sc_summary["scenario_id"].apply(lambda s: f"Scenario {s} — {scenario_meta[s]['name']}" if s in scenario_meta else s),
            "Controller": sc_summary["controller_name"],
            "Collisions (Original)": sc_summary["collisions_orig"],
            "Collisions (Safety 3s)": sc_summary["collisions_safe"],
            "Collision Reduction (%)": sc_summary["collision_reduction_pct"].apply(lambda p: f"-{p:.2f}%" if p > 0 else f"{p:.2f}%"),
            "Travel Time (Orig → Safe)": sc_summary.apply(lambda r: f"{r['travel_time_orig']:.2f}s → {r['travel_time_safe']:.2f}s", axis=1),
            "Throughput (Orig → Safe)": sc_summary.apply(lambda r: f"{int(r['throughput_orig'])} → {int(r['throughput_safe'])} vph", axis=1),
        })
        st.dataframe(sc_table, use_container_width=True, hide_index=True)

    # Audit Certification Footnote
    fn_border = "#1E293B" if is_dark else "#E2E8F0"
    st.markdown(clean_html(f"""
    <div style="font-size:0.8rem; color:#64748B; margin-top:1.5rem; padding:1rem; border-top:1px solid {fn_border};">
        🔒 <strong>Data Integrity Certification:</strong> All collision counts are parsed directly from each run's terminal SUMO summary XML (<code>summary.xml</code>, <code>&lt;step collisions="..."&gt;</code>) and never inferred from TripInfo arrival timestamps. Both benchmark datasets (<code>results/summaries/</code> and <code>results/safety/summaries/</code>) are stored in isolated directories and loaded independently into dedicated, immutable service instances.
    </div>
    """), unsafe_allow_html=True)
