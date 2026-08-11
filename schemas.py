# schemas.py
import operator
from typing import Annotated, List, Dict, Any, TypedDict
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
    next_step: str
    root_cause_summary: Dict[str, Any]

    # Reducers aggregate data from parallel branches instead of overwriting
    relevant_logs: Annotated[List[str], operator.add]
    metric_anomalies: Annotated[List[Dict[str, Any]], operator.add]
    historical_matches: Annotated[List[Dict[str, Any]], operator.add]
    investigation_steps_taken: Annotated[List[str], operator.add]
    
    # NEW FIELDS FOR WEAPONIZATION
    remediation_approved: bool    # Set to True when a human approves the action
    remediation_executed: bool    # Tracks if the script finished running
    remediation_logs: str         # Captures the standard output of the fix script