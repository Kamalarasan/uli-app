# AI Loan Underwriting Platform (ULI)

A complete, production-grade, two-container AI-powered loan underwriting platform featuring an 8-stage automated risk analysis pipeline, Document AI, an embedded FAISS Vector RAG engine with NVIDIA NIM integration, a "What-If" scenario Digital Twin simulator, granular AI observability tracking, and a sleek **Metallic CRM** dark dashboard.

---

## 📑 Table of Contents
- [Architecture Overview](#-architecture-overview)
- [Tech Stack](#-tech-stack)
- [Key Features](#-key-features)
- [8-Stage AI Underwriting Pipeline](#-8-stage-ai-underwriting-pipeline)
- [Project Directory Structure](#-project-directory-structure)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Configuration & Environment Variables](#-configuration--environment-variables)
- [Frontend Navigation & Metallic CRM UI](#-frontend-navigation--metallic-crm-ui)
- [API Endpoints Reference](#-api-endpoints-reference)
- [Resilience & Fallback Mechanisms](#-resilience--fallback-mechanisms)
- [Troubleshooting](#-troubleshooting)

---

## 🏛 Architecture Overview

The system is streamlined into a minimal **2-container deployment** (`mariadb` + `app`) eliminating unnecessary queue and caching broker dependencies while retaining 100% of all analytical, algorithmic, and LLM features.

```
                  ┌────────────────────────────────────────────────────────┐
                  │                      Docker Host                       │
                  │                                                        │
┌──────────────┐  │  ┌────────────────────────┐   ┌─────────────────────┐  │
│              │  │  │        mariadb         │   │         app         │  │
│ Web Browser  │◄─┼──┼─                       │   │  (Python 3.11 Slim) │  │
│ (Metallic    │──┼──┼─►                      │   │                     │  │
│  CRM UI)     │  │  │  - MariaDB 11          │◄──┼─► FastAPI Gateway   │  │
└──────────────┘  │  │  - Relational Schema   │   │   Jinja2 / Bootstrap│  │
                  │  │  - Audit & Observability   │   Document AI Engine│  │
                  │  │  - Health Checked      │   │   FAISS Vector RAG  │  │
                  │  └────────────────────────┘   │   8-Stage Pipeline  │  │
                  │                               │   Digital Twin Sim  │  │
                  │                               └──────────┬──────────┘  │
                  └──────────────────────────────────────────┼─────────────┘
                                                             │ HTTPS (REST)
                                                             ▼
                                                ┌──────────────────────────┐
                                                │   NVIDIA NIM Cloud API   │
                                                │                          │
                                                │ - NV-Embed-v1            │
                                                │ - Mistral-4B Reranker    │
                                                │ - Nemotron Mini (Small)  │
                                                │ - Nemotron 70B (Large)   │
                                                └──────────────────────────┘
```

1. **`mariadb` Container**:
   - MariaDB 11 instance housing 6 relational tables: `applicants`, `loan_applications`, `documents`, `underwriting_reports`, `digital_twin_scenarios`, and `observability_logs`.
   - Native health-check integration ensures database readiness before web services bootstrap.
2. **`app` Container**:
   - FastAPI gateway handling REST API endpoints, Jinja2 template rendering, and background task dispatch.
   - Built-in connection retry loop (up to 30 attempts) for fail-safe DB synchronization.
   - Embedded FAISS vector store with automated institutional credit policy indexing.
   - NVIDIA Cloud API connectors for embeddings, reranking, and Nemotron models.

---

## 🛠 Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, PyMySQL, Pydantic v2 Settings.
- **AI & RAG**:
  - `openai` Python SDK targeting NVIDIA NIM endpoints (`https://integrate.api.nvidia.com/v1`).
  - Embedding: `nvidia/nv-embed-v1` (4096 dimensions).
  - Reranker: `nvidia/reranking-mistral-4b-instruct`.
  - Small Reasoning: `nvidia/nemotron-mini-4b-instruct`.
  - Large Reasoning & Synthesis: `nvidia/llama-3.1-nemotron-70b-instruct`.
  - Vector Store: `faiss-cpu` (L2 Normalized Inner Product for Cosine Similarity).
- **Document Processing**: `pdfplumber`, `PyPDF2`, `pytesseract` (OCR), `Pillow`.
- **Database**: MariaDB 11.
- **Frontend**: Jinja2 Templates, Bootstrap 5.3 (Dark Theme), Bootstrap Icons, Chart.js 4.x, Custom Metallic CRM CSS theme.

---

## ⚡ Key Features

- **End-to-End Underwriting Automation**: Runs an applicant through 8 continuous analytical stages from document intake to final sanction conditions.
- **Document AI**: Ingestion of PDF and image pay slips, bank statements, tax forms, and IDs with OCR extraction and rule-based key attribute parsing.
- **Regulatory & Credit Policy RAG**: Embedded 20+ policy knowledge base evaluating debt-to-income limits, credit score requirements, tenure bounds, and industry risk ratings.
- **Digital Twin Scenario Simulator**: Interactive "What-If" analysis allowing loan officers to test perturbations in salary, inflation, interest rate shifts, and macro-economic cycles.
- **Deep AI Observability**: Interceptor logging latency (ms), token consumption, validation status (`SUCCESS`, `FAILED`, `RECOVERED`), prompt templates, model versions, and outputs.
- **Metallic CRM Aesthetics**: Industrial dark layout (`#0a0c11`) with neon cyan accents (`#4fc3f7`), glowing cards, risk gauges, radar charts, and interactive sliders.

---

## 🔬 8-Stage AI Underwriting Pipeline

The core orchestration engine (`app/pipeline/orchestrator.py`) executes 8 sequential evaluation stages:

| Stage | Name | Engine / Tech | Purpose |
|:---:|---|---|---|
| **1** | **Data Validation & Cleaning** | Python / Pydantic | Validates data types, sanitizes phone/PAN/Aadhaar formats, scores baseline data quality. |
| **2** | **Identity Summary & KYC Profiling** | Mock Connectors | Reconciles PAN/Aadhaar identities, Form 26AS/GST filings, PEP checks, and flags discrepancies. |
| **3** | **Cash Flow Analysis** | **Nemotron Small** | Evaluates 12-month transaction streams, categorizes expenses, checks volatility and net disposable income. |
| **4** | **Financial Health Scoring** | Algorithmic Math | Computes DTI ratio, savings rate consistency, credit score mapping, and assigns risk tier (`EXCELLENT` to `CRITICAL`). |
| **5** | **Fraud & Anomaly Analysis** | **Nemotron Large** | Scans for synthetic identity traits, inflated incomes, unverified employer anomalies, velocity risks. |
| **6** | **Policy Matching & Rules** | **FAISS + NV Rerank** | Vector search against institutional credit guidelines to catch critical rule infractions. |
| **7** | **Affordability Check** | Stress-Test Engine | Determines Maximum Allowable EMI and evaluates capacity under -20% income / +15% expense shocks. |
| **8** | **AI Recommendation & Decision** | **Nemotron Large** | Generates final verdict (`APPROVED`, `REVIEW`, `REJECTED`), recommended APR %, tenure, conditions, and risk rationale. |

---

## 📂 Project Directory Structure

```
ULI-App/
├── docker-compose.yml              # 2-service configuration (mariadb + app)
├── Dockerfile                      # Python 3.11-slim + OCR and Poppler binaries
├── requirements.txt                # Production Python dependencies
├── .env.example                    # Environment variable template
├── .env                            # Active configuration (user managed)
├── README.md                       # Complete documentation
└── app/
    ├── __init__.py
    ├── main.py                     # FastAPI entrypoint, lifespan & HTML routes
    ├── config.py                   # Pydantic BaseSettings loading from .env
    ├── database.py                 # SQLAlchemy engine, session maker & DB retry loop
    ├── connectors/                 # Mock & Open API integration layer
    │   ├── kyc.py                  # PAN/Aadhaar validator & KYC profiling
    │   ├── account_aggregator.py   # 12-month transaction & statement generator
    │   └── gst_income.py           # GSTIN and Form 26AS tax filing verification
    ├── document_ai/                # Document extraction & classification
    │   ├── extractor.py            # pdfplumber, PyPDF2 & Tesseract OCR fallback
    │   └── classifier.py           # Document type classifier & attribute parser
    ├── rag/                        # Policy knowledge store & retrieval
    │   ├── vector_store.py         # FAISS store seeded with credit rules & NV-Embed
    │   └── retriever.py            # NV-Embed search + Mistral-4B Reranker pipeline
    ├── pipeline/                   # 8-Stage Underwriting Engine
    │   ├── orchestrator.py         # Pipeline sequencer, DB updater & state manager
    │   ├── stage1_validation.py    # Payload sanitization & validation
    │   ├── stage2_kyc_profiling.py # Identity verification & flag reconciliation
    │   ├── stage3_cashflow.py      # LLM cash flow & income volatility analysis
    │   ├── stage4_health_scoring.py# Arithmetic scoring & risk tier classification
    │   ├── stage5_fraud_detection.py# LLM anomaly & synthetic identity detection
    │   ├── stage6_policy_matching.py# RAG policy retrieval & compliance check
    │   ├── stage7_affordability.py # Stress testing & Max EMI calculation
    │   └── stage8_decision.py      # Final LLM sanction decision & term offering
    ├── digital_twin/               # Simulation Engine
    │   └── simulator.py            # What-if scenario execution & delta analytics
    ├── observability/              # Telemetry & LLM Audit Logging
    │   └── logger.py               # Call interceptor recording latency, tokens, & status
    ├── models/
    │   ├── orm.py                  # SQLAlchemy declarative models
    │   └── schemas.py              # Pydantic request & response schemas
    ├── routers/                    # REST API Endpoints
    │   ├── applications.py         # Loan application CRUD & pipeline triggers
    │   ├── documents.py            # Document upload & text extraction API
    │   ├── reports.py              # Underwriting report retrieval & radar metrics
    │   ├── simulator.py            # Digital twin scenario runner API
    │   └── observability.py        # Telemetry logs & metric trends API
    ├── templates/                  # Jinja2 HTML Templates
    │   ├── base.html               # Base layout with Metallic CRM Sidebar
    │   ├── dashboard.html          # KPI cards & live application tracker
    │   ├── new_application.html    # Multi-section loan intake & doc dropzone
    │   ├── report.html             # Visual risk gauge, radar chart & audit trail
    │   ├── simulator.html          # Interactive parameter sliders & scenario delta
    │   └── observability.html      # LLM latency trends, tokens, & audit table
    └── static/
        ├── css/
        │   └── metallic.css        # Metallic CRM Dark Theme styling
        └── js/
            └── charts.js           # Chart.js dark-theme rendering utilities
```

---

## 📋 Prerequisites

- **Docker Desktop** (Engine 24.0+ and Compose 2.20+).
- **NVIDIA API Key** *(Optional but recommended)*:
  - Create an account and generate a free API key at [build.nvidia.com](https://build.nvidia.com).
  - *Note: If no API key is provided, the application runs entirely in deterministic fallback mode.*

---

## 🚀 Quick Start

### 1. Configure the Environment
Ensure a `.env` file exists in the root directory (one is already prepared). If creating from scratch:
```bash
cp .env.example .env
```
Open `.env` and configure your credentials:
```env
NVIDIA_API_KEY=nvapi-your-real-key-here
```

### 2. Launch Containers
Run the stack with a single command from the project root:
```bash
docker compose up --build
```

### 3. Access the Platform
Once the startup healthcheck completes and the database initializes, open your browser:
- **Dashboard**: [http://localhost:8000](http://localhost:8000)
- **New Loan Application**: [http://localhost:8000/app/new](http://localhost:8000/app/new)
- **Digital Twin Simulator**: [http://localhost:8000/app/simulator](http://localhost:8000/app/simulator)
- **Observability & Audit Logs**: [http://localhost:8000/app/observability](http://localhost:8000/app/observability)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Seed Demo Data
To immediately populate the dashboard with 5 pre-configured loan profiles across different risk categories:
```bash
curl -X POST http://localhost:8000/api/seed
```
Or click the **Seed Demo Applications** trigger via the API docs.

---

## ⚙️ Configuration & Environment Variables

All settings are strongly typed via Pydantic `BaseSettings` (`app/config.py`):

| Variable | Default Value | Description |
|---|---|---|
| `NVIDIA_API_KEY` | `nvapi-placeholder...` | NVIDIA API Key for NIM endpoints |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | Base URL for NVIDIA AI endpoints |
| `NVIDIA_EMBED_MODEL` | `nvidia/nv-embed-v1` | Model ID for RAG vector embeddings |
| `NVIDIA_RERANKER_MODEL`| `nvidia/reranking-mistral-4b-instruct` | Model ID for ranking top RAG chunks |
| `NVIDIA_SMALL_MODEL` | `nvidia/nemotron-mini-4b-instruct` | Small model for cash flow analysis |
| `NVIDIA_LARGE_MODEL` | `nvidia/llama-3.1-nemotron-70b-instruct` | Large model for fraud and final decisions |
| `DB_HOST` | `mariadb` | Hostname of MariaDB container |
| `DB_PORT` | `3306` | MariaDB port |
| `DB_USER` | `uli_user` | MariaDB database user |
| `DB_PASS` | `uli_password` | MariaDB database password |
| `DB_NAME` | `uli_db` | Database name |
| `SECRET_KEY` | `uli-platform-secret...` | Session and security key |
| `DEBUG` | `false` | Enable verbose SQLAlchemy output |
| `UPLOAD_DIR` | `/app/uploads` | Document storage path in container |
| `MAX_RETRIES` | `30` | Max connection retries waiting for MariaDB |
| `RETRY_INTERVAL` | `2` | Interval in seconds between connection retries |

---

## 🎨 Frontend Navigation & Metallic CRM UI

The UI strictly adheres to the **Metallic CRM Dashboard** aesthetic inspired by modern fintech interfaces:

- **Palette**: Deep slate-black background (`#0a0c11`), charcoal cards (`#13161e`), subtle border glows (`rgba(79, 195, 247, 0.12)`), and high-contrast electric blue highlights (`#4fc3f7`).
- **Sidebar**: Sticky navigation bar with active route highlighting, categorized by Main and Analytics sections.
- **Interactive Visuals**:
  - **Risk Gauge**: Doughnut chart charting risk scores (0–100) with color-coded safety bands.
  - **Financial Health Radar**: 5-axis chart displaying Income Stability, Expense Management, Debt Management, Credit History, and Fraud Resistance.
  - **What-If Sliders**: Real-time slider controls to simulate salary changes, inflation, interest rate shifts, and tenure adjustments.
  - **Telemetry Trends**: 7-day latency and token usage charts for AI calls.

---

## 📡 API Endpoints Reference

### Applications (`/api/applications`)
- `POST /api/applications`: Create a new applicant and loan application record.
- `GET /api/applications`: Fetch paginated list of all applications.
- `GET /api/applications/{app_id}`: Fetch detailed application data and report summary.
- `POST /api/applications/{app_id}/process`: Asynchronously trigger the 8-stage pipeline.
- `POST /api/seed`: Seed 5 realistic Indian loan applicant test profiles.

### Document AI (`/api/documents`)
- `POST /api/documents/upload/{app_id}`: Upload loan documents (PDF/Image) for extraction and classification.
- `GET /api/documents/{app_id}`: List all uploaded documents for a specific application.
- `DELETE /api/documents/{doc_id}`: Delete an uploaded document.

### Underwriting Reports (`/api/reports`)
- `GET /api/reports/{app_id}`: Retrieve the full 8-stage underwriting report.
- `GET /api/reports/{app_id}/summary`: Retrieve radar and gauge chart metrics.

### Digital Twin Simulator (`/api/simulator`)
- `POST /api/simulator/run`: Run a "What-If" scenario against an existing application.
- `GET /api/simulator/scenarios/{app_id}`: Retrieve all previously run scenarios for an application.
- `GET /api/simulator/applications`: List applications eligible for scenario simulations.

### AI Observability (`/api/observability`)
- `GET /api/observability/logs`: Paginated audit log table with filter support for models and stages.
- `GET /api/observability/metrics`: Aggregate operational metrics (total calls, average latency, tokens, success rate).

### Health Check
- `GET /health`: Returns service status and application version.

---

## 🛡 Resilience & Fallback Mechanisms

1. **Database Startup Retry**:
   - `app/database.py` executes `wait_for_db()`, probing MariaDB for up to 60 seconds (30 attempts × 2s) to prevent container crash loops during cold starts.
2. **Deterministic LLM Fallbacks**:
   - Every stage utilizing external AI (`stage3`, `stage5`, `stage8`) implements structured regex-based JSON extraction (`parse_json_response`).
   - If an API key is absent, rate-limited, or fails, the pipeline transitions seamlessly to rule-based financial models without throwing 500 errors.
3. **FAISS Vector Embeddings Fallback**:
   - If the `nvidia/nv-embed-v1` endpoint is unavailable, `app/rag/vector_store.py` generates normalized pseudo-random vectors for demo environments, allowing the RAG pipeline to continue executing gracefully.

---

## 🔍 Troubleshooting

### Container fails to connect to MariaDB
- Check that both containers are on the same network (`uli_network`).
- Check MariaDB container logs:
  ```bash
  docker compose logs mariadb
  ```

### Running the App locally without Docker
1. Install system binaries (Tesseract OCR & Poppler) for your operating system.
2. Start a local MariaDB instance matching credentials in `.env` (or change `DB_HOST=localhost`).
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the development server:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

---

## 📄 License
This project is licensed under the MIT License. Built for production-grade loan risk assessment and financial technology demonstrations.
