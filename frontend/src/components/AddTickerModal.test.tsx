import type { FormEvent } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AddTickerModal } from './AddTickerModal';

describe('AddTickerModal', () => {
  it('keeps submit disabled until a ticker is entered and submits the form', async () => {
    const user = userEvent.setup();
    const onTickerChange = vi.fn();
    const onSubmit = vi.fn((event: FormEvent) => event.preventDefault());

    const { rerender } = render(
      <AddTickerModal
        open
        newTicker=""
        onTickerChange={onTickerChange}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />
    );

    expect(screen.getByRole('button', { name: /^add asset$/i })).toBeDisabled();

    await user.type(screen.getByPlaceholderText(/ticker symbol/i), 'msft');
    expect(onTickerChange).toHaveBeenCalled();

    rerender(
      <AddTickerModal
        open
        newTicker="MSFT"
        onTickerChange={onTickerChange}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />
    );

    await user.click(screen.getByRole('button', { name: /^add asset$/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('closes from the explicit close action', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <AddTickerModal
        open
        newTicker="AAPL"
        onTickerChange={vi.fn()}
        onClose={onClose}
        onSubmit={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: /close add asset dialog/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
