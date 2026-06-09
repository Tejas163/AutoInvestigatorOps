from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, cast
from pipeline import investigation_engine
from dotenv import load_dotenv # This pulls variables from your .env file into os.environ
load_dotenv() 
import logging

# Configure logging for production visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("incident_webhook")

app = FastAPI(title="Autonomous Investigator - Inbound Webhook", version="1.0.0")

# ==========================================
# 1. PYDANTIC SCHEMAS FOR VALIDATION
# ==========================================

class PDService(BaseModel):
    id: str
    summary: str  # Name of the microservice (e.g., "payment-gateway-v2")
    html_url: str

class PDIncident(BaseModel):
    id: str
    incident_number: int
    title: str
    created_at: str
    status: str  # triggered, acknowledged, resolved
    urgency: str  # high, low
    html_url: str
    service: PDService
    first_trigger_log_entry: Optional[Dict[str, Any]] = None

class PDWebhookMessage(BaseModel):
    id: str
    event: str  # e.g., "incident.triggered"
    created_at: str
    incident: PDIncident

class PagerDutyWebhookPayload(BaseModel):
    messages: List[PDWebhookMessage]


# ==========================================
# 2. CORE AGENT TRIGGER WORKFLOW (ASYNC)
# ==========================================

def trigger_agent_investigation(extracted_context: Dict[str, Any]):
    """
    Spawns the LangGraph state machine workflow.
    """
    logger.info(f"--- SPARKING AI INVESTIGATION FOR INCIDENT {extracted_context['incident_id']} ---")

    # Pass the webhook payload right into the LangGraph state machine!
    final_output_state = investigation_engine.invoke(extracted_context) # pyright: ignore[reportArgumentType]

    # NEW EXPANDED LOGGING BLOCK
    summary = final_output_state.get("root_cause_summary", {})
    print("\n" + "="*50)
    print(f"🔴 ROOT CAUSE      : {summary.get('root_cause')}")
    print(f"🎯 CONFIDENCE SCORE: {summary.get('confidence_score') * 100}%")
    print(f"🛠️  REMEDIATION STEP: {summary.get('recommended_action')}")
    print("="*50 + "\n")
# ==========================================
# 3. WEBHOOK ENDPOINT
# ==========================================

@app.post("/webhooks/pagerduty", status_code=202)
async def handle_pagerduty_webhook(
    payload: PagerDutyWebhookPayload, 
    background_tasks: BackgroundTasks
):
    """
    Inbound endpoint for PagerDuty v3 Webhooks.
    Validates, extracts payload telemetry, and hands off to the background AI runner.
    """
    for message in payload.messages:
        # We only care about new incidents that require immediate triage
        if message.event != "incident.triggered":
            logger.info(f"Skipping non-trigger event: {message.event}")
            continue
            
        incident = message.incident
        
        # Flatten and extract only the meat of the alert for the LLM
        extracted_context = {
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
            "title": incident.title,
            "status": incident.status,
            "urgency": incident.urgency,
            "service_name": incident.service.summary,
            "service_id": incident.service.id,
            "pdr_url": incident.html_url,
            "triggered_at": incident.created_at,
            # Placeholders for data elements our LangGraph nodes will soon enrich
            "service_dependencies": [],
            "relevant_logs": [],
            "metric_anomalies": [],
            "historical_matches": []
        }
        
        logger.info(f"Validated incident {incident.id} received for service '{incident.service.summary}'")
        
        # Hand off execution asynchronously so we don't time out PagerDuty's server
        background_tasks.add_task(trigger_agent_investigation, extracted_context)

    return {"status": "accepted", "message": "Trigger events queued for investigation"}