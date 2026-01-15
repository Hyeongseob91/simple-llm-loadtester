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
  e2e_avg: number;
  throughput_current: number;
  timestamp?: number;  // Unix timestamp for time-series charts
}

export interface RequestLogEntry {
  requestId: number;
  status: "pending" | "running" | "completed" | "failed";
  ttftMs: number | null;
  e2eMs: number | null;
  outputTokens: number | null;
  success: boolean;
  errorType: string | null;
  timestamp: number;
}

export interface ValidationLogEntry {
  step: string;
  message: string;
  status: "running" | "warning" | "completed" | "failed";
  timestamp: number;
}

export interface BenchmarkProgress {
  type: "progress" | "completed" | "failed" | "validation_log";
  run_id: string;
  status: string;
  progress?: ProgressData;
  concurrency?: ConcurrencyData;
  overall_percent?: number;
  metrics?: PartialMetrics | null;
  request_log?: {
    request_id: number;
    status: string;
    ttft_ms: number | null;
    e2e_ms: number | null;
    output_tokens: number | null;
    success: boolean;
    error_type: string | null;
    timestamp: number;
  };
  validation_log?: {
    step: string;
    message: string;
    status: string;
    timestamp: number;
  };
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
  /** Request logs (최근 50개) */
  requestLogs: RequestLogEntry[];
  /** Validation logs */
  validationLogs: ValidationLogEntry[];
  /** Whether WebSocket is connected */
  isConnected: boolean;
  /** Connection error if any */
  error: string | null;
  /** Manually disconnect */
  disconnect: () => void;
  /** Manually reconnect */
  reconnect: () => void;
  /** Clear request logs */
  clearLogs: () => void;
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
  const [requestLogs, setRequestLogs] = useState<RequestLogEntry[]>([]);
  const [validationLogs, setValidationLogs] = useState<ValidationLogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const MAX_LOG_ENTRIES = 50;

  const clearLogs = useCallback(() => {
    setRequestLogs([]);
  }, []);

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
          // Handle ping/pong
          if (event.data === "ping") {
            ws.send("pong");
            return;
          }

          const data = JSON.parse(event.data) as BenchmarkProgress;

          setProgress(data);

          // request_log가 있으면 로그 배열에 추가
          if (data.request_log) {
            const logEntry: RequestLogEntry = {
              requestId: data.request_log.request_id,
              status: data.request_log.status as RequestLogEntry["status"],
              ttftMs: data.request_log.ttft_ms,
              e2eMs: data.request_log.e2e_ms,
              outputTokens: data.request_log.output_tokens,
              success: data.request_log.success,
              errorType: data.request_log.error_type,
              timestamp: data.request_log.timestamp,
            };

            setRequestLogs((prev) => {
              const newLogs = [...prev, logEntry];
              // 최근 50개만 유지
              if (newLogs.length > MAX_LOG_ENTRIES) {
                return newLogs.slice(-MAX_LOG_ENTRIES);
              }
              return newLogs;
            });
          }

          // validation_log가 있으면 validation 로그 배열에 추가
          if (data.validation_log) {
            const validationEntry: ValidationLogEntry = {
              step: data.validation_log.step,
              message: data.validation_log.message,
              status: data.validation_log.status as ValidationLogEntry["status"],
              timestamp: data.validation_log.timestamp,
            };

            setValidationLogs((prev) => [...prev, validationEntry]);
          }

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
    requestLogs,
    validationLogs,
    isConnected,
    error,
    disconnect,
    reconnect,
    clearLogs,
  };
}

export default useBenchmarkProgress;
