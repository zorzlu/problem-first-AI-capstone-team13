import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { RunControls } from './RunControls';

function renderControls(overrides = {}) {
  const props = {
    scenarioId: 'live',
    iteration: 3,
    loading: false,
    watchlistCount: 2,
    onScenarioChange: vi.fn(),
    onClearLedger: vi.fn(),
    onExploreGraph: vi.fn(),
    onOpenSettings: vi.fn(),
    onRunPipeline: vi.fn(),
    ...overrides,
  };

  render(<RunControls {...props} />);
  return props;
}

describe('RunControls', () => {
  it('dispatches scenario, graph, settings, and run actions', async () => {
    const user = userEvent.setup();
    const props = renderControls();

    await user.selectOptions(screen.getByLabelText(/source/i), 'cross_impact');
    await user.click(screen.getByRole('button', { name: /explore graph/i }));
    await user.click(screen.getByRole('button', { name: /settings/i }));
    await user.click(screen.getByRole('button', { name: /fetch catalysts/i }));

    expect(props.onScenarioChange).toHaveBeenCalledWith('cross_impact');
    expect(props.onExploreGraph).toHaveBeenCalledTimes(1);
    expect(props.onOpenSettings).toHaveBeenCalledTimes(1);
    expect(props.onRunPipeline).toHaveBeenCalledTimes(1);
  });

  it('disables catalyst fetches when no watchlist assets exist', () => {
    renderControls({ watchlistCount: 0 });

    expect(screen.getByRole('button', { name: /fetch catalysts/i })).toBeDisabled();
  });

  it('hides graph controls before iteration 3', () => {
    renderControls({ iteration: 2 });

    expect(screen.queryByRole('button', { name: /explore graph/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset cache/i })).toBeInTheDocument();
  });
});
