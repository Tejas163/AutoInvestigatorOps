# pipeline.py
import os
import subprocess
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from schemas import InvestigationState
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from dotenv import load_dotenv
load_dotenv()
from prometheus_client import Histogram
import time

LLM_INFERENCE_DURATION = Histogram(
    "sre_llm_inference_duration_seconds",
    "Time taken for LLM to synthesize root cause analysis",
    buckets=[1, 2, 5, 10, 30, 60]
)
# Initialize local LLM and Vector Engine
SRE_AGENT_LLM_URL = os.getenv("SRE_AGENT_LLM_URL")
SRE_AGENT_LLM_KEY = os.getenv("SRE_AGENT_LLM_KEY")

llm = ChatOpenAI(base_url=SRE_AGENT_LLM_URL, api_key=SRE_AGENT_LLM_KEY, model="liquid/lfm2.5-1.2b", temperature=0.1)
embedding_engine = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(embedding_function=embedding_engine)

# Seed Runbooks
runbook_path = os.path.join("runbooks", "redis_runbook.md")
if os.path.exists(runbook_path):
    with open(runbook_path, "r", encoding="utf-8") as f:
        content = f.read()
    vector_db.add_documents([Document(page_content=content, metadata={"source": "redis_runbook.md"})])


# ==================================================
# EXISTING NODES (Triage, Telemetry, Vector Search)
# ==================================================
def triage_alert_node(state: InvestigationState) -> Dict[str, Any]:
    print(f"[NODE - Triage]: Analyzing alert metadata for incident: {state['incident_id']}")
    return {"investigation_steps_taken": state.get("investigation_steps_taken", []) + ["triaged_alert"], "next_step": "gather_telemetry"}

def gather_telemetry_node(state: InvestigationState) -> Dict[str, Any]:
    target_service = state["service_name"]
    print(f"[NODE - Telemetry]: Scanning production_logs.txt for: '{target_service}'")
    found_logs = []
    if os.path.exists("production_logs.txt"):
        with open("production_logs.txt", "r") as file:
            for line in file:
                if target_service in line: found_logs.append(line.strip())
    detected_metrics = []
    if any("exhausted" in log.lower() for log in found_logs):
        detected_metrics.append({"metric": "redis.connected_clients", "value": 150, "status": "MAX_EXHAUSTED"})
    return {"relevant_logs": found_logs, "metric_anomalies": detected_metrics, "investigation_steps_taken": state["investigation_steps_taken"] + ["gathered_telemetry"], "next_step": "search_runbooks"}

def search_runbooks_node(state: InvestigationState) -> Dict[str, Any]:
    search_query = f"{state['title']} {state['service_name']} Redis exhaustion"
    print(f"[NODE - Vector Search]: Querying local vector store for runbooks...")
    results = vector_db.similarity_search(search_query, k=1)
    context = results[0].page_content if results else "No engineering runbook found."
    return {"historical_matches": [{"runbook_text": context}], "investigation_steps_taken": state["investigation_steps_taken"] + ["searched_runbooks"], "next_step": "synthesize_rca"}


# ==================================================
# RCA NODE WITH EXPLICIT ENFORCED SCRIPT COMMAND OUTPUT
# ==================================================
def synthesize_rca_node(state: InvestigationState):
    print(f"[NODE - RCA Synthesizer]: Parsing system context with LFM-2b...")
    logs_context = "\n".join(state.get("relevant_logs", []))
    metrics_context = str(state.get("metric_anomalies", []))
    history = state.get("historical_matches", [])
    runbook_instructions = history[0]["runbook_text"] if history else ""

    prompt = f"""You are an SRE AI Agent. Analyze the telemetry and provide an RCA JSON.
    You must include an exact script string matching the instructions for remediation.

    RUNBOOK DIRECTIONS:
    {runbook_instructions}

    LOGS: {logs_context} | METRICS: {metrics_context}

    Return a raw JSON object only.
    EXAMPLE FORMAT:
    {{"root_cause": "Reason", "confidence_score": 0.95, "recommended_action": "Run fix", 
    "target_script": "Write a powershell command here matching runbook"}}
    """

    # Track LLM inference time specifically
    llm_start = time.time()
    try:
        ai_response = llm.invoke(prompt)
        llm_duration = time.time() - llm_start
        LLM_INFERENCE_DURATION.observe(llm_duration)
        print(f"[METRICS]: LLM inference completed in {llm_duration:.2f}s")

        raw_content = ai_response.content.strip().strip("```json").strip("```").strip()
        import json
        summary = json.loads(raw_content)

    except Exception as e:
        llm_duration = time.time() - llm_start
        LLM_INFERENCE_DURATION.observe(llm_duration)
        summary = {
            "root_cause": "Parsing failed",
            "confidence_score": 0.5,
            "recommended_action": "Manual check",
            "target_script": "Write-Output 'Error'"
        }

    return {
        "root_cause_summary": summary,
        "investigation_steps_taken": state["investigation_steps_taken"] + ["synthesized_rca"],
        "next_step": "execute_remediation" if state.get("remediation_approved") else "end"
    }


# ==================================================
# GRAPH ORCHESTRATION LAYER WITH ROUTING LOGIC
# ==================================================
workflow = StateGraph(InvestigationState)

workflow.add_node("triage_alert", triage_alert_node)
workflow.add_node("gather_telemetry", gather_telemetry_node)
workflow.add_node("search_runbooks", search_runbooks_node)
workflow.add_node("synthesize_rca", synthesize_rca_node)
workflow.add_node("execute_remediation", execute_remediation_node) # Register node

workflow.add_edge("triage_alert", "gather_telemetry")
workflow.add_edge("gather_telemetry", "search_runbooks")
workflow.add_edge("search_runbooks", "synthesize_rca")

# Conditional Routing logic
def remediation_router(state: InvestigationState):
    if state["next_step"] == "execute_remediation":
        return "execute_remediation"
    return END

workflow.add_conditional_edges("synthesize_rca", remediation_router)
workflow.add_edge("execute_remediation", END)

workflow.set_entry_point("triage_alert")
investigation_engine = workflow.compile()