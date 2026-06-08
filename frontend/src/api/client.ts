import type { AppSettings, ExposureGraph, ExpansionStatus, RunResult } from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function readJson<T>(res: Response): Promise<T> {
  const data = await res.json();
  if (!res.ok) {
    const message = data?.error?.message
      || (typeof data?.detail === 'string' ? data.detail : JSON.stringify(data?.detail || data))
      || 'Request failed';
    throw new Error(message);
  }
  return data as T;
}

export async function getWatchlist(): Promise<{ tickers: string[] }> {
  return readJson(await fetch(apiUrl('/api/watchlist')));
}

export async function updateWatchlist(tickers: string[]): Promise<{ tickers: string[]; expansionStatus: ExpansionStatus }> {
  return readJson(await fetch(apiUrl('/api/watchlist'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers }),
  }));
}

export async function getGraph(): Promise<ExposureGraph> {
  return readJson(await fetch(apiUrl('/api/graph')));
}

export async function getGraphStatus(): Promise<{ status: ExpansionStatus }> {
  return readJson(await fetch(apiUrl('/api/graph/status')));
}

export async function expandGraph(ticker: string): Promise<{ expansionStatus: ExpansionStatus }> {
  return readJson(await fetch(apiUrl('/api/graph/expand'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, force: true }),
  }));
}

export async function rebuildGraph(reset: boolean): Promise<{ expansionStatus: ExpansionStatus }> {
  return readJson(await fetch(apiUrl('/api/graph/rebuild'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reset }),
  }));
}

export async function getResults(): Promise<Record<string, RunResult>> {
  return readJson(await fetch(apiUrl('/api/results')));
}

export async function getLedger(iteration: number): Promise<any[]> {
  return readJson(await fetch(apiUrl(`/api/ledger?iteration=${iteration}`)));
}

export async function clearLedger(iteration: number): Promise<void> {
  await readJson(await fetch(apiUrl(`/api/ledger/clear?iteration=${iteration}`), { method: 'POST' }));
}

export async function getPhoenixStatus(): Promise<any> {
  return readJson(await fetch(apiUrl('/api/phoenix-status')));
}

export async function getMemoryStatus(): Promise<any> {
  return readJson(await fetch(apiUrl('/api/memory-status')));
}

export async function getSettings(): Promise<{ settings: AppSettings; allowedLlmProviders: string[] }> {
  return readJson(await fetch(apiUrl('/api/settings')));
}

export async function saveSettings(settings: AppSettings): Promise<{ settings: AppSettings }> {
  return readJson(await fetch(apiUrl('/api/settings'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  }));
}

export async function runPipeline(params: {
  iteration: number;
  scenarioId: string;
  simulatedNow: string;
}, signal?: AbortSignal): Promise<RunResult> {
  // `signal` lets the UI stop waiting on a long run. Note: aborting only cancels the
  // browser's wait — the backend keeps executing until it finishes or hits
  // PIPELINE_RUN_TIMEOUT_SECONDS.
  return readJson(await fetch(apiUrl('/api/run'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      iteration: params.iteration,
      scenario_id: params.scenarioId,
      simulated_now: params.simulatedNow,
    }),
    signal,
  }));
}
