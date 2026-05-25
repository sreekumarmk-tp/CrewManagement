"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { Anchor, ArrowLeft, RefreshCw, ChevronDown, ChevronUp, Zap, Clock, DollarSign, Target } from "lucide-react";
import { workflowApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useWorkflowStore } from "@/store/workflowStore";
import type { WorkflowState, AgentExecution } from "@/types";
import { cn, statusBg, agentIcon, formatDuration, formatCost } from "@/lib/utils";

export default function WorkflowPage() {
  const [workflows, setWorkflows] = useState<WorkflowState[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const { agentStates } = useWorkflowStore();
  useWebSocket();

  useEffect(() => {
    loadWorkflows();
    const interval = setInterval(loadWorkflows, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadWorkflows = async () => {
    try {
      const data = await workflowApi.listWorkflows(20);
      setWorkflows(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ocean-gradient">
      <nav className="border-b border-ocean-border bg-ocean-card/90 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent-gradient flex items-center justify-center">
              <Anchor className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold gradient-text">MarineCrewOS</h1>
              <p className="text-xs text-gray-500">Workflow Visualization</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white text-sm">
              <ArrowLeft className="w-4 h-4" /> Dashboard
            </Link>
            <Link href="/monitoring" className="px-4 py-2 text-gray-400 hover:text-white text-sm">Monitoring</Link>
            <button onClick={loadWorkflows} className="p-2 text-gray-400 hover:text-white">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-screen-2xl mx-auto px-6 py-8 space-y-6">
        {/* Agent Flow Graph */}
        <AgentFlowGraph agentStates={agentStates} />

        {/* Workflow List */}
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-ocean-border flex items-center justify-between">
            <h2 className="text-base font-semibold text-white">Workflow History</h2>
            <span className="text-sm text-gray-400">{workflows.length} workflows</span>
          </div>

          {loading ? (
            <div className="p-20 flex justify-center">
              <div className="w-8 h-8 border-4 border-ocean-accent/30 border-t-ocean-accent rounded-full animate-spin" />
            </div>
          ) : workflows.length === 0 ? (
            <div className="p-16 text-center text-gray-500">
              <p>No workflows yet. Initiate a sign-off from the Dashboard to begin.</p>
            </div>
          ) : (
            <div className="divide-y divide-ocean-border/30">
              {workflows.map((wf) => (
                <WorkflowRow
                  key={wf.workflow_id}
                  workflow={wf}
                  expanded={expanded === wf.workflow_id}
                  onToggle={() => setExpanded(expanded === wf.workflow_id ? null : wf.workflow_id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AgentFlowGraph({ agentStates }: { agentStates: Record<string, { status: string; tool_calls: number }> }) {
  const agents = [
    { name: "Master Agent", x: 50, y: 30, color: "#00d4ff" },
    { name: "Crew Matching Agent", x: 20, y: 65, color: "#a855f7" },
    { name: "Travel Agent", x: 50, y: 65, color: "#3b82f6" },
    { name: "Notification Agent", x: 80, y: 65, color: "#f59e0b" },
    { name: "Compliance Agent", x: 50, y: 90, color: "#22c55e" },
  ];

  return (
    <div className="glass rounded-2xl p-6">
      <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
        <Zap className="w-4 h-4 text-ocean-accent" />
        Live Agent Orchestration Graph
      </h2>
      <div className="relative h-64 bg-ocean/30 rounded-xl overflow-hidden border border-ocean-border/30">
        {/* SVG connections */}
        <svg className="absolute inset-0 w-full h-full">
          {/* Master → 3 agents */}
          {[20, 50, 80].map((x) => (
            <line
              key={x}
              x1="50%" y1="30%" x2={`${x}%`} y2="65%"
              stroke="#1e3a5f" strokeWidth="1.5"
              strokeDasharray={agentStates["Master Agent"]?.status === "running" ? "5" : "0"}
              className={agentStates["Master Agent"]?.status === "running" ? "data-flow-line" : ""}
            />
          ))}
          {/* Travel → Compliance */}
          <line x1="50%" y1="65%" x2="50%" y2="90%"
            stroke="#1e3a5f" strokeWidth="1.5"
            strokeDasharray={agentStates["Travel Agent"]?.status === "completed" ? "5" : "0"}
          />
        </svg>

        {/* Agent nodes */}
        {agents.map((agent) => {
          const state = agentStates[agent.name];
          const status = state?.status || "idle";
          return (
            <motion.div
              key={agent.name}
              style={{ left: `${agent.x}%`, top: `${agent.y}%`, transform: "translate(-50%, -50%)" }}
              className="absolute"
              animate={status === "running" ? { scale: [1, 1.05, 1] } : {}}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              <div className={cn(
                "px-3 py-2 rounded-xl border text-center min-w-[120px] transition-all",
                status === "running"
                  ? "bg-ocean-card border-ocean-accent/60 shadow-lg"
                  : status === "completed"
                  ? "bg-green-900/30 border-green-500/40"
                  : status === "failed"
                  ? "bg-red-900/30 border-red-500/40"
                  : "bg-ocean-card border-ocean-border/40"
              )}>
                <div className="text-base">{agentIcon(agent.name)}</div>
                <div className="text-xs font-medium text-white leading-tight mt-0.5">
                  {agent.name.replace(" Agent", "")}
                </div>
                <div className={cn("text-xs mt-0.5", statusBg(status).split(" ")[1] || "text-gray-500")}>
                  {status}
                </div>
                {state?.tool_calls > 0 && (
                  <div className="text-xs text-gray-600 mt-0.5">{state.tool_calls} tools</div>
                )}
              </div>
              {status === "running" && (
                <motion.div
                  className="absolute inset-0 rounded-xl border border-ocean-accent/30"
                  animate={{ opacity: [0.3, 0.8, 0.3] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                />
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

function WorkflowRow({
  workflow, expanded, onToggle
}: {
  workflow: WorkflowState;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full px-6 py-4 flex items-center gap-4 hover:bg-ocean-accent/5 transition-colors text-left"
      >
        <span className={cn("w-2 h-2 rounded-full shrink-0", {
          "bg-blue-400 animate-pulse": workflow.status === "running",
          "bg-orange-400 animate-pulse": workflow.status === "waiting",
          "bg-green-400": workflow.status === "completed",
          "bg-red-400": workflow.status === "failed",
          "bg-yellow-400": workflow.status === "paused",
          "bg-gray-500": ["pending", "cancelled"].includes(workflow.status),
        })} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-white truncate">
              {workflow.trigger || `Workflow ${workflow.workflow_id.slice(0, 8)}`}
            </span>
            <span className={cn("text-xs px-2 py-0.5 rounded border", statusBg(workflow.status))}>
              {workflow.status}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-1">
            <span className="text-xs text-gray-500">
              {new Date(workflow.created_at).toLocaleString()}
            </span>
            <span className="text-xs text-gray-600">
              {workflow.agent_executions?.length || 0} agents · {workflow.total_tokens?.toLocaleString() || 0} tokens
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{formatCost(workflow.total_cost || 0)}</span>
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-ocean-border/30 bg-ocean/20"
          >
            <div className="p-6 grid grid-cols-2 gap-6">
              {/* Agent executions */}
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-3">Agent Executions</h4>
                <div className="space-y-2">
                  {workflow.agent_executions?.map((exec) => (
                    <AgentExecutionCard key={exec.agent_id} execution={exec} />
                  )) || <p className="text-xs text-gray-600">No agent data yet</p>}
                </div>
              </div>

              {/* Timeline */}
              <div>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-3">Timeline</h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {workflow.timeline?.map((entry, i) => (
                    <div key={i} className="flex gap-2 text-xs">
                      <span className="text-gray-600 font-mono shrink-0">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </span>
                      <span className="text-gray-400">{entry.event}</span>
                    </div>
                  )) || <p className="text-xs text-gray-600">No timeline data</p>}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AgentExecutionCard({ execution }: { execution: AgentExecution }) {
  return (
    <div className={cn(
      "rounded-lg p-3 border text-xs",
      execution.status === "completed" ? "bg-green-900/20 border-green-500/20" :
      execution.status === "failed" ? "bg-red-900/20 border-red-500/20" :
      "bg-ocean/40 border-ocean-border/30"
    )}>
      <div className="flex items-center justify-between">
        <span className="font-medium text-white flex items-center gap-1.5">
          {agentIcon(execution.agent_name)} {execution.agent_name}
        </span>
        <span className={cn("px-1.5 py-0.5 rounded border", statusBg(execution.status))}>
          {execution.status}
        </span>
      </div>
      <div className="flex items-center gap-3 mt-1.5 text-gray-500">
        {execution.duration_ms && <span><Clock className="w-3 h-3 inline mr-0.5" />{formatDuration(execution.duration_ms)}</span>}
        {execution.tokens_used > 0 && <span>{execution.tokens_used.toLocaleString()} tokens</span>}
        {execution.tool_calls?.length > 0 && <span>{execution.tool_calls.length} tool calls</span>}
        {execution.confidence_score && (
          <span className="text-green-400 ml-auto">{(execution.confidence_score * 100).toFixed(0)}%</span>
        )}
      </div>
      {execution.error_message && (
        <p className="text-red-400 mt-1.5 text-xs">{execution.error_message}</p>
      )}
    </div>
  );
}
