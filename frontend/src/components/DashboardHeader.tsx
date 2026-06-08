import { EngineStatusPopover } from './EngineStatusPopover';
import { RunControls } from './RunControls';

interface DashboardHeaderProps {
  iteration: number;
  scenarioId: string;
  loading: boolean;
  watchlistCount: number;
  phoenixStatus: { running: boolean; dashboardUrl: string };
  memoryStatus: any;
  onIterationChange: (n: number) => void;
  onScenarioChange: (id: string) => void;
  onClearLedger: () => void;
  onExploreGraph: () => void;
  onOpenSettings: () => void;
  onRunPipeline: () => void;
  onCancelRun: () => void;
}

export function DashboardHeader({
  iteration,
  scenarioId,
  loading,
  watchlistCount,
  phoenixStatus,
  memoryStatus,
  onIterationChange,
  onScenarioChange,
  onClearLedger,
  onExploreGraph,
  onOpenSettings,
  onRunPipeline,
  onCancelRun,
}: DashboardHeaderProps) {
  return (
    <header className="main-app-header">
      {/* Top Tier: Main Header */}
      <div className="header-top-tier">
        <div className="header-left">
          <span className="app-brand-title">Cross-Impact Catalyst Briefings</span>
        </div>

        {/* Iteration Switcher */}
        <nav className="iteration-tabs-container">
          <button
            className={`iteration-tab-item ${iteration === 1 ? 'active' : ''}`}
            onClick={() => onIterationChange(1)}
          >
            <span className="tab-title">Iteration 1</span>
            <span className="tab-subtitle">Direct News Only</span>
          </button>
          <button
            className={`iteration-tab-item ${iteration === 2 ? 'active' : ''}`}
            onClick={() => onIterationChange(2)}
          >
            <span className="tab-title">Iteration 2</span>
            <span className="tab-subtitle">News + History</span>
          </button>
          <button
            className={`iteration-tab-item ${iteration === 3 ? 'active' : ''}`}
            onClick={() => onIterationChange(3)}
          >
            <span className="tab-title">Iteration 3</span>
            <span className="tab-subtitle">Cross-Impact Graph</span>
          </button>
        </nav>

        <div className="header-right">
          {/* Phoenix Active Indicator */}
          <div className="header-status-item">
            <span className="status-indicator-dot green-pulse" />
            <span className="status-label">PHOENIX: <span className="status-value-active">ACTIVE</span></span>
            {phoenixStatus.running && phoenixStatus.dashboardUrl && (
              <a
                href={phoenixStatus.dashboardUrl}
                target="_blank"
                rel="noreferrer"
                className="status-link-purple"
              >
                Phoenix Traces
              </a>
            )}
          </div>

          <EngineStatusPopover memoryStatus={memoryStatus} />
        </div>
      </div>

      <RunControls
        scenarioId={scenarioId}
        iteration={iteration}
        loading={loading}
        watchlistCount={watchlistCount}
        onScenarioChange={onScenarioChange}
        onClearLedger={onClearLedger}
        onExploreGraph={onExploreGraph}
        onOpenSettings={onOpenSettings}
        onRunPipeline={onRunPipeline}
        onCancelRun={onCancelRun}
      />
    </header>
  );
}
