import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

async function importClientWithBaseUrl(baseUrl?: string) {
  vi.resetModules();
  if (baseUrl === undefined) {
    vi.unstubAllEnvs();
  } else {
    vi.stubEnv('VITE_API_BASE_URL', baseUrl);
  }
  return import('./client');
}

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('uses relative API paths when no deployed base URL is configured', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(jsonResponse({ tickers: ['AAPL'] }));

    const client = await importClientWithBaseUrl();
    await client.getWatchlist();

    expect(fetchMock).toHaveBeenCalledWith('/api/watchlist');
  });

  it('prefixes requests with VITE_API_BASE_URL and trims a trailing slash', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(jsonResponse({ nodes: [], edges: [] }));

    const client = await importClientWithBaseUrl('https://backend.example.com/');
    await client.getGraph();

    expect(fetchMock).toHaveBeenCalledWith('https://backend.example.com/api/graph');
  });

  it('serializes run parameters using the backend field names', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(jsonResponse({ runId: 'run_1' }));

    const client = await importClientWithBaseUrl();
    await client.runPipeline({
      iteration: 3,
      scenarioId: 'scenario-3',
      simulatedNow: '2026-05-28T17:25:00Z',
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        iteration: 3,
        scenario_id: 'scenario-3',
        simulated_now: '2026-05-28T17:25:00Z',
      }),
    });
  });

  it('surfaces backend error envelopes as thrown errors', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(jsonResponse(
      { error: { message: 'Graph expansion is already running' } },
      { status: 409 },
    ));

    const client = await importClientWithBaseUrl();

    await expect(client.expandGraph('AAPL')).rejects.toThrow('Graph expansion is already running');
  });
});
