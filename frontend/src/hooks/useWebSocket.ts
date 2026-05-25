"use client";
import { useEffect, useRef, useCallback } from "react";
import { useWorkflowStore } from "@/store/workflowStore";
import type { WSEvent } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleWSEvent = useWorkflowStore((s) => s.handleWSEvent);
  const mounted = useRef(true);

  const connect = useCallback(() => {
    if (!mounted.current) return;
    try {
      ws.current = new WebSocket(`${WS_URL}/ws`);

      ws.current.onopen = () => {
        console.log("[WS] Connected");
      };

      ws.current.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          // Server sends {"type":"pong"} — skip it and any message without event_type
          if (!msg.event_type || msg.type === "pong" || msg.event_type === "pong") return;
          handleWSEvent(msg as WSEvent);
        } catch {
          // ignore parse errors
        }
      };

      ws.current.onclose = () => {
        if (mounted.current) {
          reconnectTimer.current = setTimeout(connect, 3000);
        }
      };

      ws.current.onerror = () => {
        ws.current?.close();
      };
    } catch {
      if (mounted.current) {
        reconnectTimer.current = setTimeout(connect, 5000);
      }
    }
  }, [handleWSEvent]);

  useEffect(() => {
    mounted.current = true;
    connect();

    const pingInterval = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);

    return () => {
      mounted.current = false;
      clearInterval(pingInterval);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [connect]);

  return {
    isConnected: ws.current?.readyState === WebSocket.OPEN,
  };
}
