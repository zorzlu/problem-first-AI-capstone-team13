import { Layers, Plus, Search } from 'lucide-react';

import type { RunResult } from '../types';

interface WatchlistSidebarProps {
  open: boolean;
  watchlist: string[];
  activeTicker: string;
  searchQuery: string;
  runResult: RunResult | null;
  getTickerCompanyName: (ticker: string) => string;
  onBackdropClick: () => void;
  onDashboardSelect: () => void;
  onSearchChange: (query: string) => void;
  onAddAsset: () => void;
  onTickerSelect: (ticker: string) => void;
}

export function WatchlistSidebar({
  open,
  watchlist,
  activeTicker,
  searchQuery,
  runResult,
  getTickerCompanyName,
  onBackdropClick,
  onDashboardSelect,
  onSearchChange,
  onAddAsset,
  onTickerSelect,
}: WatchlistSidebarProps) {
  return (
    <>
      {open && (
        <div className="sidebar-backdrop" onClick={onBackdropClick} />
      )}
      <aside className={`glass sidebar ${open ? 'open' : ''}`}>
        <button
          className={`glass glass-hover watchlist-dashboard-btn ${activeTicker === 'dashboard' ? 'active' : ''}`}
          onClick={onDashboardSelect}
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
              onChange={(event) => onSearchChange(event.target.value)}
            />
          </div>

          <button type="button" className="btn-secondary add-asset-btn" onClick={onAddAsset}>
            <Plus size={15} />
            <span>Add Asset</span>
          </button>
        </div>

        <div className="watchlist-list">
          {watchlist.map(ticker => {
            const companyName = getTickerCompanyName(ticker);
            const query = searchQuery.trim().toLowerCase();
            if (query && !ticker.toLowerCase().includes(query) && !companyName.toLowerCase().includes(query)) return null;

            const isActive = activeTicker === ticker;
            const tickerSynthesis = runResult?.tickerSyntheses?.[ticker];
            const influence = tickerSynthesis?.overallPossibleInfluence || 'unclear';
            const hasCatalysts = tickerSynthesis && tickerSynthesis.summaryHeadline !== 'No new catalysts detected';

            return (
              <div
                key={ticker}
                className={`glass glass-hover watchlist-item ${isActive ? 'active' : ''}`}
                onClick={() => onTickerSelect(ticker)}
              >
                <div className="watchlist-copy">
                  <div className="ticker-name">{ticker}</div>
                  <div className="company-name">{companyName}</div>
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
    </>
  );
}
