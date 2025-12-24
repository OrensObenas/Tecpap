import { useState, useEffect, useCallback, useRef } from 'react';

interface PollingOptions {
  intervalMs: number;
  enabled?: boolean;
  onError?: (error: Error) => void;
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  options: PollingOptions
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false); // ✅ important
  const [error, setError] = useState<Error | null>(null);

  const intervalRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const { intervalMs, enabled = true, onError } = options;

  const fetchData = useCallback(async (setLoadingFlag: boolean) => {
    if (setLoadingFlag) setLoading(true);
    try {
      const result = await fetchFn();
      if (!mountedRef.current) return;
      setData(result);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      const e = err instanceof Error ? err : new Error('Unknown error');
      setError(e);
      onError?.(e);
    } finally {
      if (!mountedRef.current) return;
      if (setLoadingFlag) setLoading(false);
    }
  }, [fetchFn, onError]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // clear previous
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!enabled) return;

    // initial fetch (no spinner by default)
    fetchData(false);

    intervalRef.current = window.setInterval(() => {
      fetchData(false);
    }, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, intervalMs, fetchData]);

  const refetch = useCallback(async () => {
    await fetchData(true); // ✅ show spinner only on manual refetch
  }, [fetchData]);

  return { data, loading, error, refetch };
}
