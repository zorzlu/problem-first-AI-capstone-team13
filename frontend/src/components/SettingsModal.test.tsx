import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DEFAULT_SETTINGS } from '../types';
import { SettingsModal } from './SettingsModal';

describe('SettingsModal', () => {
  it('calls route-change handlers for provider and model edits', async () => {
    const user = userEvent.setup();
    const onRouteChange = vi.fn();

    render(
      <SettingsModal
        open
        appSettings={DEFAULT_SETTINGS}
        allowedLlmProviders={['openai', 'gemini']}
        settingsSaving={false}
        settingsError={null}
        onClose={vi.fn()}
        onSave={vi.fn()}
        onRouteChange={onRouteChange}
      />
    );

    const extractionRow = screen.getByText('Extraction').closest('.settings-row');
    expect(extractionRow).not.toBeNull();

    await user.selectOptions(within(extractionRow as HTMLElement).getByRole('combobox'), 'openai');
    await user.type(within(extractionRow as HTMLElement).getByPlaceholderText(/provider default model/i), 'gpt-test');

    expect(onRouteChange).toHaveBeenCalledWith('extraction', 'provider', 'openai');
    expect(onRouteChange).toHaveBeenCalledWith('extraction', 'model', expect.stringContaining('g'));
  });

  it('shows errors and disables save while saving', () => {
    render(
      <SettingsModal
        open
        appSettings={DEFAULT_SETTINGS}
        allowedLlmProviders={['openai']}
        settingsSaving
        settingsError="Settings failed"
        onClose={vi.fn()}
        onSave={vi.fn()}
        onRouteChange={vi.fn()}
      />
    );

    expect(screen.getByText('Settings failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save settings/i })).toBeDisabled();
  });
});
