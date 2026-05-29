import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Plus, Search, ExternalLink, Network, Database, ShieldAlert, Cpu, Layers, Maximize2, X, RefreshCw, Menu, ChevronDown, ChevronUp, Clock, AlertCircle } from 'lucide-react';

interface Catalyst {
  label: string;
  relationshipType: 'direct' | 'indirect';
  eventType: string;
  possibleInfluence: 'positive' | 'negative' | 'mixed' | 'unclear';
  confidence: 'low' | 'medium' | 'high' | 'tentative';
  impactPath?: string[];
}

interface GuardrailMetadata {
  judgeStatus: 'passed' | 'regenerated_passed' | 'degraded' | 'skipped_empty' | 'skipped_no_llm_mock_mode' | 'not_run_synthesis_failed';
  judgeAttempts: number;
  judgeDefects: string[];
  regenerated: boolean;
  degraded: boolean;
}

interface TickerSummary {
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

interface EventEntry {
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

interface TickerBucket {
  ticker: string;
  directEvents: EventEntry[];
  crossImpactEvents: EventEntry[];
  suppressedDuplicateCount: number;
}

interface RunResult {
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

interface GraphNode {
  nodeId: string;
  nodeType: string;
  name: string;
  ticker?: string;
  queryTerms: string[];
}

interface GraphEdge {
  fromNodeId: string;
  toNodeId: string;
  edgeType: string;
  strength: string;
  confidence: number;
  notes?: string;
}

interface ExposureGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

type ExpansionStatus = Record<string, { ticker: string; status: string; error?: string; addedNodes?: number; addedEdges?: number; updatedAt?: string }>;

// ---------------------------------------------------------------------------
// Exposure-graph layout + rendering (shared by the sidebar card and the modal)
// ---------------------------------------------------------------------------
const MID_NODE_TYPES = ['technology_theme', 'private_company', 'sector'];

// Evenly distribute nodes into 3 columns (source factors -> themes/companies -> tickers)
// and space them vertically by column count so the canvas never overlaps regardless of size.
function computeLayout(nodes: GraphNode[], width: number, height: number) {
  const padX = Math.max(38, width * 0.1);
  const padY = Math.max(18, height * 0.06);
  const cols: { left: GraphNode[]; mid: GraphNode[]; right: GraphNode[] } = { left: [], mid: [], right: [] };
  for (const n of nodes) {
    if (n.nodeType === 'ticker') cols.right.push(n);
    else if (MID_NODE_TYPES.includes(n.nodeType)) cols.mid.push(n);
    else cols.left.push(n);
  }
  const xs = { left: padX, mid: width / 2, right: width - padX };
  const positions = new Map<string, { x: number; y: number }>();
  (['left', 'mid', 'right'] as const).forEach(col => {
    const arr = cols[col];
    arr.forEach((n, i) => {
      const y = padY + (height - 2 * padY) * (i + 1) / (arr.length + 1);
      positions.set(n.nodeId, { x: xs[col], y });
    });
  });
  return positions;
}

function getNodeColor(nodeType: string, isHighlighted: boolean) {
  if (isHighlighted) return 'var(--accent-purple)';
  switch (nodeType) {
    case 'ticker': return 'var(--accent-purple)';
    case 'technology_theme': return 'var(--accent-blue)';
    case 'private_company': return 'var(--accent-cyan)';
    case 'sector': return 'var(--accent-cyan)';
    default: return 'var(--accent-orange)'; // region, risk_factor, shipping_route, commodity
  }
}

function GraphView({ graphData, width, height, scale = 1, selectedCatalystPath }: {
  graphData: ExposureGraph;
  width: number;
  height: number;
  scale?: number;
  selectedCatalystPath: string[] | null;
}) {
  if (graphData.nodes.length === 0) {
    return <div className="canvas-placeholder">Loading graph nodes...</div>;
  }
  const positions = computeLayout(graphData.nodes, width, height);
  const fontSize = 6.5 * scale;
  const nodeById = new Map(graphData.nodes.map(n => [n.nodeId, n]));

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" style={{ background: '#07080d' }}>
      {/* Edges */}
      {graphData.edges.map((edge, idx) => {
        const fromPos = positions.get(edge.fromNodeId);
        const toPos = positions.get(edge.toNodeId);
        if (!fromPos || !toPos) return null;

        let isHighlighted = false;
        if (selectedCatalystPath) {
          const fromNode = nodeById.get(edge.fromNodeId);
          const toNode = nodeById.get(edge.toNodeId);
          if (fromNode && toNode) {
            const fromIdx = selectedCatalystPath.indexOf(fromNode.name);
            const toIdx = selectedCatalystPath.indexOf(toNode.name);
            if (fromIdx !== -1 && toIdx !== -1 && Math.abs(fromIdx - toIdx) === 1) isHighlighted = true;
          }
        }

        return (
          <line
            key={idx}
            x1={fromPos.x} y1={fromPos.y} x2={toPos.x} y2={toPos.y}
            stroke={isHighlighted ? 'var(--accent-cyan)' : '#27272a'}
            strokeWidth={(isHighlighted ? 2.5 : 1) * scale}
            strokeDasharray={edge.edgeType.includes('exposure') ? `${3 * scale},${3 * scale}` : 'none'}
            opacity={selectedCatalystPath && !isHighlighted ? 0.2 : 0.8}
          />
        );
      })}

      {/* Nodes */}
      {graphData.nodes.map((node) => {
        const pos = positions.get(node.nodeId);
        if (!pos) return null;
        const isHighlighted = selectedCatalystPath?.includes(node.name) || false;
        const r = (node.nodeType === 'ticker' ? 6 : 4.5) * scale;
        const labelOffset = (node.nodeType === 'ticker' ? 8 : -8) * scale;
        const textAnchor = node.nodeType === 'ticker' ? 'start' : 'end';

        return (
          <g key={node.nodeId} opacity={selectedCatalystPath && !isHighlighted ? 0.35 : 1} style={{ cursor: 'help' }}>
            <circle
              cx={pos.x} cy={pos.y} r={r}
              fill={getNodeColor(node.nodeType, isHighlighted)}
              stroke={isHighlighted ? 'white' : 'transparent'} strokeWidth={scale}
            />
            <text
              x={pos.x + labelOffset} y={pos.y + 3 * scale}
              fill={isHighlighted ? 'white' : 'var(--text-secondary)'}
              fontSize={`${fontSize}px`}
              fontWeight={node.nodeType === 'ticker' || isHighlighted ? 'bold' : 'normal'}
              textAnchor={textAnchor}
            >
              {node.ticker ? `${node.name} (${node.ticker})` : node.name}
            </text>
            <title>{`${node.name}${node.ticker ? ` (${node.ticker})` : ''} (${node.nodeType})\nQuery terms: ${node.queryTerms.join(', ')}`}</title>
          </g>
        );
      })}
    </svg>
  );
}

export default function App() {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [newTicker, setNewTicker] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [iteration, setIteration] = useState<number>(3);
  const [scenarioId, setScenarioId] = useState<string>('live');
  const [activeTicker, setActiveTicker] = useState<string>('dashboard');
  const [runResults, setRunResults] = useState<Record<number, RunResult | null>>({});
  const runResult = runResults[iteration] || null;
  const [graphData, setGraphData] = useState<ExposureGraph>({ nodes: [], edges: [] });
  const [ledgerEntries, setLedgerEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [phoenixStatus, setPhoenixStatus] = useState<any>({ running: false, dashboardUrl: '' });
  const [selectedCatalystPath, setSelectedCatalystPath] = useState<string[] | null>(null);
  const [memoryStatus, setMemoryStatus] = useState<any>(null);
  const [graphModalOpen, setGraphModalOpen] = useState(false);
  const [graphStatus, setGraphStatus] = useState<ExpansionStatus>({});

  // Dashboard Tabs & Status Bar states
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [ledgerExpanded, setLedgerExpanded] = useState(false);
  const [activeDashTab, setActiveDashTab] = useState<'watchlist' | 'ledger'>('watchlist');
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [addTickerOpen, setAddTickerOpen] = useState(false);
  const [synthesisExpanded, setSynthesisExpanded] = useState(false);
  const [selectedBackgroundStory, setSelectedBackgroundStory] = useState<string | null>(null);
  const [summaryDetailExpanded, setSummaryDetailExpanded] = useState(false);


  // Time conversion helper
  const formatRelativeTime = (publishedAt: string): string => {
    if (!publishedAt) return '—';
    const pub = new Date(publishedAt).getTime();
    const now = scenarioId === 'live' ? Date.now() : new Date('2026-05-28T17:25:00Z').getTime();
    const diffMs = now - pub;
    const diffMins = Math.max(0, Math.floor(diffMs / 60000));
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  const getEventDecision = (eventId: string): string => {
    if (!runResult || !runResult.routedCandidates) return 'new';
    const cand = runResult.routedCandidates.find(c => c.eventId === eventId && c.ticker === activeTicker);
    return cand?.ledgerDecision || 'new';
  };

  const getEventCatalystId = (eventId: string): string | null => {
    if (!runResult || !runResult.routedCandidates) return null;
    const cand = runResult.routedCandidates.find(c => c.eventId === eventId && c.ticker === activeTicker);
    return cand?.catalystId || null;
  };

  const getEventTimestamp = (sourceArticleIds: string[]): string | null => {
    if (!runResult || !runResult.rawArticles || !sourceArticleIds || sourceArticleIds.length === 0) return null;
    const art = runResult.rawArticles.find(a => sourceArticleIds.includes(a.articleId));
    return art?.publishedAt || null;
  };

  // Removed initial load; now handled by connection manager check below

  useEffect(() => {
    fetchLedger();
  }, [iteration]);

  // Poll expansion status while any ticker is pending/running, refreshing the graph as
  // edges land. The effect re-arms on each graphStatus change and stops once all settle.
  useEffect(() => {
    const active = Object.values(graphStatus).some(s => s.status === 'pending' || s.status === 'running');
    if (!active) return;
    const t = setTimeout(() => {
      fetchGraphStatus();
      fetchGraph();
    }, 2500);
    return () => clearTimeout(t);
  }, [graphStatus]);

  const fetchWatchlist = async () => {
    try {
      const res = await fetch('/api/watchlist');
      const data = await res.json();
      setWatchlist(data.tickers);
      if (data.tickers.length > 0 && !activeTicker) {
        setActiveTicker('dashboard');
      }
    } catch (e) {
      console.error('Error fetching watchlist', e);
    }
  };

  const fetchGraph = async () => {
    try {
      const res = await fetch('/api/graph');
      const data = await res.json();
      setGraphData(data);
    } catch (e) {
      console.error('Error fetching graph', e);
    }
  };

  const fetchGraphStatus = async () => {
    try {
      const res = await fetch('/api/graph/status');
      const data = await res.json();
      setGraphStatus(data.status || {});
    } catch (e) {
      console.error('Error fetching graph status', e);
    }
  };

  // Manually (re-)run the LLM exposure-graph expansion for a ticker.
  const triggerExpansion = async (ticker: string) => {
    try {
      const res = await fetch('/api/graph/expand', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, force: true })
      });
      const data = await res.json();
      setGraphStatus(data.expansionStatus || {});
    } catch (e) {
      console.error('Error triggering graph expansion', e);
    }
  };

  // Rebuild the whole graph for every watchlist ticker. reset=true restores the curated
  // seed first (dropping accumulated LLM additions); reset=false refreshes additively.
  const rebuildGraph = async (reset: boolean) => {
    if (reset && !confirm('Reset the exposure graph to its curated seed and re-expand every watchlist ticker? This discards all accumulated LLM-generated nodes/edges.')) return;
    try {
      const res = await fetch('/api/graph/rebuild', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset })
      });
      const data = await res.json();
      setGraphStatus(data.expansionStatus || {});
      fetchGraph();
    } catch (e) {
      console.error('Error rebuilding graph', e);
    }
  };

  // Resolves the display status for a ticker: explicit status entry, else "ready" if a
  // node already exists in the graph (seeded), else "none".
  const graphStatusFor = (ticker: string): string => {
    const s = graphStatus[ticker]?.status;
    if (s) return s;
    return graphData.nodes.some(n => n.nodeId === `ticker_${ticker}`) ? 'ready' : 'none';
  };

  const fetchResults = async () => {
    try {
      const res = await fetch('/api/results');
      if (res.ok) {
        const data = await res.json();
        if (data) {
          const formatted: Record<number, RunResult> = {};
          Object.entries(data).forEach(([k, v]) => {
            formatted[Number(k)] = v as RunResult;
          });
          setRunResults(formatted);
        }
      }
    } catch (e) {
      console.error('Error fetching run results', e);
    }
  };

  const fetchLedger = async () => {
    try {
      const res = await fetch(`/api/ledger?iteration=${iteration}`);
      const data = await res.json();
      setLedgerEntries(data);
    } catch (e) {
      console.error('Error fetching ledger', e);
    }
  };

  const fetchPhoenixStatus = async () => {
    try {
      const res = await fetch('/api/phoenix-status');
      const data = await res.json();
      setPhoenixStatus(data);
    } catch (e) {
      console.error('Error fetching Phoenix status', e);
    }
  };

  const fetchMemoryStatus = async () => {
    try {
      const res = await fetch('/api/memory-status');
      const data = await res.json();
      setMemoryStatus(data);
    } catch (e) {
      console.error('Error fetching memory status', e);
    }
  };

  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'failed'>('connecting');
  const [retryCount, setRetryCount] = useState(0);

  const checkConnectionDirect = async (): Promise<boolean> => {
    try {
      const res = await fetch('/api/watchlist');
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.tickers);
        if (data.tickers.length > 0 && !activeTicker) {
          setActiveTicker('dashboard');
        }
        // Fetch all other data on successful connection
        fetchGraph();
        fetchGraphStatus();
        fetchResults();
        fetchPhoenixStatus();
        fetchMemoryStatus();
        setConnectionState('connected');
        return true;
      }
    } catch (e) {
      console.warn('Backend connection attempt failed:', e);
    }
    return false;
  };

  useEffect(() => {
    let intervalId: any;
    let elapsed = 0;

    const runCheck = async () => {
      const success = await checkConnectionDirect();
      if (!success) {
        intervalId = setInterval(async () => {
          elapsed += 10;
          if (elapsed >= 90) { // 1.5 minutes
            setConnectionState('failed');
            clearInterval(intervalId);
          } else {
            setRetryCount(c => c + 1);
            const ok = await checkConnectionDirect();
            if (ok) {
              clearInterval(intervalId);
            }
          }
        }, 10000);
      }
    };

    runCheck();

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  const handleManualRetry = () => {
    setConnectionState('connecting');
    setRetryCount(0);
    let elapsed = 0;

    const runCheck = async () => {
      const success = await checkConnectionDirect();
      if (!success) {
        const intervalId = setInterval(async () => {
          elapsed += 10;
          if (elapsed >= 90) {
            setConnectionState('failed');
            clearInterval(intervalId);
          } else {
            setRetryCount(c => c + 1);
            const ok = await checkConnectionDirect();
            if (ok) {
              clearInterval(intervalId);
            }
          }
        }, 10000);
      }
    };

    runCheck();
  };

  const addTicker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker) return;
    const cleanTicker = newTicker.trim().toUpperCase();
    if (watchlist.includes(cleanTicker)) {
      setNewTicker('');
      setActiveTicker(cleanTicker);
      setAddTickerOpen(false);
      return;
    }

    const updated = [...watchlist, cleanTicker];
    try {
      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: updated })
      });
      const data = await res.json();
      setWatchlist(data.tickers);
      setNewTicker('');
      setAddTickerOpen(false);
      setActiveTicker(cleanTicker);
      // The add is immediate; graph expansion runs in the background. Seed the status
      // map so the polling effect starts and the UI shows "pending" right away.
      setGraphStatus(data.expansionStatus || {});
    } catch (e) {
      console.error('Error updating watchlist', e);
    }
  };

  const clearLedgerMemory = async () => {
    if (!confirm('Are you sure you want to clear the Catalyst Ledger memory for this iteration? This will reset all story updates.')) return;
    try {
      const res = await fetch(`/api/ledger/clear?iteration=${iteration}`, { method: 'POST' });
      await res.json();
      fetchLedger();
      alert('Ledger cleared successfully!');
    } catch (e) {
      console.error('Error clearing ledger', e);
    }
  };

  const runPipeline = async () => {
    setLoading(true);
    setSelectedCatalystPath(null);
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          iteration,
          scenario_id: scenarioId,
          simulated_now: scenarioId === 'live' ? new Date().toISOString() : '2026-05-28T17:25:00Z'
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Pipeline execution failed');
      }
      const data = await res.json();
      setRunResults(prev => ({
        ...prev,
        [iteration]: data
      }));
      fetchLedger();
      fetchGraph();
      fetchMemoryStatus();
    } catch (e: any) {
      alert(`Pipeline execution error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getActiveSynthesis = (): TickerSummary | null => {
    if (!runResult || !runResult.tickerSyntheses) return null;
    return runResult.tickerSyntheses[activeTicker] || null;
  };

  const getActiveBucket = (): TickerBucket | null => {
    if (!runResult || !runResult.tickerBuckets) return null;
    return runResult.tickerBuckets[activeTicker] || null;
  };

  const getTickerCompanyName = (ticker: string): string => {
    const node = graphData.nodes.find(n => n.nodeType === 'ticker' && n.ticker === ticker);
    if (node) return node.name;
    return (
      ticker === 'AAPL' ? 'Apple Inc.' :
      ticker === 'MSFT' ? 'Microsoft Corp.' :
      ticker === 'NVDA' ? 'Nvidia Corp.' :
      ticker === 'TSM' ? 'TSMC' :
      ticker === 'DAL' ? 'Delta Air Lines' : 'Public Company'
    );
  };

  // Small status pill shown next to each watchlist ticker, reflecting graph expansion.
  const renderGraphStatusPill = (ticker: string) => {
    const status = graphStatusFor(ticker);
    const map: Record<string, { label: string; color: string }> = {
      pending: { label: 'graph: queued', color: 'var(--accent-orange)' },
      running: { label: 'graph: building…', color: 'var(--accent-orange)' },
      done: { label: 'graph: ready', color: 'var(--accent-green)' },
      ready: { label: 'graph: ready', color: 'var(--accent-green)' },
      skipped: { label: 'graph: ready', color: 'var(--accent-green)' },
      failed: { label: 'graph: failed', color: 'var(--accent-red)' },
      none: { label: 'graph: —', color: 'var(--text-muted)' },
    };
    const meta = map[status] || map.none;
    const spinning = status === 'pending' || status === 'running';
    return (
      <span style={{ fontSize: '0.6rem', color: meta.color, display: 'flex', alignItems: 'center', gap: '0.2rem' }} title={graphStatus[ticker]?.error || meta.label}>
        {spinning && <span className="spinner" style={{ width: '8px', height: '8px', borderWidth: '1.5px' }} />}
        {meta.label}
      </span>
    );
  };

  if (connectionState === 'connecting') {
    return (
      <div className="connection-overlay">
        <div className="glass connection-card">
          <div className="connection-glow" />
          <div className="pulse-loader">
            <Cpu className="pulse-icon" size={48} />
          </div>
          <h2>⚡ Connecting to Cross-Impact Engine</h2>
          <p className="connection-status">
            The backend server at <code>http://localhost:8000</code> is still loading or offline.
          </p>
          <div className="polling-indicator">
            <span className="dot-pulse" />
            <span>Retrying connection (Attempt {retryCount + 1})...</span>
          </div>
          <div className="progress-bar-container">
            <div className="progress-bar-fill" style={{ width: `${(retryCount / 9) * 100}%` }} />
          </div>
          <span className="connection-info">Polling will stop automatically after 1.5 minutes.</span>
        </div>
      </div>
    );
  }

  if (connectionState === 'failed') {
    return (
      <div className="connection-overlay">
        <div className="glass connection-card connection-failed-card">
          <div className="connection-failed-glow" />
          <AlertCircle className="failed-icon" size={48} />
          <h2>❌ Server Offline / Connection Failed</h2>
          <p className="connection-status">
            Unable to establish a connection to the backend server at <code>http://localhost:8000</code> after 1.5 minutes of polling.
          </p>
          <p className="connection-instructions">
            Please make sure that the backend FastAPI server is running (e.g. via <code>uvicorn backend.main:app --reload</code>).
          </p>
          <button className="btn-primary retry-btn" onClick={handleManualRetry}>
            <RotateCcw size={16} style={{ marginRight: '0.4rem' }} />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Header Panel */}
      <header className="glass">
        <div className="logo-section">
          <h1>⚡ Cross-Impact Catalyst Briefings</h1>
          <p>Deduplicated Geopolitical & Tech Catalyst Synthesizer for Intraday Traders</p>
        </div>

        <div className="header-controls">
          {/* Affinity-style Segmented control Iteration Switcher */}
          <div className="affinity-switcher">
            <div className={`affinity-slider slider-it${iteration}`} />
            <button 
              className={`affinity-btn ${iteration === 1 ? 'active' : ''}`} 
              onClick={() => {
                setIteration(1);
                setSelectedCatalystPath(null);
              }}
            >
              ⚡ Direct News
            </button>
            <button 
              className={`affinity-btn ${iteration === 2 ? 'active' : ''}`} 
              onClick={() => {
                setIteration(2);
                setSelectedCatalystPath(null);
              }}
            >
              🧠 Memory Dedup
            </button>
            <button 
              className={`affinity-btn ${iteration === 3 ? 'active' : ''}`} 
              onClick={() => {
                setIteration(3);
                setSelectedCatalystPath(null);
              }}
            >
              🕸 Graph Routing
            </button>
          </div>

          {/* Mobile hamburger menu toggle button */}
          <button 
            className="btn-secondary mobile-menu-btn" 
            style={{ padding: '0.5rem', height: '36px', width: '36px', display: 'none', alignItems: 'center', justifyContent: 'center' }} 
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={16} />
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="workspace">
        
        {/* Left Sidebar - Watchlist */}
        {sidebarOpen && (
          <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
        )}
        <aside className={`glass sidebar ${sidebarOpen ? 'open' : ''}`}>
          {/* Pinned Overview Dashboard Selector */}
          <button
              className={`glass glass-hover watchlist-dashboard-btn ${activeTicker === 'dashboard' ? 'active' : ''}`}
              onClick={() => {
                setActiveTicker('dashboard');
                setSelectedCatalystPath(null);
                setSidebarOpen(false);
              }}
            >
              <Layers size={14} style={{ color: 'var(--accent-purple)' }} />
              <span>Overview Dashboard</span>
          </button>

          <div className="watchlist-controls">
            <div>
              <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.2rem' }}>
                Watchlist Tickers
              </h2>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>Active Asset Impact</div>
            </div>
            
            <div className="watchlist-search">
              <Search size={14} />
              <input 
                type="search" 
                placeholder="Search tickers..." 
                className="watchlist-input" 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <button type="button" className="btn-secondary add-asset-btn" onClick={() => setAddTickerOpen(true)}>
              <Plus size={15} />
              <span>Add Asset</span>
            </button>
          </div>

          {/* Ticker List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', flex: 1, overflowY: 'auto' }}>
            {watchlist.map(ticker => {
              const companyName = getTickerCompanyName(ticker);
              const query = searchQuery.trim().toLowerCase();
              if (query && !ticker.toLowerCase().includes(query) && !companyName.toLowerCase().includes(query)) return null;
              const isActive = activeTicker === ticker;
              const tickerSynthesis = runResult?.tickerSyntheses?.[ticker];
              const influence = tickerSynthesis?.overallPossibleInfluence || 'unclear';
              const hasCatalysts = tickerSynthesis && tickerSynthesis.summaryHeadline !== "No new catalysts detected";

              return (
                <div 
                  key={ticker} 
                  className={`glass glass-hover watchlist-item ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setActiveTicker(ticker);
                    setSelectedCatalystPath(null);
                    setSidebarOpen(false);
                  }}
                >
                  <div className="watchlist-copy">
                    <div className="ticker-name">{ticker}</div>
                    <div className="company-name">
                      {companyName}
                    </div>
                  </div>
                  <div className="watchlist-meta">
                    {runResult && (
                      <span className={`badge ${hasCatalysts ? influence : 'unclear'}`} style={{ fontSize: '0.65rem' }}>
                        {hasCatalysts ? influence : 'no change'}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Center Panel - Dashboard and Synthesized briefing */}
        <main className="main-content">
          
          {/* Action Control Panel */}
          <div className="action-control-panel">
            <div className="action-control-group">
              {/* Scenario Selector */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'var(--text-secondary)', fontWeight: 800 }}>News Source / Replay</span>
                <select 
                  className="custom-select" 
                  value={scenarioId} 
                  onChange={(e) => setScenarioId(e.target.value)}
                  style={{ height: '36px', padding: '0.4rem 0.8rem', fontSize: '0.82rem' }}
                >
                  <option value="live">Live Feeds (Finnhub + Currents)</option>
                  <option value="direct_news">Replay Scenario 1: Direct Announcements</option>
                  <option value="duplicate_news">Replay Scenario 2: Duplicate Articles</option>
                  <option value="cross_impact">Replay Scenario 3: Untickered Geopolitical/Tech</option>
                </select>
              </div>

              {/* Ledger Clear Reset (Only relevant in Memory iterations) */}
              {iteration > 1 && (
                <button 
                  className="btn-secondary" 
                  onClick={clearLedgerMemory} 
                  title="Reset active story thread cache in Ledger"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', height: '36px', marginTop: '12px' }}
                >
                  <RotateCcw size={14} />
                  <span style={{ fontSize: '0.8rem' }}>Reset Cache</span>
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {/* Run Button */}
              <button 
                className="btn-primary" 
                onClick={runPipeline} 
                disabled={loading || watchlist.length === 0}
                style={{ height: '36px', padding: '0.5rem 1.25rem', marginTop: '12px' }}
              >
                {loading ? (
                  <div className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>
                ) : (
                  <Play size={14} fill="white" />
                )}
                <span style={{ fontSize: '0.82rem' }}>Fetch Catalysts</span>
              </button>
            </div>
          </div>

          {loading ? (
            <div className="glass loading-overlay" style={{ flex: 1 }}>
              <div className="spinner"></div>
              <h2>
                {iteration === 1 && "Executing LLM Direct News Workflow"}
                {iteration === 2 && "Executing LLM Memory Deduplication"}
                {iteration === 3 && "Executing LLM Catalyst Workflow Graph"}
              </h2>
              <p style={{ color: 'var(--text-secondary)' }}>
                {iteration === 1 && "Fetching direct articles and executing extraction + synthesis..."}
                {iteration === 2 && "Deduplicating articles using local vector memory ledger..."}
                {iteration === 3 && "Expanding search terms and routing untickered geopolitical shocks..."}
              </p>
            </div>
          ) : activeTicker === 'dashboard' ? (
            /* ==========================================================
               View A: WATCHLIST OVERVIEW DASHBOARD (2-COLUMN SPLIT)
               ========================================================== */
            <div className="dashboard-split">
              {/* Left Column: Watchlist Signals */}
              {(() => {
                const activeAlertTickers = watchlist.filter(t => {
                  const synth = runResult?.tickerSyntheses?.[t];
                  return synth && synth.summaryHeadline !== "No new catalysts detected";
                });
                const quietTickers = watchlist.filter(t => !activeAlertTickers.includes(t));

                return (
                  <div className="dashboard-signals">
                    {/* Active Alerts */}
                    <div className="active-alerts-section">
                      <h2 className="section-title">🚨 Active Shocks & Alerts</h2>
                      {watchlist.length === 0 ? (
                        <div className="glass" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                          <h3>Watchlist is empty</h3>
                          <p style={{ marginTop: '0.5rem' }}>Add tickers in the left sidebar to start monitoring signals.</p>
                        </div>
                      ) : activeAlertTickers.length === 0 ? (
                        <div className="glass" style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                          No active breaking news alerts. Monitor quiet watchlist below.
                        </div>
                      ) : (
                        <div className="dashboard-grid">
                          {activeAlertTickers.map(ticker => {
                            const tickerSynthesis = runResult?.tickerSyntheses?.[ticker];
                            const influence = tickerSynthesis?.overallPossibleInfluence || 'unclear';
                            const headline = tickerSynthesis?.summaryHeadline || 'No new catalysts detected';
                            
                            // Find relative time of the last catalyst
                            const bucket = runResult?.tickerBuckets?.[ticker];
                            const allEvents = [...(bucket?.directEvents || []), ...(bucket?.crossImpactEvents || [])];
                            
                            let timeStr = '';
                            if (allEvents.length > 0) {
                              const firstEvt = allEvents[0];
                              const ts = getEventTimestamp(firstEvt.sourceArticleIds);
                              if (ts) {
                                timeStr = formatRelativeTime(ts);
                              }
                            }

                            const influenceIcons = {
                              positive: '▲',
                              negative: '▼',
                              mixed: '◆',
                              unclear: '—'
                            };

                            return (
                              <div 
                                key={ticker} 
                                className={`dashboard-card active-alert-card glow-${influence}`}
                                onClick={() => setActiveTicker(ticker)}
                              >
                                <div className="dashboard-card-header">
                                  <div>
                                    <div className="dashboard-card-ticker">{ticker}</div>
                                    <div className="dashboard-card-company">
                                      {(() => {
                                        const node = graphData.nodes.find(n => n.nodeType === 'ticker' && n.ticker === ticker);
                                        return node ? node.name : 'Public Company';
                                      })()}
                                    </div>
                                  </div>
                                  
                                  <span className={`dashboard-card-signal-badge ${influence}`}>
                                    <span style={{ fontSize: '0.8rem', lineHeight: 1, marginRight: '0.15rem' }}>
                                      {influenceIcons[influence]}
                                    </span>
                                    <span>{influence}</span>
                                  </span>
                                </div>
                                
                                <div className="dashboard-card-headline">
                                  {headline}
                                </div>
                                
                                <div className="dashboard-card-footer">
                                  <span className="dashboard-card-time">
                                    <Clock size={11} style={{ marginRight: '0.25rem', verticalAlign: 'middle', display: 'inline' }} />
                                    {timeStr ? `Updated ${timeStr}` : 'No recent update'}
                                  </span>
                                  <span className="dashboard-card-action">
                                    View Briefing →
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Quiet Tickers */}
                    {quietTickers.length > 0 && (
                      <div className="quiet-watchlist-section">
                        <h2 className="section-title">⚪ Quiet Watchlist</h2>
                        <table className="quiet-watchlist-table">
                          <thead>
                            <tr>
                              <th>Ticker</th>
                              <th>Company Name</th>
                              <th>Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {quietTickers.map(ticker => {
                              const tickerSynthesis = runResult?.tickerSyntheses?.[ticker];
                              const influence = tickerSynthesis?.overallPossibleInfluence || 'unclear';
                              return (
                                <tr key={ticker} onClick={() => setActiveTicker(ticker)}>
                                  <td className="quiet-row-ticker">{ticker}</td>
                                  <td className="quiet-row-company">
                                    {(() => {
                                      const node = graphData.nodes.find(n => n.nodeType === 'ticker' && n.ticker === ticker);
                                      return node ? node.name : (
                                        ticker === 'AAPL' ? 'Apple Inc.' :
                                        ticker === 'MSFT' ? 'Microsoft Corp.' :
                                        ticker === 'NVDA' ? 'Nvidia Corp.' :
                                        ticker === 'TSM' ? 'TSMC' :
                                        ticker === 'DAL' ? 'Delta Air Lines' : 'Public Company'
                                      );
                                    })()}
                                  </td>
                                  <td>
                                    <span className="quiet-row-badge">
                                      {influence === 'unclear' ? 'no change' : influence}
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Right Column: Global Active Story Ledger */}
              {iteration > 1 && (
                <div className="dashboard-ledger glass">
                  <div className="dashboard-ledger-header">
                    <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
                      <Database size={14} style={{ color: 'var(--accent-purple)' }} />
                      Active Story Ledger (Global)
                    </h2>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {ledgerEntries.length} threads
                    </span>
                  </div>
                  <div className="dashboard-ledger-list">
                    {ledgerEntries.length > 0 ? (
                      ledgerEntries.map(entry => (
                        <div key={entry.catalystId} className="ledger-list-card">
                          <div className="ledger-card-header">
                            <span className="ledger-card-ticker">{entry.ticker}</span>
                            <span className="ledger-card-type">{entry.eventType}</span>
                          </div>
                          <div className="ledger-card-summary">{entry.canonicalSummary}</div>
                          <div className="ledger-card-footer">
                            <span>Facts: {entry.hardFactsSeen.length}</span>
                            <span>First seen: {formatRelativeTime(entry.firstSeenAt)}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="ledger-list-empty">
                        No active story threads in memory ledger.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ==========================================================
               View B: TICKER DETAILS WORKSPACE
               ========================================================== */
            <>
              {(() => {
                const synthesis = getActiveSynthesis();
                const bucket = getActiveBucket();
                if (!synthesis) {
                  return (
                    <div className="glass" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)', flex: 1 }}>
                      <h2>No Active Run Data</h2>
                      <p style={{ marginTop: '0.5rem' }}>Select an iteration and news scenario, then click "Fetch Catalysts" to populate briefing cards.</p>
                    </div>
                  );
                }

                const influenceColor = synthesis.overallPossibleInfluence;
                const hasCatalysts = synthesis.summaryHeadline !== "No new catalysts detected";

                // Gather and filter supporting events
                const allEvents = [...bucket.directEvents, ...bucket.crossImpactEvents];
                
                // Filter out cross-impact events from feeds if iteration < 3
                const filteredAllEvents = iteration < 3 
                  ? allEvents.filter(e => !bucket.crossImpactEvents.find(c => c.eventId === e.eventId))
                  : allEvents;

                // Helper to get score for sorting
                const getCombinedScore = (evt: EventEntry) => {
                  const ts = getEventTimestamp(evt.sourceArticleIds);
                  const timeMs = ts ? new Date(ts).getTime() : 0;
                  const now = scenarioId === 'live' ? Date.now() : new Date('2026-05-28T17:25:00Z').getTime();
                  const ageMinutes = Math.max(0, (now - timeMs) / 60000);
                  
                  // Find significance from synthesis mainCatalysts
                  const catalystInfo = synthesis.mainCatalysts?.find((c: any) => c.eventId === evt.eventId);
                  const significance = catalystInfo ? (catalystInfo.significance || 5) : 3;
                  
                  return (significance * 10) - (ageMinutes * 0.5);
                };

                // Merge and sort events
                const sortedEvents = [...filteredAllEvents].sort((a, b) => getCombinedScore(b) - getCombinedScore(a));

                const activeTickerLedger = ledgerEntries.filter(l => l.ticker === activeTicker);

                return (
                  <div className="ticker-detail-split">
                    {/* Left Column: Ticker Synthesis Briefing */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', minWidth: 0 }}>
                      <div className="glass synthesis-card compact-synthesis-strip">
                        <div className="compact-synthesis-header" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem', marginBottom: '0.5rem' }}>
                          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                            <span className={`iteration-indicator it${iteration}`}>Iteration {iteration}</span>
                            <span className={`badge ${hasCatalysts ? influenceColor : 'unclear'}`}>
                              {hasCatalysts ? synthesis.overallPossibleInfluence : 'no catalysts'}
                            </span>
                            <span className="badge" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', display: 'inline-flex' }}>
                              Confidence: {synthesis.confidence}
                            </span>
                            {synthesis.guardrailMetadata && (
                              <span className="badge" style={{
                                background: 
                                  synthesis.guardrailMetadata.judgeStatus === 'passed' ? 'rgba(34, 197, 94, 0.1)' :
                                  synthesis.guardrailMetadata.judgeStatus === 'regenerated_passed' ? 'rgba(234, 88, 12, 0.1)' :
                                  synthesis.guardrailMetadata.judgeStatus === 'degraded' ? 'rgba(239, 68, 68, 0.1)' :
                                  'rgba(255, 255, 255, 0.05)',
                                color:
                                  synthesis.guardrailMetadata.judgeStatus === 'passed' ? 'var(--accent-green)' :
                                  synthesis.guardrailMetadata.judgeStatus === 'regenerated_passed' ? 'var(--accent-orange)' :
                                  synthesis.guardrailMetadata.judgeStatus === 'degraded' ? 'var(--accent-red)' :
                                  'var(--text-secondary)',
                                borderColor:
                                  synthesis.guardrailMetadata.judgeStatus === 'passed' ? 'rgba(34, 197, 94, 0.2)' :
                                  synthesis.guardrailMetadata.judgeStatus === 'regenerated_passed' ? 'rgba(234, 88, 12, 0.2)' :
                                  synthesis.guardrailMetadata.judgeStatus === 'degraded' ? 'rgba(239, 68, 68, 0.2)' :
                                  'rgba(255, 255, 255, 0.1)',
                                display: 'inline-flex'
                              }}>
                                {synthesis.guardrailMetadata.judgeStatus === 'passed' ? 'Verified' :
                                 synthesis.guardrailMetadata.judgeStatus === 'regenerated_passed' ? 'Regenerated after guardrail' :
                                 synthesis.guardrailMetadata.judgeStatus === 'degraded' ? 'Suppressed pending verification' :
                                 synthesis.guardrailMetadata.judgeStatus === 'skipped_empty' ? 'Skipped (No catalysts)' :
                                 synthesis.guardrailMetadata.judgeStatus === 'skipped_no_llm_mock_mode' ? 'Skipped (No LLM keys)' :
                                 synthesis.guardrailMetadata.judgeStatus}
                              </span>
                            )}
                          </div>
                        </div>

                        <h2 style={{ fontSize: '1.3rem', fontWeight: 800, margin: '0.25rem 0 0.5rem 0', color: 'var(--text-primary)' }}>
                          {synthesis.summaryHeadline}
                        </h2>

                        <div className="synthesis-content-expanded" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: 0 }}>
                          <div className="synthesis-summary" style={{ fontSize: '0.92rem', lineHeight: '1.55', background: 'rgba(255,255,255,0.01)' }}>
                            {(() => {
                              const text = synthesis.situationSummary || "";
                              const sentences = text.match(/[^.!?]+[.!?]+(\s|$)/g) || [text];
                              if (sentences.length <= 2) {
                                return <span>{text}</span>;
                              }
                              const shortPart = sentences.slice(0, 2).join("").trim();
                              const restPart = sentences.slice(2).join("").trim();
                              
                              if (summaryDetailExpanded) {
                                return (
                                  <span>
                                    {shortPart} {restPart}
                                    <span className="summary-toggle-link" onClick={() => setSummaryDetailExpanded(false)}>
                                      [Show Less]
                                    </span>
                                  </span>
                                );
                              } else {
                                return (
                                  <span>
                                    {shortPart}...
                                    <span className="summary-toggle-link" onClick={() => setSummaryDetailExpanded(true)}>
                                      [Show More]
                                    </span>
                                  </span>
                                );
                              }
                            })()}
                          </div>

                          {/* Columns: Uncertainties & Watch Items */}
                          <div className="synthesis-details-grid" style={{ gridTemplateColumns: '1fr', gap: '1rem' }}>
                            <div className="details-column">
                              <h3 style={{ fontSize: '0.78rem' }}>🔑 Uncertainties / Open Risks</h3>
                              <ul className="details-list" style={{ paddingLeft: '0.25rem' }}>
                                {synthesis.uncertainties.map((u, i) => (
                                  <li key={i} style={{ fontSize: '0.82rem' }}>{u}</li>
                                ))}
                              </ul>
                            </div>

                            <div className="details-column">
                              <h3 style={{ fontSize: '0.78rem' }}>👀 Trader Watchlist Items</h3>
                              <ul className="details-list" style={{ paddingLeft: '0.25rem' }}>
                                {synthesis.watchItems.map((wi, i) => (
                                  <li key={i} style={{ fontSize: '0.82rem' }}>{wi}</li>
                                ))}
                              </ul>
                            </div>
                          </div>

                          {/* Exposure Graph Button (Iteration 3 only) */}
                          {iteration === 3 && (
                            <button
                              onClick={() => setGraphModalOpen(true)}
                              className="btn-secondary"
                              style={{ padding: '0.45rem 0.9rem', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', marginTop: '0.25rem', width: 'fit-content' }}
                              title="Open full-screen exposure graph"
                            >
                              <Network size={14} /> View Causal Exposure Graph
                            </button>
                          )}

                          {/* Compliance Disclaimer */}
                          <div className="compliance-disclaimer" style={{ marginTop: '0.5rem', padding: '0.6rem 0.75rem' }}>
                            <ShieldAlert size={14} style={{ color: 'var(--accent-orange)', flexShrink: 0 }} />
                            <p style={{ fontSize: '0.7rem' }}>{synthesis.complianceDisclaimer || "Grounded information only. Not investment advice."}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Right Column: Unified Live Feed + Structured Memory Index */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', minWidth: 0 }}>
                      
                      {/* Unified Live Feed */}
                      <div className="catalysts-section">
                        <h3 className="feed-type-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span className="pulsing-dot" style={{ color: iteration === 1 ? 'var(--accent-blue)' : iteration === 2 ? 'var(--accent-purple)' : 'var(--accent-cyan)' }} />
                            ⚡ Live Updates & Catalyst Feed
                          </span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'none', fontWeight: 'normal' }}>
                            {sortedEvents.length} events sorted by recency & significance
                          </span>
                        </h3>

                        {sortedEvents.length > 0 ? (
                          <div className="catalysts-grid">
                            {sortedEvents.map((evt) => {
                              const isCross = bucket.crossImpactEvents.find(c => c.eventId === evt.eventId);
                              const isGraphHovered = selectedCatalystPath && selectedCatalystPath.join(',') === evt.impactPath?.join(',');
                              const ts = getEventTimestamp(evt.sourceArticleIds);
                              
                              const catId = getEventCatalystId(evt.eventId);
                              const elId = catId ? `evt-${catId}` : `evt-${evt.eventId}`;

                              const ledgerEntry = ledgerEntries.find(l => l.catalystId === catId);
                              
                              // Check decision: new vs update
                              const decision = iteration === 1 ? 'new' : getEventDecision(evt.eventId);
                              const isUpdate = decision === 'update';

                              // Find significance rating for badge
                              const catalystInfo = synthesis.mainCatalysts?.find((c: any) => c.eventId === evt.eventId);
                              const significance = catalystInfo ? (catalystInfo.significance || 5) : 3;

                              // Segment facts: new vs previous
                              const newFacts = evt.hardFacts;
                              const prevFacts = (isUpdate && ledgerEntry)
                                ? ledgerEntry.hardFactsSeen.filter((f: string) => !newFacts.includes(f))
                                : [];

                              return (
                                <div 
                                  id={elId}
                                  key={evt.eventId} 
                                  className={`glass catalyst-card ${isUpdate ? 'ongoing-card' : `fresh-card accent-${iteration}`}`}
                                  style={isCross ? { 
                                    borderColor: isGraphHovered ? 'var(--accent-cyan)' : 'var(--border-color)',
                                    boxShadow: isGraphHovered ? '0 0 15px rgba(6, 182, 212, 0.15)' : 'none',
                                    transition: 'all 0.2s'
                                  } : {}}
                                  onMouseEnter={() => isCross && evt.impactPath && setSelectedCatalystPath(evt.impactPath)}
                                  onMouseLeave={() => isCross && setSelectedCatalystPath(null)}
                                >
                                  <div className="catalyst-card-header" style={{ paddingRight: '12rem' }}>
                                    <span className="badge" style={{ 
                                      borderColor: isCross ? 'rgba(6, 182, 212, 0.3)' : isUpdate ? 'rgba(255,255,255,0.1)' : 'rgba(168, 85, 247, 0.3)', 
                                      color: isCross ? 'var(--accent-cyan)' : isUpdate ? 'var(--text-secondary)' : 'var(--accent-purple)' 
                                    }}>
                                      {isCross 
                                        ? (isUpdate ? 'Ongoing Cross-Impact' : 'Cross-Impact Catalyst') 
                                        : (isUpdate ? 'Ongoing Direct Thread' : 'Direct Catalyst')}
                                    </span>
                                    <span className={`badge ${evt.possibleDirectionalPressure}`}>{evt.possibleDirectionalPressure}</span>
                                  </div>

                                  <div style={{ position: 'absolute', top: '1.25rem', right: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                    {/* Significance Badge */}
                                    <span className="badge" style={{
                                      background: significance >= 7 ? 'rgba(239, 68, 68, 0.12)' : 'rgba(255, 255, 255, 0.05)',
                                      color: significance >= 7 ? 'var(--accent-red)' : 'var(--text-secondary)',
                                      border: `1px solid ${significance >= 7 ? 'rgba(239, 68, 68, 0.25)' : 'var(--border-color)'}`,
                                      fontSize: '0.65rem',
                                      padding: '0.1rem 0.4rem',
                                      fontWeight: 800
                                    }}>
                                      Sig: {significance}/10
                                    </span>

                                    {/* Recency Badge */}
                                    <span className={isUpdate ? 'ongoing-badge' : 'fresh-badge'} style={{ position: 'static', margin: 0 }}>
                                      {!isUpdate && <span className="pulsing-dot" />}
                                      {ts ? formatRelativeTime(ts) : 'breaking'}
                                    </span>
                                  </div>

                                  <div className="catalyst-title" style={{ marginTop: '0.35rem' }}>{evt.headline}</div>
                                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                                    {evt.eventSummary}
                                  </p>

                                  {isUpdate ? (
                                    /* Story Timeline progression for Updates */
                                    <div className="storyline-timeline">
                                      <div className="timeline-title">Story Timeline & Fact Progression</div>
                                      <div className="timeline-facts-box">
                                        {/* New Facts */}
                                        {newFacts.map((fact, index) => (
                                          <div key={`new-${index}`} className="timeline-node new-fact">
                                            <span style={{ fontSize: '0.62rem', textTransform: 'uppercase', background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)', padding: '0.05rem 0.25rem', borderRadius: '3px', marginRight: '0.35rem' }}>New Fact</span>
                                            {fact}
                                          </div>
                                        ))}
                                        
                                        {/* Previous Facts (Dimmed) */}
                                        {prevFacts.map((fact: string, index: number) => (
                                          <div key={`prev-${index}`} className="timeline-node" style={{ opacity: 0.55 }}>
                                            <span style={{ fontSize: '0.62rem', textTransform: 'uppercase', background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-muted)', padding: '0.05rem 0.25rem', borderRadius: '3px', marginRight: '0.35rem' }}>Priced In</span>
                                            {fact}
                                          </div>
                                        ))}
                                      </div>
                                      
                                      {ledgerEntry && (
                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', display: 'flex', gap: '1rem', marginTop: '0.25rem', paddingLeft: '0.75rem' }}>
                                          <span>First Seen: {formatRelativeTime(ledgerEntry.firstSeenAt)}</span>
                                          <span>Total reports: {ledgerEntry.memberArticleIds.length}</span>
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    /* Hard facts for new news cards */
                                    <div className="catalyst-fact-box">
                                      <div className="fact-title">Hard Facts Grounded in Text:</div>
                                      {evt.hardFacts.map((fact, index) => (
                                        <div key={index} className="catalyst-fact">• {fact}</div>
                                      ))}
                                    </div>
                                  )}

                                  {isCross && evt.impactPath && (
                                    <div style={{ marginTop: '1rem' }}>
                                      <div className="fact-title" style={{ marginBottom: '0.25rem' }}>Exposure Chain Traversed:</div>
                                      <div className="impact-path-display">
                                        {evt.impactPath.map((step, idx) => {
                                          const isFirst = idx === 0;
                                          const isLast = idx === evt.impactPath!.length - 1;
                                          return (
                                            <React.Fragment key={idx}>
                                              <span className={`path-step ${isFirst ? 'source' : ''} ${isLast ? 'ticker' : ''}`}>
                                                {step}
                                              </span>
                                              {!isLast && <span className="path-arrow">→</span>}
                                            </React.Fragment>
                                          );
                                        })}
                                        {!isUpdate && (
                                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                                            Path Score: {evt.pathConfidence}
                                          </span>
                                        )}
                                      </div>
                                      {!isUpdate && evt.reasonForRouting && (
                                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem', fontStyle: 'italic' }}>
                                          <strong>Causal path:</strong> {evt.reasonForRouting}
                                        </p>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="glass" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                            No catalysts detected in this run.
                          </div>
                        )}
                      </div>

                      {/* Active Memory Index (Database state - shown in Iterations 2 & 3) */}
                      {iteration > 1 && activeTickerLedger.length > 0 && (
                        <section className="glass panel-card">
                          <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
                            <Database size={13} style={{ color: 'var(--accent-purple)' }} />
                            Active Memory Index ({activeTickerLedger.length} stories in local DB)
                          </h2>
                          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                            Current state of local vector database memory. Click active updates to scroll to card, or background entries to expand hard facts inline.
                          </p>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '400px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                            {activeTickerLedger.map((entry) => {
                              const isUpdatedInRun = sortedEvents.some(e => getEventCatalystId(e.eventId) === entry.catalystId);
                              const isSelected = selectedBackgroundStory === entry.catalystId;
                              
                              return (
                                <div 
                                  key={entry.catalystId} 
                                  className={`memory-index-row ${isUpdatedInRun ? 'status-active' : 'status-background'}`}
                                  onClick={() => {
                                    if (isUpdatedInRun) {
                                      const el = document.getElementById(`evt-${entry.catalystId}`);
                                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                    } else {
                                      setSelectedBackgroundStory(isSelected ? null : entry.catalystId);
                                    }
                                  }}
                                >
                                  <div className="index-row-header">
                                    <span className="index-row-type">{entry.eventType}</span>
                                    <span className={`index-row-status-dot ${isUpdatedInRun ? 'active' : 'background'}`} />
                                  </div>
                                  <div className="index-row-title">{entry.canonicalSummary}</div>
                                  <div className="index-row-footer">
                                    <span>First seen: {formatRelativeTime(entry.firstSeenAt)}</span>
                                    <span>Facts: {entry.hardFactsSeen.length}</span>
                                  </div>

                                  {!isUpdatedInRun && isSelected && (
                                    <div className="index-row-expanded" onClick={(e) => e.stopPropagation()}>
                                      <div className="expanded-summary-title">Full Grounded Memory State:</div>
                                      <div className="expanded-facts-list">
                                        {entry.hardFactsSeen.map((fact: string, idx: number) => (
                                          <div key={idx} className="expanded-fact-item">• {fact}</div>
                                        ))}
                                      </div>
                                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                                        First seen: {formatRelativeTime(entry.firstSeenAt)} | Reports: {entry.memberArticleIds.length}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </section>
                      )}
                    </div>
                  </div>
                );
              })()}
            </>
          )}
        </main>
      </div>

      {addTickerOpen && (
        <div className="modal-backdrop" onClick={() => setAddTickerOpen(false)}>
          <form className="glass add-ticker-modal" onSubmit={addTicker} onClick={(e) => e.stopPropagation()}>
            <div className="add-ticker-header">
              <div>
                <h2>Add Asset</h2>
                <p>Add a ticker to the active watchlist.</p>
              </div>
              <button type="button" className="icon-btn" onClick={() => setAddTickerOpen(false)} aria-label="Close add asset dialog">
                <X size={16} />
              </button>
            </div>
            <input
              autoFocus
              type="text"
              placeholder="Ticker symbol, e.g. MSFT"
              className="watchlist-input add-ticker-input"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
            />
            <div className="add-ticker-actions">
              <button type="button" className="btn-secondary" onClick={() => setAddTickerOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={!newTicker.trim()}>
                <Plus size={15} />
                <span>Add Asset</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Bottom Status Bar */}
      <footer className="status-bar">
        <div className="status-bar-left">
          <div className="status-bar-item">
            <span>Arize Phoenix:</span>
            <span className="status-indicator" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontWeight: 'bold' }}>
              <div className={phoenixStatus.running ? 'pulse-dot' : ''} style={{ width: '8px', height: '8px', borderRadius: '50%', background: phoenixStatus.running ? 'var(--accent-green)' : 'var(--accent-red)', boxShadow: phoenixStatus.running ? '0 0 8px var(--accent-green)' : 'none' }} />
              {phoenixStatus.running ? 'ACTIVE' : 'OFFLINE'}
            </span>
          </div>
          {phoenixStatus.running && phoenixStatus.dashboardUrl && (
            <a 
              href={phoenixStatus.dashboardUrl}
              target="_blank" 
              rel="noreferrer"
              className="status-bar-link"
            >
              <span>Phoenix Traces</span>
              <ExternalLink size={11} />
            </a>
          )}
        </div>

        {/* Workflow Metrics */}
        <div className="status-bar-item" style={{ gap: '1rem' }}>
          {runResult && (
            <>
              <span>Ingested: <strong>{runResult.articlesCount}</strong></span>
              <span>Extractions: <strong>{runResult.eventsCount}</strong></span>
              <span>Connections: <strong>{runResult.routedCount}</strong></span>
              <span>Duplicates Suppressed: <strong>{Object.values(runResult.duplicateCounts).reduce((a,b) => a+b, 0)}</strong></span>
            </>
          )}
        </div>

        <div className="status-bar-right">
          {/* Embeddings Memory Engine Trigger */}
          <div 
            className="engine-popover-trigger"
            onClick={() => setPopoverOpen(!popoverOpen)}
          >
            <Cpu size={12} />
            <span>Memory Engine: {memoryStatus?.dedupProvider || 'loading...'}</span>
          </div>

          {/* Embeddings Memory Engine Popover */}
          {popoverOpen && (
            <>
              <div className="engine-popover-backdrop" onClick={() => setPopoverOpen(false)} />
              <div className="engine-popover">
                <div className="engine-popover-header">
                  Embeddings Memory Engine
                </div>
                {memoryStatus ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Dedup Provider</span>
                      <span style={{
                        fontWeight: 700,
                        padding: '0.1rem 0.35rem',
                        borderRadius: '3px',
                        background: memoryStatus.isFallbackActive ? 'rgba(234, 88, 12, 0.12)' : 'rgba(6, 182, 212, 0.12)',
                        color: memoryStatus.isFallbackActive ? 'var(--accent-orange)' : 'var(--accent-cyan)',
                        border: `1px solid ${memoryStatus.isFallbackActive ? 'rgba(234,88,12,0.3)' : 'rgba(6,182,212,0.3)'}`
                      }}>{memoryStatus.dedupProvider}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Extraction LLM</span>
                      <span style={{ color: 'var(--accent-green)', fontFamily: 'monospace' }}>{memoryStatus.llmExtractionModel}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Synthesis LLM</span>
                      <span style={{ color: 'var(--accent-purple)', fontFamily: 'monospace' }}>{memoryStatus.llmSynthesisModel}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Dedup Method</span>
                      <span>{memoryStatus.dedupModel}</span>
                    </div>
                    <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.2rem 0' }} />
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Cosine Threshold</span>
                      <span style={{ color: 'var(--accent-purple)' }}>&ge; {memoryStatus.similarityThreshold}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Jaccard Threshold</span>
                      <span style={{ color: 'var(--accent-blue)' }}>&ge; {memoryStatus.jaccardFactThreshold}</span>
                    </div>
                    <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.2rem 0' }} />
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Stories in Ledger</span>
                      <span>{memoryStatus.ledgerLiveEntries} / {memoryStatus.ledgerTotalEntries}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">Vectors Stored</span>
                      <span style={{ color: 'var(--accent-green)' }}>{memoryStatus.ledgerEmbeddedEntries}</span>
                    </div>
                    {memoryStatus.isFallbackActive && (
                      <div style={{
                        marginTop: '0.35rem',
                        padding: '0.4rem 0.5rem',
                        background: 'rgba(234, 88, 12, 0.08)',
                        border: '1px solid rgba(234,88,12,0.25)',
                        borderRadius: '5px',
                        fontSize: '0.7rem',
                        color: 'var(--accent-orange)',
                        lineHeight: 1.4
                      }}>
                        ⚠ Local embedding model unavailable. Using deterministic lexical cosine fallback.
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>Loading engine status...</div>
                )}
              </div>
            </>
          )}
        </div>
      </footer>

      {/* Full-screen Exposure Graph Modal */}
      {graphModalOpen && (
        <div
          onClick={() => setGraphModalOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(3, 4, 8, 0.82)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem'
          }}
        >
          <div
            className="glass"
            onClick={(e) => e.stopPropagation()}
            style={{ width: 'min(1200px, 95vw)', height: 'min(800px, 92vh)', display: 'flex', flexDirection: 'column', padding: '1.25rem', gap: '0.75rem' }}
          >
            {/* Modal header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
                <Network size={18} /> Causal Exposure Graph
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                  {graphData.nodes.length} nodes · {graphData.edges.length} edges
                </span>
              </h2>
              <button onClick={() => setGraphModalOpen(false)} className="btn-secondary" style={{ padding: '0.35rem 0.6rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <X size={14} /> Close
              </button>
            </div>

            <div style={{ display: 'flex', flex: 1, gap: '1rem', minHeight: 0 }}>
              {/* Large graph canvas */}
              <div style={{ flex: 1, minWidth: 0, border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
                <GraphView graphData={graphData} width={900} height={620} scale={2.2} selectedCatalystPath={selectedCatalystPath} />
              </div>

              {/* Side rail: legend + per-ticker expansion controls */}
              <div style={{ width: '260px', display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowY: 'auto' }}>
                <div>
                  <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Legend</h3>
                  {[
                    ['Ticker (watchlist)', 'var(--accent-purple)'],
                    ['Technology theme', 'var(--accent-blue)'],
                    ['Company / sector', 'var(--accent-cyan)'],
                    ['Region / risk / commodity / route', 'var(--accent-orange)'],
                  ].map(([label, color]) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: color, flexShrink: 0 }} />
                      {label}
                    </div>
                  ))}
                  <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                    Dashed edges = exposure links · solid = supplier/competitor/partner. Flow runs left → right into the ticker.
                  </div>
                </div>

                <div style={{ height: '1px', background: 'var(--border-color)' }} />

                <div>
                  <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Global Rebuild</h3>
                  {(() => {
                    const anyBusy = watchlist.some(t => ['pending', 'running'].includes(graphStatusFor(t)));
                    return (
                      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.75rem' }}>
                        <button
                          onClick={() => rebuildGraph(true)}
                          disabled={anyBusy}
                          className="btn-secondary"
                          style={{ flex: 1, padding: '0.35rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: anyBusy ? 0.5 : 1 }}
                          title="Reset to curated seed, then re-expand every watchlist ticker"
                        >
                          <RotateCcw size={12} /> From seed
                        </button>
                        <button
                          onClick={() => rebuildGraph(false)}
                          disabled={anyBusy}
                          className="btn-secondary"
                          style={{ flex: 1, padding: '0.35rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: anyBusy ? 0.5 : 1 }}
                          title="Force a fresh expansion for every watchlist ticker on top of the current graph"
                        >
                          <RefreshCw size={12} /> Refresh all
                        </button>
                      </div>
                    );
                  })()}

                  <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Per-Ticker</h3>
                  {watchlist.map(ticker => {
                    const status = graphStatusFor(ticker);
                    const busy = status === 'pending' || status === 'running';
                    return (
                      <div key={ticker} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.4rem', padding: '0.35rem 0', borderBottom: '1px solid var(--border-color)' }}>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.8rem' }}>{ticker}</span>
                          {renderGraphStatusPill(ticker)}
                        </div>
                        <button
                          onClick={() => triggerExpansion(ticker)}
                          disabled={busy}
                          className="btn-secondary"
                          style={{ padding: '0.25rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: busy ? 0.5 : 1 }}
                          title="Re-run the LLM exposure-graph update for this ticker"
                        >
                          <RefreshCw size={12} /> Update
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
