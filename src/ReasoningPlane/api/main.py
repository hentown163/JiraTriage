from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import time

app = FastAPI(title="JIRA Triage Agent - Reasoning Plane", version="1.0.0")

class SanitizedTicket(BaseModel):
    ticket_id: str
    issue_key: str
    summary: str
    description: str
    issue_type: Optional[str] = None
    priority: Optional[str] = None
    reporter: Optional[str] = None
    created_at: datetime
    redaction_flags: List[str] = []
    sanitized_input_hash: Optional[str] = None

class Classification(BaseModel):
    department: Optional[str] = None
    team: Optional[str] = None
    suggested_priority: Optional[str] = None
    suggested_assignee: Optional[str] = None
    confidence: float = 0.0

class EnrichedTicketResult(BaseModel):
    ticket_id: str
    issue_key: str
    classification: Optional[Classification] = None
    generated_comment: Optional[str] = None
    citations: List[str] = []
    policy_flags: List[str] = []
    confidence: float = 0.0
    model_used: str = "demo-mock-llm"
    latency_ms: int = 0
    requires_human_review: bool = False

@app.get("/")
async def root():
    return {
        "service": "JIRA Triage Agent - Reasoning Plane",
        "status": "operational",
        "architecture": "Hybrid Polyglot - Python GenAI Layer"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/process_ticket", response_model=EnrichedTicketResult)
async def process_ticket(ticket: SanitizedTicket) -> EnrichedTicketResult:
    """
    Process a sanitized ticket through the LangGraph agent.
    This is a simplified version for demonstration.
    """
    start_time = time.time()
    
    try:
        classification = classify_ticket(ticket)
        
        retrieved_docs = retrieve_knowledge(ticket, classification)
        
        comment = generate_response(ticket, classification, retrieved_docs)
        
        policy_flags = check_policy(ticket)
        
        confidence = classification.confidence
        requires_review = confidence < 0.7 or len(policy_flags) > 0 or "external_email" in ticket.redaction_flags
        
        latency = int((time.time() - start_time) * 1000)
        
        return EnrichedTicketResult(
            ticket_id=ticket.ticket_id,
            issue_key=ticket.issue_key,
            classification=classification,
            generated_comment=comment,
            citations=retrieved_docs,
            policy_flags=policy_flags,
            confidence=confidence,
            model_used="mock-classifier-v1",
            latency_ms=latency,
            requires_human_review=requires_review
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def classify_ticket(ticket: SanitizedTicket) -> Classification:
    """
    Mock classification logic - Replace with LangGraph ClassifyNode
    """
    summary_lower = ticket.summary.lower()
    description_lower = ticket.description.lower()
    
    if any(word in summary_lower or word in description_lower 
           for word in ["database", "db", "sql", "timeout", "connection"]):
        return Classification(
            department="IT",
            team="DBA",
            suggested_priority="High",
            suggested_assignee="dba-lead@company.com",
            confidence=0.92
        )
    elif any(word in summary_lower or word in description_lower 
             for word in ["onboard", "hire", "employee", "contractor"]):
        return Classification(
            department="HR",
            team="Onboarding",
            suggested_priority="Medium",
            suggested_assignee="hr-onboarding@company.com",
            confidence=0.85
        )
    else:
        return Classification(
            department="General",
            team="Support",
            suggested_priority="Medium",
            confidence=0.65
        )

def retrieve_knowledge(ticket: SanitizedTicket, classification: Classification) -> List[str]:
    """
    Mock RAG retrieval - Replace with actual vector DB query
    """
    if classification.department == "IT":
        return ["Confluence:KB-887", "Confluence:NetACLs-Staging"]
    elif classification.department == "HR":
        return ["HR-Policy:Contractor-Onboarding-Checklist"]
    return ["GeneralKB:Support-Guidelines"]

def generate_response(ticket: SanitizedTicket, classification: Classification, citations: List[str]) -> str:
    """
    Mock LLM generation - Replace with actual LLM call
    """
    if classification.department == "IT":
        return f"This appears to be a database connectivity issue. Please verify your network access per {citations[0]}. Assigning to DBA team."
    elif classification.department == "HR":
        return f"This is an onboarding request. Please review the contractor onboarding checklist ({citations[0]}) and ensure all compliance requirements are met."
    return "This ticket has been received and will be reviewed by the support team."

def check_policy(ticket: SanitizedTicket) -> List[str]:
    """
    Policy validation
    """
    flags = []
    if "external_email" in ticket.redaction_flags:
        flags.append("external_contact_detected")
    if any(flag in ticket.redaction_flags for flag in ["ssn_detected", "credit_card_detected"]):
        flags.append("high_sensitivity_pii")
    return flags

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
