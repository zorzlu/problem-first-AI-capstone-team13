import { useState } from 'react';
import { Database } from 'lucide-react';

interface EngineStatusPopoverProps {
  memoryStatus: any;
}

export function EngineStatusPopover({ memoryStatus }: EngineStatusPopoverProps) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="header-status-item engine-popover-trigger"
      style={{ position: 'relative', cursor: 'pointer' }}
      onClick={() => setOpen(!open)}
    >
      <Database size={14} style={{ color: 'var(--text-muted)' }} />
      <span className="status-label">Memory Engine: <span className="status-value-bold">Local embeddings</span></span>

      {open && (
        <>
          <div className="engine-popover-backdrop" onClick={(e) => { e.stopPropagation(); setOpen(false); }} />
          <div className="engine-popover" onClick={(e) => e.stopPropagation()}>
            <div className="engine-popover-header">
              Embeddings Memory Engine
            </div>
            {memoryStatus ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--text-primary)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="metric-label">Dedup Provider</span>
                  <span style={{
                    fontWeight: 700,
                    padding: '0.1rem 0.35rem',
                    borderRadius: '3px',
                    background: memoryStatus.isFallbackActive ? 'rgba(234, 88, 12, 0.12)' : 'rgba(87, 0, 225, 0.12)',
                    color: memoryStatus.isFallbackActive ? 'var(--accent-orange)' : 'var(--accent-purple)',
                    border: `1px solid ${memoryStatus.isFallbackActive ? 'rgba(234,88,12,0.3)' : 'rgba(87,0,225,0.3)'}`
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
                    Local embedding model unavailable. Using deterministic lexical cosine fallback.
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
  );
}
