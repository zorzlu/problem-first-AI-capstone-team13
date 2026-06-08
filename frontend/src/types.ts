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

export interface RunResult {
  runId: string;
  iteration: number;
  watchlist: string[];
  articlesCount: number;
  eventsCount: number;
  routedCount: number;
  duplicateCounts: Record<string, number>;
  tickerSyntheses: Record<string, TickerSummary>;
  rawArticles: any[];
  canonicalEvents: any[];
  routedCandidates: any[];
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


