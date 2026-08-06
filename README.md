# AutoInvestigatorOps 🚀

> **Autonomous SRE Agent** — LangGraph • RAG • Local LLM • PagerDuty • Human-in-the-Loop

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-green.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async-red.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 The Problem This Solves

Every engineering team has that **one senior SRE** — the person who has lived through every production incident, built the runbooks, and knows exactly what to do when things break.

Then they leave.

The new engineer joins on Monday. A critical production incident fires on Tuesday. They have access to the systems but not the **institutional knowledge**. Every minute of confusion costs the business.

**AutoInvestigatorOps solves this.**

It's an autonomous SRE agent that:
- Intercepts production incidents the moment they fire
- Searches historical runbooks to find what matches
- Uses AI to perform root cause analysis
- Generates a remediation script
- **Waits for human approval before executing anything**

The experienced engineer's knowledge — codified, searchable, always available.

---

## 🏗️ Architecture

```
PagerDuty / Datadog Webhook
           ↓
   FastAPI Webhook Server
   (async, non-blocking — returns 202
    immediately to prevent retry storms)
           ↓
   LangGraph State Machine
   ┌─────────────────────────────┐
   │  Node 1: Triage Alert       │
   │  Node 2: Gather Telemetry   │
   │  Node 3: Search Runbooks    │
   │  Node 4: Synthesize RCA     │
   │  Node 5: Execute Remediation│
   └─────────────────────────────┘
           ↓
   ChromaDB Vector Store
   (semantic search over runbooks)
           ↓
   Local LLM (LFM-2B via LM Studio)
   (root cause analysis — no data
    leaves your network)
           ↓
   Human Approval Gate ← critical
           ↓
   PowerShell Remediation Execution
           ↓
   Prometheus + Grafana
   (full observability)
```

---

## ✨ Key Features

### 🔒 Privacy-First Local LLM
All incident data stays within your network. No cloud API calls for sensitive operational data. LFM-2B runs entirely on local hardware via LM Studio.

### 🧠 RAG-Powered Runbook Retrieval
ChromaDB stores engineering runbooks as vector embeddings. When an incident fires, semantic search finds the most relevant runbook — even if the incident description is worded differently from the runbook title.

### 👤 Human-in-the-Loop Governance
AI generates the remediation script. **A human approves it before it runs.** This protects against:
- Prompt injection attacks via malicious log entries
- AI errors affecting production dependencies
- Unintended consequences of automated execution

### ⚡ Async Non-Blocking Processing
PagerDuty expects a webhook response within 5 seconds or it retries — creating duplicate investigations. FastAPI BackgroundTasks returns `202 Accepted` immediately while the investigation runs asynchronously.

### 📊 Production Observability
Prometheus metrics track:
- `sre_incidents_received_total` — incidents by urgency and service
- `sre_investigation_duration_seconds` — full investigation time
- `sre_llm_inference_duration_seconds` — LLM response latency
- `sre_remediation_outcomes_total` — success/failed/skipped
- `sre_active_investigations` — concurrent investigations

All visualised in Grafana dashboards.

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Layer | FastAPI + Pydantic | Async webhook ingestion |
| Orchestration | LangGraph | 5-node state machine |
| Vector Search | ChromaDB | Runbook RAG retrieval |
| Embeddings | HuggingFace MiniLM-L6-v2 | Semantic search |
| Local LLM | LFM-2B via LM Studio | Root cause analysis |
| Remediation | PowerShell subprocess | Safe script execution |
| Metrics | Prometheus + Grafana | Production observability |
| Schema | TypedDict | Typed state management |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- [LM Studio](https://lmstudio.ai) — for local LLM inference
- Prometheus + Grafana (optional, for observability)

### 1. Clone and Setup

```bash
git clone https://github.com/Tejas163/AutoInvestigatorOps.git
cd AutoInvestigatorOps

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\Activate.ps1

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
SRE_AGENT_LLM_URL=http://localhost:1234/v1
SRE_AGENT_LLM_KEY=your-lm-studio-key
```

### 3. Start LM Studio

- Open LM Studio
- Load the LFM-2B model
- Start the local server on port 1234

### 4. Run the Agent

```bash
python investigator.py
```

Server starts at `http://localhost:8000`

### 5. Test with Sample Payload

```bash
curl -X POST http://localhost:8000/webhooks/pagerduty \
  -H "Content-Type: application/json" \
  -d @payload.json
```

---

## 📊 Observability Setup

### Option A — With Docker (Prometheus + Grafana)

```bash
docker-compose -f docker-compose-monitoring.yml up
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)
- Metrics endpoint: http://localhost:8000/metrics

### Option B — Without Docker (Windows)

**Prometheus:**
1. Download from [prometheus.io/download](https://prometheus.io/download)
2. Extract and run: `prometheus.exe --config.file=prometheus.yml`

**Grafana:**
1. Download installer from [grafana.com/grafana/download](https://grafana.com/grafana/download)
2. Run installer — starts as Windows service automatically
3. Open http://localhost:3000

---

## 🔄 How It Works — Step by Step

**1. Incident Fires**
PagerDuty detects a production anomaly and sends a webhook to `/webhooks/pagerduty`

**2. Async Dispatch**
FastAPI validates the payload and immediately returns `202 Accepted`. The investigation runs in a background task — PagerDuty doesn't time out.

**3. Triage**
LangGraph enters the first node — extracting incident metadata: service name, urgency, incident ID, timestamp.

**4. Telemetry Gathering**
The agent scans `production_logs.txt` for log entries matching the affected service. It detects metric anomalies — like connection pool exhaustion — from log patterns.

**5. Runbook Retrieval**
ChromaDB performs semantic similarity search over stored runbooks. The most relevant runbook is retrieved based on incident description — not just keyword matching.

**6. Root Cause Analysis**
The local LLM receives three inputs:
- Relevant production logs
- Detected metric anomalies  
- Retrieved runbook content

It synthesises a structured JSON response:
```json
{
  "root_cause": "Redis connection pool exhausted",
  "confidence_score": 0.95,
  "recommended_action": "Flush connection pools",
  "target_script": "Write-Output 'Flushing...'"
}
```

**7. Human Approval Gate**
The remediation script is NOT executed automatically. The `remediation_approved` flag must be set to `True` by a human operator before execution proceeds.

**8. Remediation Execution**
Once approved, the generated PowerShell script is written to disk and executed via subprocess. Output is captured and logged.

**9. Metrics Updated**
Prometheus counters and histograms are updated with investigation duration, LLM latency, and remediation outcome.

---

## 🔐 Security Design Decisions

### Why Local LLM?
Production incident data contains sensitive infrastructure details — server names, database connection strings, error messages with internal paths. Sending this to a cloud API creates data exfiltration risk. Local inference keeps all data within the enterprise boundary.

### Why Human-in-the-Loop?
- **Prompt injection protection**: A malicious log entry could attempt to trick the LLM into generating a destructive script. Human review catches this.
- **Dependency awareness**: The LLM doesn't know which files and folders other applications depend on. A human does.
- **Audit compliance**: Every remediation action requires human sign-off — creating an audit trail for compliance.

### Why Async Processing?
PagerDuty retries webhooks that don't respond within 5 seconds. A synchronous investigation (15-30 seconds) would trigger duplicate alerts. Background tasks solve this without message queues.

---

## 📁 Project Structure

```
AutoInvestigatorOps/
├── investigator.py          # FastAPI webhook server + Prometheus metrics
├── pipeline.py              # LangGraph 5-node state machine
├── schemas.py               # TypedDict state schema
├── requirements.txt         # Python dependencies
├── prometheus.yml           # Prometheus scrape config
├── docker-compose-monitoring.yml  # Prometheus + Grafana stack
├── Dockerfile               # Container definition
├── .env.example             # Environment variable template
├── payload.json             # Sample PagerDuty webhook payload
└── runbooks/
    └── redis_runbook.md     # Sample Redis incident runbook
```

---

## 🧩 LangGraph State Schema

```python
class InvestigationState(TypedDict):
    incident_id: str
    service_name: str
    relevant_logs: List[str]
    metric_anomalies: List[Dict]
    historical_matches: List[Dict]
    root_cause_summary: Dict
    remediation_approved: bool    # Human sets this
    remediation_executed: bool
    remediation_logs: str
    investigation_steps_taken: List[str]
    next_step: str
```

---

## 🗺️ Roadmap

- [ ] Multi-agent architecture — parallel log analysis and runbook retrieval agents
- [ ] Langfuse LLM observability integration
- [ ] RAGAS evaluation for RAG pipeline quality
- [ ] Input guardrails for prompt injection protection
- [ ] pytest test suite
- [ ] GitHub Actions CI/CD pipeline
- [ ] Cloud deployment (AWS/GCP)
- [ ] Slack/Teams notification integration
- [ ] Support for Datadog, OpsGenie webhooks

---

## 👤 Author

**Tejaswi S K** — AI Engineer | AIOps | LangGraph | Enterprise IT Operations

- 🐙 GitHub: [github.com/Tejas163](https://github.com/Tejas163)
- 🤗 HuggingFace: [huggingface.co/Tejas86](https://huggingface.co/Tejas86) — Fine-tuned RPA & DevOps SLM (100+ downloads)
- 📧 tejaskrshna@gmail.com

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built on 10 years of enterprise IT operations experience — solving the problems I've watched teams struggle with firsthand.*
