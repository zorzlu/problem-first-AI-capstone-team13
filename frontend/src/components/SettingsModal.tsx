import { Settings, X } from 'lucide-react';

import { DEFAULT_SETTINGS, LLM_STEP_LABELS } from '../types';
import type { AppSettings } from '../types';

interface SettingsModalProps {
  open: boolean;
  appSettings: AppSettings;
  allowedLlmProviders: string[];
  settingsSaving: boolean;
  settingsError: string | null;
  onClose: () => void;
  onSave: () => void;
  onRouteChange: (step: string, field: 'provider' | 'model', value: string) => void;
}

export function SettingsModal({
  open,
  appSettings,
  allowedLlmProviders,
  settingsSaving,
  settingsError,
  onClose,
  onSave,
  onRouteChange,
}: SettingsModalProps) {
  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="glass settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="add-ticker-header">
          <div>
            <h2>Runtime Settings</h2>
            <p>Non-secret model routing. API keys remain in backend/.env.</p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close settings dialog">
            <X size={16} />
          </button>
        </div>

        <div className="settings-grid">
          {Object.keys(DEFAULT_SETTINGS.llmRoutes).map(step => {
            const route = appSettings.llmRoutes[step] || { provider: '', model: '' };
            return (
              <div key={step} className="settings-row">
                <div>
                  <div className="settings-row-title">{LLM_STEP_LABELS[step]}</div>
                  <div className="settings-row-subtitle">Blank uses the backend default route.</div>
                </div>
                <select
                  className="settings-select"
                  value={route.provider}
                  onChange={(e) => onRouteChange(step, 'provider', e.target.value)}
                >
                  <option value="">Default</option>
                  {allowedLlmProviders.map(provider => (
                    <option key={provider} value={provider}>{provider}</option>
                  ))}
                </select>
                <input
                  className="settings-input"
                  value={route.model}
                  onChange={(e) => onRouteChange(step, 'model', e.target.value)}
                  placeholder="Provider default model"
                />
              </div>
            );
          })}
        </div>

        {settingsError && <div className="settings-error">{settingsError}</div>}

        <div className="add-ticker-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn-primary" onClick={onSave} disabled={settingsSaving}>
            {settingsSaving ? <div className="spinner-white" /> : <Settings size={15} />}
            <span>Save Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
}
