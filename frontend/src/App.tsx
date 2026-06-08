import { AlertCircle, Cpu, RotateCcw } from 'lucide-react';

import { useDashboardState } from './hooks/useDashboardState';
import { usePollingStatus } from './hooks/usePollingStatus';
import { AddTickerModal } from './components/AddTickerModal';
import { DashboardHeader } from './components/DashboardHeader';
import { GraphModal } from './components/GraphModal';
import { ResultsView } from './components/ResultsView';
import { SettingsModal } from './components/SettingsModal';
import { TickerDetailPanel } from './components/TickerDetailPanel';
import { WatchlistSidebar } from './components/WatchlistSidebar';

export default function App() {
  const dash = useDashboardState();

  const { connectionState, retryCount, handleManualRetry } = usePollingStatus({
    checkConnectionDirect: dash.checkConnectionDirect,
    graphStatus: dash.graphStatus,
    fetchGraphStatus: dash.fetchGraphStatus,
    fetchGraph: dash.fetchGraph,
  });

  // ─── Connection screens ───────────────────────────────────────────────────

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

  // ─── Main app ─────────────────────────────────────────────────────────────

  return (
    <div className={`app-layout theme-iter-${dash.iteration}`}>

      <DashboardHeader
        iteration={dash.iteration}
        scenarioId={dash.scenarioId}
        loading={dash.loading}
        watchlistCount={dash.watchlist.length}
        phoenixStatus={dash.phoenixStatus}
        memoryStatus={dash.memoryStatus}
        onIterationChange={(n) => {
          dash.setIteration(n);
          dash.setSelectedCatalystPath(null);
        }}
        onScenarioChange={dash.setScenarioId}
        onClearLedger={dash.clearLedgerMemory}
        onExploreGraph={() => {
          dash.setGraphFilterTicker(null);
          dash.setGraphModalOpen(true);
        }}
        onOpenSettings={() => dash.setSettingsOpen(true)}
        onRunPipeline={dash.runPipeline}
        onCancelRun={dash.cancelRun}
      />

      {/* Main Workspace */}
      <div className="workspace">

        <WatchlistSidebar
          open={dash.sidebarOpen}
          watchlist={dash.watchlist}
          activeTicker={dash.activeTicker}
          searchQuery={dash.searchQuery}
          runResult={dash.runResult}
          getTickerCompanyName={dash.getTickerCompanyName}
          onBackdropClick={() => dash.setSidebarOpen(false)}
          onDashboardSelect={() => {
            dash.setActiveTicker('dashboard');
            dash.setSelectedCatalystPath(null);
            dash.setSidebarOpen(false);
          }}
          onSearchChange={dash.setSearchQuery}
          onAddAsset={() => dash.setAddTickerOpen(true)}
          onTickerSelect={(ticker) => {
            dash.setActiveTicker(ticker);
            dash.setSelectedCatalystPath(null);
            dash.setSidebarOpen(false);
          }}
        />

        {/* Center Panel */}
        <main className="main-content">

          {dash.loading ? (
            <div className="glass loading-overlay" style={{ flex: 1 }}>
              <div className="spinner"></div>
              <h2>
                {dash.iteration === 1 && 'Executing LLM Direct News Workflow'}
                {dash.iteration === 2 && 'Executing LLM Memory Deduplication'}
                {dash.iteration === 3 && 'Executing LLM Catalyst Workflow Graph'}
              </h2>
              <p style={{ color: 'var(--text-secondary)' }}>
                {dash.iteration === 1 && 'Fetching direct articles and executing extraction + synthesis...'}
                {dash.iteration === 2 && 'Deduplicating articles using local vector memory ledger...'}
                {dash.iteration === 3 && 'Expanding search terms and routing untickered geopolitical shocks...'}
              </p>
            </div>
          ) : dash.activeTicker === 'dashboard' ? (
            <ResultsView
              watchlist={dash.watchlist}
              iteration={dash.iteration}
              scenarioId={dash.scenarioId}
              runResult={dash.runResult}
              ledgerEntries={dash.ledgerEntries}
              graphData={dash.graphData}
              onTickerSelect={(ticker) => {
                dash.setActiveTicker(ticker);
              }}
            />
          ) : (
            <TickerDetailPanel
              activeTicker={dash.activeTicker}
              iteration={dash.iteration}
              scenarioId={dash.scenarioId}
              runResult={dash.runResult}
              ledgerEntries={dash.ledgerEntries}
              selectedCatalystPath={dash.selectedCatalystPath}
              selectedBackgroundStory={dash.selectedBackgroundStory}
              summaryDetailExpanded={dash.summaryDetailExpanded}
              getTickerCompanyName={dash.getTickerCompanyName}
              onSelectCatalystPath={dash.setSelectedCatalystPath}
              onSelectBackgroundStory={dash.setSelectedBackgroundStory}
              onToggleSummaryDetail={dash.setSummaryDetailExpanded}
              onOpenGraph={(filterTicker) => {
                dash.setGraphFilterTicker(filterTicker);
                dash.setGraphModalOpen(true);
              }}
            />
          )}
        </main>
      </div>

      <AddTickerModal
        open={dash.addTickerOpen}
        newTicker={dash.newTicker}
        onTickerChange={dash.setNewTicker}
        onClose={() => dash.setAddTickerOpen(false)}
        onSubmit={dash.addTicker}
      />

      <SettingsModal
        open={dash.settingsOpen}
        appSettings={dash.appSettings}
        allowedLlmProviders={dash.allowedLlmProviders}
        settingsSaving={dash.settingsSaving}
        settingsError={dash.settingsError}
        onClose={() => dash.setSettingsOpen(false)}
        onSave={dash.saveSettings}
        onRouteChange={dash.updateLlmRoute}
      />

      {/* Full-screen Exposure Graph Modal */}
      {dash.graphModalOpen && (
        <GraphModal
          graphData={dash.graphData}
          graphStatus={dash.graphStatus}
          watchlist={dash.watchlist}
          graphFilterTicker={dash.graphFilterTicker}
          selectedCatalystPath={dash.selectedCatalystPath}
          onClose={() => dash.setGraphModalOpen(false)}
          onRebuildGraph={dash.rebuildGraph}
          onTriggerExpansion={dash.triggerExpansion}
        />
      )}
    </div>
  );
}
