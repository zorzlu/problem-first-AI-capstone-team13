"""Pydantic request/response schemas for the FastAPI surface."""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RunRequest(BaseModel):
    iteration: int
    scenario_id: str
    simulated_now: Optional[str] = "2026-05-28T17:25:00Z"


class WatchlistRequest(BaseModel):
    tickers: List[str]


class ExpandRequest(BaseModel):
    ticker: str
    force: bool = True


class RebuildRequest(BaseModel):
    reset: bool = True


GraphNodeType = Literal[
    "ticker",
    "private_company",
    "country",
    "region",
    "policy_area",
    "government_agency",
    "technology_theme",
    "shipping_route",
    "risk_factor",
    "sector",
    "commodity",
]


GraphEdgeType = Literal[
    "supplier_of",
    "customer_of",
    "competitor_of",
    "partner_of",
    "technology_exposure",
    "regional_exposure",
    "shipping_exposure",
    "macro_sensitivity",
    "policy_exposure",
    "defense_exposure",
    "trade_exposure",
    "sector_exposure",
    "commodity_exposure",
]


class GraphNodeRequest(BaseModel):
    nodeId: str = Field(min_length=1)
    nodeType: GraphNodeType
    name: str = Field(min_length=1)
    ticker: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    queryTerms: List[str] = Field(default_factory=list)

    @field_validator("nodeId", "name", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("ticker", mode="before")
    @classmethod
    def _normalize_ticker(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized or None


class GraphEdgeRequest(BaseModel):
    fromNodeId: str = Field(min_length=1)
    toNodeId: str = Field(min_length=1)
    edgeType: GraphEdgeType
    strength: Literal["high", "medium", "low"] = "medium"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    notes: str = ""

    @field_validator("fromNodeId", "toNodeId", mode="before")
    @classmethod
    def _strip_node_id(cls, value: str) -> str:
        return str(value or "").strip()


class RuntimeSettingsRequest(BaseModel):
    llmRoutes: Dict[str, Dict[str, str]] = {}


class SuppressRouteRequest(BaseModel):
    """Remediation feedback: never route `ticker` from paths anchored at `anchorName`."""
    ticker: str = Field(min_length=1)
    anchorName: str = Field(min_length=1)
    reason: str = ""

    @field_validator("ticker", mode="before")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        return str(value or "").strip().upper()

    @field_validator("anchorName", mode="before")
    @classmethod
    def _strip_anchor(cls, value: str) -> str:
        return str(value or "").strip()


class RoutingOverridesRequest(BaseModel):
    """Full replacement payload for routing overrides."""
    suppressedRoutes: List[Dict[str, str]] = []
    extraBroadGeoNodes: List[str] = []
    notBroadGeoNodes: List[str] = []
