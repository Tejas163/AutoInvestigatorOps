# schemas.py
from typing import List, Dict, Any, TypedDict
class InvestigationState(TypedDict):
    incident_id: str
    incident_number: int
    title: str
    status: str
    urgency: str
    service_name: str
    service_id: str
    pdr_url: str
    triggered_at: str
    service_dependencies: List[str]
    relevant_logs: List[str]
    metric_anomalies: List[Dict[str, Any]]
    historical_matches: List[Dict[str, Any]]
    next_step: str
    investigation_steps_taken: List[str]
    root_cause_summary: Dict[str, Any]
    
    # NEW FIELDS FOR WEAPONIZATION
    remediation_approved: bool    # Set to True when a human approves the action
    remediation_executed: bool    # Tracks if the script finished running
    remediation_logs: str         # Captures the standard output of the fix script