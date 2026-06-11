export interface Catalyst {
  label: string;
  relationshipType: 'direct' | 'indirect';
  eventType: string;
  possibleInfluence: 'positive' | 'negative' | 'mixed' | 'unclear';
  confidence: 'low' | 'medium' | 'high' | 'tentative';
  impactPath?: string[];
  significance?: number;
}

export interface GuardrailMetadata {
  judgeStatus: 'passed' | 'regenerated_passed' | 'degraded' | 'skipped_empty' | 'skipped_no_llm_mock_mode' | 'not_run_synthesis_failed';
  judgeAttempts: number;
  judgeDefects: string[];
  regenerated: boolean;
  degraded: boolean;
}

export interface TickerSummary {
  summaryId: string;
  ticker: string;
  summaryHeadline: string;
  situationSummary: string;
  mainCatalysts: Catalyst[];
  overallPossibleInfluence: 'positive' | 'negative' | 'mixed' | 'unclear';
  confidence: 'low' | 'medium' | 'high' | 'tentative';
  uncertainties: string[];
  watchItems: string[];
  sourceEventIds: string[];
  sourceArticleUrls: string[];
  complianceDisclaimer?: string;
  notFinancialAdvice: boolean;
  guardrailMetadata?: GuardrailMetadata;
}

export interface EventEntry {
  eventId: string;
  eventType: string;
  headline: string;
  eventSummary: string;
  hardFacts: string[];
  possibleDirectionalPressure: 'positive' | 'negative' | 'mixed' | 'unclear';
  sourceArticleIds: string[];
  sourceUrl?: string;
  impactPath?: string[];
  reasonForRouting?: string;
  pathConfidence?: number;
}

export interface TickerBucket {
  ticker: string;
  directEvents: EventEntry[];
  crossImpactEvents: EventEntry[];
  suppressedDuplicateCount: number;
}

// Mirrors the article dicts built in backend/ingestion/news.py.
export interface RawArticle {
  articleId: string;
  sourceApi: string;
  sourceName: string;
  url: string;
  headline: string;
  summary: string;
  publishedAt: string;
  relatedTickers?: string[];
  queryTerms?: string[];
}

// Mirrors CanonicalEventOut (backend/iterations/contracts.py) plus the enrichment
// fields attached in backend/iterations/extraction.py after articleId reconciliation.
export interface CanonicalEvent {
  eventId: string;
  articleId: string;
  eventType: string;
  eventSummary: string;
  hardFacts: string[];
  mentionedTickers: string[];
  entities: string[];
  eventTags: string[];
  regions: string[];
  sectors: string[];
  commodities: string[];
  technologyThemes: string[];
  possibleDirectionalPressure: 'positive' | 'negative' | 'mixed' | 'unclear';
  uncertaintyNotes: string[];
  evidence: string[];
  sourceArticleIds: string[];
  relatedTickers: string[];
  sourceUrl?: string;
  sourceName?: string;
  sourceHeadline?: string;
  publishedAt?: string;
}

// Mirrors the candidate dicts built in backend/iterations/routing_nodes.py (direct)
// and backend/graph/graph.py route_cross_impact (indirect).
export interface RoutedCandidate {
  candidateId: string;
  ticker: string;
  relationshipType: 'direct' | 'indirect';
  eventId: string;
  impactPath: string[];
  pathConfidence: number;
  pathStrength?: 'strong' | 'weak';
  reasonForRouting: string;
  // Stamped by the ledger memory step (iterations 2/3).
  catalystId?: string;
  ledgerDecision?: 'new' | 'update' | 'duplicate';
}

export interface RunResult {
  runId: string;
  iteration: number;
  watchlist: string[];
  articlesCount: number;
  eventsCount: number;
  routedCount: number;
  duplicateCounts: Record<string, number>;
  tickerSyntheses: Record<string, TickerSummary>;
  rawArticles: RawArticle[];
  canonicalEvents: CanonicalEvent[];
  routedCandidates: RoutedCandidate[];
  tickerBuckets: Record<string, TickerBucket>;
}

export interface GraphNode {
  nodeId: string;
  nodeType: string;
  name: string;
  ticker?: string;
  queryTerms: string[];
}

export interface GraphEdge {
  fromNodeId: string;
  toNodeId: string;
  edgeType: string;
  strength: string;
  confidence: number;
  notes?: string;
}

export interface ExposureGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type ExpansionStatus = Record<string, { ticker: string; status: string; error?: string; addedNodes?: number; addedEdges?: number; updatedAt?: string }>;

export type LlmRouteSettings = Record<string, { provider: string; model: string }>;

export interface AppSettings {
  llmRoutes: LlmRouteSettings;
}

export const DEFAULT_SETTINGS: AppSettings = {
  llmRoutes: {
    extraction: { provider: '', model: '' },
    synthesis: { provider: '', model: '' },
    judge: { provider: '', model: '' },
    graph_expansion: { provider: '', model: '' }
  }
};

export const LLM_STEP_LABELS: Record<string, string> = {
  extraction: 'Extraction',
  synthesis: 'Synthesis',
  judge: 'Safety judge',
  graph_expansion: 'Graph expansion'
};


