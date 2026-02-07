"""schemas for CTI analysis outputs"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class ThreatActor(BaseModel):
    """threat actor information"""
    name: str
    aliases: List[str] = Field(default_factory=list)
    motivation: Optional[str] = None
    sophistication: Optional[str] = None
    targets: List[str] = Field(default_factory=list)

class TTPMapping(BaseModel):
    """MITRE ATT&CK TTP mapping"""
    ttp_id: str = Field(..., description="MITRE ATT&CK ID like T1550.001")
    ttp_name: str = Field(..., description="technique name")
    tactic: str = Field(..., description="tactic like Credential Access")
    description: str = Field(..., description="how technique applies to GCP")
    gcp_relevance: str = Field(..., description="GCP-specific context")
    priority: str = Field(..., description="HIGH/MEDIUM/LOW")
    evidence: List[str] = Field(default_factory=list, description="quotes from CTI")

class TTPMappingOutput(BaseModel):
    """output from ttp_mapper_agent"""
    ttps: List[TTPMapping] = Field(default_factory=list, description="list of mapped TTPs")
    total_ttps: int = Field(default=0, description="total number of TTPs mapped")

class CTIAnalysisOutput(BaseModel):
    """output from cti_analyzer_agent"""
    threat_summary: str = Field(..., description="executive summary of threats")
    threat_actors: List[ThreatActor] = Field(default_factory=list)
    objectives: List[str] = Field(default_factory=list, description="attacker goals")
    attack_vectors: List[str] = Field(default_factory=list)
    ttps: List[TTPMapping] = Field(default_factory=list)
    gcp_services_targeted: List[str] = Field(default_factory=list)
    key_indicators: List[str] = Field(default_factory=list)
    research_references: List[str] = Field(
        default_factory=list,
        description="URLs to official docs and research"
    )
