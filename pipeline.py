# pipeline.py
import os
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from schemas import InvestigationState
from langchain_openai import ChatOpenAI

# Vector Search Imports
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from dotenv import load_dotenv
load_dotenv()

# 1. INITIALIZE LOCAL AI AND EMBEDDING ENGINE
SRE_AGENT_LLM_URL = os.environ.get("SRE_AGENT_LLM_URL")
SRE_AGENT_LLM_KEY = os.environ.get("SRE_AGENT_LLM_KEY")
llm = ChatOpenAI(
    base_url=SRE_AGENT_LLM_URL,
    api_key=SRE_AGENT_LLM_KEY,
    model="liquid/lfm2.5-1.2b",
    temperature=0.1
)

# Small, fast embedding model that runs entirely on your Ryzen 5 CPU
embedding_engine = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Create/Load an in-memory local Chroma vector database
vector_db = Chroma(embedding_function=embedding_engine)

# On startup, seed the database with our human troubleshooting guide
runbook_path = os.path.join("runbooks", "redis_runbook.md")
if os.path.exists(runbook_path):
    with open(runbook_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Add to our local vector index
    vector_db.add_documents([Document(page_content=content, metadata={"source": "redis_runbook.md"})])
    print("[INIT]: Successfully indexed internal engineering runbooks into VectorDB.")


# ==========================================
# WORKFLOW NODES
# ==========================================

def triage_alert_node(state: InvestigationState) -> Dict[str, Any]:
    print(f"[NODE - Triage]: Analyzing alert metadata for incident: {state['incident_id']}")
    return {
        "investigation_steps_taken": state.get("investigation_steps_taken", []) + ["triaged_alert"],
        "next_step": "gather_telemetry"
    }


def gather_telemetry_node(state: InvestigationState) -> Dict[str, Any]:
    target_service = state["service_name"]
    print(f"[NODE - Telemetry]: Dynamically scanning production_logs.txt for service: '{target_service}'")
    
    found_logs = []
    log_file_path = "production_logs.txt"
    
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as file:
            for line in file:
                if target_service in line:
                    found_logs.append(line.strip())
                    
    detected_metrics = []
    if any("exhausted" in log.lower() for log in found_logs):
        detected_metrics.append({"metric": "redis.connected_clients", "value": 150, "status": "MAX_EXHAUSTED"})

    return {
        "relevant_logs": found_logs,
        "metric_anomalies": detected_metrics,
        "investigation_steps_taken": state["investigation_steps_taken"] + ["gathered_telemetry"],
        "next_step": "search_runbooks" # Point to our new Vector Search Node!
    }


# 2. THE NEW VECTOR SEARCH RUNBOOK NODE
def search_runbooks_node(state: InvestigationState) -> Dict[str, Any]:
    search_query = f"{state['title']} {state['service_name']} Redis exhaustion"
    print(f"[NODE - Vector Search]: Searching internal runbooks matching context: '{search_query}'")
    
    # Query Chroma for the top matching document snippet
    results = vector_db.similarity_search(search_query, k=1)
    
    matched_runbook_context = ""
    if results:
        matched_runbook_context = results[0].page_content
        print(f"[NODE - Vector Search]: Match discovered in file: {results[0].metadata['source']}")
    else:
        matched_runbook_context = "No relevant engineering runbook found for this error profile."

    return {
        # Store the found manual instructions inside our state variable
        "historical_matches": [{"runbook_text": matched_runbook_context}],
        "investigation_steps_taken": state["investigation_steps_taken"] + ["searched_runbooks"],
        "next_step": "synthesize_rca"
    }


def synthesize_rca_node(state: InvestigationState) -> Dict[str, Any]:
    print(f"[NODE - RCA Synthesizer]: Blending logs, metrics, AND Vector Runbooks into LLM Context...")

    logs_context = "\n".join(state.get("relevant_logs", []))
    metrics_context = str(state.get("metric_anomalies", []))
    
    # Extract the runbook context we saved in the previous node
    history = state.get("historical_matches", [])
    runbook_instructions = history[0]["runbook_text"] if history else "No runbook provided."
    
    # Give the local model access to the exact human instructions!
    prompt = f"""You are an SRE AI Agent. Analyze the telemetry and provide a Root Cause Analysis (RCA). Use the RUNBOOK INSTRUCTIONS below to formulate your recommended action.

INCIDENT CONTEXT:
- Service: {state['service_name']}
- Alert: {state['title']}

TELEMETRY LOGS:
{logs_context}

METRIC ANOMALIES:
{metrics_context}

INTERNAL HUMAN RUNBOOK INSTRUCTIONS:
{runbook_instructions}

You must respond with a raw JSON object and nothing else. Do not use markdown code blocks. 

RESPONSE FORMAT EXAMPLE:
{{"root_cause": "The exact issue found.", "confidence_score": 0.90, "recommended_action": "Clear steps based on the runbook instructions."}}

YOUR JSON RESPONSE:"""

    try:
        ai_response = llm.invoke(prompt)
        raw_content = ai_response.content.strip()
        
        if raw_content.startswith("```"):
            raw_content = raw_content.split("\n", 1)[-1]
        if raw_content.endswith("```"):
            raw_content = raw_content.rsplit("\n", 1)[0]
        raw_content = raw_content.strip().strip("`json").strip()

        import json
        summary = json.loads(raw_content)
        
    except Exception as e:
        print(f"[ERROR]: Local LLM output processing failed: {e}")
        summary = {
            "root_cause": "Failed to extract clean structural diagnostics from local model payload.",
            "confidence_score": 0.50,
            "recommended_action": f"Review terminal logs. Error: {str(e)}"
        }

    return {
        "root_cause_summary": summary,
        "investigation_steps_taken": state["investigation_steps_taken"] + ["synthesized_rca"],
        "next_step": "end"
    }


# ==========================================
# GRAPH ORCHESTRATION CONFIGURATION
# ==========================================
workflow = StateGraph(InvestigationState)

workflow.add_node("triage_alert", triage_alert_node)
workflow.add_node("gather_telemetry", gather_telemetry_node)
workflow.add_node("search_runbooks", search_runbooks_node) # Register node
workflow.add_node("synthesize_rca", synthesize_rca_node)

# Connect the nodes in sequence
workflow.add_edge("triage_alert", "gather_telemetry")
workflow.add_edge("gather_telemetry", "search_runbooks") # Connect telemetry to search
workflow.add_edge("search_runbooks", "synthesize_rca")   # Connect search to analyzer

def router(state: InvestigationState):
    if state["next_step"] == "end":
        return END
    return state["next_step"]

workflow.add_conditional_edges("synthesize_rca", router)
workflow.set_entry_point("triage_alert")

investigation_engine = workflow.compile()