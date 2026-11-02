# P1 / P2 Interface Specification

> [!WARNING]
> **PROPOSED — NOT CONFIRMED BY P1**
> This interface specification defines the proposed architectural contract between Partner 1 (P1 - Simulation, Controllers, and Safety) and Partner 2 (P2 - Experiment Execution, Route Generation, Metrics, and Analysis).
> It serves as a working agreement draft and requires formal review and confirmation by P1 before implementation in Milestone 02.

---

## 1. Architectural Boundary and Division of Responsibilities

### Partner 1 (P1) Owns:
1. **SUMO Network Construction**: Physical layout, arm geometry, lane connections, junction logic (`simulation/network/`).
2. **Vehicle Definitions**: Heterogeneous Indian vehicle classes, dimensions, acceleration, minGap, car-following models (`simulation/vehicles/`).
3. **Signal Phase Definitions**: Permissible signal phases, stage sequences, and phase state strings.
4. **Controllers**:
   - `fixed_time`: Fixed-time baseline controller (`controllers/fixed_time.py`).
   - `max_pressure`: Dynamic max-pressure controller (`controllers/max_pressure.py`).
   - `ppo`: Trained Proximal Policy Optimization RL model and inference wrapper (`training/`, `controllers/ppo_agent.py`).
5. **Gymnasium / TraCI Environment**: Low-level simulation stepping, state observation encoding, and action dispatch (`environment/`).
6. **Traffic Signal Safety Manager**: Enforcement of minimum green ($G_{\text{min}}$), maximum green ($G_{\text{max}}$), yellow clearance ($Y$), and all-red ($AR$) safety constraints (`safety/`).

### Partner 2 (P2) Owns:
1. **Experiment Configurations**: Global experiment and scenario specifications (`configs/`).
2. **Controlled-Variable Documentation & Register**: Experimental rigor documentation (`docs/`).
3. **Deterministic Route Generation**: Upfront generation of reproducible route files per scenario and seed (`simulation/routes/`).
4. **Parameter Register & Research Citations**: Sourced and assumed parameters (`docs/`).
5. **Metric Definitions & Collection**: Analytical formulations and data extraction (`docs/`, `src/metrics/`).
6. **TripInfo Parser**: Robust extraction of completed and unfinished vehicle data (`src/metrics/tripinfo_parser.py`).
7. **Experiment Runner**: Execution harness orchestrating matched-seed controller runs across scenarios.
8. **Results Analysis & Reporting**: Tabular metrics, statistical validation, and reporting (`results/`).
9. **Streamlit Dashboard**: Interactive visualization of comparative metrics (`dashboard/`).

---

## 2. Proposed Execution Contract: `run_one`

To enable clean, decoupled orchestration by P2's experiment runner without coupling P2 to internal controller implementation details, we propose a single unified entry point:

```python
def run_one(
    scenario: str,
    controller: str,
    seed: int,
    cfg_path: str,
    gui: bool = False
) -> dict:
    """
    Executes a single simulation run for a specific scenario, controller, and random seed.

    STATUS: PROPOSED — NOT CONFIRMED BY P1.

    Parameters
    ----------
    scenario : str
        Scenario identifier (e.g., 'S1', 'S2', 'S3', 'S4').
    controller : str
        Controller identifier (e.g., 'fixed_time', 'max_pressure', 'ppo').
    seed : int
        Random seed for the simulation run (e.g., 42, 101, 202, 303, 404).
    cfg_path : str
        Path to the experiment configuration YAML file (e.g., 'configs/experiment.yaml').
    gui : bool, default=False
        Whether to launch the SUMO graphical interface ('sumo-gui') or headless ('sumo').

    Returns
    -------
    dict
        Dictionary containing execution metadata and paths to generated artifacts:
        {
            "scenario": str,
            "controller": str,
            "seed": int,
            "status": "SUCCESS" | "FAILED",
            "tripinfo_path": str,          # Path to generated tripinfo XML output
            "queue_log_path": str | None,  # Path to generated E2/queue log (if enabled)
            "sim_duration_seconds": float, # Total elapsed wall-clock or simulation time
            "error_message": str | None    # Exception details if status == "FAILED"
        }
    """
```

---

## 3. Agreed Experimental Parameters

The following operational parameters have been agreed between P1 and P2 for the benchmarking evaluation:

| Parameter | Agreed value |
|---|---|
| Baseline demand | 600 vehicles/hour/approach |
| Turning split | Left 20%, straight 60%, right 20% |
| SUMO simulation step | 0.1 seconds |
| Controller decision interval | 10 seconds |
| Warm-up | 600 seconds |
| Evaluation | 3600 seconds |
| Drain | 900 seconds |
| Seeds | 42, 101, 202, 303, 404 |
| Traffic direction | LHT |
| Traffic-light ID | J2 |
| Signal program | 0 |
| Incoming edges | -E1, -E2, -E3, -E4 |
| Outgoing edges | E1, E2, E3, E4 |

### Turning Movement Proportions
The turning proportions below are agreed experimental assumptions. They are applied uniformly across all four approaches.

- **Left turn**: 20%
- **Straight**: 60%
- **Right turn**: 20%

### Vehicle Fleet Composition Status
> [!CAUTION]
> **AWAITING CLARIFICATION — INCOMPLETE FLEET PROPORTIONS (95% TOTAL)**
> The currently proposed vehicle mix proportions are:
> - `car`: 30%
> - `bike`: 35%
> - `auto`: 20%
> - `bus`: 5%
> - `truck`: 5%
>
> **Total**: $30\% + 35\% + 20\% + 5\% + 5\% = \mathbf{95\%}$.
>
> The project defines **six** active vehicle types in `vTypes.add.xml` (`car`, `bike`, `auto`, `bus`, `truck`, `bicycle`). The proposed specification provides shares for only 5 classes and leaves 5% unallocated (e.g., whether `bicycle` receives the remaining 5%, or if other proportions should be adjusted).
>
> **Resolution Protocol**: In accordance with experimental rigor, P2 will **not invent** the missing 5% or silently normalise the mix. Generation of the 20 final experimental route datasets is suspended until P1 clarifies the complete 100% allocation across all vehicle types.

### Network Capacity & Demand Validation Note
> [!WARNING]
> **CAPACITY VALIDATION PENDING**
> With baseline demand agreed at $600\text{ veh/h/approach}$ ($2400\text{ veh/h}$ total baseline demand across the 4 approaches in S3, scaling to $3000\text{ veh/h}$ in S4), network storage capacity must be empirically validated against P1's network. The four approach arms are physically short ($20.5\text{ m}$ to $28.9\text{ m}$), holding only 2–3 passenger cars or 1 bus per lane. Simulation runs must verify whether queue spillback into insertion boundaries produces unmanageable `departDelay`.

---

## 4. Outstanding Information & Assets Required from P1

Before P2 can finalize the experimental route datasets and implement the experiment runner, P1 must confirm and provide the following 14 items:

| # | Item Required | Description | Blocking For |
| :- | :--- | :--- | :--- |
| 1 | **SUMO Network Path** | Absolute/relative path to the compiled `.net.xml` intersection file. | Route generator & runner |
| 2 | **Vehicle Type IDs & Definitions** | Exact `vtype` IDs (e.g., `moto`, `auto`, `car`, `bus`, `truck`) and their `.vtype.xml` file. | Route generator |
| 3 | **Valid Route Edges** | Exact edge IDs for the 4 inflow arms and 4 outflow arms (North, South, East, West). | Route generator |
| 4 | **Traffic-Light ID** | SUMO junction traffic light logic ID (e.g., `J1` or `center`). | Runner & metrics |
| 5 | **Signal Phase Definitions** | Phase state strings (e.g., `"GrGr..."`), phase index mappings, and stage sequences. | Safety & runner |
| 6 | **Minimum/Maximum Green Durations** | Numeric values ($G_{\text{min}}, G_{\text{max}}$ in seconds) enforced by the safety manager. | Methodology & safety |
| 7 | **Yellow & All-Red Clearance Rules** | Numeric values ($Y, AR$ in seconds) enforced during phase switching. | Methodology & safety |
| 8 | **Controller Identifiers** | Exact string identifiers accepted by P1's runner (e.g., `["fixed_time", "max_pressure", "ppo"]`). | Experiment config |
| 9 | **Controller Invocation Method** | Clarification on whether controllers are callable via Python function, CLI, or TraCI step callback. | Experiment runner |
| 10 | **PPO Policy Loading Method** | Saved checkpoint path format, model architecture loading function (e.g. PyTorch / Stable-Baselines3), and device placement (CPU/CUDA). | Experiment runner |
| 11 | **SUMO Start/Stop Lifecycle** | Standard method for initializing `traci.start(...)` and cleanly terminating with `traci.close()`. | Experiment runner |
| 12 | **TripInfo Output Configuration** | Confirmation of SUMO launch flags: whether `--tripinfo-output.write-unfinished` is supported and enabled. | TripInfo parser |
| 13 | **Queue Measurement Output** | Decision on whether queue metrics are collected via E2 loop detectors (`--lanearea-output`) or periodic TraCI subscription polling. | Metric pipeline |
| 14 | **Temporal Period Compatibility** | Confirmation that P1's TraCI loop supports $T_{\text{warm}}$ (warm-up), $T_{\text{eval}}$ (evaluation), and $T_{\text{drain}}$ (clearance) stepping. | Experiment runner |

---

## 5. Next Steps for Interface Ratification
1. P1 reviews this document and confirms or amends the signature of `run_one(...)`.
2. P1 populates the 14 placeholder items with finalized network paths and IDs.
3. P2 transitions the placeholders from `PENDING_P1` to `SOURCED` in `docs/parameter_register.csv`.
4. P2 proceeds with Milestone 02 (Deterministic Route Generation & Experiment Runner) based on the ratified contract.

