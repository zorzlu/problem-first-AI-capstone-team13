"""Structured contracts for LangGraph iteration workflows."""
import operator
from typing import Annotated, Any, Dict, List, Literal, TypedDict

from pydantic import BaseModel, Field


EventType = Literal[
    "earnings", "guidance", "supply_chain", "regulatory", "legal", "macro",
    "geopolitical", "commodity", "sector", "private_company_technology",
    "natural_disaster", "market_attention", "other",
]
DirectionalPressure = Literal["positive", "negative", "mixed", "unclear"]
ConfidenceLevel = Literal["low", "medium", "high", "tentative"]


class CanonicalEventOut(BaseModel):
    """One extracted catalyst event."""
    articleId: str = Field(description="The exact articleId of the source article")
    eventType: EventType
    eventSummary: str = Field(description="One sentence summarizing the key catalyst event")
    hardFacts: List[str] = Field(description="Grounded facts, numbers, dates mentioned in the text")
    mentionedTickers: List[str] = Field(
        default_factory=list,
        description="Public-company ticker symbols explicitly mentioned in or confidently mapped from the article text using the provided ticker alias map",
    )
    entities: List[str] = Field(description="Companies, products, routes, places, or platforms involved")
    eventTags: List[str] = Field(description="Normalized keywords useful for graph matching")
    regions: List[str] = Field(description="Countries or regions affected")
    sectors: List[str] = Field(description="Economic sectors affected")
    commodities: List[str] = Field(description="Commodities affected")
    technologyThemes: List[str] = Field(description="Specific technology sub-themes, if any")
    possibleDirectionalPressure: DirectionalPressure = Field(description="Short-term intraday influence")
    uncertaintyNotes: List[str] = Field(description="Key uncertainties remaining from this article")
    evidence: List[str] = Field(description="Verbatim phrases from the article proving the hard facts")


class ExtractionResult(BaseModel):
    """Top-level wrapper: structured outputs require an object root."""
    events: List[CanonicalEventOut]


class MainCatalystOut(BaseModel):
    eventId: str = Field(description="The exact eventId of the corresponding event in the context")
    label: str = Field(description="Short catalyst title")
    relationshipType: Literal["direct", "indirect"]
    eventType: str
    possibleInfluence: DirectionalPressure
    confidence: ConfidenceLevel
    recency: Literal["breaking", "recent", "background"]
    impactPath: List[str] = Field(description="Ordered list of nodes describing the impact path")
    significance: int = Field(description="Intraday significance score from 1 to 10 for this ticker today")


class SynthesisOut(BaseModel):
    """Per-ticker catalyst briefing."""
    summaryHeadline: str
    situationSummary: str
    mainCatalysts: List[MainCatalystOut]
    overallPossibleInfluence: DirectionalPressure
    confidence: ConfidenceLevel
    uncertainties: List[str]
    watchItems: List[str]


class OutputSafetyJudgeOut(BaseModel):
    passes: bool = Field(description="True if the synthesis output passes safety, grounding, path, and advice checks")
    groundingPassed: bool = Field(description="True if every claim is grounded and supported by the ticker context bucket")
    advicePassed: bool = Field(description="True if the synthesis contains no trading recommendations or action language")
    pathPassed: bool = Field(description="True if indirect explanations stay inside the supplied impact path")
    defects: List[str] = Field(description="Specific safety or grounding defects")
    regenerationInstruction: str = Field(description="Correction instruction for regeneration when the judge fails")


class WorkflowState(TypedDict):
    iteration: int
    watchlist: List[str]
    scenario_id: str
    simulated_now: str
    articles: List[Dict[str, Any]]
    canonical_events: List[Dict[str, Any]]
    routed_candidates: List[Dict[str, Any]]
    ticker_buckets: Dict[str, Dict[str, Any]]
    ticker_syntheses: Dict[str, Dict[str, Any]]
    duplicate_counts: Dict[str, int]
    ticker_synthesis_results: Annotated[List[Dict[str, Any]], operator.add]
    ingestion_metadata: Dict[str, Any]
    expansion_keywords: List[str]
    expansion_tickers: List[str]
    llm_failed: bool
    failure_reason: str
