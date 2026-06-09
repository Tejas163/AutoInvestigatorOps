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