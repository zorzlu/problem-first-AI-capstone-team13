import type { FormEvent } from 'react';
import { Plus, X } from 'lucide-react';

interface AddTickerModalProps {
  open: boolean;
  newTicker: string;
  onTickerChange: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}

export function AddTickerModal({
  open,
  newTicker,
  onTickerChange,
  onClose,
  onSubmit,
}: AddTickerModalProps) {
  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="glass add-ticker-modal" onSubmit={onSubmit} onClick={(e) => e.stopPropagation()}>
        <div className="add-ticker-header">
          <div>
            <h2>Add Asset</h2>
            <p>Add a ticker to the active watchlist.</p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close add asset dialog">
            <X size={16} />
          </button>
        </div>
        <input
          autoFocus
          type="text"
          placeholder="Ticker symbol, e.g. MSFT"
          className="watchlist-input add-ticker-input"
          value={newTicker}
          onChange={(e) => onTickerChange(e.target.value)}
        />
        <div className="add-ticker-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={!newTicker.trim()}>
            <Plus size={15} />
            <span>Add Asset</span>
          </button>
        </div>
      </form>
    </div>
  );
}
