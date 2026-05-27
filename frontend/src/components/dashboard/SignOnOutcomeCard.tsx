"use client";
import { motion } from "framer-motion";
import { UserCheck, UserX, Loader2, ShieldCheck, AlertTriangle } from "lucide-react";
import { useWorkflowStore } from "@/store/workflowStore";
import { cn } from "@/lib/utils";

// Shows the crew member the Crew Matching agent selected, and the compliance
// verdict: validating → signed on (with any conditional warnings) or rejected
// (with the reason). Driven by auto_compliance / crew_signed_on / sign_on_rejected.
export default function SignOnOutcomeCard() {
  const outcome = useWorkflowStore((s) => s.signOnOutcome);
  if (!outcome) return null;

  const { phase, crewName, crewRank, matchConfidence, complianceStatus, complianceScore, reasons, recommendation } =
    outcome;

  const theme =
    phase === "signed_on"
      ? complianceStatus === "warning"
        ? { ring: "border-orange-500/40 bg-orange-900/15", label: "Signed On (conditional)", color: "text-orange-300", Icon: AlertTriangle }
        : { ring: "border-green-500/40 bg-green-900/15", label: "Signed On", color: "text-green-300", Icon: UserCheck }
      : phase === "rejected"
      ? { ring: "border-red-500/40 bg-red-900/15", label: "Rejected", color: "text-red-300", Icon: UserX }
      : { ring: "border-ocean-accent/40 bg-ocean-accent/10", label: "Validating documents…", color: "text-ocean-accent", Icon: Loader2 };

  const reasonLabel = phase === "rejected" ? "Reason" : "Notes";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("glass rounded-2xl border p-4", theme.ring)}
    >
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck className="w-4 h-4 text-ocean-accent" />
        <h3 className="text-sm font-semibold text-white">Sign-On Outcome</h3>
      </div>

      {/* Selected crew */}
      <div className="flex items-center justify-between mb-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-gray-500">Crew Matching selected</p>
          <p className="text-sm font-medium text-white truncate">{crewName || "—"}</p>
          <p className="text-xs text-gray-400">
            {crewRank}
            {typeof matchConfidence === "number" && ` · ${matchConfidence}% match`}
          </p>
        </div>
        <span
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium shrink-0",
            theme.ring,
            theme.color
          )}
        >
          <theme.Icon className={cn("w-3.5 h-3.5", phase === "validating" && "animate-spin")} />
          {theme.label}
        </span>
      </div>

      {/* Compliance score */}
      {typeof complianceScore === "number" && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] uppercase tracking-wider text-gray-500 w-20">Compliance</span>
          <span className={cn("text-xs font-mono", theme.color)}>
            {complianceStatus} · {complianceScore}%
          </span>
        </div>
      )}

      {/* Reason / notes */}
      {reasons && reasons.length > 0 && (
        <div className="mt-2 pt-2 border-t border-ocean-border/30">
          <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">{reasonLabel}</p>
          <ul className="space-y-0.5">
            {reasons.map((r, i) => (
              <li key={i} className="text-xs text-gray-300 flex items-start gap-1.5">
                <span className={cn("mt-1 w-1 h-1 rounded-full shrink-0", phase === "rejected" ? "bg-red-400" : "bg-orange-400")} />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {recommendation && (
        <p className="mt-2 text-xs text-gray-400 italic">{recommendation}</p>
      )}
    </motion.div>
  );
}
