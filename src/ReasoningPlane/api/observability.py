"""
Application Insights Integration
Distributed tracing, metrics collection, and structured logging
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.tracer import Tracer
from opencensus.trace.samplers import ProbabilitySampler


class ObservabilityManager:
    """
    Application Insights manager for telemetry and monitoring
    
    Features:
    - Distributed tracing across .NET and Python components
    - Custom metrics tracking (latency, confidence, etc.)
    - Structured logging with correlation IDs
    - Performance monitoring
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        service_name: str = "ReasoningPlane"
    ):
        self.connection_string = connection_string or os.environ.get(
            "APPLICATIONINSIGHTS_CONNECTION_STRING"
        )
        self.service_name = service_name
        
        if not self.connection_string:
            print("Warning: Application Insights not configured. Logging to console only.")
            self.configured = False
            self._setup_console_logging()
            return
        
        self.configured = True
        self._setup_logging()
        self._setup_tracing()
    
    def _setup_console_logging(self):
        """Setup basic console logging when App Insights is not configured"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.service_name)
    
    def _setup_logging(self):
        """Configure Application Insights logging"""
        logger = logging.getLogger(self.service_name)
        logger.setLevel(logging.INFO)
        
        handler = AzureLogHandler(connection_string=self.connection_string)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(console_handler)
        
        self.logger = logger
    
    def _setup_tracing(self):
        """Configure distributed tracing"""
        if not self.configured:
            self.tracer = None
            return
        
        exporter = AzureExporter(connection_string=self.connection_string)
        sampler = ProbabilitySampler(rate=1.0)
        
        self.tracer = Tracer(
            exporter=exporter,
            sampler=sampler
        )
    
    def trace_ticket_processing(
        self,
        ticket_id: str,
        issue_key: str,
        operation: str
    ):
        """
        Create a distributed trace span for ticket processing
        
        Args:
            ticket_id: Unique ticket identifier
            issue_key: JIRA issue key
            operation: Operation name (classify, retrieve, generate, policy)
        """
        if not self.tracer:
            return None
        
        span = self.tracer.span(name=f"{operation}_ticket")
        span.add_attribute("ticket_id", ticket_id)
        span.add_attribute("issue_key", issue_key)
        span.add_attribute("operation", operation)
        return span
    
    def log_classification(
        self,
        ticket_id: str,
        department: str,
        team: str,
        confidence: float,
        latency_ms: int
    ):
        """Log classification event with metrics"""
        self.logger.info(
            f"Classification complete: {ticket_id}",
            extra={
                "custom_dimensions": {
                    "ticket_id": ticket_id,
                    "department": department,
                    "team": team,
                    "confidence": confidence,
                    "latency_ms": latency_ms,
                    "event_type": "classification"
                }
            }
        )
    
    def log_policy_decision(
        self,
        ticket_id: str,
        requires_review: bool,
        policy_flags: list,
        sla_hours: float
    ):
        """Log policy evaluation result"""
        self.logger.info(
            f"Policy evaluation: {ticket_id}",
            extra={
                "custom_dimensions": {
                    "ticket_id": ticket_id,
                    "requires_review": requires_review,
                    "policy_flags": ",".join(policy_flags),
                    "sla_hours": sla_hours,
                    "event_type": "policy_decision"
                }
            }
        )
    
    def log_error(
        self,
        ticket_id: str,
        error_message: str,
        error_type: str,
        stack_trace: Optional[str] = None
    ):
        """Log error with full context"""
        self.logger.error(
            f"Error processing ticket: {ticket_id}",
            extra={
                "custom_dimensions": {
                    "ticket_id": ticket_id,
                    "error_type": error_type,
                    "error_message": error_message,
                    "stack_trace": stack_trace,
                    "event_type": "error"
                }
            }
        )
    
    def track_metric(
        self,
        metric_name: str,
        value: float,
        properties: Optional[Dict[str, Any]] = None
    ):
        """
        Track custom metric in Application Insights
        
        Examples:
        - ticket_processing_latency
        - classification_confidence
        - human_review_rate
        - sla_compliance_rate
        """
        self.logger.info(
            f"Metric: {metric_name} = {value}",
            extra={
                "custom_dimensions": {
                    "metric_name": metric_name,
                    "metric_value": value,
                    "event_type": "metric",
                    **(properties or {})
                }
            }
        )
    
    def log_request(
        self,
        method: str,
        url: str,
        status_code: int,
        duration_ms: int
    ):
        """Log HTTP request"""
        self.logger.info(
            f"Request: {method} {url}",
            extra={
                "custom_dimensions": {
                    "method": method,
                    "url": url,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "event_type": "request"
                }
            }
        )


observability = ObservabilityManager()
