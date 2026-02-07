"""schemas for sigma rule generation"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any

class SigmaLogSource(BaseModel):
    """sigma logsource specification"""
    product: str = Field(..., description="product like 'gcp'")
    service: str = Field(..., description="service like 'gcp.audit'")
    category: Optional[str] = Field(None, description="optional category")

class SigmaDetection(BaseModel):
    """sigma detection logic"""
    selection: Dict[str, Any] = Field(..., description="fields to match")
    filter_legitimate: Optional[Dict[str, Any]] = Field(
        None,
        description="legitimate activity to exclude"
    )
    condition: str = Field(..., description="detection condition")

class TestScenarios(BaseModel):
    """test scenarios for rule validation"""
    true_positive: str = Field(..., description="malicious activity that should alert")
    false_negative: str = Field(..., description="evasion that won't alert")
    false_positive: str = Field(..., description="benign activity that might false alarm")
    true_negative: str = Field(..., description="normal activity that shouldn't alert")
    log_source_schema: str = Field(..., description="link to log format docs")
    example_log_fields: Dict[str, str] = Field(
        default_factory=dict,
        description="example field values from real logs"
    )

class SigmaRule(BaseModel):
    """complete sigma rule structure"""
    title: str = Field(..., description="descriptive title")
    id: str = Field(..., description="unique UUID")
    status: Literal["stable", "experimental", "deprecated"] = Field(
        "experimental",
        description="rule maturity"
    )
    description: str = Field(..., description="what this rule detects")
    references: List[str] = Field(
        default_factory=list,
        description="links to official docs and research"
    )
    author: str = Field(default="Automated Detection Agent")
    date: str = Field(..., description="creation date YYYY-MM-DD")
    modified: Optional[str] = Field(None, description="last modified date")
    tags: List[str] = Field(
        default_factory=list,
        description="MITRE tags like attack.credential_access, attack.t1550.001"
    )
    logsource: SigmaLogSource
    detection: SigmaDetection
    falsepositives: List[str] = Field(
        default_factory=list,
        description="known false positive scenarios"
    )
    level: Literal["informational", "low", "medium", "high", "critical"] = Field(
        "medium",
        description="severity level"
    )
    fields: List[str] = Field(
        default_factory=list,
        description="important fields to include in alerts"
    )
    test_scenarios: TestScenarios = Field(
        ...,
        description="test cases for validation"
    )

class SigmaRuleOutput(BaseModel):
    """output from sigma_generator_agent"""
    rules: List[SigmaRule] = Field(default_factory=list)
    total_rules: int = Field(0, description="count of generated rules")
    ttp_coverage: List[str] = Field(
        default_factory=list,
        description="list of MITRE TTPs covered"
    )
    generation_notes: Optional[str] = Field(
        None,
        description="notes about rule generation process"
    )
