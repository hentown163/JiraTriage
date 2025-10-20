"""
LangGraph Multi-Agent Workflow for JIRA Ticket Triage
Implements ClassifyNode, RetrieveNode, GenerateNode, PolicyNode with vertical slicing
"""

import os
from typing import Annotated, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import json

from azure_ai_search import search_manager
from azure_cosmos import decision_logger
from azure_keyvault import keyvault
from enhanced_policy_engine import policy_engine

class TicketState(TypedDict):
    """State object passed through the LangGraph workflow"""
    ticket_id: str
    issue_key: str
    summary: str
    description: str
    issue_type: str
    priority: str
    reporter: str
    redaction_flags: list[str]
    
    department: str
    team: str
    suggested_priority: str
    suggested_assignee: str
    classification_confidence: float
    
    retrieved_docs: list[str]
    generated_comment: str
    
    policy_flags: list[str]
    requires_human_review: bool
    
    messages: Annotated[list, add_messages]


class JIRATriageAgent:
    """
    LangGraph-based multi-agent system for ticket triage with vertical slicing
    """
    
    def __init__(self):
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or keyvault.get_secret("Azure-OpenAI-Endpoint")
        azure_api_key = os.environ.get("AZURE_OPENAI_API_KEY") or keyvault.get_secret("Azure-OpenAI-API-Key")
        azure_api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        
        if azure_endpoint and azure_api_key:
            self.llm = AzureChatOpenAI(
                azure_deployment="gpt-5",
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
                max_tokens=2048
            )
            
            self.embeddings = AzureOpenAIEmbeddings(
                azure_deployment="text-embedding-3-small",
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version
            )
            print("Initialized Azure OpenAI (Enterprise)")
        elif openai_api_key:
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
            self.llm = ChatOpenAI(
                model="gpt-5",
                api_key=openai_api_key,
                max_completion_tokens=2048
            )
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=openai_api_key
            )
            print("Warning: Using public OpenAI endpoint (development only)")
        else:
            raise ValueError("No OpenAI credentials configured. Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY or OPENAI_API_KEY")
        
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow with conditional routing
        """
        workflow = StateGraph(TicketState)
        
        workflow.add_node("classify", self.classify_node)
        workflow.add_node("retrieve", self.retrieve_node)
        workflow.add_node("generate", self.generate_node)
        workflow.add_node("policy", self.policy_node)
        
        workflow.set_entry_point("classify")
        
        workflow.add_edge("classify", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", "policy")
        workflow.add_edge("policy", END)
        
        return workflow.compile()
    
    def classify_node(self, state: TicketState) -> dict:
        """
        ClassifyNode: Department/team/priority prediction with confidence scores
        Uses GPT-5 for multi-class classification with structured output
        """
        system_prompt = """You are an expert JIRA ticket classifier for enterprise IT operations.
        
Classify the ticket into:
- department: IT, HR, Finance, Legal, General
- team: DBA, DevOps, Security, Onboarding, Payroll, Contracts, Support
- suggested_priority: Critical, High, Medium, Low
- suggested_assignee: team lead email
- confidence: 0.0 to 1.0

Consider:
- Technical keywords for IT (database, server, deployment, auth)
- HR keywords (onboard, hire, termination, benefits)
- Finance keywords (invoice, payment, expense, budget)
- Legal keywords (contract, compliance, GDPR, NDA)

Respond ONLY with valid JSON matching this schema:
{
  "department": "string",
  "team": "string", 
  "suggested_priority": "string",
  "suggested_assignee": "string",
  "confidence": number
}"""
        
        user_content = f"""Ticket Summary: {state['summary']}
Ticket Description: {state['description']}
Original Priority: {state['priority']}
Issue Type: {state['issue_type']}
Redaction Flags: {', '.join(state['redaction_flags']) if state['redaction_flags'] else 'None'}"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        try:
            response = self.llm.invoke(
                messages,
                response_format={"type": "json_object"}
            )
            
            classification = json.loads(response.content)
            
            return {
                "department": classification.get("department", "General"),
                "team": classification.get("team", "Support"),
                "suggested_priority": classification.get("suggested_priority", state['priority']),
                "suggested_assignee": classification.get("suggested_assignee", "support@company.com"),
                "classification_confidence": classification.get("confidence", 0.5),
                "messages": [response]
            }
        except Exception as e:
            return {
                "department": "General",
                "team": "Support",
                "suggested_priority": state['priority'],
                "suggested_assignee": "support@company.com",
                "classification_confidence": 0.0,
                "messages": [AIMessage(content=f"Classification error: {str(e)}")]
            }
    
    def retrieve_node(self, state: TicketState) -> dict:
        """
        RetrieveNode: Hybrid search (vector + keyword) from Azure AI Search
        Vertical slice routing - different knowledge bases per department
        """
        department = state.get("department", "General")
        team = state.get("team", "Support")
        summary = state['summary']
        description = state['description']
        
        query_text = f"{summary} {description}"
        
        try:
            search_results = search_manager.hybrid_search(
                query=query_text,
                department=department,
                team=team,
                top_k=5
            )
            
            if search_results:
                retrieved_docs = [
                    f"{result.get('id', 'unknown')}: {result.get('title', 'Untitled')}"
                    for result in search_results[:3]
                ]
            else:
                retrieved_docs = [
                    f"{department}-KB-001: General Support Guidelines",
                    f"{department}-KB-002: Escalation Procedures"
                ]
            
            return {
                "retrieved_docs": retrieved_docs
            }
        except Exception as e:
            print(f"Retrieve error: {e}")
            return {
                "retrieved_docs": [
                    f"{department}-KB-001: General Support Guidelines (fallback)"
                ]
            }
    
    def generate_node(self, state: TicketState) -> dict:
        """
        GenerateNode: Context-aware response generation using retrieved docs
        """
        department = state.get("department", "General")
        team = state.get("team", "Support")
        citations = state.get("retrieved_docs", [])
        
        system_prompt = f"""You are an AI assistant helping triage JIRA tickets for the {department} department, {team} team.

Generate a professional comment for the ticket that:
1. Acknowledges the issue
2. References relevant knowledge base articles (cite by ID)
3. Provides next steps or initial guidance
4. Suggests appropriate assignment

Keep responses concise (2-3 sentences). Be helpful but direct."""
        
        user_content = f"""Ticket: {state['summary']}
Description: {state['description']}
Classification: {department} > {team} (confidence: {state.get('classification_confidence', 0.0):.2f})
Priority: {state.get('suggested_priority', 'Medium')}
Knowledge Base: {', '.join(citations)}

Generate a triage comment:"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        try:
            response = self.llm.invoke(messages)
            generated_text = response.content
            
            return {
                "generated_comment": generated_text,
                "messages": [response]
            }
        except Exception as e:
            return {
                "generated_comment": f"This ticket has been received and classified as {department} - {team}. Assigning to {state.get('suggested_assignee', 'support@company.com')} for review.",
                "messages": [AIMessage(content=f"Generation error: {str(e)}")]
            }
    
    def policy_node(self, state: TicketState) -> dict:
        """
        PolicyNode: Enhanced policy evaluation using policy engine
        """
        ticket_data = {
            "reporter": state.get("reporter", ""),
            "redaction_flags": state.get("redaction_flags", [])
        }
        
        classification = {
            "department": state.get("department"),
            "suggested_priority": state.get("suggested_priority"),
            "confidence": state.get("classification_confidence", 0.0)
        }
        
        try:
            evaluation = policy_engine.evaluate_ticket(
                ticket_data=ticket_data,
                classification=classification,
                policy_flags=[]
            )
            
            return {
                "policy_flags": evaluation["policy_flags"],
                "requires_human_review": evaluation["requires_human_review"]
            }
        except Exception as e:
            print(f"Policy evaluation error: {e}")
            return {
                "policy_flags": ["policy_evaluation_error"],
                "requires_human_review": True
            }
    
    def process(self, ticket_data: dict) -> dict:
        """
        Process a ticket through the complete LangGraph workflow
        """
        initial_state = TicketState(
            ticket_id=ticket_data.get("ticket_id", ""),
            issue_key=ticket_data.get("issue_key", ""),
            summary=ticket_data.get("summary", ""),
            description=ticket_data.get("description", ""),
            issue_type=ticket_data.get("issue_type", ""),
            priority=ticket_data.get("priority", "Medium"),
            reporter=ticket_data.get("reporter", ""),
            redaction_flags=ticket_data.get("redaction_flags", []),
            department="",
            team="",
            suggested_priority="",
            suggested_assignee="",
            classification_confidence=0.0,
            retrieved_docs=[],
            generated_comment="",
            policy_flags=[],
            requires_human_review=False,
            messages=[]
        )
        
        final_state = self.graph.invoke(initial_state)
        
        result = {
            "ticket_id": final_state["ticket_id"],
            "issue_key": final_state["issue_key"],
            "classification": {
                "department": final_state.get("department"),
                "team": final_state.get("team"),
                "suggested_priority": final_state.get("suggested_priority"),
                "suggested_assignee": final_state.get("suggested_assignee"),
                "confidence": final_state.get("classification_confidence", 0.0)
            },
            "generated_comment": final_state.get("generated_comment"),
            "citations": final_state.get("retrieved_docs", []),
            "policy_flags": final_state.get("policy_flags", []),
            "confidence": final_state.get("classification_confidence", 0.0),
            "model_used": "gpt-5-langgraph",
            "requires_human_review": final_state.get("requires_human_review", False)
        }
        
        try:
            decision_logger.log_decision(
                ticket_id=result["ticket_id"],
                issue_key=result["issue_key"],
                decision_data=result
            )
        except Exception as e:
            print(f"Decision logging error: {e}")
        
        return result


agent = JIRATriageAgent()
