import { Clock, Database } from 'lucide-react';

import { getTickerSymbol } from './GraphView';
import type { ExposureGraph, RunResult } from '../types';

interface ResultsViewProps {
  watchlist: string[];
  iteration: number;
  scenarioId: string;
  runResult: RunResult | null;
  ledgerEntries: any[];
  graphData: ExposureGraph;
  onTickerSelect: (ticker: string) => void;
}

export function ResultsView({
  watchlist,
  iteration,
  scenarioId,
  runResult,
  ledgerEntries,
  graphData,
  onTickerSelect,
}: ResultsViewProps) {
  // ─── Helpers ────────────────────────────────────────────────────────────────

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

  const getEventTimestamp = (sourceArticleIds: string[]): string | null => {
    if (!runResult || !runResult.rawArticles || !sourceArticleIds || sourceArticleIds.length === 0) return null;
    const art = runResult.rawArticles.find((a: any) => sourceArticleIds.includes(a.articleId));
    return art?.publishedAt || null;
  };

  const getTickerCompanyName = (ticker: string): string => {
    const node = graphData.nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === ticker);
    if (node) return node.name;
    return (
      ticker === 'AAPL' ? 'Apple Inc.' :
      ticker === 'MSFT' ? 'Microsoft Corp.' :
      ticker === 'NVDA' ? 'Nvidia Corp.' :
      ticker === 'TSM' ? 'TSMC' :
      ticker === 'DAL' ? 'Delta Air Lines' : 'Public Company'
    );
  };

  // ─── Partition tickers ───────────────────────────────────────────────────────

  const activeAlertTickers = watchlist.filter(t => {
    const synth = runResult?.tickerSyntheses?.[t];
    return synth && synth.summaryHeadline !== 'No new catalysts detected';
  });
  const quietTickers = watchlist.filter(t => !activeAlertTickers.includes(t));

  const influenceIcons: Record<string, string> = {
    positive: '▲',
    negative: '▼',
    mixed: '◆',
    unclear: '—',
  };

  return (
    <div className={`dashboard-split ${iteration === 1 ? 'single-col' : ''}`}>
      {/* Left Column: Watchlist Signals */}
      <div className="dashboard-signals">
        {/* Active Alerts */}
        <div className="active-alerts-section">
          <h2 className="section-title">🚨 Active Shocks &amp; Alerts</h2>
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

                return (
                  <div
                    key={ticker}
                    className={`dashboard-card active-alert-card glow-${influence}`}
                    onClick={() => onTickerSelect(ticker)}
                  >
                    <div className="dashboard-card-header">
                      <div>
                        <div className="dashboard-card-ticker">{ticker}</div>
                        <div className="dashboard-card-company">
                          {(() => {
                            const node = graphData.nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === ticker);
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
                    <tr key={ticker} onClick={() => onTickerSelect(ticker)}>
                      <td className="quiet-row-ticker">{ticker}</td>
                      <td className="quiet-row-company">
                        {(() => {
                          const node = graphData.nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === ticker);
                          return node ? node.name : getTickerCompanyName(ticker);
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
              ledgerEntries.map((entry: any) => (
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
  );
}
