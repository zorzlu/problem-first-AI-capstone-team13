import React from 'react';
import { Database, Network, ShieldAlert } from 'lucide-react';

import type { EventEntry, RunResult, TickerSummary, TickerBucket } from '../types';

interface TickerDetailPanelProps {
  activeTicker: string;
  iteration: number;
  scenarioId: string;
  runResult: RunResult | null;
  ledgerEntries: any[];
  selectedCatalystPath: string[] | null;
  selectedBackgroundStory: string | null;
  summaryDetailExpanded: boolean;
  getTickerCompanyName: (ticker: string) => string;
  onSelectCatalystPath: (path: string[] | null) => void;
  onSelectBackgroundStory: (id: string | null) => void;
  onToggleSummaryDetail: (expanded: boolean) => void;
  onOpenGraph: (filterTicker: string) => void;
}

export function TickerDetailPanel({
  activeTicker,
  iteration,
  scenarioId,
  runResult,
  ledgerEntries,
  selectedCatalystPath,
  selectedBackgroundStory,
  summaryDetailExpanded,
  getTickerCompanyName,
  onSelectCatalystPath,
  onSelectBackgroundStory,
  onToggleSummaryDetail,
  onOpenGraph,
}: TickerDetailPanelProps) {
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

  const getEventDecision = (eventId: string): string => {
    if (!runResult || !runResult.routedCandidates) return 'new';
    const cand = runResult.routedCandidates.find((c: any) => c.eventId === eventId && c.ticker === activeTicker);
    return cand?.ledgerDecision || 'new';
  };

  const getEventCatalystId = (eventId: string): string | null => {
    if (!runResult || !runResult.routedCandidates) return null;
    const cand = runResult.routedCandidates.find((c: any) => c.eventId === eventId && c.ticker === activeTicker);
    return cand?.catalystId || null;
  };

  const getEventTimestamp = (sourceArticleIds: string[]): string | null => {
    if (!runResult || !runResult.rawArticles || !sourceArticleIds || sourceArticleIds.length === 0) return null;
    const art = runResult.rawArticles.find((a: any) => sourceArticleIds.includes(a.articleId));
    return art?.publishedAt || null;
  };

  const getActiveSynthesis = (): TickerSummary | null => {
    if (!runResult || !runResult.tickerSyntheses) return null;
    return runResult.tickerSyntheses[activeTicker] || null;
  };

  const getActiveBucket = (): TickerBucket | null => {
    if (!runResult || !runResult.tickerBuckets) return null;
    return runResult.tickerBuckets[activeTicker] || null;
  };

  // ─── Render ──────────────────────────────────────────────────────────────────

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
  const hasCatalysts = synthesis.summaryHeadline !== 'No new catalysts detected';

  // Gather and filter supporting events
  const directEvents = bucket?.directEvents ?? [];
  const crossImpactEvents = bucket?.crossImpactEvents ?? [];
  const allEvents = [...directEvents, ...crossImpactEvents];

  // Filter out cross-impact events if iteration < 3
  const filteredAllEvents = iteration < 3
    ? allEvents.filter(e => !crossImpactEvents.find(c => c.eventId === e.eventId))
    : allEvents;

  // Helper to get score for sorting
  const getCombinedScore = (evt: EventEntry): number => {
    const ts = getEventTimestamp(evt.sourceArticleIds);
    const timeMs = ts ? new Date(ts).getTime() : 0;
    const now = scenarioId === 'live' ? Date.now() : new Date('2026-05-28T17:25:00Z').getTime();
    const ageMinutes = Math.max(0, (now - timeMs) / 60000);

    const catalystInfo = synthesis.mainCatalysts?.find((c: any) => c.eventId === evt.eventId);
    const significance = catalystInfo ? (catalystInfo.significance || 5) : 3;

    return (significance * 10) - (ageMinutes * 0.5);
  };

  const sortedEvents = [...filteredAllEvents].sort((a, b) => getCombinedScore(b) - getCombinedScore(a));
  const activeTickerLedger = ledgerEntries.filter((l: any) => l.ticker === activeTicker);

  return (
    <div className="ticker-detail-split">
      {/* Left Column: Ticker Synthesis Briefing */}
      <div className="briefing-column">

        {/* FOCUS ASSET INFO CARD */}
        <div className="glass focus-asset-info-card">
          <div className="focus-asset-header-row">
            <div>
              <span className="focus-ticker-title">{activeTicker}</span>
              <span className="focus-company-subtitle">{getTickerCompanyName(activeTicker)}</span>
            </div>
            <span className="focus-asset-badge">FOCUS ASSET</span>
          </div>

          <div className="focus-metrics-row">
            {/* Sentiment Card */}
            <div className={`focus-metric-card sentiment-${influenceColor}`}>
              <div className="focus-metric-title">SYNTHESIS SENTIMENT</div>
              <div className="focus-metric-value-row">
                <span className="focus-metric-value">
                  {hasCatalysts ? (
                    influenceColor === 'positive' ? 'Bullish Bias' :
                    influenceColor === 'negative' ? 'Bearish Bias' :
                    influenceColor === 'mixed' ? 'Mixed Pressures' : 'Unclear Direction'
                  ) : 'No New Catalysts'}
                </span>
                <span className="focus-metric-icon">
                  {influenceColor === 'positive' && (
                    <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"></path>
                    </svg>
                  )}
                  {influenceColor === 'negative' && (
                    <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6L9 12.75l4.306-4.307a11.95 11.95 0 015.814 5.519l2.74 1.22m0 0l-5.94 2.28m5.94-2.28l-2.28-5.941"></path>
                    </svg>
                  )}
                  {(influenceColor === 'mixed' || influenceColor === 'unclear') && (
                    <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14"></path>
                    </svg>
                  )}
                </span>
              </div>
            </div>

            {/* Confidence Card */}
            <div className="focus-metric-card confidence-purple">
              <div className="focus-metric-title">MODEL CONFIDENCE</div>
              <div className="focus-metric-value-row">
                <span className="focus-metric-value">
                  {synthesis.confidence === 'high' ? 'High (88%)' :
                   synthesis.confidence === 'medium' ? 'Medium (65%)' :
                   synthesis.confidence === 'low' ? 'Low (42%)' : 'Tentative (30%)'}
                </span>
                <span className="focus-metric-icon">
                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z"></path>
                  </svg>
                </span>
              </div>
            </div>
          </div>

          {/* View Causal Graph Button */}
          {iteration === 3 && (
            <div style={{ marginTop: '1rem' }}>
              <button
                onClick={() => onOpenGraph(activeTicker)}
                className="btn-primary-purple"
              >
                <Network size={16} style={{ marginRight: '0.5rem' }} />
                View Causal Graph
              </button>
            </div>
          )}
        </div>

        {/* DETAILED BRIEFING CARD */}
        <div className="glass synthesis-card briefing-detail-card">
          <h2 className="briefing-headline">{synthesis.summaryHeadline}</h2>

          <div className="synthesis-summary briefing-summary-box">
            {(() => {
              const text = synthesis.situationSummary || '';
              const sentences = text.match(/[^.!?]+[.!?]+(\s|$)/g) || [text];
              if (sentences.length <= 2) {
                return <span>{text}</span>;
              }
              const shortPart = sentences.slice(0, 2).join('').trim();
              const restPart = sentences.slice(2).join('').trim();

              if (summaryDetailExpanded) {
                return (
                  <span>
                    {shortPart} {restPart}
                    <span className="summary-toggle-link" onClick={() => onToggleSummaryDetail(false)}>
                      [Show Less]
                    </span>
                  </span>
                );
              } else {
                return (
                  <span>
                    {shortPart}...
                    <span className="summary-toggle-link" onClick={() => onToggleSummaryDetail(true)}>
                      [Show More]
                    </span>
                  </span>
                );
              }
            })()}
          </div>

          {/* Columns: Uncertainties & Watch Items */}
          <div className="synthesis-details-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginTop: '1.25rem' }}>
            <div className="details-column uncertainties-box">
              <h3 className="uncertainties-title">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '0.35rem' }}>
                  <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                  <line x1="12" y1="9" x2="12" y2="13"/>
                  <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                Uncertainties / Open Risks
              </h3>
              <ul className="details-list">
                {synthesis.uncertainties.map((u, i) => (
                  <li key={i} className="uncertainty-item">{u}</li>
                ))}
              </ul>
            </div>

            <div className="details-column watchitems-box">
              <h3 className="watchitems-title">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '0.35rem' }}>
                  <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
                Trader Watchlist Items
              </h3>
              <ul className="details-list">
                {synthesis.watchItems.map((wi, i) => (
                  <li key={i} className="watchitem-item">{wi}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Compliance Disclaimer */}
          <div className="compliance-disclaimer">
            <ShieldAlert size={14} style={{ color: 'var(--accent-orange)', flexShrink: 0 }} />
            <p style={{ fontSize: '0.75rem', margin: 0 }}>{synthesis.complianceDisclaimer || 'Grounded information only. Not investment advice.'}</p>
          </div>
        </div>
      </div>

      {/* Right Column: Unified Live Feed + Structured Memory Index */}
      <div className="feed-column">

        {/* Unified Live Feed */}
        <div className="catalysts-section">
          <h3 className="feed-type-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span className="pulsing-dot" style={{ color: iteration === 1 ? 'var(--accent-blue)' : iteration === 2 ? 'var(--accent-purple)' : 'var(--accent-cyan)' }} />
              ⚡ Live Updates &amp; Catalyst Feed
            </span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'none', fontWeight: 'normal' }}>
              {sortedEvents.length} events sorted by recency &amp; significance
            </span>
          </h3>

          {sortedEvents.length > 0 ? (
            <div className="catalysts-grid">
              {sortedEvents.map((evt) => {
                const isCross = crossImpactEvents.find(c => c.eventId === evt.eventId);
                const isGraphHovered = selectedCatalystPath && selectedCatalystPath.join(',') === evt.impactPath?.join(',');
                const ts = getEventTimestamp(evt.sourceArticleIds);

                const catId = getEventCatalystId(evt.eventId);
                const elId = catId ? `evt-${catId}` : `evt-${evt.eventId}`;

                const ledgerEntry = ledgerEntries.find((l: any) => l.catalystId === catId);

                const decision = iteration === 1 ? 'new' : getEventDecision(evt.eventId);
                const isUpdate = decision === 'update';

                const catalystInfo = synthesis.mainCatalysts?.find((c: any) => c.eventId === evt.eventId);
                const significance = catalystInfo ? (catalystInfo.significance || 5) : 3;

                const newFacts = evt.hardFacts;
                const prevFacts = (isUpdate && ledgerEntry)
                  ? ledgerEntry.hardFactsSeen
                      .map((f: any) => (typeof f === 'object' && f !== null) ? f.fact : String(f))
                      .filter((factText: string) => !newFacts.includes(factText))
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
                    onMouseEnter={() => isCross && evt.impactPath && onSelectCatalystPath(evt.impactPath)}
                    onMouseLeave={() => isCross && onSelectCatalystPath(null)}
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
                        <div className="timeline-title">Story Timeline &amp; Fact Progression</div>
                        <div className="timeline-facts-box">
                          {/* New Facts */}
                          {newFacts.map((fact, index) => (
                            <div key={`new-${index}`} className="timeline-node new-fact">
                              <span className="timeline-badge-new">NEW</span>
                              {fact}
                            </div>
                          ))}

                          {/* Previous Facts (Dimmed) */}
                          {prevFacts.map((fact: string, index: number) => (
                            <div key={`prev-${index}`} className="timeline-node" style={{ opacity: 0.55 }}>
                              <span className="timeline-badge-priced-in">PRICED IN</span>
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

        {/* Active Memory Index (Database state — shown in Iterations 2 & 3) */}
        {iteration > 1 && activeTickerLedger.length > 0 && (
          <section className="glass panel-card">
            <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
              <Database size={13} style={{ color: 'var(--accent-purple)' }} />
              Active Memory Index ({activeTickerLedger.length} stories in local DB)
            </h2>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
              Current state of local vector database memory. Click active updates to scroll to card, or background entries to expand hard facts inline.
            </p>
            <div className="memory-index-scroll">
              {activeTickerLedger.map((entry: any) => {
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
                        onSelectBackgroundStory(isSelected ? null : entry.catalystId);
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
                          {entry.hardFactsSeen.map((factObj: any, idx: number) => {
                            const factText = (typeof factObj === 'object' && factObj !== null) ? factObj.fact : String(factObj);
                            return (
                              <div key={idx} className="expanded-fact-item">• {factText}</div>
                            );
                          })}
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
}
