"use client";
import { motion, AnimatePresence } from "framer-motion";
import { Clock, CheckCircle, AlertCircle } from "lucide-react";
import type { WorkflowState } from "@/types";
import { agentIcon } from "@/lib/utils";
import { workflowApi } from "@/lib/api";
import { useWorkflowStore } from "@/store/workflowStore";
import toast from "react-hot-toast";

interface Props { workflow: WorkflowState; }

export default function WorkflowTimeline({ workflow }: Props) {
  const { updateActiveWorkflow } = useWorkflowStore();

  const handleControl = async (action: "pause" | "resume" | "cancel") => {
    try {
      await workflowApi.controlWorkflow(workflow.workflow_id, action);
      updateActiveWorkflow({ status: action === "pause" ? "paused" : action === "cancel" ? "cancelled" : "running" });
      toast.success(`Workflow ${action}d`);
    } catch {
      toast.error(`Failed to ${action} workflow`);
    }
  };

  return (
    <div className="glass rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-ocean-border">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-ocean-accent" />
            Workflow Timeline
          </h3>
          <div className="flex gap-1.5">
            {workflow.status === "running" && (
              <button
                onClick={() => handleControl("pause")}
                className="px-2 py-1 text-xs bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 rounded-lg hover:bg-yellow-500/30"
              >
                Pause
              </button>
            )}
            {workflow.status === "paused" && (
              <button
                onClick={() => handleControl("resume")}
                className="px-2 py-1 text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg hover:bg-blue-500/30"
              >
                Resume
              </button>
            )}
            {["running", "paused", "waiting"].includes(workflow.status) && (
              <button
                onClick={() => handleControl("cancel")}
                className="px-2 py-1 text-xs bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/30"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1 font-mono">{workflow.workflow_id.slice(0, 16)}...</p>
      </div>

      <div className="p-4 max-h-72 overflow-y-auto space-y-2">
        <AnimatePresence>
          {workflow.timeline.length === 0 && (
            <p className="text-xs text-gray-600 text-center py-4">Timeline will appear here...</p>
          )}
          {[...workflow.timeline].reverse().map((entry, idx) => (
            <motion.div
              key={`${entry.timestamp}-${idx}`}
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-2.5"
            >
              <div className="mt-0.5 shrink-0">
                <span className="text-sm">{agentIcon(entry.agent)}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-300 leading-relaxed">{entry.event}</p>
                <p className="text-xs text-gray-600 font-mono mt-0.5">
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </p>
              </div>
              {idx === 0 && (
                <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-ocean-accent animate-pulse mt-1.5" />
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Compliance result if available */}
      {workflow.compliance_result?.compliance_report && (
        <div className="border-t border-ocean-border p-4">
          <ComplianceResultCard report={workflow.compliance_result.compliance_report} />
        </div>
      )}
    </div>
  );
}

function ComplianceResultCard({ report }: { report: NonNullable<WorkflowState["compliance_result"]>["compliance_report"] }) {
  if (!report) return null;
  const isPass = report.overall_status === "passed";
  const isWarn = report.overall_status === "warning";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`rounded-xl p-3 border ${
        isPass ? "bg-green-900/20 border-green-500/30" :
        isWarn ? "bg-yellow-900/20 border-yellow-500/30" :
        "bg-red-900/20 border-red-500/30"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-white flex items-center gap-1.5">
          {isPass ? <CheckCircle className="w-3.5 h-3.5 text-green-400" /> : <AlertCircle className="w-3.5 h-3.5 text-yellow-400" />}
          Compliance Result
        </span>
        <span className={`text-sm font-bold ${isPass ? "text-green-400" : isWarn ? "text-yellow-400" : "text-red-400"}`}>
          {report.compliance_score?.toFixed(1)}%
        </span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-1.5 mb-2">
        <div
          className={`h-1.5 rounded-full ${isPass ? "bg-green-400" : isWarn ? "bg-yellow-400" : "bg-red-400"}`}
          style={{ width: `${report.compliance_score || 0}%` }}
        />
      </div>
      <p className={`text-xs ${isPass ? "text-green-400" : isWarn ? "text-yellow-400" : "text-red-400"}`}>
        {report.recommendation}
      </p>
      {report.warnings?.slice(0, 2).map((w, i) => (
        <p key={i} className="text-xs text-yellow-500 mt-1">⚠ {w}</p>
      ))}
      {report.failures?.slice(0, 2).map((f, i) => (
        <p key={i} className="text-xs text-red-500 mt-1">✕ {f}</p>
      ))}
    </motion.div>
  );
}
