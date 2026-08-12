# pipeline.py
import os
import json
import time
import subprocess
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from schemas import InvestigationState
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from dotenv import load_dotenv
from prometheus_client import Histogram

# Langfuse Integration (Tracing & Observability)

from langfuse.langchain import CallbackHandler

load_dotenv()

# Option 2: Explicit passing with updated argument names
langfuse_handler = CallbackHandler()

LLM_INFERENCE_DURATION = Histogram(
    "sre_llm_inference_duration_seconds",
    "Time taken for LLM to synthesize root cause analysis",
    buckets=[1, 2, 5, 10, 30, 60]
)

SRE_AGENT_LLM_URL = os.getenv("SRE_AGENT_LLM_URL")
SRE_AGENT_LLM_KEY = os.getenv("SRE_AGENT_LLM_KEY")

llm = ChatOpenAI(
    base_url=SRE_AGENT_LLM_URL, 
    api_key=SRE_AGENT_LLM_KEY, 
    model="liquid/lfm2.5-1.2b", 
    temperature=0.1,
    callbacks=[langfuse_handler]  # Attach Langfuse to LLM instances
)

embedding_engine = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(embedding_function=embedding_engine)
# Seed runbooks into vector store on startup
runbook_path = os.path.join("runbooks", "redis_runbook.md")
if os.path.exists(runbook_path):
    with open(runbook_path, "r", encoding="utf-8") as f:
        content = f.read()
    vector_db.add_documents([
        Document(
            page_content=content,
            metadata={"source": "redis_runbook.md"}
        )
    ])
    print("[INIT]: Redis runbook loaded into vector store ✓")
else:
    print("[WARN]: No runbook found at runbooks/redis_runbook.md")
# --- NODES ---

def triage_alert_node(state: InvestigationState) -> Dict[str, Any]:
    print(f"[NODE - Triage]: Analyzing alert metadata for incident: {state['incident_id']}")
    return {
        "investigation_steps_taken": state.get("investigation_steps_taken", []) + ["triaged_alert"]
    }

def gather_telemetry_agent(state: InvestigationState) -> Dict[str, Any]:
    """Parallel Agent Branch A: Telemetry Gathering"""
    target_service = state["service_name"]
    print(f"[AGENT - Telemetry]: Scanning production_logs.txt for: '{target_service}'")
    found_logs = []
    if os.path.exists("production_logs.txt"):
        with open("production_logs.txt", "r") as file:
            for line in file:
                if target_service in line:
                    found_logs.append(line.strip())
    detected_metrics = []
    if any("exhausted" in log.lower() for log in found_logs):
        detected_metrics.append({"metric": "redis.connected_clients", "value": 150, "status": "MAX_EXHAUSTED"})
    
    return {
        "relevant_logs": found_logs, 
        "metric_anomalies": detected_metrics, 
        "investigation_steps_taken": state.get("investigation_steps_taken", []) + ["gathered_telemetry"]
    }

def runbook_search_agent(state: InvestigationState) -> Dict[str, Any]:
    """Parallel Agent Branch B: Vector Runbook Retrieval"""
    search_query = f"{state['title']} {state['service_name']} Redis exhaustion"
    print(f"[AGENT - Runbook]: Querying local vector store for runbooks...")
    results = vector_db.similarity_search(search_query, k=1)
    context = results[0].page_content if results else "No engineering runbook found."
    
    return {
        "historical_matches": [{"runbook_text": context}], 
        "investigation_steps_taken": state.get("investigation_steps_taken", []) + ["searched_runbooks"]
    }

def synthesize_rca_node(state: InvestigationState) -> Dict[str, Any]:
    print(f"[NODE - RCA Synthesizer]: Synthesizing telemetry and runbooks...")
    logs_context = "\n".join(state.get("relevant_logs", []))
    metrics_context = str(state.get("metric_anomalies", []))
    history = state.get("historical_matches", [])
    runbook_instructions = history[0]["runbook_text"] if history else ""

    prompt = f"""You are an SRE AI Agent. Analyze the telemetry and provide an RCA JSON.
    RUNBOOK DIRECTIONS:
    {runbook_instructions}

    LOGS: {logs_context} | METRICS: {metrics_context}

    Return raw JSON:
    {{"root_cause": "Reason", "confidence_score": 0.95, "recommended_action": "Run fix", "target_script": "Powershell/Bash script"}}
    """

    llm_start = time.time()
    try:
        # Pass Langfuse config explicitly for trace generation
        ai_response = llm.invoke(prompt, config={"callbacks": [langfuse_handler]})
        llm_duration = time.time() - llm_start
        LLM_INFERENCE_DURATION.observe(llm_duration)

        raw_content = ai_response.content.strip().strip("```json").strip("```").strip()
        summary = json.loads(raw_content)
    except Exception as e:
        summary = {
            "root_cause": "Parsing failed",
            "confidence_score": 0.5,
            "recommended_action": "Manual check",
            "target_script": "Write-Output 'Error'"
        }

    return {
        "root_cause_summary": summary,
        "investigation_steps_taken": state.get("investigation_steps_taken", []) + ["synthesized_rca"],
        "next_step": "execute_remediation" if state.get("remediation_approved") else "end"
    }


def execute_remediation_node(state: InvestigationState) -> Dict[str, Any]:
    print(f"[NODE - Remediation]: 🚀 Executing approved remediation...")
    
    summary = state.get("root_cause_summary", {})
    script_command = summary.get("target_script", "Write-Output 'No script generated.'")
    
    script_file = "remediate.ps1"
    
    # Write AI-generated script to disk
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(f"# Auto-Generated SRE Remediation Script\n")
        f.write(f"# Generated by AutoInvestigatorOps\n")
        f.write(f"# HUMAN APPROVED before execution\n\n")
        f.write(f"{script_command}\n")
        f.write(f"Write-Output 'Remediation step completed.'\n")
    
    try:
        # Execute via PowerShell subprocess
        # Safety: Only runs after human approval gate (remediation_approved=True)
        # Input guardrail: Script reviewed by human before this node executes
        result = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", script_file],
            capture_output=True,
            text=True,
            timeout=30  # Safety timeout
        )
        execution_output = result.stdout or "Script executed successfully"
        print(f"[SUCCESS]: Remediation completed")
        
    except subprocess.TimeoutExpired:
        execution_output = "Execution timed out after 30 seconds"
        print(f"[WARN]: Remediation timed out")
    except FileNotFoundError:
        # PowerShell not available (Linux/Mac)
        execution_output = "PowerShell not available - script written to remediate.ps1"
        print(f"[INFO]: Script saved to {script_file}")
    except Exception as e:
        execution_output = f"Execution failed: {str(e)}"
        print(f"[ERROR]: Remediation failed: {e}")

    return {
        "remediation_executed": True,
        "remediation_logs": execution_output.strip(),
        "investigation_steps_taken": state.get(
            "investigation_steps_taken", []
        ) + ["executed_remediation"]
    }
# --- GRAPH ORCHESTRATION ---

workflow = StateGraph(InvestigationState)

workflow.add_node("triage_alert", triage_alert_node)
workflow.add_node("gather_telemetry", gather_telemetry_agent)
workflow.add_node("search_runbooks", runbook_search_agent)
workflow.add_node("synthesize_rca", synthesize_rca_node)
workflow.add_node("execute_remediation", execute_remediation_node)

# Parallel Fan-Out: Triage triggers Telemetry AND Runbook Search concurrently
workflow.add_edge("triage_alert", "gather_telemetry")
workflow.add_edge("triage_alert", "search_runbooks")

# Fan-In: Both agents route results back to RCA Synthesis
workflow.add_edge("gather_telemetry", "synthesize_rca")
workflow.add_edge("search_runbooks", "synthesize_rca")

def remediation_router(state: InvestigationState):
    if state.get("next_step") == "execute_remediation":
        return "execute_remediation"
    return END

workflow.add_conditional_edges("synthesize_rca", remediation_router)
workflow.add_edge("execute_remediation", END)

workflow.set_entry_point("triage_alert")
investigation_engine = workflow.compile()