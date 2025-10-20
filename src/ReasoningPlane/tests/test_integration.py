"""
Integration Tests for JIRA Triage Agent
End-to-end workflow validation
"""

import pytest
from datetime import datetime
import sys
sys.path.insert(0, '../api')

from langgraph_agent import agent
from enhanced_policy_engine import policy_engine


class TestEndToEndWorkflow:
    """Test complete ticket processing workflow"""
    
    def test_database_ticket_classification(self):
        """Test IT/DBA ticket classification"""
        ticket_data = {
            "ticket_id": "test-001",
            "issue_key": "PROJ-123",
            "summary": "Database connection timeout",
            "description": "Cannot connect to staging database - timeout after 30 seconds",
            "issue_type": "Bug",
            "priority": "High",
            "reporter": "john@company.com",
            "redaction_flags": []
        }
        
        result = agent.process(ticket_data)
        
        assert result["ticket_id"] == "test-001"
        assert result["classification"]["department"] == "IT"
        assert result["classification"]["team"] in ["DBA", "DevOps", "Support"]
        assert result["confidence"] > 0.5
        assert result["generated_comment"] is not None
        assert len(result["citations"]) > 0
    
    def test_hr_onboarding_ticket(self):
        """Test HR/Onboarding ticket classification"""
        ticket_data = {
            "ticket_id": "test-002",
            "issue_key": "PROJ-124",
            "summary": "New contractor onboarding",
            "description": "Need to onboard new contractor starting next week - background check pending",
            "issue_type": "Task",
            "priority": "Medium",
            "reporter": "hr@company.com",
            "redaction_flags": []
        }
        
        result = agent.process(ticket_data)
        
        assert result["classification"]["department"] == "HR"
        assert result["classification"]["team"] == "Onboarding"
        assert "onboarding" in result["generated_comment"].lower() or "contractor" in result["generated_comment"].lower()
    
    def test_external_email_detection(self):
        """Test policy engine flags external emails"""
        ticket_data = {
            "ticket_id": "test-003",
            "issue_key": "PROJ-125",
            "summary": "Support request",
            "description": "Need help with account access",
            "issue_type": "Support",
            "priority": "Medium",
            "reporter": "external@gmail.com",
            "redaction_flags": []
        }
        
        result = agent.process(ticket_data)
        
        assert result["requires_human_review"] == True
        assert "external_contact_detected" in result["policy_flags"]
    
    def test_high_sensitivity_pii(self):
        """Test policy engine flags high-sensitivity PII"""
        ticket_data = {
            "ticket_id": "test-004",
            "issue_key": "PROJ-126",
            "summary": "Payment issue",
            "description": "Credit card was declined",
            "issue_type": "Bug",
            "priority": "High",
            "reporter": "user@company.com",
            "redaction_flags": ["credit_card_detected", "email_address_detected"]
        }
        
        result = agent.process(ticket_data)
        
        assert result["requires_human_review"] == True
        assert any("pii" in flag.lower() for flag in result["policy_flags"])
    
    def test_low_confidence_requires_review(self):
        """Test low confidence triggers human review"""
        ticket_data = {
            "ticket_id": "test-005",
            "issue_key": "PROJ-127",
            "summary": "Misc issue",
            "description": "Something is not working correctly",
            "issue_type": "Unknown",
            "priority": "Low",
            "reporter": "user@company.com",
            "redaction_flags": []
        }
        
        result = agent.process(ticket_data)
        
        if result["confidence"] < 0.7:
            assert result["requires_human_review"] == True


class TestPolicyEngine:
    """Test enhanced policy engine"""
    
    def test_sla_prediction_critical(self):
        """Test SLA prediction for critical priority"""
        evaluation = policy_engine.evaluate_ticket(
            ticket_data={"reporter": "user@company.com", "redaction_flags": []},
            classification={"department": "IT", "suggested_priority": "Critical", "confidence": 0.95},
            policy_flags=[]
        )
        
        assert evaluation["sla_target"] == 1.0
        assert evaluation["sla_breach_time"] is not None
    
    def test_external_email_detection(self):
        """Test external email detection"""
        is_external = policy_engine._is_external_email("user@gmail.com")
        assert is_external == True
        
        is_internal = policy_engine._is_external_email("user@company.com")
        assert is_internal == False
    
    def test_legal_department_requires_review(self):
        """Test Legal department always requires human review"""
        evaluation = policy_engine.evaluate_ticket(
            ticket_data={"reporter": "user@company.com", "redaction_flags": []},
            classification={"department": "Legal", "suggested_priority": "Medium", "confidence": 0.90},
            policy_flags=[]
        )
        
        assert evaluation["requires_human_review"] == True
        assert "department_policy_requires_review" in evaluation["policy_flags"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
