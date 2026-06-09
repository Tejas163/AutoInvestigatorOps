# AutoInvestigatorOps 🚀

AutoInvestigatorOps is a local-first, privacy-focused, automated Site Reliability Engineering (SRE) triage and auto-remediation agent. It intercepts incoming infrastructure incident webhooks (e.g., PagerDuty, Datadog), builds an isolated state machine to gather telemetry logs, queries a local vector database of engineering runbooks, and utilizes a local LLM to deduce root causes and execute remediation steps safely under a human-in-the-loop paradigm.

## 🏗️ Architecture

The system is built entirely out of lightweight, open-source, and free-to-run components on local hardware:

- **API Gateway:** FastAPI intercepts production webhooks asynchronously, immediately dispatching background threads.
- **State Orchestration Core:** LangGraph manages the sequential investigation lifecycle nodes cleanly while isolating execution state schemas.
- **Vector Search Engine:** ChromaDB + SentenceTransformers (`all-MiniLM-L6-v2`) embed and retrieve matching engineering markdown runbooks entirely on CPU.
- **Local Intelligence Brain:** LM Studio hosting an ultra-efficient 2B model (`LFM-2b`) to perform reasoning, synthesis, and script compilation without internet API dependencies.

---

## 🛠️ Getting Started

### Prerequisites
- **Python 3.11+**
- **LM Studio** installed on your machine.

### 1. Clone & Set Up the Virtual Environment
```powershell
git clone (https://github.com/Tejas163/AutoInvestigatorOps.git)
cd AutoInvestigatorOps

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install core framework dependencies
pip install -r requirements.txt
