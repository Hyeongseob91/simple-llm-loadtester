# Simple LLM Tester

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

<p align="center">
  <strong>English</strong> •
  <a href="README.ko.md">한국어</a>
</p>

---

> Load testing tool for LLM inference servers with real-time dashboard and AI-powered analysis

Comprehensive benchmarking system for vLLM, SGLang, Ollama, and other OpenAI-compatible API servers. Monitor performance in real-time and visualize results through an interactive web dashboard.

---

## User Flow

### 1. Dashboard
View benchmark history and recent runs at a glance.

<img src="assets/user_flow_dashboard.png" alt="Dashboard" width="800"/>

### 2. New Benchmark
Configure and start a new benchmark with custom parameters.

<img src="assets/user_flow_new_benchmark.png" alt="New Benchmark" width="800"/>

### 3. Benchmark Result
Monitor real-time progress and view detailed results after completion.

<img src="assets/user_flow_benchmark_result.png" alt="Benchmark Result" width="800"/>

### 4. AI Analysis Report
Generate AI-powered analysis reports with insights and recommendations.

<img src="assets/user_flow_ai_analysis_report.png" alt="AI Analysis Report" width="800"/>

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Accurate Metrics** | tiktoken-based token counting, LLM-specific metrics (TTFT, TPOT, ITL) |
| **Quality-Based Evaluation** | Goodput - measures the percentage of requests meeting SLO thresholds |
| **Real-time Monitoring** | WebSocket progress updates, GPU metrics (memory, utilization, temperature, power) |
| **Visualization** | Interactive charts, export to CSV/Excel |
| **Extensibility** | Adapter pattern supporting vLLM, SGLang, Ollama, Triton, and more |
| **AI Analysis** | LLM-powered benchmark analysis reports with Thinking model support |

---

## Quick Start

### Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/Hyeongseob91/Simple-llm-tester.git
cd Simple-llm-tester

# Start all services
docker compose up -d

# Access (replace <your-host> with your server IP or domain)
# - Web UI: http://<your-host>:5050
# - API Docs: http://<your-host>:8085/docs
```

### CLI Installation

```bash
# From project root
pip install -e .

# Basic load test
# Replace <your-llm-server> with the LLM server URL you want to test
# Replace <your-model> with the model name served by your LLM server
llm-loadtest run \
  --server http://<your-llm-server> \
  --model <your-model> \
  --concurrency 1,10,50 \
  --num-prompts 100

# Goodput measurement (SLO-based)
llm-loadtest run \
  --server http://<your-llm-server> \
  --model <your-model> \
  --concurrency 50 \
  --goodput ttft:500,tpot:50
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Dashboard                          │
│                    (Next.js + React)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │ REST API / WebSocket
┌─────────────────────────▼───────────────────────────────────┐
│                       API Server                            │
│                       (FastAPI)                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Shared Core                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Load         │  │ Metrics      │  │ GPU          │      │
│  │ Generator    │  │ Calculator   │  │ Monitor      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Adapters     │  │ Database     │  │ Validator    │      │
│  │ (vLLM, etc.) │  │ (SQLite)     │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Project Structure (MSA)

```
llm-loadtest/
├── services/
│   ├── api/              # FastAPI backend server
│   │   └── routers/      # API endpoints (benchmarks, websocket, recommend)
│   ├── cli/              # Typer CLI tool
│   │   └── commands/     # CLI commands (run, recommend, info, gpu)
│   └── web/              # Next.js dashboard
│       ├── app/          # Pages (dashboard, benchmark, history)
│       └── components/   # UI components
├── shared/
│   ├── core/             # Core logic
│   │   ├── load_generator.py   # Load generation engine
│   │   ├── metrics.py          # Metrics calculation
│   │   ├── gpu_monitor.py      # GPU monitoring
│   │   ├── validator.py        # Metrics validation
│   │   └── models.py           # Data models
│   ├── adapters/         # Server adapters
│   │   ├── base.py             # Adapter interface + factory
│   │   └── openai_compat.py    # OpenAI API compatible adapter
│   └── database/         # SQLite storage
├── docs/guides/          # Documentation
└── docker-compose.yml
```

---

## Metrics

### LLM-Specific Metrics

| Metric | Description | Unit | Calculation |
|--------|-------------|------|-------------|
| **TTFT** | Time To First Token | ms | First token arrival time - request start time |
| **TPOT** | Time Per Output Token | ms | (E2E - TTFT) / output token count |
| **E2E** | End-to-End Latency | ms | Response complete time - request start time |
| **ITL** | Inter-Token Latency | ms | Time interval between consecutive tokens |
| **Throughput** | Processing rate | tok/s | Total output tokens / test duration |
| **Request Rate** | Request processing rate | req/s | Completed requests / test duration |
| **Error Rate** | Error percentage | % | Failed requests / total requests × 100 |

### Goodput (Quality-Based Throughput)

Percentage of requests meeting all SLO (Service Level Objective) thresholds.

```bash
# Goodput measurement example
llm-loadtest run \
  --server http://<your-llm-server> \
  --model <your-model> \
  --goodput ttft:500,tpot:50,e2e:5000
```

**Calculation:**
```
Goodput = (Requests where TTFT ≤ 500ms AND TPOT ≤ 50ms AND E2E ≤ 5000ms) / Total requests × 100
```

### Statistics

Each metric provides the following statistics:
- **min / max**: Minimum/Maximum values
- **mean**: Average
- **median (p50)**: Median value
- **p95 / p99**: Percentiles
- **std**: Standard deviation

---

## Supported Servers

| Server | Adapter | Status |
|--------|---------|--------|
| vLLM | openai | ✅ Supported |
| SGLang | openai | ✅ Supported |
| Ollama | openai | ✅ Supported |
| Triton | triton | 🚧 In Development |

Any server providing OpenAI-compatible API (`/v1/chat/completions`) is generally supported.

---

## CLI Commands

```bash
# Load test
# --server: URL of your LLM server (e.g., vLLM, SGLang, Ollama)
# --model: Model name being served (check your server for the exact name)
llm-loadtest run \
  --server http://<your-llm-server> \
  --model <your-model> \
  --concurrency 1,10,50,100 \
  --num-prompts 100 \
  --input-len 256 \
  --output-len 128 \
  --goodput ttft:500,tpot:50 \
  --stream

# Infrastructure recommendation
llm-loadtest recommend \
  --server http://<your-llm-server> \
  --model <your-model> \
  --peak-concurrency 500 \
  --ttft-target 500 \
  --goodput-target 95

# System info
llm-loadtest info

# GPU status
llm-loadtest gpu
```

---

## API Endpoints

**Base URL:** `http://<your-host>:8085/api/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/benchmark/run` | Start benchmark |
| `GET` | `/benchmark/{run_id}` | Get details |
| `GET` | `/benchmark` | List benchmarks |
| `DELETE` | `/benchmark/{run_id}` | Delete benchmark |
| `POST` | `/benchmark/{run_id}/cancel` | Cancel benchmark |
| `GET` | `/benchmark/{run_id}/export/csv` | Export to CSV |
| `GET` | `/benchmark/{run_id}/export/excel` | Export to Excel |
| `GET` | `/benchmark/result/{run_id}/analysis` | AI analysis report |
| `WS` | `/benchmark/{run_id}/progress` | Real-time progress |

---

## Web UI

| Page | Path | Features |
|------|------|----------|
| **Dashboard** | `/` | Benchmark list, recent runs |
| **New Benchmark** | `/benchmark/new` | Configure and start benchmarks |
| **Detail Page** | `/benchmark/[id]` | Real-time monitoring, results, AI analysis |
| **History** | `/history` | Past benchmark records |
| **Recommend** | `/recommend` | GPU infrastructure recommendation (Coming Soon) |
| **Compare** | `/compare` | Benchmark comparison (Coming Soon) |

---

## Tech Stack

**Backend:** Python 3.11+, FastAPI, asyncio/aiohttp, WebSocket, SQLite, tiktoken, pynvml, Typer

**Frontend:** Next.js 14, TypeScript, TanStack Query, Recharts, Tailwind CSS

**Infrastructure:** Docker Compose

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

Bug reports, feature requests, and PRs are welcome!

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request
