"use client";
import { motion, AnimatePresence } from "framer-motion";
import {
  Navigation, Users, Plane, Bell, Shield,
  Zap, Clock, DollarSign
} from "lucide-react";
import { useWorkflowStore } from "@/store/workflowStore";
import { cn, statusBg, agentIcon, formatCost } from "@/lib/utils";

const AGENT_HIERARCHY = [
  { name: "Master Agent", icon: Navigation, color: "text-ocean-accent", role: "Orchestrator" },
  { name: "Crew Matching Agent", icon: Users, color: "text-purple-400", role: "Matching" },
  { name: "Travel Agent", icon: Plane, color: "text-blue-400", role: "Travel" },
  { name: "Notification Agent", icon: Bell, color: "text-yellow-400", role: "Notifications" },
  { name: "Compliance Agent", icon: Shield, color: "text-green-400", role: "Compliance" },
];

export default function AgentOrchestrationPanel() {
  const { agentStates, activeWorkflow, events } = useWorkflowStore();

  const recentEvents = events.slice(0, 8);

  return (
    <div className="glass rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-ocean-border">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Zap className="w-4 h-4 text-ocean-accent" />
              Agent Orchestration
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {Object.values(agentStates).filter(a => a.status === "running").length} agents active
            </p>
          </div>
          {activeWorkflow && (
            <span className={cn("text-xs px-2 py-1 rounded-full border", statusBg(activeWorkflow.status))}>
              {activeWorkflow.status}
            </span>
          )}
        </div>
      </div>

      {/* Agent Hierarchy */}
      <div className="p-4 space-y-2">
        {AGENT_HIERARCHY.map((agent, idx) => {
          const state = agentStates[agent.name];
          const status = state?.status || "idle";
          const isActive = status === "running";
          const isCompleted = status === "completed";

          return (
            <div key={agent.name}>
              <motion.div
                layout
                className={cn(
                  "rounded-xl p-3 border transition-all duration-300",
                  isActive
                    ? "bg-ocean-accent/10 border-ocean-accent/40 glow-card"
                    : isCompleted
                    ? "bg-green-900/20 border-green-500/30"
                    : status === "failed"
                    ? "bg-red-900/20 border-red-500/30"
                    : status === "waiting"
                    ? "bg-orange-900/20 border-orange-500/30"
                    : "bg-ocean/40 border-ocean-border/40 hover:border-ocean-border"
                )}
              >
                <div className="flex items-center gap-3">
                  {/* Agent icon + status dot */}
                  <div className="relative">
                    <div className={cn(
                      "w-9 h-9 rounded-lg flex items-center justify-center text-lg",
                      isActive ? "bg-ocean-accent/20" : "bg-ocean/50"
                    )}>
                      {agentIcon(agent.name)}
                    </div>
                    {/* Status indicator */}
                    <span className={cn(
                      "absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-ocean-card",
                      status === "running" ? "bg-blue-400 animate-pulse" :
                      status === "completed" ? "bg-green-400" :
                      status === "failed" ? "bg-red-400" :
                      status === "waiting" ? "bg-orange-400 animate-pulse" :
                      status === "pending" ? "bg-yellow-400" :
                      "bg-gray-600"
                    )} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className={cn("text-xs font-semibold", agent.color)}>
                        {agent.name}
                      </span>
                      <span className={cn("text-xs px-1.5 py-0.5 rounded border", statusBg(status))}>
                        {status}
                      </span>
                    </div>
                    {state?.current_task && isActive && (
                      <p className="text-xs text-gray-400 mt-0.5 truncate">
                        {state.current_task.slice(0, 60)}...
                      </p>
                    )}
                    {state?.last_tool && (
                      <p className="text-xs text-ocean-accent/70 mt-0.5">
                        Tool: {state.last_tool}
                      </p>
                    )}
                  </div>
                </div>

                {/* Metrics row */}
                {(state?.tokens_used > 0 || state?.tool_calls > 0) && (
                  <div className="mt-2 pt-2 border-t border-ocean-border/30 flex items-center gap-4">
                    {state.tool_calls > 0 && (
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <Zap className="w-3 h-3" />
                        {state.tool_calls} calls
                      </div>
                    )}
                    {state.tokens_used > 0 && (
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <Clock className="w-3 h-3" />
                        {state.tokens_used.toLocaleString()} tokens
                      </div>
                    )}
                    {state.estimated_cost > 0 && (
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <DollarSign className="w-3 h-3" />
                        {formatCost(state.estimated_cost)}
                      </div>
                    )}
                    {state.confidence_score !== undefined && (
                      <div className="flex items-center gap-1 text-xs text-green-400 ml-auto">
                        {(state.confidence_score * 100).toFixed(0)}% conf
                      </div>
                    )}
                  </div>
                )}
              </motion.div>

              {/* Connector line (except after last) */}
              {idx < AGENT_HIERARCHY.length - 1 && (
                <div className="flex justify-center py-0.5">
                  <motion.div
                    className="w-px h-4 bg-ocean-border"
                    animate={
                      agentStates[AGENT_HIERARCHY[idx + 1].name]?.status === "running"
                        ? { backgroundColor: ["#1e3a5f", "#00d4ff", "#1e3a5f"] }
                        : {}
                    }
                    transition={{ repeat: Infinity, duration: 1.5 }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Workflow totals */}
      {activeWorkflow && (activeWorkflow.total_tokens > 0 || activeWorkflow.total_cost > 0) && (
        <div className="px-4 pb-4">
          <div className="rounded-xl bg-ocean/50 border border-ocean-border/30 p-3 grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="text-xs text-gray-500">Tokens</p>
              <p className="text-sm font-semibold text-white">
                {activeWorkflow.total_tokens.toLocaleString()}
              </p>
            </div>
            <div className="text-center border-x border-ocean-border/30">
              <p className="text-xs text-gray-500">Est. Cost</p>
              <p className="text-sm font-semibold text-white">
                {formatCost(activeWorkflow.total_cost)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-500">Agents</p>
              <p className="text-sm font-semibold text-white">
                {activeWorkflow.agent_executions?.length || 0}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Live Events Feed */}
      {recentEvents.length > 0 && (
        <div className="border-t border-ocean-border px-4 pb-4">
          <p className="text-xs text-gray-500 py-3 font-medium uppercase tracking-wider">Live Events</p>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            <AnimatePresence>
              {recentEvents.map((e, i) => (
                <motion.div
                  key={`${e.event_type ?? "evt"}-${e.timestamp ?? i}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-start gap-2 text-xs"
                >
                  <span className="text-ocean-accent mt-0.5 shrink-0">
                    {agentIcon(e.agent_name || "Master Agent")}
                  </span>
                  <div className="min-w-0">
                    <span className="text-gray-500 font-mono">
                      {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ""}
                    </span>{" "}
                    <span className="text-gray-400">
                      {(e.event_type ?? "event").replace(/_/g, " ")}
                    </span>
                    {e.agent_name && (
                      <span className="text-gray-600"> · {e.agent_name}</span>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
