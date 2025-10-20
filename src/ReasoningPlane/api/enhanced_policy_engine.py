"""
Enhanced Policy Engine
SLA prediction, external email detection, escalation rules
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum


class Priority(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SLATarget:
    """SLA targets by priority level"""
    CRITICAL = timedelta(hours=1)
    HIGH = timedelta(hours=4)
    MEDIUM = timedelta(hours=24)
    LOW = timedelta(hours=72)


class EnhancedPolicyEngine:
    """
    Advanced policy enforcement engine with SLA prediction and escalation
    
    Features:
    - SLA breach prediction
    - External email detection and flagging
    - Automatic escalation rules
    - Confidence-based routing
    - Department-specific policies
    """
    
    def __init__(self):
        self.confidence_threshold = 0.7
        self.external_domain_whitelist = [
            "company.com",
            "internal.company.com",
            "corp.company.com"
        ]
        
        self.department_policies = {
            "Legal": {
                "requires_human_review": True,
                "min_confidence": 0.85,
                "sla_multiplier": 0.5
            },
            "Finance": {
                "requires_human_review": True,
                "min_confidence": 0.85,
                "sla_multiplier": 0.75
            },
            "HR": {
                "requires_human_review": False,
                "min_confidence": 0.70,
                "sla_multiplier": 1.0
            },
            "IT": {
                "requires_human_review": False,
                "min_confidence": 0.70,
                "sla_multiplier": 1.0
            }
        }
    
    def evaluate_ticket(
        self,
        ticket_data: Dict[str, Any],
        classification: Dict[str, Any],
        policy_flags: List[str]
    ) -> Dict[str, Any]:
        """
        Comprehensive policy evaluation for a ticket
        
        Args:
            ticket_data: Original ticket information
            classification: AI classification results
            policy_flags: Existing policy flags
            
        Returns:
            Enhanced policy decision with SLA, escalation, and routing
        """
        department = classification.get("department", "General")
        priority = classification.get("suggested_priority", "Medium")
        confidence = classification.get("confidence", 0.0)
        redaction_flags = ticket_data.get("redaction_flags", [])
        
        enhanced_flags = list(policy_flags)
        requires_human_review = False
        escalation_reason = []
        
        dept_policy = self.department_policies.get(department, {})
        dept_min_confidence = dept_policy.get("min_confidence", self.confidence_threshold)
        
        if confidence < dept_min_confidence:
            enhanced_flags.append("low_confidence_classification")
            requires_human_review = True
            escalation_reason.append(f"Confidence {confidence:.2f} below threshold {dept_min_confidence}")
        
        if self._is_external_email(ticket_data.get("reporter", "")):
            enhanced_flags.append("external_contact_detected")
            requires_human_review = True
            escalation_reason.append("External email address detected")
        
        high_risk_pii = ["us_ssn_detected", "credit_card_detected", "crypto_detected", "us_passport_detected"]
        if any(flag in redaction_flags for flag in high_risk_pii):
            enhanced_flags.append("high_sensitivity_pii")
            requires_human_review = True
            escalation_reason.append("High-sensitivity PII detected")
        
        if dept_policy.get("requires_human_review", False):
            enhanced_flags.append("department_policy_requires_review")
            requires_human_review = True
            escalation_reason.append(f"{department} department requires human review")
        
        if priority == Priority.CRITICAL:
            enhanced_flags.append("critical_priority_escalation")
            escalation_reason.append("Critical priority ticket")
        
        sla_prediction = self._predict_sla(priority, department)
        
        if self._should_auto_escalate(priority, confidence, requires_human_review):
            enhanced_flags.append("auto_escalated")
            escalation_reason.append("Automatic escalation triggered")
        
        return {
            "policy_flags": enhanced_flags,
            "requires_human_review": requires_human_review,
            "escalation_reason": escalation_reason,
            "sla_target": sla_prediction["target_hours"],
            "sla_warning_time": sla_prediction["warning_time"],
            "sla_breach_time": sla_prediction["breach_time"],
            "recommended_assignee": classification.get("suggested_assignee"),
            "auto_escalate": "auto_escalated" in enhanced_flags
        }
    
    def _is_external_email(self, email: str) -> bool:
        """
        Check if email is from external domain
        """
        if not email or "@" not in email:
            return False
        
        domain = email.split("@")[1].lower()
        return not any(domain.endswith(allowed) for allowed in self.external_domain_whitelist)
    
    def _predict_sla(
        self,
        priority: str,
        department: str
    ) -> Dict[str, Any]:
        """
        Predict SLA targets with department-specific adjustments
        """
        base_sla = {
            Priority.CRITICAL: SLATarget.CRITICAL,
            Priority.HIGH: SLATarget.HIGH,
            Priority.MEDIUM: SLATarget.MEDIUM,
            Priority.LOW: SLATarget.LOW
        }.get(priority, SLATarget.MEDIUM)
        
        dept_policy = self.department_policies.get(department, {})
        multiplier = dept_policy.get("sla_multiplier", 1.0)
        
        adjusted_sla = base_sla * multiplier
        
        current_time = datetime.utcnow()
        warning_time = current_time + (adjusted_sla * 0.75)
        breach_time = current_time + adjusted_sla
        
        return {
            "target_hours": adjusted_sla.total_seconds() / 3600,
            "warning_time": warning_time.isoformat(),
            "breach_time": breach_time.isoformat(),
            "adjusted_for_department": multiplier != 1.0
        }
    
    def _should_auto_escalate(
        self,
        priority: str,
        confidence: float,
        already_flagged: bool
    ) -> bool:
        """
        Determine if ticket should be automatically escalated
        """
        if priority == Priority.CRITICAL and confidence < 0.9:
            return True
        
        if priority == Priority.HIGH and confidence < 0.6:
            return True
        
        if already_flagged and priority in [Priority.CRITICAL, Priority.HIGH]:
            return True
        
        return False
    
    def get_escalation_path(self, department: str, team: str) -> List[str]:
        """
        Get escalation path for a department/team
        """
        escalation_paths = {
            "IT": {
                "DBA": ["dba-lead@company.com", "it-director@company.com", "cto@company.com"],
                "Security": ["security-lead@company.com", "ciso@company.com", "cto@company.com"],
                "DevOps": ["devops-lead@company.com", "it-director@company.com"]
            },
            "HR": {
                "Onboarding": ["hr-lead@company.com", "hr-director@company.com"],
                "Payroll": ["payroll-lead@company.com", "finance-director@company.com"]
            },
            "Finance": {
                "Accounting": ["accounting-lead@company.com", "cfo@company.com"]
            },
            "Legal": {
                "Contracts": ["legal-lead@company.com", "general-counsel@company.com"]
            }
        }
        
        return escalation_paths.get(department, {}).get(team, ["support@company.com", "escalations@company.com"])


policy_engine = EnhancedPolicyEngine()
