"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UserCheck, Star, Search, Trophy, Shield } from "lucide-react";
import type { CrewMember } from "@/types";
import { useWorkflowStore } from "@/store/workflowStore";
import { statusBg, cn } from "@/lib/utils";

interface Props {
  crew: CrewMember[];
  onSignOn: (id: string, name: string) => void;
}

export default function SignOnTab({ crew, onSignOn }: Props) {
  const { matchedCandidateId, activeWorkflow } = useWorkflowStore();
  const [search, setSearch] = useState("");
  const [signingOn, setSigningOn] = useState<string | null>(null);

  const filtered = crew.filter((c) =>
    Object.values(c).some((v) =>
      String(v).toLowerCase().includes(search.toLowerCase())
    )
  );

  // Sort: matched candidate first
  const sorted = [...filtered].sort((a, b) => {
    if (a.crew_id === matchedCandidateId) return -1;
    if (b.crew_id === matchedCandidateId) return 1;
    return 0;
  });

  const matchedCrewData = activeWorkflow?.crew_match_result;

  const handleSignOn = async (id: string, name: string) => {
    setSigningOn(id);
    await onSignOn(id, name);
    setSigningOn(null);
  };

  return (
    <div className="glass rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-ocean-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">Sign-On Crew Pool</h2>
          <p className="text-xs text-gray-500 mt-0.5">{filtered.length} available crew members</p>
        </div>
        <div className="flex items-center gap-3">
          {matchedCandidateId && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-purple-500/20 border border-purple-500/30"
            >
              <Trophy className="w-3 h-3 text-purple-400" />
              <span className="text-xs text-purple-300">AI Match Found</span>
            </motion.div>
          )}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search crew..."
              className="bg-ocean/50 border border-ocean-border rounded-xl pl-9 pr-4 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-ocean-accent/50 w-56"
            />
          </div>
        </div>
      </div>

      {/* Matched candidate banner */}
      <AnimatePresence>
        {matchedCandidateId && matchedCrewData?.top_match && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="px-6 py-3 bg-purple-900/30 border-b border-purple-500/30"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-purple-500/30 flex items-center justify-center">
                  <Star className="w-4 h-4 text-purple-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-purple-300">
                    AI Recommended: {matchedCrewData.top_match.name}
                  </p>
                  <p className="text-xs text-purple-400">
                    {matchedCrewData.top_match.rank} · {matchedCrewData.top_match.port} ·{" "}
                    Match: {matchedCrewData.top_match.confidence_score}%
                  </p>
                </div>
              </div>
              <div className="flex gap-1">
                {matchedCrewData.top_match.match_reasons?.slice(0, 3).map((r, i) => (
                  <span key={i} className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-300 rounded-full border border-purple-500/30">
                    {r}
                  </span>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ocean-border bg-ocean/30">
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Crew ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Rank</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Grade</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Port</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Nationality</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Medical</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">STCW</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Visa</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Exp (yrs)</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Match</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">Action</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, idx) => {
              const isMatched = c.crew_id === matchedCandidateId;
              return (
                <motion.tr
                  key={c.crew_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.02 }}
                  className={cn(
                    "crew-row border-b border-ocean-border/30 transition-all",
                    isMatched
                      ? "bg-purple-900/20 border-purple-500/30 active-workflow-border"
                      : ""
                  )}
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-400">{c.crew_id}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {isMatched && (
                        <motion.span
                          animate={{ scale: [1, 1.2, 1] }}
                          transition={{ repeat: Infinity, duration: 2 }}
                        >
                          <Star className="w-3.5 h-3.5 text-purple-400 fill-purple-400" />
                        </motion.span>
                      )}
                      <span className={cn("font-medium", isMatched ? "text-purple-200" : "text-white")}>
                        {c.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-300 whitespace-nowrap text-xs">{c.rank}</td>
                  <td className="px-4 py-3">
                    <span className={cn("px-2 py-0.5 rounded text-xs border", statusBg(c.grade || ""))}>
                      {c.grade}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-300 text-xs">{c.port}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{c.nationality}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{c.medical_expiry || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={cn("px-2 py-0.5 rounded text-xs border", statusBg(c.stcw_status))}>
                      {c.stcw_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn("px-2 py-0.5 rounded text-xs border", statusBg(c.visa_status))}>
                      {c.visa_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-300 text-xs text-center">{c.experience_years ?? "—"}</td>
                  <td className="px-4 py-3">
                    {isMatched ? (
                      <div className="flex items-center gap-1">
                        <div className="w-16 bg-gray-700 rounded-full h-1.5">
                          <div
                            className="bg-purple-400 h-1.5 rounded-full"
                            style={{ width: `${matchedCrewData?.top_match?.confidence_score || 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-purple-300">
                          {matchedCrewData?.top_match?.confidence_score?.toFixed(0)}%
                        </span>
                      </div>
                    ) : (
                      <span className="text-gray-600 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {(isMatched || activeWorkflow?.status === "waiting") && (
                      <motion.button
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => handleSignOn(c.crew_id, c.name)}
                        disabled={signingOn !== null}
                        className={cn(
                          "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                          isMatched
                            ? "bg-success-gradient text-white shadow-lg shadow-green-900/30"
                            : "bg-ocean-accent/20 text-ocean-accent border border-ocean-accent/30 hover:bg-ocean-accent/30"
                        )}
                      >
                        {signingOn === c.crew_id ? (
                          <><span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> Checking</>
                        ) : (
                          <>
                            {isMatched ? <Shield className="w-3 h-3" /> : <UserCheck className="w-3 h-3" />}
                            Sign On
                          </>
                        )}
                      </motion.button>
                    )}
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
