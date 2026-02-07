"""schemas for test payload generation and validation"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any

class TestPayload(BaseModel):
    """single test payload for detection rule"""
    payload_type: Literal["TP", "FN", "FP", "TN"] = Field(
        ...,
        description="True Positive, False Negative, False Positive, True Negative"
    )
    description: str = Field(..., description="what this payload tests")
    log_entry: Dict[str, Any] = Field(..., description="GCP audit log JSON")
    expected_alert: bool = Field(..., description="should this trigger detection")
    evasion_technique: Optional[str] = Field(
        None,
        description="for FN: what evasion is used"
    )
    legitimate_scenario: Optional[str] = Field(
        None,
        description="for FP/TN: why this is normal activity"
    )
    timestamp: str = Field(..., description="ISO timestamp")

class TestPayloadSet(BaseModel):
    """complete set of test payloads for a rule"""
    rule_id: str = Field(..., description="sigma rule ID this tests")
    rule_title: str = Field(..., description="sigma rule title")
    payloads: List[TestPayload] = Field(default_factory=list)
    total_tp: int = Field(0, description="count of true positives")
    total_fn: int = Field(0, description="count of false negatives")
    total_fp: int = Field(0, description="count of false positives")
    total_tn: int = Field(0, description="count of true negatives")

class TestMetrics(BaseModel):
    """calculated metrics from test execution"""
    rule_id: str
    expected: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="expected results: {TP: [...], FN: [...], FP: [...], TN: [...]}"
    )
    actual_alerts: List[str] = Field(
        default_factory=list,
        description="payloads that actually triggered alerts"
    )
    true_positives: int = Field(0, description="correctly detected attacks")
    false_negatives: int = Field(0, description="missed attacks")
    false_positives: int = Field(0, description="false alarms")
    true_negatives: int = Field(0, description="correctly ignored benign")
    precision: float = Field(0.0, description="TP / (TP + FP)")
    recall: float = Field(0.0, description="TP / (TP + FN)")
    f1_score: float = Field(0.0, description="harmonic mean of precision/recall")

class TestValidationOutput(BaseModel):
    """output from test_validator_agent"""
    rule_id: str
    valid: bool = Field(..., description="all tests structurally valid")
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    payloads_validated: int = Field(0)
    validation_details: Optional[str] = Field(None)
