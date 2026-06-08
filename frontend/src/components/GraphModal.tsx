import { Network, RefreshCw, RotateCcw, X } from 'lucide-react';

import { GraphView } from './GraphView';
import type { ExposureGraph, ExpansionStatus } from '../types';

interface GraphModalProps {
  graphData: ExposureGraph;
  graphStatus: ExpansionStatus;
  watchlist: string[];
  graphFilterTicker: string | null;
  selectedCatalystPath: string[] | null;
  onClose: () => void;
  onRebuildGraph: (reset: boolean) => void;
  onTriggerExpansion: (ticker: string) => void;
}

export function GraphModal({
  graphData,
  graphStatus,
  watchlist,
  graphFilterTicker,
  selectedCatalystPath,
  onClose,
  onRebuildGraph,
  onTriggerExpansion,
}: GraphModalProps) {
  // ─── Helpers ────────────────────────────────────────────────────────────────

  const graphStatusFor = (ticker: string): string => {
    const s = graphStatus[ticker]?.status;
    if (s) return s;
    return graphData.nodes.some(n => n.nodeId === `ticker_${ticker}`) ? 'ready' : 'none';
  };

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
    const meta = map[status] || map['none'];
    const spinning = status === 'pending' || status === 'running';
    return (
      <span style={{ fontSize: '0.6rem', color: meta.color, display: 'flex', alignItems: 'center', gap: '0.2rem' }} title={graphStatus[ticker]?.error || meta.label}>
        {spinning && <span className="spinner" style={{ width: '8px', height: '8px', borderWidth: '1.5px' }} />}
        {meta.label}
      </span>
    );
  };

  // ─── Render ──────────────────────────────────────────────────────────────────

  const anyBusy = watchlist.some(t => ['pending', 'running'].includes(graphStatusFor(t)));

  return (
    <div className="graph-modal-backdrop" onClick={onClose}>
      <div className="graph-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Modal header */}
        <div className="graph-modal-header">
          <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
            <Network size={18} /> Causal Exposure Graph
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>
              {graphData.nodes.length} nodes · {graphData.edges.length} edges
            </span>
          </h2>
          <button onClick={onClose} className="btn-secondary" style={{ padding: '0.35rem 0.6rem', display: 'flex', alignItems: 'center', gap: '0.3rem', height: '30px' }}>
            <X size={14} /> Close
          </button>
        </div>

        <div className="graph-modal-body">
          {/* Large graph canvas */}
          <div className="graph-canvas-wrapper">
            <GraphView
              graphData={graphData}
              width={900}
              height={620}
              scale={2.2}
              selectedCatalystPath={selectedCatalystPath}
              activeTicker={graphFilterTicker || 'dashboard'}
              watchlist={watchlist}
            />
          </div>

          {/* Side rail: legend + per-ticker expansion controls */}
          <div className="graph-sidebar-rail">
            <div className="legend-section">
              <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Legend</h3>

              <div className="legend-item">
                <span className="legend-color-dot" style={{ background: 'var(--accent-purple)' }} />
                Ticker (watchlist)
              </div>

              <div className="legend-item">
                <span
                  className="legend-color-dot"
                  style={{
                    background: 'var(--accent-purple-light)',
                    border: '1.25px dashed var(--accent-purple)',
                    boxSizing: 'border-box'
                  }}
                />
                Ticker (derived)
              </div>

              <div className="legend-item">
                <span className="legend-color-dot" style={{ background: 'var(--accent-blue)' }} />
                Technology theme
              </div>

              <div className="legend-item">
                <span className="legend-color-dot" style={{ background: 'var(--accent-cyan)' }} />
                Company / sector
              </div>

              <div className="legend-item">
                <span className="legend-color-dot" style={{ background: 'var(--accent-orange)' }} />
                Region / risk / commodity / route
              </div>

              <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                Dashed edges = exposure links · solid = supplier/competitor/partner. Flow runs left → right into the ticker.
              </div>
            </div>

            <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.5rem 0' }} />

            <div>
              <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Global Rebuild</h3>
              <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.75rem' }}>
                <button
                  onClick={() => onRebuildGraph(true)}
                  disabled={anyBusy}
                  className="btn-secondary"
                  style={{ flex: 1, padding: '0.35rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: anyBusy ? 0.5 : 1, height: '30px' }}
                  title="Reset to curated seed, then re-expand every watchlist ticker"
                >
                  <RotateCcw size={12} /> From seed
                </button>
                <button
                  onClick={() => onRebuildGraph(false)}
                  disabled={anyBusy}
                  className="btn-secondary"
                  style={{ flex: 1, padding: '0.35rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: anyBusy ? 0.5 : 1, height: '30px' }}
                  title="Force a fresh expansion for every watchlist ticker on top of the current graph"
                >
                  <RefreshCw size={12} /> Refresh all
                </button>
              </div>

              <h3 className="section-title" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Per-Ticker</h3>
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
                      onClick={() => onTriggerExpansion(ticker)}
                      disabled={busy}
                      className="btn-secondary"
                      style={{ padding: '0.25rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem', opacity: busy ? 0.5 : 1, height: '28px' }}
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
  );
}
