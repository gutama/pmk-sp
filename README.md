# FMI-SimEngine

**FMI Simulation Engine — Simulator Benchmarking Indikator PMK Sub-Protokol Sistem Pembayaran Wholesale**

Versi: 1.0-DRAFT | Bank Indonesia — Internal

---

## Overview

FMI-SimEngine is an agent-based simulator that reproduces, stress-tests, and benchmarks risk indicators in the BI Wholesale Payment System Sub-Protocol heatmap. It covers three vulnerability pillars (Velocity, Interconnection Structure, Infrastructure) and supports dual-perspective analysis (Version NB + Version PMKT-Risk).

**Key capabilities:**
- Replicate wholesale payment network dynamics (BI-RTGS, BI-FAST, RAJA)
- Generate synthetic time-series for all heatmap indicators calibrated to historical data
- Stress-testing framework with Normal-Waspada, Normal-Siaga, Ditenggarai Krisis scenarios
- Policy benchmarking through counterfactual analysis

---

## Architecture

```
fmi-simengine/
├── src/fmi_sim/          # Python simulation engine
│   ├── core/             # Network, agents, settlement, liquidity, simulation runner
│   ├── indicators/       # Heatmap indicator computation (NB + PMKT)
│   ├── contagion/        # DebtRank + cascade failure simulation
│   ├── scenarios/        # Stress-test scenario controller
│   ├── api/              # FastAPI REST + WebSocket server
│   └── visualization/    # Python/Dash prototype dashboard
│
├── src/frontend/         # React 18 + TypeScript production dashboard
│   └── src/
│       ├── components/   # Heatmap, charts, network, layout
│       ├── pages/        # 7 dashboard pages
│       ├── stores/       # Zustand state management
│       └── hooks/        # WebSocket + TanStack Query hooks
│
├── config/               # YAML configuration
│   ├── thresholds.yaml   # Risk zone thresholds
│   ├── network_params.yaml
│   ├── scenarios/        # Scenario definitions
│   └── calibration/      # Historical calibration data
│
└── tests/                # pytest test suite
```

---

## Installation

### Backend (Python)

```bash
pip install -e ".[dev]"
```

### Frontend (React)

```bash
cd src/frontend
npm install
npm run dev
```

---

## Quick Start

### Run simulation via Python API

```python
from fmi_sim import SimulationRunner

runner = SimulationRunner(n_banks=140, systems=["rtgs", "fast", "raja"], seed=42)
result = runner.run(n_days=30, scenario="baseline")

heatmap = result.compute_heatmap()
print(heatmap.nb_version.to_dataframe())
```

### Run stress scenario

```python
result = runner.run(
    n_days=30,
    scenario="contagion_cascade",
    scenario_params={"failing_bank": "BK_001"}
)
```

### Start the API server

```bash
python -m fmi_sim.api.main
# → http://localhost:8000/api/docs
```

### Run the React dashboard

```bash
cd src/frontend && npm run dev
# → http://localhost:3000
```

### Run the Dash prototype

```bash
python -m fmi_sim.visualization.dashboard
# → http://localhost:8050
```

---

## Scenarios

| Scenario | Description | Expected Zone |
|----------|-------------|---------------|
| `baseline` | Normal operating conditions | Normal |
| `liquidity_squeeze` | 30% giro reduction + 50% credit facility cut | Siaga |
| `counterparty_withdrawal` | Core bank reduces 60% of connections | Siaga |
| `infrastructure_disruption` | 120-min outage, 60% capacity reduction | Siaga |
| `contagion_cascade` | Core bank sudden stop, 3-round cascade | Krisis |
| `cyber_incident` | 15% of participants affected, 4h downtime | Siaga |

---

## Indicators

### Versi NB (Neraca Bank)

**Pilar Risiko (Headline):**
- Unsettled (bank) — W:1, S:5, K:10
- AD (Average Degree) — W:65.80, S:63.18, K:60.55
- System Availability — W:97%, S:98.5%, K:99.975%

**Pilar 1 — Velositas:**
- TOR — W:1.36, S:2.19, K:3.03
- TOR Adj — W:1.36, S:2.19, K:3.03
- QR (Queue Ratio) — W:4.21, S:3.98, K:2.74 (lower = riskier)
- Throughput Zona 3 — W:40%, S:50%, K:60%

**Pilar 2 — Struktur:**
- AWD — W:2.29, S:2.14, K:1.98
- AVG Koneksi — W:4000, S:3959, K:3918
- Volatility Interconnectedness — W:243, S:252, K:280

**Pilar 3 — Infrastruktur:**
- Insiden vs RTO/MTPD
- SU (%) — W:26.94, S:27.99, K:29.56

---

## Testing

```bash
pytest tests/ -v
```

---

## API Reference

```
POST /api/simulate          Start simulation
GET  /api/simulate/{id}     Get simulation status
GET  /api/results/{id}/heatmap      Get heatmap (NB or PMKT)
GET  /api/results/{id}/timeseries   Get time-series for indicator
GET  /api/results/{id}/network      Get network snapshot
GET  /api/results/{id}/contagion    Get contagion results
POST /api/compare           Compare multiple simulations
GET  /api/scenarios         List available scenarios
```

Full API docs: `http://localhost:8000/api/docs`

---

## Tech Stack

**Backend:** Python 3.11+, Mesa (ABM), NetworkX, NumPy/Pandas/SciPy, FastAPI, Socket.IO, DuckDB
**Frontend:** React 18 + TypeScript, Vite, Recharts, TanStack Table/Query, Zustand, D3, Tailwind CSS
**Prototype:** Python Dash + Plotly

---

## References

1. BIS CPMI — "Monitoring tools for intraday liquidity management" (2013/2023)
2. Soramäki et al. — "The topology of interbank payment flows" (2007)
3. Battiston et al. — "DebtRank: Too Central to Fail" (2012)
4. Bech & Garratt — "The mechanics of a graceful degradation of RTGS" (2012)
5. Galbiati & Soramäki — "An agent-based model of payment systems" (2011)
6. Bank Indonesia — Sub-Protokol Pengawasan Makroprudensial Sistem Pembayaran

---

*Internal — Bank Indonesia. Living specification — updated as development progresses.*
