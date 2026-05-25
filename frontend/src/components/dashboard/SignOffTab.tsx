"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { LogOut, Search, ChevronUp, ChevronDown, AlertTriangle } from "lucide-react";
import type { CrewMember } from "@/types";
import { statusBg, cn } from "@/lib/utils";

interface Props {
  crew: CrewMember[];
  initiatingId: string | null;
  onInitiateSignOff: (id: string, name: string) => void;
}

export default function SignOffTab({ crew, initiatingId, onInitiateSignOff }: Props) {
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<keyof CrewMember>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<string | null>(null);

  const filtered = crew
    .filter((c) =>
      Object.values(c).some((v) =>
        String(v).toLowerCase().includes(search.toLowerCase())
      )
    )
    .sort((a, b) => {
      const av = String(a[sortField] || "");
      const bv = String(b[sortField] || "");
      return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    });

  const toggleSort = (field: keyof CrewMember) => {
    if (sortField === field) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const SortIcon = ({ field }: { field: keyof CrewMember }) => (
    <span className="ml-1 opacity-50">
      {sortField === field ? (
        sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
      ) : null}
    </span>
  );

  return (
    <div className="glass rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-ocean-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">Crew Onboard — Sign-Off Candidates</h2>
          <p className="text-xs text-gray-500 mt-0.5">{filtered.length} crew members across all vessels</p>
        </div>
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

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ocean-border bg-ocean/30">
              {[
                { key: "crew_id", label: "Crew ID" },
                { key: "name", label: "Name" },
                { key: "rank", label: "Rank" },
                { key: "grade", label: "Grade" },
                { key: "vessel", label: "Vessel" },
                { key: "port", label: "Port" },
                { key: "nationality", label: "Nationality" },
                { key: "medical_expiry", label: "Medical Exp." },
                { key: "stcw_status", label: "STCW" },
                { key: "visa_status", label: "Visa" },
                { key: "status", label: "Status" },
              ].map(({ key, label }) => (
                <th
                  key={key}
                  onClick={() => toggleSort(key as keyof CrewMember)}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white select-none whitespace-nowrap"
                >
                  <span className="flex items-center">
                    {label}
                    <SortIcon field={key as keyof CrewMember} />
                  </span>
                </th>
              ))}
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, idx) => (
              <motion.tr
                key={c.crew_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.02 }}
                onClick={() => setSelected(selected === c.crew_id ? null : c.crew_id)}
                className={cn(
                  "crew-row border-b border-ocean-border/30 cursor-pointer transition-all",
                  selected === c.crew_id ? "bg-ocean-accent/10 border-ocean-accent/20" : ""
                )}
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-400">{c.crew_id}</td>
                <td className="px-4 py-3">
                  <div className="font-medium text-white">{c.name}</div>
                </td>
                <td className="px-4 py-3 text-gray-300 whitespace-nowrap">{c.rank}</td>
                <td className="px-4 py-3">
                  <span className={cn("px-2 py-0.5 rounded text-xs border", statusBg(c.grade || ""))}>
                    {c.grade}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-300 text-xs">{c.vessel}</td>
                <td className="px-4 py-3 text-gray-300 text-xs">{c.port}</td>
                <td className="px-4 py-3 text-gray-400 text-xs">{c.nationality}</td>
                <td className="px-4 py-3">
                  <MedicalExpiry date={c.medical_expiry} />
                </td>
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
                <td className="px-4 py-3">
                  <span className={cn("px-2 py-0.5 rounded text-xs border", statusBg(c.status))}>
                    {c.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      onInitiateSignOff(c.crew_id, c.name);
                    }}
                    disabled={initiatingId !== null}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                      initiatingId === c.crew_id
                        ? "bg-ocean-accent/30 text-ocean-accent border border-ocean-accent/40"
                        : "bg-danger-gradient text-white hover:opacity-90 shadow-sm"
                    )}
                  >
                    {initiatingId === c.crew_id ? (
                      <><span className="w-3 h-3 border-2 border-ocean-accent border-t-transparent rounded-full animate-spin" /> Processing</>
                    ) : (
                      <><LogOut className="w-3 h-3" /> Initiate Sign Off</>
                    )}
                  </motion.button>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length === 0 && (
        <div className="py-16 text-center text-gray-500">
          No crew members found matching your search.
        </div>
      )}
    </div>
  );
}

function MedicalExpiry({ date }: { date?: string }) {
  if (!date) return <span className="text-gray-600 text-xs">—</span>;
  const today = new Date();
  const exp = new Date(date);
  const days = Math.floor((exp.getTime() - today.getTime()) / 86400000);

  if (days < 0)
    return (
      <span className="flex items-center gap-1 text-red-400 text-xs">
        <AlertTriangle className="w-3 h-3" /> Expired
      </span>
    );
  if (days < 60)
    return (
      <span className="flex items-center gap-1 text-yellow-400 text-xs">
        <AlertTriangle className="w-3 h-3" /> {days}d
      </span>
    );
  return <span className="text-gray-400 text-xs">{date}</span>;
}
