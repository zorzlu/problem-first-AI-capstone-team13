"""Pydantic schemas for golden test cases and eval results.

Golden cases are versioned JSON files defining expected behavior across iterations.
Each case contains articles, a watchlist, graph state, and suite-specific assertions.
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class GoldenArticle(BaseModel):
    """A real or synthetic article for golden case injection."""
    articleId: str = Field(description="Unique article ID")
    sourceApi: str = Field(default="mock", description="API source (mock, finnhub, currents, etc.)")
    sourceName: str = Field(description="News source name")
    url: str = Field(description="Article URL")
    headline: str = Field(description="Article headline")
    summary: str = Field(description="Article summary or full text")
    publishedAt: str = Field(description="ISO 8601 timestamp")
    relatedTickers: Optional[List[str]] = Field(default=None, description="Source-provided ticker hints")
    queryTerms: Optional[List[str]] = Field(default=None, description="Query terms that matched this article")


class Iter1Expected(BaseModel):
    """Expected outputs for iter1_direct suite (extraction + direct routing only)."""
    events: List[Dict[str, Any]] = Field(description="Expected extracted events with eventType, eventSummary")
    directRoutes: List[str] = Field(description="Tickers that must be routed directly")
    forbiddenRoutes: List[str] = Field(default_factory=list, description="Tickers that must NOT be routed")
    requiredSyntheses: List[str] = Field(default_factory=list, description="Tickers that must have synthesis")


class Iter2ExpectedStep(BaseModel):
    """Expected dedup/ledger state for one step of iter2_memory."""
    ledgerDecisions: Dict[str, Literal["new", "update", "duplicate"]] = Field(
        description="Per-articleId: was it new, updated existing, or marked duplicate?"
    )
    duplicateCountsAtLeast: Dict[str, int] = Field(default_factory=dict, description="Minimum duplicate counts per ticker")
    ledgerLiveEntriesEquals: Dict[str, int] = Field(default_factory=dict, description="Expected live entries per ticker")
    expectedNewFactSubstrings: List[str] = Field(default_factory=list, description="Fact substrings that must appear if new")


class Iter3RouteExpectation(BaseModel):
    """One expected route for iter3_cross_impact."""
    ticker: str = Field(description="Target ticker")
    pathMustIncludeAnyOf: List[str] = Field(default_factory=list, description="Route must include at least one of these nodes")
    minPathConfidence: float = Field(default=0.0, description="Minimum path confidence")


class Iter3Expected(BaseModel):
    """Expected outputs for iter3_cross_impact suite (cross-impact routing + paths)."""
    indirectRoutes: List[Iter3RouteExpectation] = Field(default_factory=list, description="Expected indirect routes")
    forbiddenIndirectRoutes: List[Dict[str, str]] = Field(default_factory=list, description="Routes that must NOT exist")
    pathValidity: bool = Field(default=True, description="All paths must be valid (no cycles, proper graph structure)")


class JudgeLabel(BaseModel):
    """Human label for judge calibration case."""
    passes: bool = Field(description="Judge should pass or fail")
    groundingPassed: bool = Field(default=True, description="Claims are grounded")
    advicePassed: bool = Field(default=True, description="No trading advice")
    pathPassed: bool = Field(default=True, description="Path stays in bounds")
    defectNotes: List[str] = Field(default_factory=list, description="Specific defects if failing")


class JudgeCalibrationExpected(BaseModel):
    """Expected judge verdict for judge_calibration suite."""
    input: Dict[str, Any] = Field(description="Input synthesis to judge")
    labels: JudgeLabel = Field(description="Expected judge verdict")


class GoldenStep(BaseModel):
    """One step in a golden case (article injection + expected outputs)."""
    stepId: str = Field(description="Step identifier within case")
    articles: List[GoldenArticle] = Field(description="Articles to inject at this step")
    expected: Dict[str, Any] = Field(description="Suite-specific expected block (Iter1Expected | Iter2ExpectedStep | Iter3Expected | JudgeCalibrationExpected)")


class GoldenCase(BaseModel):
    """One golden test case for eval suites."""
    schemaVersion: int = Field(default=1, description="Golden schema version")
    caseId: str = Field(description="Unique case ID across all suites")
    suite: Literal[
        "iter1_direct",
        "iter2_memory",
        "iter3_cross_impact",
        "judge_calibration",
    ] = Field(description="Which eval suite this case belongs to")
    iteration: int = Field(description="Workflow iteration (1, 2, or 3)")
    description: str = Field(description="Human-readable case description")
    tags: List[str] = Field(default_factory=list, description="Categorization tags (e.g., negative, false_butterfly, high_priority)")
    watchlist: List[str] = Field(description="Stock tickers being watched")
    simulatedNow: str = Field(description="ISO 8601 timestamp for 'now' in this case")
    graphFixture: Any = Field(
        default="seed",
        description='Either "seed" (use default seed graph) or {nodes, edges} dict for custom graph state'
    )
    steps: List[GoldenStep] = Field(description="Ordered steps; usually 1 for iter1/iter3, N for iter2 memory progression")
    labels: Optional[Dict[str, str]] = Field(default=None, description="Metadata: annotator, labeledAt, notes")


class EvalResult(BaseModel):
    """Result of running one golden case through eval harness."""
    caseId: str = Field(description="Golden case ID")
    suite: str = Field(description="Suite name")
    passed: bool = Field(description="Overall pass/fail")
    metrics: Dict[str, Any] = Field(description="Suite-specific metrics")
    errors: List[str] = Field(default_factory=list, description="Assertion failures or exceptions")


class EvalReport(BaseModel):
    """Summary of running a full eval suite."""
    suite: str = Field(description="Suite name")
    timestamp: str = Field(description="ISO 8601 timestamp of eval run")
    totalCases: int = Field(description="Total cases in suite")
    passedCases: int = Field(description="Cases that passed all assertions")
    failedCases: int = Field(description="Cases that failed")
    results: List[EvalResult] = Field(description="Per-case results")
    notes: str = Field(default="", description="Optional summary notes")
