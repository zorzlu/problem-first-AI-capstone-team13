import { Network, RefreshCw, RotateCcw, Settings, X } from 'lucide-react';

interface RunControlsProps {
  scenarioId: string;
  iteration: number;
  loading: boolean;
  watchlistCount: number;
  onScenarioChange: (scenarioId: string) => void;
  onClearLedger: () => void;
  onExploreGraph: () => void;
  onOpenSettings: () => void;
  onRunPipeline: () => void;
  onCancelRun?: () => void;
}

export function RunControls({
  scenarioId,
  iteration,
  loading,
  watchlistCount,
  onScenarioChange,
  onClearLedger,
  onExploreGraph,
  onOpenSettings,
  onRunPipeline,
  onCancelRun,
}: RunControlsProps) {
  return (
    <div className="header-bottom-tier">
      <div className="subheader-left">
        <div className="scenario-selector-wrapper-header">
          <span className="scenario-label-header">SOURCE:</span>
          <select
            id="header-scenario-select"
            aria-label="Source"
            className="scenario-select-header"
            value={scenarioId}
            onChange={(event) => onScenarioChange(event.target.value)}
          >
            <option value="live">Live Feeds (Finnhub + Currents)</option>
            <option value="direct_news">Replay Scenario 1: Direct Announcements</option>
            <option value="duplicate_news">Replay Scenario 2: Duplicate Articles</option>
            <option value="cross_impact">Replay Scenario 3: Untickered Geopolitical/Tech</option>
          </select>
        </div>

        {iteration > 1 && (
          <button
            className="btn-reset-cache-header"
            onClick={onClearLedger}
            title="Reset active story thread cache in Ledger"
          >
            <RotateCcw size={12} />
            <span>Reset Cache</span>
          </button>
        )}

        {iteration === 3 && (
          <button
            className="btn-explore-graph-header"
            onClick={onExploreGraph}
            title="Explore the entire Causal Exposure Graph"
          >
            <Network size={12} />
            <span>Explore Graph</span>
          </button>
        )}

        <button
          type="button"
          className="btn-secondary"
          onClick={onOpenSettings}
          title="Configure non-secret model routing"
        >
          <Settings size={12} />
          <span>Settings</span>
        </button>
      </div>

      <div className="subheader-right">
        <span className="last-updated-label">
          LAST UPDATED: <span className="last-updated-value">14:32 UTC</span>
        </span>
        <div className="header-vertical-divider" style={{ height: '16px', background: 'var(--border-color)', width: '1px', margin: '0 0.5rem' }} />
        <div className="live-feed-indicator" style={{ marginRight: '0.5rem' }}>
          <span className="indicator-dot green-pulse" />
          <span className="indicator-text">LIVE FEED ACTIVE</span>
        </div>

        <button
          className="btn-fetch-catalysts"
          onClick={onRunPipeline}
          disabled={loading || watchlistCount === 0}
        >
          {loading ? (
            <div className="spinner-white" />
          ) : (
            <RefreshCw size={14} style={{ marginRight: '0.4rem' }} />
          )}
          <span>Fetch Catalysts</span>
        </button>

        {/* While a run is in flight, offer to stop waiting on it. This aborts the browser
            request only; the backend keeps running until it finishes or times out. */}
        {loading && onCancelRun && (
          <button
            type="button"
            className="btn-secondary"
            onClick={onCancelRun}
            title="Stop waiting for the current run (backend keeps processing)"
            style={{ marginLeft: '0.5rem' }}
          >
            <X size={12} />
            <span>Stop Waiting</span>
          </button>
        )}
      </div>
    </div>
  );
}
