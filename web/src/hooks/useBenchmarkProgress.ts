"use client";

import { useState, useEffect, useCallback, useRef } from "react";

export interface ProgressData {
  current: number;
  total: number;
  percent: number;
}

export interface ConcurrencyData {
  level: number;
  index: number;
  total: number;
}

export interface PartialMetrics {
  concurrency: number;
  completed: number;
  success_count: number;
  error_count: number;
  ttft_avg: number;
  ttft_p50: number;
  throughput_current: number;
  timestamp?: number;  // Unix timestamp for time-series charts
}

export interface BenchmarkProgress {
  type: "progress" | "completed" | "failed";
  run_id: string;
  status: string;
  progress?: ProgressData;
  concurrency?: ConcurrencyData;
  overall_percent?: number;
  metrics?: PartialMetrics | null;
  summary?: Record<string, unknown>;
  error?: string;
}

interface UseBenchmarkProgressOptions {
  /** Whether to auto-reconnect on disconnect */
  autoReconnect?: boolean;
  /** Reconnect delay in ms */
  reconnectDelay?: number;
  /** Maximum reconnect attempts */
  maxReconnectAttempts?: number;
}

interface UseBenchmarkProgressReturn {
  /** Current progress data */
  progress: BenchmarkProgress | null;
  /** Whether WebSocket is connected */
  isConnected: boolean;
  /** Connection error if any */
  error: string | null;
  /** Manually disconnect */
  disconnect: () => void;
  /** Manually reconnect */
  reconnect: () => void;
}

/**
 * Hook for subscribing to real-time benchmark progress updates via WebSocket.
 *
 * @param runId - The benchmark run ID to subscribe to
 * @param enabled - Whether to enable the WebSocket connection
 * @param options - Connection options
 *
 * @example
 * ```tsx
 * const { progress, isConnected, error } = useBenchmarkProgress(runId, status === "running");
 *
 * if (progress) {
 *   console.log(`Progress: ${progress.overall_percent}%`);
 * }
 * ```
 */
export function useBenchmarkProgress(
  runId: string,
  enabled: boolean = true,
  options: UseBenchmarkProgressOptions = {}
): UseBenchmarkProgressReturn {
  const {
    autoReconnect = true,
    reconnectDelay = 2000,
    maxReconnectAttempts = 5,
  } = options;

  const [progress, setProgress] = useState<BenchmarkProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const getWebSocketUrl = useCallback(() => {
    // Determine WebSocket URL based on current location
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;

    // In development, the WebSocket might be on a different port
    // Adjust if your API runs on a different port
    const wsHost =
      process.env.NODE_ENV === "development"
        ? host.replace(":5050", ":8085")
        : host;

    return `${protocol}//${wsHost}/api/v1/benchmark/ws/run/${runId}`;
  }, [runId]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const ws = new WebSocket(getWebSocketUrl());

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as BenchmarkProgress;

          // Handle ping/pong
          if (event.data === "ping") {
            ws.send("pong");
            return;
          }

          setProgress(data);

          // Stop reconnecting if completed or failed
          if (data.type === "completed" || data.type === "failed") {
            reconnectAttemptsRef.current = maxReconnectAttempts;
          }
        } catch (e) {
          // Ignore non-JSON messages (like pong)
        }
      };

      ws.onerror = () => {
        setError("WebSocket connection error");
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;

        // Attempt reconnect if enabled
        if (
          autoReconnect &&
          reconnectAttemptsRef.current < maxReconnectAttempts
        ) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, reconnectDelay);
        }
      };

      wsRef.current = ws;
    } catch (e) {
      setError(`Failed to create WebSocket: ${e}`);
    }
  }, [getWebSocketUrl, autoReconnect, reconnectDelay, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttemptsRef.current = maxReconnectAttempts; // Prevent auto-reconnect

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [maxReconnectAttempts]);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttemptsRef.current = 0;
    connect();
  }, [disconnect, connect]);

  // Connect/disconnect based on enabled state
  useEffect(() => {
    if (enabled && runId) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, runId, connect, disconnect]);

  return {
    progress,
    isConnected,
    error,
    disconnect,
    reconnect,
  };
}

export default useBenchmarkProgress;
