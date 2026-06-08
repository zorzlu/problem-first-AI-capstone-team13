import { useState, useEffect } from 'react';

import type { ExpansionStatus } from '../types';

interface UsePollingStatusParams {
  /** Attempt connection; returns true on success. Caller must NOT set connectionState. */
  checkConnectionDirect: () => Promise<boolean>;
  graphStatus: ExpansionStatus;
  fetchGraphStatus: () => Promise<void>;
  fetchGraph: () => Promise<void>;
}

export function usePollingStatus({
  checkConnectionDirect,
  graphStatus,
  fetchGraphStatus,
  fetchGraph,
}: UsePollingStatusParams) {
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'failed'>('connecting');
  const [retryCount, setRetryCount] = useState(0);

  // ─── Initial connection attempt + retry interval ─────────────────────────────

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | undefined;
    let elapsed = 0;

    const runCheck = async () => {
      const success = await checkConnectionDirect();
      if (success) {
        setConnectionState('connected');
      } else {
        intervalId = setInterval(async () => {
          elapsed += 10;
          if (elapsed >= 90) { // 1.5 minutes
            setConnectionState('failed');
            clearInterval(intervalId);
          } else {
            setRetryCount(c => c + 1);
            const ok = await checkConnectionDirect();
            if (ok) {
              setConnectionState('connected');
              clearInterval(intervalId);
            }
          }
        }, 10000);
      }
    };

    runCheck();

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Graph status polling — re-arms while any ticker is pending/running ──────

  useEffect(() => {
    const active = Object.values(graphStatus).some(
      s => s.status === 'pending' || s.status === 'running'
    );
    if (!active) return;
    const t = setTimeout(() => {
      fetchGraphStatus();
      fetchGraph();
    }, 2500);
    return () => clearTimeout(t);
  }, [graphStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Manual retry ─────────────────────────────────────────────────────────────

  const handleManualRetry = (): void => {
    setConnectionState('connecting');
    setRetryCount(0);
    let elapsed = 0;

    const runCheck = async () => {
      const success = await checkConnectionDirect();
      if (success) {
        setConnectionState('connected');
      } else {
        const intervalId = setInterval(async () => {
          elapsed += 10;
          if (elapsed >= 90) {
            setConnectionState('failed');
            clearInterval(intervalId);
          } else {
            setRetryCount(c => c + 1);
            const ok = await checkConnectionDirect();
            if (ok) {
              setConnectionState('connected');
              clearInterval(intervalId);
            }
          }
        }, 10000);
      }
    };

    runCheck();
  };

  return { connectionState, retryCount, handleManualRetry };
}
