"""
JIRA Triage Agent - Reasoning Plane
FastAPI service with LangGraph multi-agent workflow for ticket triage
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import time
import os

from langgraph_agent import agent

app = FastAPI(title="JIRA Triage Agent - Reasoning Plane", version="2.0.0")

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
    model_used: str = "gpt-5-langgraph"
    latency_ms: int = 0
    requires_human_review: bool = False

@app.get("/")
async def root():
    return {
        "service": "JIRA Triage Agent - Reasoning Plane",
        "status": "operational",
        "architecture": "Hybrid Polyglot - Python GenAI Layer with LangGraph",
        "ai_model": "gpt-5",
        "features": [
            "Multi-agent workflow (Classify → Retrieve → Generate → Policy)",
            "Vertical slice routing (IT, HR, Finance, Legal)",
            "Zero-trust data governance",
            "Human-in-the-loop policy enforcement"
        ]
    }

@app.get("/health")
async def health():
    openai_configured = bool(os.environ.get("OPENAI_API_KEY"))
    azure_openai_configured = bool(
        os.environ.get("AZURE_OPENAI_ENDPOINT") and 
        os.environ.get("AZURE_OPENAI_API_KEY")
    )
    agent_ready = openai_configured or azure_openai_configured
    
    return {
        "status": "healthy" if agent_ready else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "openai_public_configured": openai_configured,
        "azure_openai_configured": azure_openai_configured,
        "agent_ready": agent_ready,
        "message": "OK" if agent_ready else "No OpenAI credentials configured (OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT+API_KEY required)"
    }

@app.post("/process_ticket", response_model=EnrichedTicketResult)
async def process_ticket(ticket: SanitizedTicket) -> EnrichedTicketResult:
    """
    Process a sanitized ticket through the LangGraph multi-agent workflow.
    
    Workflow: ClassifyNode → RetrieveNode → GenerateNode → PolicyNode
    """
    start_time = time.time()
    
    try:
        ticket_data = {
            "ticket_id": ticket.ticket_id,
            "issue_key": ticket.issue_key,
            "summary": ticket.summary,
            "description": ticket.description,
            "issue_type": ticket.issue_type or "Unknown",
            "priority": ticket.priority or "Medium",
            "reporter": ticket.reporter or "unknown",
            "redaction_flags": ticket.redaction_flags
        }
        
        result = agent.process(ticket_data)
        
        latency = int((time.time() - start_time) * 1000)
        
        classification_data = result.get("classification", {})
        classification = Classification(
            department=classification_data.get("department"),
            team=classification_data.get("team"),
            suggested_priority=classification_data.get("suggested_priority"),
            suggested_assignee=classification_data.get("suggested_assignee"),
            confidence=classification_data.get("confidence", 0.0)
        )
        
        return EnrichedTicketResult(
            ticket_id=result["ticket_id"],
            issue_key=result["issue_key"],
            classification=classification,
            generated_comment=result.get("generated_comment", ""),
            citations=result.get("citations", []),
            policy_flags=result.get("policy_flags", []),
            confidence=result.get("confidence", 0.0),
            model_used=result.get("model_used", "gpt-5-langgraph"),
            latency_ms=latency,
            requires_human_review=result.get("requires_human_review", False)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
