import React, { useState, useRef, useEffect } from 'react';

import * as api from '../api/client';
import { getTickerSymbol } from '../components/GraphView';
import { DEFAULT_SETTINGS } from '../types';
import type { AppSettings, ExposureGraph, ExpansionStatus, RunResult } from '../types';

export function useDashboardState() {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [newTicker, setNewTicker] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [iteration, setIteration] = useState<number>(3);
  const [scenarioId, setScenarioId] = useState<string>('live');
  const [activeTicker, setActiveTicker] = useState<string>('dashboard');
  const [runResults, setRunResults] = useState<Record<number, RunResult | null>>({});
  const runResult = runResults[iteration] || null;
  const [graphData, setGraphData] = useState<ExposureGraph>({ nodes: [], edges: [] });
  const [ledgerEntries, setLedgerEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [phoenixStatus, setPhoenixStatus] = useState<any>({ running: false, dashboardUrl: '' });
  const [selectedCatalystPath, setSelectedCatalystPath] = useState<string[] | null>(null);
  const [memoryStatus, setMemoryStatus] = useState<any>(null);
  const [graphModalOpen, setGraphModalOpen] = useState(false);
  const [graphFilterTicker, setGraphFilterTicker] = useState<string | null>(null);
  const [graphStatus, setGraphStatus] = useState<ExpansionStatus>({});

  // Dashboard tabs & status bar states
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [ledgerExpanded, setLedgerExpanded] = useState(false);
  const [activeDashTab, setActiveDashTab] = useState<'watchlist' | 'ledger'>('watchlist');
  const [addTickerOpen, setAddTickerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [appSettings, setAppSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [allowedLlmProviders, setAllowedLlmProviders] = useState<string[]>([]);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [synthesisExpanded, setSynthesisExpanded] = useState(false);
  const [selectedBackgroundStory, setSelectedBackgroundStory] = useState<string | null>(null);
  const [summaryDetailExpanded, setSummaryDetailExpanded] = useState(false);

  // Fetch ledger whenever iteration changes
  useEffect(() => {
    fetchLedger();
  }, [iteration]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── API helpers ────────────────────────────────────────────────────────────

  const fetchGraph = async (): Promise<void> => {
    try {
      const data = await api.getGraph();
      setGraphData(data);
    } catch (e) {
      console.error('Error fetching graph', e);
    }
  };

  const fetchGraphStatus = async (): Promise<void> => {
    try {
      const data = await api.getGraphStatus();
      setGraphStatus(data.status || {});
    } catch (e) {
      console.error('Error fetching graph status', e);
    }
  };

  const fetchResults = async (): Promise<void> => {
    try {
      const data = await api.getResults();
      if (data) {
        const formatted: Record<number, RunResult> = {};
        Object.entries(data).forEach(([k, v]) => {
          formatted[Number(k)] = v as RunResult;
        });
        setRunResults(formatted);
      }
    } catch (e) {
      console.error('Error fetching run results', e);
    }
  };

  const fetchLedger = async (): Promise<void> => {
    try {
      const data = await api.getLedger(iteration);
      setLedgerEntries(data);
    } catch (e) {
      console.error('Error fetching ledger', e);
    }
  };

  const fetchPhoenixStatus = async (): Promise<void> => {
    try {
      const data = await api.getPhoenixStatus();
      setPhoenixStatus(data);
    } catch (e) {
      console.error('Error fetching Phoenix status', e);
    }
  };

  const fetchMemoryStatus = async (): Promise<void> => {
    try {
      const data = await api.getMemoryStatus();
      setMemoryStatus(data);
    } catch (e) {
      console.error('Error fetching memory status', e);
    }
  };

  const fetchSettings = async (): Promise<void> => {
    try {
      const data = await api.getSettings();
      setAppSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
      setAllowedLlmProviders(data.allowedLlmProviders || []);
    } catch (e) {
      console.error('Error fetching settings', e);
    }
  };

  // ─── Connection check (does NOT set connectionState — managed by usePollingStatus) ──

  const checkConnectionDirect = async (): Promise<boolean> => {
    try {
      const data = await api.getWatchlist();
      setWatchlist(data.tickers);
      if (data.tickers.length > 0 && !activeTicker) {
        setActiveTicker('dashboard');
      }
      // Kick off all other data loads on successful connection
      fetchGraph();
      fetchGraphStatus();
      fetchResults();
      fetchPhoenixStatus();
      fetchMemoryStatus();
      fetchSettings();
      return true;
    } catch (e) {
      console.warn('Backend connection attempt failed:', e);
    }
    return false;
  };

  // ─── Derived helpers ─────────────────────────────────────────────────────────

  const getTickerCompanyName = (ticker: string): string => {
    const node = graphData.nodes.find(n => n.nodeType === 'ticker' && getTickerSymbol(n) === ticker);
    if (node) return node.name;
    return (
      ticker === 'AAPL' ? 'Apple Inc.' :
      ticker === 'MSFT' ? 'Microsoft Corp.' :
      ticker === 'NVDA' ? 'Nvidia Corp.' :
      ticker === 'TSM' ? 'TSMC' :
      ticker === 'DAL' ? 'Delta Air Lines' : 'Public Company'
    );
  };

  // ─── Action handlers ──────────────────────────────────────────────────────────

  const triggerExpansion = async (ticker: string): Promise<void> => {
    try {
      const data = await api.expandGraph(ticker);
      setGraphStatus(data.expansionStatus || {});
    } catch (e) {
      console.error('Error triggering graph expansion', e);
    }
  };

  const rebuildGraph = async (reset: boolean): Promise<void> => {
    if (reset && !confirm('Reset the exposure graph to its curated seed and re-expand every watchlist ticker? This discards all accumulated LLM-generated nodes/edges.')) return;
    try {
      const data = await api.rebuildGraph(reset);
      setGraphStatus(data.expansionStatus || {});
      fetchGraph();
    } catch (e) {
      console.error('Error rebuilding graph', e);
    }
  };

  const addTicker = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    if (!newTicker) return;
    const cleanTicker = newTicker.trim().toUpperCase();
    if (watchlist.includes(cleanTicker)) {
      setNewTicker('');
      setActiveTicker(cleanTicker);
      setAddTickerOpen(false);
      return;
    }

    const updated = [...watchlist, cleanTicker];
    try {
      const data = await api.updateWatchlist(updated);
      setWatchlist(data.tickers);
      setNewTicker('');
      setAddTickerOpen(false);
      setActiveTicker(cleanTicker);
      // Seed the status map so the polling effect starts immediately
      setGraphStatus(data.expansionStatus || {});
    } catch (e) {
      console.error('Error updating watchlist', e);
    }
  };

  const clearLedgerMemory = async (): Promise<void> => {
    if (!confirm('Are you sure you want to clear the Catalyst Ledger memory for this iteration? This will reset all story updates.')) return;
    try {
      await api.clearLedger(iteration);
      fetchLedger();
      alert('Ledger cleared successfully!');
    } catch (e) {
      console.error('Error clearing ledger', e);
    }
  };

  const runAbortRef = useRef<AbortController | null>(null);

  const cancelRun = (): void => {
    runAbortRef.current?.abort();
  };

  const runPipeline = async (): Promise<void> => {
    const controller = new AbortController();
    runAbortRef.current = controller;
    setLoading(true);
    setSelectedCatalystPath(null);
    try {
      const data = await api.runPipeline({
        iteration,
        scenarioId,
        simulatedNow: scenarioId === 'live' ? new Date().toISOString() : '2026-05-28T17:25:00Z',
      }, controller.signal);
      setRunResults(prev => ({
        ...prev,
        [iteration]: data
      }));
      fetchLedger();
      fetchGraph();
      fetchMemoryStatus();
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        alert(`Pipeline execution error: ${e.message}`);
      }
    } finally {
      if (runAbortRef.current === controller) {
        runAbortRef.current = null;
      }
      setLoading(false);
    }
  };

  const updateLlmRoute = (step: string, field: 'provider' | 'model', value: string): void => {
    setAppSettings(prev => ({
      ...prev,
      llmRoutes: {
        ...prev.llmRoutes,
        [step]: {
          ...(prev.llmRoutes[step] || { provider: '', model: '' }),
          [field]: value
        }
      }
    }));
  };

  const saveSettings = async (): Promise<void> => {
    setSettingsSaving(true);
    setSettingsError(null);
    try {
      const data = await api.saveSettings(appSettings);
      setAppSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
      await fetchMemoryStatus();
      setSettingsOpen(false);
    } catch (e: any) {
      setSettingsError(e.message || 'Unable to save settings');
    } finally {
      setSettingsSaving(false);
    }
  };

  return {
    // ── state ──
    watchlist,
    newTicker,
    searchQuery,
    iteration,
    scenarioId,
    activeTicker,
    runResults,
    runResult,
    graphData,
    ledgerEntries,
    loading,
    phoenixStatus,
    selectedCatalystPath,
    memoryStatus,
    graphModalOpen,
    graphFilterTicker,
    graphStatus,
    sidebarOpen,
    ledgerExpanded,
    activeDashTab,
    addTickerOpen,
    settingsOpen,
    appSettings,
    allowedLlmProviders,
    settingsSaving,
    settingsError,
    synthesisExpanded,
    selectedBackgroundStory,
    summaryDetailExpanded,

    // ── setters ──
    setNewTicker,
    setSearchQuery,
    setIteration,
    setScenarioId,
    setActiveTicker,
    setSelectedCatalystPath,
    setGraphModalOpen,
    setGraphFilterTicker,
    setSidebarOpen,
    setLedgerExpanded,
    setActiveDashTab,
    setAddTickerOpen,
    setSettingsOpen,
    setSynthesisExpanded,
    setSelectedBackgroundStory,
    setSummaryDetailExpanded,

    // ── fetch helpers ──
    fetchGraph,
    fetchGraphStatus,
    fetchResults,
    fetchLedger,
    fetchPhoenixStatus,
    fetchMemoryStatus,
    fetchSettings,

    // ── connection ──
    checkConnectionDirect,

    // ── derived helpers ──
    getTickerCompanyName,

    // ── actions ──
    addTicker,
    clearLedgerMemory,
    runPipeline,
    cancelRun,
    triggerExpansion,
    rebuildGraph,
    updateLlmRoute,
    saveSettings,
  };
}
