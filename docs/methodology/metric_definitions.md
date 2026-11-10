# Metric Definitions and Evaluation Protocol

This document establishes the formal definitions, mathematical formulations, data sources, and methodological constraints for all performance metrics collected in **SIGNALSIM-INDIA**.

---

## 1. Evaluation Cohort Definition

To avoid transient startup bias and boundary truncation artifacts, metrics are calculated with respect to a strictly defined **Evaluation Cohort** $\mathcal{C}_{\text{eval}}$.

### 1.1 Temporal Boundaries
Let:
- $T_{\text{warm}}$ be the warm-up period duration in seconds (e.g., $600\text{ s}$).
- $T_{\text{eval}}$ be the active evaluation window duration in seconds (e.g., $3600\text{ s}$).
- $T_{\text{drain}}$ be the drain clearance period duration in seconds (e.g., $900\text{ s}$).
- $t_{\text{depart}}(v)$ be the actual simulation timestamp at which vehicle $v$ enters the SUMO network.

### 1.2 Cohort Membership Rule
A vehicle $v$ belongs to the evaluation cohort if and only if its departure timestamp falls within the active evaluation window:
$$\mathcal{C}_{\text{eval}} = \{v \in \mathcal{V} \mid T_{\text{warm}} \le t_{\text{depart}}(v) < T_{\text{warm}} + T_{\text{eval}}\}$$

Vehicles with $t_{\text{depart}}(v) < T_{\text{warm}}$ are **Warm-Up Vehicles** and are excluded from all evaluation statistics.

### 1.3 Completed vs. Unfinished Partitioning
The evaluation cohort is partitioned into two mutually exclusive subsets upon simulation termination at $T_{\text{total}} = T_{\text{warm}} + T_{\text{eval}} + T_{\text{drain}}$:
- **Completed Subset ($\mathcal{C}_{\text{comp}}$)**: Vehicles in $\mathcal{C}_{\text{eval}}$ that successfully traversed their route and reached their destination edge before or at $T_{\text{total}}$.
- **Unfinished Subset ($\mathcal{C}_{\text{unf}}$)**: Vehicles in $\mathcal{C}_{\text{eval}}$ that were inserted into the network but remain in-flight (queued, decelerating, or traversing) or waiting in insertion buffers at $T_{\text{total}}$.

$$\mathcal{C}_{\text{eval}} = \mathcal{C}_{\text{comp}} \cup \mathcal{C}_{\text{unf}}, \quad \mathcal{C}_{\text{comp}} \cap \mathcal{C}_{\text{unf}} = \emptyset, \quad |\mathcal{C}_{\text{eval}}| = N_{\text{eval}} = N_{\text{comp}} + N_{\text{unf}}$$

---

## 2. Vehicle-Level vs. Run-Level Metrics

- **Vehicle-Level Metrics**: Recorded individually for each vehicle (e.g., trip duration, waiting time, time loss, distance travelled). These serve as sample points.
- **Run-Level Metrics**: Aggregated across the cohort for a specific simulation execution (run specified by scenario $S_k$, controller $C_m$, and seed $s_i$), producing summary statistics (mean, median, standard deviation, totals).

---

## 3. Core Metric Specifications

### 3.1 Average Travel Time ($\bar{T}$)
- **Meaning**: The arithmetic mean duration required for vehicles in the completed evaluation cohort to traverse the intersection from insertion to exit.
- **Formula**:
  $$\bar{T} = \frac{1}{|\mathcal{C}_{\text{comp}}|} \sum_{v \in \mathcal{C}_{\text{comp}}} \tau_{\text{duration}}(v)$$
  where $\tau_{\text{duration}}(v) = t_{\text{arrival}}(v) - t_{\text{depart}}(v)$.
- **Unit**: Seconds ($\text{s}$).
- **Data Source**: SUMO `tripinfo-output` XML attribute `duration`.
- **TripInfo Sufficiency**: **YES** (for completed cohort).
- **Limitations & Survivorship Bias**: Only measurable for completed vehicles ($\mathcal{C}_{\text{comp}}$). In severely oversaturated conditions where gridlock occurs, a poorly performing controller may clear only a tiny fraction of vehicles that experienced brief delays, falsely showing low travel times if unfinished vehicles are ignored. **Must always be interpreted alongside Completion Rate and Unfinished Vehicles.**

---

### 3.2 Average Waiting Time ($\bar{W}$)
- **Meaning**: The average cumulative time spent by completed evaluation-cohort vehicles at near-zero velocity (speed $< 0.1\text{ m/s}$ in SUMO default).
- **Formula**:
  $$\bar{W} = \frac{1}{|\mathcal{C}_{\text{comp}}|} \sum_{v \in \mathcal{C}_{\text{comp}}} \tau_{\text{waiting}}(v)$$
- **Unit**: Seconds ($\text{s}$).
- **Data Source**: SUMO `tripinfo-output` XML attribute `waitingTime`.
- **TripInfo Sufficiency**: **YES** (for completed cohort).
- **Limitations**: Reflects complete physical standstills; does not capture slow crawl speeds typical of Indian mixed-traffic queue dissipation.

---

### 3.3 Average Time Loss ($\bar{L}$)
- **Meaning**: The average delay incurred relative to ideal free-flow conditions, accounting for deceleration, stops, acceleration cycles, and yielding to conflicting movements.
- **Formula**:
  $$\bar{L} = \frac{1}{|\mathcal{C}_{\text{comp}}|} \sum_{v \in \mathcal{C}_{\text{comp}}} \tau_{\text{loss}}(v)$$
  where $\tau_{\text{loss}}(v) = \tau_{\text{duration}}(v) - \frac{d_{\text{route}}(v)}{v_{\text{max}}(v)}$.
- **Unit**: Seconds ($\text{s}$).
- **Data Source**: SUMO `tripinfo-output` XML attribute `timeLoss`.
- **TripInfo Sufficiency**: **YES** (for completed cohort).
- **Limitations**: In heterogeneous traffic, $v_{\text{max}}$ varies significantly by vehicle class (e.g. auto-rickshaws vs cars); comparison between controllers remains fair because fleet composition is identical.

---

### 3.4 Throughput ($Q$)
- **Meaning**: The rate of completed trip deliveries achieved by the intersection per unit time during the active evaluation window.
- **Formula**:
  $$Q = \frac{|\mathcal{C}_{\text{comp}}|}{T_{\text{eval}} / 3600} = \frac{N_{\text{comp}}}{T_{\text{eval\_hours}}}$$
- **Unit**: Vehicles per hour ($\text{veh/h}$).
- **Data Source**: Count of completed records in `tripinfo-output` filtered by $v \in \mathcal{C}_{\text{eval}}$.
- **TripInfo Sufficiency**: **YES** (when combined with cohort filtering).
- **Limitations**: Must strictly normalize by $T_{\text{eval}}$ (the active demand injection duration), NOT $T_{\text{total}}$, to represent the steady-state hourly delivery capacity accurately.

---

### 3.5 Completion Rate ($C_R$)
- **Meaning**: The percentage of vehicles injected during the evaluation window that successfully cleared the network within the allotted simulation horizon (including drain time).
- **Formula**:
  $$C_R = \left( \frac{|\mathcal{C}_{\text{comp}}|}{|\mathcal{C}_{\text{eval}}|} \right) \times 100\% = \left( \frac{N_{\text{comp}}}{N_{\text{eval}}} \right) \times 100\%$$
- **Unit**: Percentage ($\%$).
- **Data Source**: Ratio of completed trips to total generated departures in $\mathcal{C}_{\text{eval}}$ (derived from route file departure count and TripInfo arrivals).
- **TripInfo Sufficiency**: **PARTIAL**. Standard TripInfo XML records *only* completed vehicles by default unless SUMO is launched with `--tripinfo-output.write-unfinished`. To reliably determine $|\mathcal{C}_{\text{eval}}|$, the parser must cross-reference route demand files or count unfinished vehicles from simulation end states.
- **Limitations**: Under unsaturated flow (S1, S2), $C_R \approx 100\%$. In oversaturated flow (S4), $C_R$ drops below $100\%$, serving as a direct index of gridlock severity.

---

### 3.6 Average Queue Length ($\bar{Q}_L$)
- **Meaning**: The time-averaged length of queued vehicles across all intersection approaches during the evaluation period.
- **Formula**:
  $$\bar{Q}_L = \frac{1}{K \cdot N_{\text{lanes}}} \sum_{k=1}^K \sum_{l=1}^{N_{\text{lanes}}} q(l, t_k)$$
  where $q(l, t_k)$ is the instantaneous queue length on lane $l$ at sample step $t_k$.
- **Unit**: Metres ($\text{m}$) or number of vehicles ($\text{veh}$).
- **Data Source**: SUMO Lane-Area Detectors (E2 detector XML output) or TraCI lane subscriptions (`traci.lane.getLastStepHaltingNumber`).
- **TripInfo Sufficiency**: **NO**. SUMO `tripinfo-output` does **NOT** contain time-series lane queue lengths. TripInfo outputs only aggregate per-trip summaries upon vehicle arrival. Attempting to deduce spatial queue dynamics from TripInfo is invalid.
- **Limitations**: Requires lane detectors or periodic TraCI sampling throughout the simulation run.

---

### 3.7 Maximum Queue Length ($Q_{L,max}$)
- **Meaning**: The peak instantaneous queue length observed across all approach lanes during the evaluation period.
- **Formula**:
  $$Q_{L,max} = \max_{k \in \{1,\dots,K\}, l \in \{1,\dots,N_{\text{lanes}}\}} q(l, t_k)$$
- **Unit**: Metres ($\text{m}$) or number of vehicles ($\text{veh}$).
- **Data Source**: SUMO Lane-Area Detectors (E2 detector XML output) or TraCI polling.
- **TripInfo Sufficiency**: **NO**. Cannot be obtained from TripInfo XML.
- **Limitations**: Susceptible to localized instantaneous spikes; must be examined alongside $\bar{Q}_L$.

---

### 3.8 Average Trip Speed ($\bar{V}$)
- **Meaning**: The harmonic or arithmetic mean trip speed of completed evaluation vehicles across their entire journey.
- **Formula**:
  $$\bar{V} = \frac{1}{|\mathcal{C}_{\text{comp}}|} \sum_{v \in \mathcal{C}_{\text{comp}}} \frac{d_{\text{route}}(v)}{\tau_{\text{duration}}(v)}$$
- **Unit**: Metres per second ($\text{m/s}$) or kilometres per hour ($\text{km/h}$).
- **Data Source**: Computed from SUMO `tripinfo-output` attributes `routeLength` and `duration`:
  $$v_{\text{speed}}(v) = \frac{\text{routeLength}}{\text{duration}}$$
- **TripInfo Sufficiency**: **YES** (for completed cohort).
- **Limitations**: Influenced by route length; since routes are controlled and identical across controllers, the metric provides a clean, interpretable operational index.

---

### 3.9 Unfinished Vehicles ($N_{\text{unf}}$)
- **Meaning**: The total count of evaluation-cohort vehicles that were introduced into the simulation during the evaluation window but failed to reach their exit edge by simulation close ($T_{\text{total}}$).
- **Formula**:
  $$N_{\text{unf}} = |\mathcal{C}_{\text{eval}}| - |\mathcal{C}_{\text{comp}}| = N_{\text{eval}} - N_{\text{comp}}$$
- **Unit**: Integer count of vehicles.
- **Data Source**: Derived by subtracting the count of completed evaluation vehicles in `tripinfo-output` from the known route file cohort departures, OR extracted directly from TripInfo if `--tripinfo-output.write-unfinished` is configured by P1.
- **TripInfo Sufficiency**: **PARTIAL** (depends on P1's SUMO command-line flags).
- **Limitations**: Absolute count depends on scenario volume ($N_{\text{eval}}$); must be evaluated alongside Completion Rate $C_R$.

---

## 4. Summary Table of Metric Requirements

| # | Metric Name | Symbol | Unit | Level | Data Source | TripInfo Sufficient? |
| :- | :--- | :---: | :---: | :---: | :--- | :---: |
| 1 | Average Travel Time | $\bar{T}$ | $\text{s}$ | Run | `tripinfo-output.xml` (`duration`) | **YES** |
| 2 | Average Waiting Time | $\bar{W}$ | $\text{s}$ | Run | `tripinfo-output.xml` (`waitingTime`) | **YES** |
| 3 | Average Time Loss | $\bar{L}$ | $\text{s}$ | Run | `tripinfo-output.xml` (`timeLoss`) | **YES** |
| 4 | Throughput | $Q$ | $\text{veh/h}$ | Run | `tripinfo-output.xml` (count filtered by $\mathcal{C}_{\text{eval}}$) | **YES** |
| 5 | Completion Rate | $C_R$ | $\%$ | Run | Route departures + `tripinfo-output.xml` | **PARTIAL** |
| 6 | Average Queue Length | $\bar{Q}_L$ | $\text{m}$ / $\text{veh}$ | Run | TraCI polling / E2 Detector XML | **NO** |
| 7 | Maximum Queue Length | $Q_{L,max}$ | $\text{m}$ / $\text{veh}$ | Run | TraCI polling / E2 Detector XML | **NO** |
| 8 | Average Trip Speed | $\bar{V}$ | $\text{km/h}$ | Run | `tripinfo-output.xml` (`routeLength`, `duration`) | **YES** |
| 9 | Unfinished Vehicles | $N_{\text{unf}}$ | Count | Run | Route departures minus completed TripInfo | **PARTIAL** |

> [!CAUTION]
> **Survivorship Bias Guard**: In oversaturated scenario S4, controllers with high gridlock may report deceptively low average travel times because only the few unimpeded vehicles complete their trips. Any analysis comparing controller travel times without reporting Completion Rate and Unfinished Vehicles is methodologically flawed.

