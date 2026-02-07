"""schemas for LLM judge quality evaluation"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict

class SecurityCheck(BaseModel):
    """individual security validation check"""
    type: str = Field(..., description="check type like INVALID_SIGMA_SYNTAX")
    status: Literal["PASS", "FAIL", "WARN"] = Field(...)
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(...)
    details: str = Field(..., description="what was found")

class RuleAssessment(BaseModel):
    """LLM judge assessment of single rule"""
    rule_id: str
    rule_title: str
    ttp_alignment_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="does rule detect mapped MITRE technique"
    )
    test_coverage_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="are edge cases covered"
    )
    false_positive_risk: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ...,
        description="risk of false alarms based on actual FP count"
    )
    evasion_resistance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="difficulty for attacker to bypass"
    )
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="overall quality 0.0-1.0"
    )
    deployment_recommendation: Literal["APPROVE", "CONDITIONAL", "REJECT"] = Field(
        ...,
        description="deploy decision"
    )
    issues: List[str] = Field(
        default_factory=list,
        description="problems found"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="improvement suggestions"
    )
    fn_analysis: Optional[str] = Field(
        None,
        description="are FN payloads actually hard to detect or rule defect"
    )

class DetectionQualityReport(BaseModel):
    """complete quality report from LLM judge"""
    overall_quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="avg quality across all rules"
    )
    deployment_recommendation: Literal["APPROVE", "CONDITIONAL", "REJECT"] = Field(
        ...,
        description="overall deployment decision"
    )
    rule_assessments: List[RuleAssessment] = Field(default_factory=list)
    metrics: Dict[str, Dict] = Field(
        default_factory=dict,
        description="empirical metrics from ELK tests per rule"
    )
    critical_issues: List[SecurityCheck] = Field(
        default_factory=list,
        description="critical security issues found"
    )
    summary: str = Field(..., description="executive summary")
    timestamp: str = Field(..., description="evaluation timestamp")
