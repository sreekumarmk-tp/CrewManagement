"use client";
import { useEffect } from "react";
import { useWorkflowStore } from "@/store/workflowStore";
import type { WSEvent } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

// ── App-wide singleton WebSocket ──────────────────────────────────────────────
// Previously every page created its OWN socket on mount and closed it on unmount.
// Switching tabs during a live workflow therefore tore the connection down and
// reopened it mid-stream — dropping events (so the live decision never landed) and
// churning the UI. Hoisting the socket to module scope means it's opened ONCE and
// survives route changes; pages just attach to it.
let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let pingTimer: ReturnType<typeof setInterval> | null = null;
let connecting = false;

function ensureSocket() {
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }
  if (connecting) return;
  connecting = true;

  try {
    const ws = new WebSocket(`${WS_URL}/ws`);
    socket = ws;

    ws.onopen = () => {
      connecting = false;
      useWorkflowStore.getState().setWsConnected(true);
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        // Server sends {"type":"pong"} — skip it and any message without event_type.
        if (!msg.event_type || msg.type === "pong" || msg.event_type === "pong") return;
        useWorkflowStore.getState().handleWSEvent(msg as WSEvent);
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      connecting = false;
      socket = null;
      useWorkflowStore.getState().setWsConnected(false);
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          ensureSocket();
        }, 3000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  } catch {
    connecting = false;
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        ensureSocket();
      }, 5000);
    }
  }
}

function startPing() {
  if (pingTimer) return;
  pingTimer = setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, 30000);
}

export function useWebSocket() {
  // Reactive connection status from the store (updated by the singleton above).
  const isConnected = useWorkflowStore((s) => s.wsConnected);

  useEffect(() => {
    ensureSocket();
    startPing();
    // Intentionally NO teardown on unmount: the socket is an app-wide singleton
    // that must outlive any single page so a live workflow keeps streaming while
    // the user navigates between tabs.
  }, []);

  return { isConnected };
}
