"""
Pydantic models for API requests and responses
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    """Request model for validator performance analysis"""

    address: str = Field(..., description="Validator SS58 address")
    change_session: int = Field(..., description="Session number when configuration change was made", gt=0)
    network: str = Field(default="kusama", description="Network (kusama or polkadot)")
    sessions_before: Optional[int] = Field(default=10, description="Number of sessions before change", gt=0)
    sessions_after: Optional[int] = Field(default=None, description="Number of sessions after change (None = auto-detect)")
    last_change_session: Optional[int] = Field(default=None, description="Previous change session for auto-calculating sessions_before")
    exclude_latest: bool = Field(default=True, description="Exclude latest session if incomplete")
    network_normalized: bool = Field(default=True, description="Use network-wide normalization (recommended)")
    detailed: bool = Field(default=False, description="Include session-by-session breakdown")
    comment: Optional[str] = Field(default=None, description="Optional comment for this analysis")

    @field_validator('network')
    @classmethod
    def validate_network(cls, v: str) -> str:
        if v.lower() not in ['kusama', 'polkadot']:
            raise ValueError('Network must be kusama or polkadot')
        return v.lower()

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        # Basic SS58 address validation (starts with letter, 47-48 chars)
        if not v or len(v) < 47 or len(v) > 48:
            raise ValueError('Invalid SS58 address format (must be 47-48 characters)')
        if not v[0].isalpha():
            raise ValueError('Invalid SS58 address format (must start with a letter)')
        return v


class SessionInfo(BaseModel):
    """Information about a single session"""
    session: int
    score: float
    grade: str
    is_para: bool
    era_points: Optional[int] = 0
    mvr: Optional[float] = 0.0
    bar: Optional[float] = 0.0
    missed_votes: Optional[int] = 0
    total_votes: Optional[int] = 0
    para_points: Optional[int] = 0
    ranking: Optional[Dict] = None
    network_stats: Optional[Dict] = None
    components: Optional[Dict] = None


class PeriodStats(BaseModel):
    """Statistics for a period (before or after)"""
    total_count: int
    para_count: int
    active_para: int
    inactive_para: int
    auth_only_count: int
    para_percentage: float
    aggregated_score: float
    aggregated_grade: str
    median_score: float
    min_score: float
    max_score: float
    aggregated_details: Optional[Dict] = None


class AnalyzeResponse(BaseModel):
    """Response model for validator performance analysis"""

    # Analysis metadata
    validator: str
    network: str
    change_session: int
    current_session: int
    excluded_current: bool
    comment: Optional[str] = None

    # Session data
    before_sessions: List[SessionInfo]
    after_sessions: List[SessionInfo]

    # Statistics
    before_stats: PeriodStats
    after_stats: PeriodStats

    # Comparison
    improvement: Optional[float]
    improvement_pct: Optional[float] = None
    direction: Optional[str] = None  # "improvement", "decline", "no_change"

    # Overall metrics
    overall_grade: str
    overall_auth_inclusion: float
    overall_para_inclusion: float

    # Analysis ID for sharing
    analysis_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""

    status: str = "healthy"
    timestamp: str
    cache_stats: Optional[Dict] = None
    uptime_seconds: Optional[float] = None


class ErrorResponse(BaseModel):
    """Response model for errors"""

    error: str
    message: str
    details: Optional[str] = None
