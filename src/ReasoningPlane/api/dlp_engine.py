"""
Enhanced DLP/Redaction Engine with ML-based PII Detection
Uses Presidio Analyzer and Anonymizer for advanced PII detection
"""

from typing import List, Tuple, Dict, Any
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult
import re


class EnhancedDLPEngine:
    """
    Enterprise-grade DLP engine with ML-based PII detection.
    Combines regex patterns with NER models for comprehensive coverage.
    """
    
    def __init__(self):
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        
        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        self.anonymizer = AnonymizerEngine()
        
        self.external_domain_pattern = re.compile(
            r'@(?!company\.com|internal\.company\.com)',
            re.IGNORECASE
        )
        
        self.pii_entity_types = [
            "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
            "CRYPTO", "DATE_TIME", "IBAN_CODE", "IP_ADDRESS", 
            "NRP", "LOCATION", "MEDICAL_LICENSE", "URL",
            "US_BANK_NUMBER", "US_DRIVER_LICENSE", "US_ITIN",
            "US_PASSPORT", "US_SSN", "UK_NHS"
        ]
    
    def redact_sensitive_data(self, text: str) -> Tuple[str, List[str]]:
        """
        Redact PII from text using both ML and regex patterns.
        
        Returns:
            Tuple of (redacted_text, list_of_detection_flags)
        """
        if not text:
            return "", []
        
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=self.pii_entity_types
        )
        
        flags = set()
        for result in results:
            flags.add(f"{result.entity_type.lower()}_detected")
        
        anonymizer_results = [
            RecognizerResult(entity_type=r.entity_type, start=r.start, end=r.end, score=r.score)
            for r in results
        ]
        
        anonymized_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=anonymizer_results,
            operators={
                "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
                "PERSON": OperatorConfig("replace", {"new_value": "[NAME_REDACTED]"}),
                "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL_REDACTED]"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE_REDACTED]"}),
                "CREDIT_CARD": OperatorConfig("replace", {"new_value": "[CARD_REDACTED]"}),
                "US_SSN": OperatorConfig("replace", {"new_value": "[SSN_REDACTED]"}),
                "LOCATION": OperatorConfig("replace", {"new_value": "[LOCATION_REDACTED]"}),
            }
        )
        
        if self.external_domain_pattern.search(text):
            flags.add("external_email_detected")
        
        return anonymized_result.text, list(flags)
    
    def detect_high_risk_content(self, text: str) -> Dict[str, Any]:
        """
        Detect high-risk content that requires mandatory human review.
        
        Returns:
            Dictionary with risk_score, risk_flags, and requires_review
        """
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=self.pii_entity_types
        )
        
        high_risk_entities = {"CREDIT_CARD", "US_SSN", "US_PASSPORT", "CRYPTO", "US_BANK_NUMBER"}
        risk_flags = []
        high_confidence_pii = 0
        
        for result in results:
            if result.entity_type in high_risk_entities:
                risk_flags.append(f"high_risk_{result.entity_type.lower()}")
                high_confidence_pii += 1
            elif result.score > 0.85:
                high_confidence_pii += 1
        
        if self.external_domain_pattern.search(text):
            risk_flags.append("external_sender")
            high_confidence_pii += 1
        
        risk_score = min(high_confidence_pii / 10.0, 1.0)
        requires_review = risk_score > 0.5 or len(risk_flags) > 0
        
        return {
            "risk_score": risk_score,
            "risk_flags": risk_flags,
            "requires_review": requires_review,
            "pii_count": len(results)
        }
    
    def validate_output_safety(self, generated_text: str) -> Tuple[bool, List[str]]:
        """
        Validate that AI-generated output doesn't contain leaked PII.
        
        Returns:
            Tuple of (is_safe, list_of_violations)
        """
        results = self.analyzer.analyze(
            text=generated_text,
            language="en",
            entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"]
        )
        
        violations = []
        for result in results:
            if result.score > 0.7:
                violations.append(f"leaked_{result.entity_type.lower()}")
        
        is_safe = len(violations) == 0
        return is_safe, violations


dlp_engine = EnhancedDLPEngine()
