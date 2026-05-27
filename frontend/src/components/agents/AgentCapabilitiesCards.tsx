"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Boxes, Wrench, Sparkles } from "lucide-react";
import { monitoringApi, type AgentSkills } from "@/lib/api";
import { agentIcon } from "@/lib/utils";

// Display order + role label per agent (Master first).
const ORDER: Record<string, number> = {
  "Master Agent": 0,
  "Crew Matching Agent": 1,
  "Travel Agent": 2,
  "Notification Agent": 3,
  "Compliance Agent": 4,
};
const ROLE: Record<string, string> = {
  "Master Agent": "Orchestrator",
  "Crew Matching Agent": "Matching",
  "Travel Agent": "Travel",
  "Notification Agent": "Notifications",
  "Compliance Agent": "Compliance",
};

export default function AgentCapabilitiesCards() {
  const [agents, setAgents] = useState<AgentSkills[]>([]);

  useEffect(() => {
    monitoringApi.getAgentSkills().then(setAgents).catch(() => setAgents([]));
  }, []);

  const ordered = [...agents].sort(
    (a, b) => (ORDER[a.name] ?? 99) - (ORDER[b.name] ?? 99)
  );

  return (
    <div className="glass rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-white flex items-center gap-2">
          <Boxes className="w-4 h-4 text-ocean-accent" />
          Agents — Tools &amp; Skills
        </h2>
        <span className="text-xs text-gray-500">{ordered.length} agents</span>
      </div>

      {ordered.length === 0 ? (
        <p className="text-sm text-gray-600">Loading agent capabilities…</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {ordered.map((a, i) => (
            <motion.div
              key={a.key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="rounded-xl bg-ocean/40 border border-ocean-border/40 p-4 flex flex-col gap-3"
            >
              {/* Header */}
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-ocean/60 flex items-center justify-center text-lg">
                  {agentIcon(a.name)}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white truncate">
                    {a.name.replace(" Agent", "")}
                  </p>
                  <p className="text-[11px] text-gray-500">{ROLE[a.name] || "Agent"}</p>
                </div>
              </div>

              {/* Tools */}
              <div>
                <p className="text-[10px] uppercase tracking-wider text-blue-300/80 flex items-center gap-1 mb-1.5">
                  <Wrench className="w-3 h-3" /> Tools
                </p>
                <div className="flex flex-wrap gap-1">
                  {a.tools.length ? (
                    a.tools.map((t) => (
                      <span
                        key={t}
                        className="px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-300 border border-blue-500/25 font-mono text-[11px]"
                      >
                        {t}
                      </span>
                    ))
                  ) : (
                    <span className="text-[11px] text-gray-600 italic">none</span>
                  )}
                </div>
              </div>

              {/* Skills */}
              <div>
                <p className="text-[10px] uppercase tracking-wider text-green-300/80 flex items-center gap-1 mb-1.5">
                  <Sparkles className="w-3 h-3" /> Skills
                </p>
                <div className="flex flex-wrap gap-1">
                  {a.skills.length ? (
                    a.skills.map((s) => (
                      <span
                        key={s}
                        className="px-1.5 py-0.5 rounded bg-green-500/15 text-green-300 border border-green-500/25 font-mono text-[11px]"
                      >
                        {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-[11px] text-gray-600 italic">none</span>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
