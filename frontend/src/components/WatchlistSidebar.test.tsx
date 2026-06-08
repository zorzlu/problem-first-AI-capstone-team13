import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { WatchlistSidebar } from './WatchlistSidebar';

function renderSidebar(overrides = {}) {
  const props = {
    open: true,
    watchlist: ['AAPL', 'MSFT'],
    activeTicker: 'dashboard',
    searchQuery: '',
    runResult: null,
    getTickerCompanyName: (ticker: string) => ticker === 'AAPL' ? 'Apple Inc.' : 'Microsoft Corp.',
    onBackdropClick: vi.fn(),
    onDashboardSelect: vi.fn(),
    onSearchChange: vi.fn(),
    onAddAsset: vi.fn(),
    onTickerSelect: vi.fn(),
    ...overrides,
  };

  render(<WatchlistSidebar {...props} />);
  return props;
}

describe('WatchlistSidebar', () => {
  it('dispatches dashboard, add, search, and ticker selection actions', async () => {
    const user = userEvent.setup();
    const props = renderSidebar();

    await user.click(screen.getByRole('button', { name: /overview dashboard/i }));
    await user.click(screen.getByRole('button', { name: /add asset/i }));
    await user.type(screen.getByPlaceholderText(/search tickers/i), 'ms');
    await user.click(screen.getByText('MSFT'));

    expect(props.onDashboardSelect).toHaveBeenCalledTimes(1);
    expect(props.onAddAsset).toHaveBeenCalledTimes(1);
    expect(props.onSearchChange).toHaveBeenCalled();
    expect(props.onTickerSelect).toHaveBeenCalledWith('MSFT');
  });

  it('filters tickers by company name', () => {
    renderSidebar({ searchQuery: 'apple' });

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
  });
});
