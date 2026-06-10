"use client";
/**
 * DecisionGraph (L4) — renders ONE captured placement decision as a graph that
 * REVEALS STEP BY STEP rather than all at once.
 *
 * Two shapes, chosen by the data:
 *
 *  • DEFAULT (single-shot): Query → Decision → Chosen → Alternatives → Outcome.
 *
 *  • RETRY (L4 #4, when a sign-off went through ≥2 compliance attempts): the
 *    middle becomes the attempt CHAIN so the reject→retry→accept journey is the
 *    story — Query → Decision → Attempt 1 (rejected) → Attempt 2 (accepted) →
 *    Outcome. A failed attempt is red; the candidate that cleared is green; if all
 *    failed, the chain ends in a red rejection.
 *
 * Each stage fades in on a timer when a decision is selected, so the viewer follows
 * the flow one step to the next. When the final (outcome) stage appears,
 * `onOutcomeRevealed` fires so the parent can reveal the matching left-card label.
 */
import { useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { GitBranch } from "lucide-react";
import type { ComplianceAttempt, DecisionTrace } from "@/types";

// Mirrors backend MAX_SIGNON_ATTEMPTS — how many ranked candidates the orchestrator
// tries (top match + fallbacks) before recording a final rejection. The live graph
// shows this many candidates up front so the full queue is visible from the start.
const MAX_LIVE_CANDIDATES = 3;

// One candidate as rendered on the retry chain. `status` unifies the live lifecycle
// (queued → checking → passed | warning | failed) so the same builder draws both the
// live queue and a completed attempts journey.
type RenderCandidate = {
  crew_id?: string;
  name?: string;
  rank?: string;
  status: string;
  score?: number | null;
  failures?: string[];
};

type NodeKind = "query" | "decision" | "chosen" | "alt" | "outcome" | "attempt";

const STAGE_MS = 850;         // pause between each reveal step

const KIND_ACCENT: Record<NodeKind, string> = {
  query: "#a78bfa",     // violet — the question
  decision: "#00d4ff",  // accent — the decision point
  chosen: "#22c55e",    // green — selected candidate
  alt: "#64748b",       // slate — considered but not chosen
  outcome: "#f59e0b",   // amber default (recolored by status)
  attempt: "#64748b",   // slate default (recolored per attempt status)
};

const OUTCOME_COLOR: Record<string, string> = {
  signed_on: "#22c55e",
  rejected: "#ef4444",
  pending: "#f59e0b",
};

// Per-compliance-status color for an attempt node / the final edge.
const STATUS_COLOR: Record<string, string> = {
  passed: "#22c55e",
  warning: "#f59e0b",
  failed: "#ef4444",
  checking: "#00d4ff",   // live — candidate's documents being validated
  queued: "#64748b",     // live — in line, not yet validated
};

interface DGNodeData {
  label: string;
  sub?: string;
  tag: string;
  kind: NodeKind;
  ring: string;
  accent?: string;      // overrides KIND_ACCENT (attempt nodes color by status)
  stage: number;
  visible: boolean;
  dim?: boolean;
  glow?: boolean;
}

function DGNode({ data }: NodeProps<DGNodeData>) {
  const accent = data.accent || KIND_ACCENT[data.kind];
  const baseOpacity = data.dim ? 0.55 : 1;
  return (
    <div
      style={{
        background: "rgba(13,31,60,0.95)",
        borderTop: `2px solid ${data.ring}`,
        borderRight: `2px solid ${data.ring}`,
        borderBottom: `2px solid ${data.ring}`,
        borderLeft: `5px solid ${accent}`,
        borderRadius: 10,
        padding: "6px 10px",
        minWidth: 130,
        opacity: data.visible ? baseOpacity : 0,
        transform: data.visible ? "none" : "scale(0.9)",
        transition: "opacity 420ms ease, transform 420ms ease",
        pointerEvents: data.visible ? "auto" : "none",
        boxShadow: data.glow ? `0 0 12px ${data.ring}55` : "none",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: accent, width: 6, height: 6 }} />
      <div style={{ fontSize: 8, letterSpacing: 0.5, textTransform: "uppercase", color: accent }}>
        {data.tag}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "#fff", lineHeight: 1.2 }}>{data.label}</div>
      {data.sub && <div style={{ fontSize: 10, color: "#94a3b8" }}>{data.sub}</div>}
      <Handle type="source" position={Position.Right} style={{ background: accent, width: 6, height: 6 }} />
      {/* Bottom handles carry the L4 #4 retry feedback loop (rejected attempt → back
          to the L3 decision node), kept off the left/right forward flow. */}
      <Handle id="loopOut" type="source" position={Position.Bottom} style={{ background: "#ef4444", width: 6, height: 6 }} />
      <Handle id="loopIn" type="target" position={Position.Bottom} style={{ background: "#ef4444", width: 6, height: 6 }} />
    </div>
  );
}

const nodeTypes = { dgNode: DGNode };

export default function DecisionGraph({
  decision,
  onOutcomeRevealed,
}: {
  decision: DecisionTrace | null;
  onOutcomeRevealed?: (decisionId: string) => void;
}) {
  const attempts = useMemo(() => decision?.attempts ?? [], [decision]);

  // The candidate queue the orchestrator works through, best-first (the top match plus
  // its ranked fallbacks). Shown in FULL from the start so every crew member is visible
  // up front and the flow then proceeds one-by-one — queued → validating → rejected →
  // next — mirroring the seed-data walkthrough, instead of a candidate appearing only
  // once the prior one is rejected.
  const queue = useMemo(() => buildLiveQueue(decision), [decision]);

  // LIVE = the placement is still pending but candidates are already being tried. While
  // live the graph mirrors the CURRENT state as events arrive (no staged replay): the
  // active candidate pulses "Validating…", rejected ones turn red and loop back to L3,
  // and the candidates still in line sit "Queued".
  const live = decision?.outcome_status === "pending" && attempts.length > 0;

  // While live the full queue drives the layout; once resolved we fall back to the
  // actual attempts journey (matches the completed / seed view).
  const candidates = useMemo<RenderCandidate[]>(() => {
    if (!retryFromAttempts(attempts, live, queue)) return [];
    return live
      ? queue
      : attempts.map((a) => ({
          crew_id: a.crew_id,
          name: a.name,
          rank: a.rank,
          status: a.compliance_status || "failed",
          score: a.compliance_score ?? null,
          failures: a.failures || [],
        }));
  }, [attempts, live, queue]);

  const retryMode = candidates.length > 0;
  const chainLen = candidates.length;

  // Default flow tops out at 4. The retry LOOP budgets two stages per candidate
  // (selected by L3, then its verdict). Live shows everything at once, so maxStage just
  // needs to cover every node + loop-back (2·len+1); completed reveals stage by stage
  // up to the outcome node at 2n+1.
  const maxStage = retryMode ? 2 * chainLen + 1 : 4;

  // Reveal stage, COUPLED to the decision it belongs to (a stale id counts as 0 so
  // nothing reveals early when the walkthrough advances to the next decision).
  const [reveal, setReveal] = useState<{ id: string | null; stage: number }>({ id: null, stage: 0 });
  const decisionId = decision?.decision_id;

  useEffect(() => {
    if (!decisionId) return;
    // Live: jump straight to the frontier so the whole queue is visible at once and
    // each status change shows the moment its event lands (a growing chain never
    // restarts the reveal from zero).
    if (live) {
      setReveal({ id: decisionId, stage: maxStage });
      return;
    }
    // Completed: reveal stage by stage so the viewer follows query → … → outcome.
    setReveal({ id: decisionId, stage: 0 });
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (let s = 1; s <= maxStage; s++) {
      timers.push(
        setTimeout(
          () => setReveal((r) => (r.id === decisionId ? { id: decisionId, stage: s } : r)),
          STAGE_MS * s
        )
      );
    }
    return () => timers.forEach(clearTimeout);
  }, [decisionId, maxStage, live]);

  const stage = reveal.id === decisionId ? reveal.stage : 0;

  useEffect(() => {
    // Reveal the (final) outcome label only once the decision has actually resolved —
    // never while it's still live/pending (its outcome is not yet known).
    if (!live && decisionId && reveal.id === decisionId && reveal.stage >= maxStage) {
      onOutcomeRevealed?.(decisionId);
    }
  }, [reveal, decisionId, onOutcomeRevealed, maxStage, live]);

  // Build the full graph (with per-node stage tags) — rebuilds as the decision (and,
  // while live, its candidate statuses) change.
  const base = useMemo(() => {
    if (!decision) return { nodes: [] as Node<DGNodeData>[], edges: [] as Edge[] };
    return retryMode ? buildRetryGraph(decision, candidates, live) : buildDefaultGraph(decision);
  }, [decision, retryMode, candidates, live]);

  // Apply the current reveal stage: nodes fade in by stage; an edge shows once both
  // its endpoints are visible.
  const nodes = useMemo<Node<DGNodeData>[]>(
    () => base.nodes.map((nd) => ({ ...nd, data: { ...nd.data, visible: stage >= nd.data.stage } })),
    [base, stage]
  );
  const edges = useMemo<Edge[]>(
    () =>
      base.edges.map((ed) => {
        const edgeStage = (ed.data?.stage as number) ?? 0;
        const on = stage >= edgeStage;
        return {
          ...ed,
          animated: on && !!ed.animated,
          // The label (and its background box) render independently of the path's
          // opacity, so hide it entirely until this edge's stage is revealed —
          // otherwise "selects/considered/outcome" show before the flow reaches them.
          label: on ? ed.label : undefined,
          style: { ...ed.style, opacity: on ? 1 : 0, transition: "opacity 420ms ease" },
        };
      }),
    [base, stage]
  );

  if (!decision) {
    return (
      <div className="glass rounded-2xl border border-ocean-border/50 p-10 flex flex-col items-center justify-center text-center" style={{ minHeight: 380 }}>
        <GitBranch className="w-8 h-8 text-ocean-accent/50 mb-3" />
        <p className="text-sm text-gray-400">Select a decision to view its graph</p>
        <p className="text-xs text-gray-600 mt-1">Query → Decision → Chosen crew → Outcome</p>
      </div>
    );
  }

  let stageLabels: string[];
  if (retryMode) {
    stageLabels = ["Query", "Decision · L3"];
    candidates.forEach((c, i) => {
      stageLabels.push(`Candidate ${i + 1}`);
      const passed = c.status === "passed" || c.status === "warning";
      const checking = c.status === "checking";
      const queued = c.status === "queued";
      stageLabels.push(
        checking ? "Validating…"
          : queued ? "Queued"
          : live ? "Feedback → L3"
          : i === candidates.length - 1 || passed ? "Outcome" : "Feedback → L3"
      );
    });
  } else {
    stageLabels = ["Query", "Decision", "Chosen crew", "Alternatives", "Outcome"];
  }

  return (
    <div className="glass rounded-2xl border border-ocean-border/50 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-ocean-accent" />
          <h3 className="text-sm font-semibold text-white">Decision Graph</h3>
          {retryMode && (
            live ? (
              <span className="flex items-center gap-1 text-[9px] font-semibold px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                <i className="w-1.5 h-1.5 rounded-full bg-cyan-300 animate-pulse" /> live · {candidates.length} candidates
              </span>
            ) : (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                {attempts.length} attempts
              </span>
            )
          )}
          <span className="text-[10px] text-ocean-accent/80">
            · {stageLabels[Math.min(stage, maxStage)]}
          </span>
        </div>
        <span className="text-[10px] text-gray-500 font-mono">{decision.decision_id.slice(0, 8)}</span>
      </div>

      <div style={{ height: 400 }} className="rounded-xl overflow-hidden border border-ocean-border/40">
        <ReactFlow
          key={decision.decision_id}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          minZoom={0.2}
          proOptions={{ hideAttribution: true }}
          nodesConnectable={false}
        >
          <Background color="#1e3a5f" gap={18} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <div className="flex items-center gap-3 mt-2 text-[10px] text-gray-400">
        {retryMode ? (
          <>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.failed }} /> Rejected attempt</span>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.passed }} /> Cleared / signed on</span>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.warning }} /> Conditional</span>
            {live && (
              <>
                <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full animate-pulse" style={{ background: STATUS_COLOR.checking }} /> Validating</span>
                <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.queued }} /> Queued</span>
              </>
            )}
          </>
        ) : (
          <>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: KIND_ACCENT.query }} /> Query</span>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: KIND_ACCENT.chosen }} /> Chosen</span>
            <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full" style={{ background: KIND_ACCENT.alt }} /> Considered</span>
          </>
        )}
        <span className="ml-auto text-gray-600">{decision.total_tokens.toLocaleString()} tokens · ${decision.total_cost.toFixed(4)}</span>
      </div>
    </div>
  );
}

// ── Default single-shot graph (Query → Decision → Chosen → Alternatives → Outcome)
function buildDefaultGraph(decision: DecisionTrace): { nodes: Node<DGNodeData>[]; edges: Edge[] } {
  const outcomeColor = OUTCOME_COLOR[decision.outcome_status] || OUTCOME_COLOR.pending;
  const dep = decision.query_context?.departing_crew || {};
  const chosen = decision.chosen_crew || {};
  const alts = decision.alternatives || [];

  const n: Node<DGNodeData>[] = [];
  const e: Edge[] = [];

  n.push({
    id: "query", type: "dgNode", position: { x: 0, y: 130 },
    data: {
      tag: "Query · Sign-off", kind: "query", ring: KIND_ACCENT.query, stage: 0, visible: true,
      label: dep.name || "Departing crew",
      sub: [dep.rank, dep.port].filter(Boolean).join(" · "),
    },
  });

  n.push({
    id: "decision", type: "dgNode", position: { x: 250, y: 130 },
    data: {
      tag: "Decision · L3", kind: "decision", ring: KIND_ACCENT.decision, glow: true, stage: 1, visible: true,
      label: "Placement",
      sub: decision.confidence_score != null ? `${decision.confidence_score}% confidence` : undefined,
    },
  });
  e.push(mkEdge("e-q-d", "query", "decision", "triggers", KIND_ACCENT.query, 1));

  n.push({
    id: "chosen", type: "dgNode", position: { x: 520, y: 40 },
    data: {
      tag: "Chosen", kind: "chosen", ring: KIND_ACCENT.chosen, glow: true, stage: 2, visible: true,
      label: chosen.name || "Selected candidate",
      sub: [chosen.rank, chosen.nationality].filter(Boolean).join(" · "),
    },
  });
  e.push(mkEdge("e-d-c", "decision", "chosen", "selects", KIND_ACCENT.chosen, 2, true));

  alts.slice(0, 3).forEach((a, i) => {
    const id = `alt-${i}`;
    n.push({
      id, type: "dgNode", position: { x: 520, y: 150 + i * 78 },
      data: {
        tag: "Considered", kind: "alt", ring: KIND_ACCENT.alt, stage: 3, visible: true, dim: true,
        label: a.name || a.crew_id,
        sub: `${a.confidence_score}%`,
      },
    });
    e.push({
      id: `e-d-${id}`, source: "decision", target: id, label: "considered",
      data: { stage: 3 },
      style: { stroke: KIND_ACCENT.alt, strokeWidth: 1.25, strokeDasharray: "4 3" },
      labelStyle: { fill: KIND_ACCENT.alt, fontSize: 8 },
      labelBgStyle: { fill: "#0a1628", fillOpacity: 0.7 },
      markerEnd: { type: MarkerType.ArrowClosed, color: KIND_ACCENT.alt },
    });
  });

  const outcomeLabel = decision.outcome_status === "signed_on"
    ? "Signed On"
    : decision.outcome_status === "rejected"
    ? "Rejected"
    : "Pending";
  n.push({
    id: "outcome", type: "dgNode", position: { x: 800, y: 40 },
    data: {
      tag: "Outcome", kind: "outcome", ring: outcomeColor, accent: outcomeColor, glow: true, stage: 4, visible: true,
      label: outcomeLabel,
      sub: decision.compliance_status
        ? `Compliance: ${decision.compliance_status}${decision.compliance_score != null ? ` (${decision.compliance_score}%)` : ""}`
        : undefined,
    },
  });
  e.push(mkEdge("e-c-o", "chosen", "outcome", decision.compliance_status || "outcome", outcomeColor, 4, decision.outcome_status === "pending"));

  return { nodes: n, edges: e };
}

// The candidate queue to render WHILE LIVE: the ranked candidates the orchestrator
// will try (top match + fallbacks), shown in full from the start, with each one's
// current live status overlaid from the attempts array (keyed by crew_id). Candidates
// not yet reached are "queued"; the active one is "checking"; tried ones carry their
// verdict.
function buildLiveQueue(decision: DecisionTrace | null): RenderCandidate[] {
  if (!decision) return [];
  const attempts = decision.attempts || [];
  const chosen = decision.chosen_crew || {};
  const alts = decision.alternatives || [];

  // Best-first, deduped by crew_id: top match, then ranked fallbacks.
  const ranked: { crew_id?: string; name?: string; rank?: string }[] = [];
  const seen = new Set<string>();
  for (const c of [chosen, ...alts]) {
    const id = c?.crew_id;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ranked.push({ crew_id: id, name: c.name, rank: c.rank });
  }

  const queue: RenderCandidate[] = ranked.slice(0, MAX_LIVE_CANDIDATES).map((c) => {
    const a = attempts.find((at) => at.crew_id === c.crew_id);
    return {
      crew_id: c.crew_id,
      name: c.name,
      rank: c.rank,
      status: a?.compliance_status || "queued",
      score: a?.compliance_score ?? null,
      failures: a?.failures || [],
    };
  });

  // Never hide a real attempt that isn't in the ranked list (ordering quirks / a crew
  // tried but absent from chosen+alternatives).
  attempts.forEach((a) => {
    if (a.crew_id && !queue.some((q) => q.crew_id === a.crew_id)) {
      queue.push({
        crew_id: a.crew_id, name: a.name, rank: a.rank,
        status: a.compliance_status || "failed",
        score: a.compliance_score ?? null, failures: a.failures || [],
      });
    }
  });

  return queue;
}

// The retry-chain view is used when the placement is LIVE (≥1 queued candidate to
// show) or, once completed, when it actually went through ≥2 attempts. A completed
// single-attempt decision keeps the simpler default graph.
function retryFromAttempts(attempts: ComplianceAttempt[], live: boolean, queue: RenderCandidate[]): boolean {
  return live ? queue.length >= 1 : attempts.length >= 2;
}

// ── Retry graph — an L3-centered LOOP, not a straight line. Candidates branch from
// the Decision (L3) node; a rejected candidate loops a "feedback to L3" edge back to
// it, and L3 then selects the next-ranked candidate. The first to clear connects to
// the Outcome; if all fail, the last connects to a Rejected outcome. While live the
// full ranked queue is shown up front (still-queued candidates dimmed).
function buildRetryGraph(decision: DecisionTrace, candidates: RenderCandidate[], live = false): { nodes: Node<DGNodeData>[]; edges: Edge[] } {
  const n = candidates.length;
  const outcomeColor = OUTCOME_COLOR[decision.outcome_status] || OUTCOME_COLOR.pending;
  const dep = decision.query_context?.departing_crew || {};

  const nodes: Node<DGNodeData>[] = [];
  const edges: Edge[] = [];
  const ROW = 130;                 // vertical gap between stacked candidates
  const yc = 30 + (n - 1) * (ROW / 2);  // center the L3 hub against the candidate stack

  nodes.push({
    id: "query", type: "dgNode", position: { x: 0, y: yc },
    data: {
      tag: "Query · Sign-off", kind: "query", ring: KIND_ACCENT.query, stage: 0, visible: true,
      label: dep.name || "Departing crew",
      sub: [dep.rank, dep.port].filter(Boolean).join(" · "),
    },
  });

  // The L3 decision hub — every candidate is selected here, and every rejection
  // feeds back here.
  nodes.push({
    id: "decision", type: "dgNode", position: { x: 250, y: yc },
    data: {
      tag: "Decision · L3", kind: "decision", ring: KIND_ACCENT.decision, glow: true, stage: 1, visible: true,
      label: "Placement",
      sub: decision.confidence_score != null ? `${decision.confidence_score}% confidence` : undefined,
    },
  });
  edges.push(mkEdge("e-q-d", "query", "decision", "triggers", KIND_ACCENT.query, 1));

  // The candidate that clears is always the LAST one (the loop breaks on a pass).
  const last = candidates[n - 1] || ({} as RenderCandidate);
  const accepted = last.status === "passed" || last.status === "warning";
  const connectIdx = n - 1;

  candidates.forEach((c, i) => {
    const status = c.status || "failed";
    const color = STATUS_COLOR[status] || STATUS_COLOR.failed;
    const passed = status === "passed" || status === "warning";
    const checking = status === "checking";   // live, in-progress candidate
    const queued = status === "queued";        // live, still in line
    const failed = status === "failed";
    const id = `att-${i}`;
    const nodeStage = 2 + 2 * i;     // L3 selects this candidate
    const resStage = 3 + 2 * i;      // its verdict resolves (loop-back or outcome)

    const subLabel = passed
      ? "Cleared compliance"
      : checking
      ? "Validating…"
      : queued
      ? "Queued"
      : "Rejected";

    nodes.push({
      id, type: "dgNode", position: { x: 620, y: 30 + i * ROW },
      data: {
        tag: i === 0 ? "Candidate 1 · top match" : `Candidate ${i + 1} · fallback`,
        kind: "attempt", ring: color, accent: color, glow: passed || checking,
        dim: queued, stage: nodeStage, visible: true,
        label: c.name || c.crew_id || "Candidate",
        sub: `${subLabel}${c.score != null ? ` · ${c.score}%` : ""}`,
      },
    });

    // Forward edge L3 → candidate. A processed/active candidate is "selected" (solid,
    // animated); a still-queued one is shown ranked-but-waiting (dim, dashed, static).
    if (queued) {
      edges.push({
        id: `e-d-${id}`, source: "decision", target: id, label: `ranked #${i + 1}`,
        data: { stage: nodeStage },
        style: { stroke: STATUS_COLOR.queued, strokeWidth: 1.25, strokeDasharray: "4 3", opacity: 0.7 },
        labelStyle: { fill: STATUS_COLOR.queued, fontSize: 8 },
        labelBgStyle: { fill: "#0a1628", fillOpacity: 0.7 },
        markerEnd: { type: MarkerType.ArrowClosed, color: STATUS_COLOR.queued },
      });
    } else {
      edges.push(mkEdge(
        `e-d-${id}`, "decision", id,
        i === 0 ? "selects #1" : `selects #${i + 1}`,
        KIND_ACCENT.decision, nodeStage, true,
      ));
    }

    // A rejected candidate routes back to L3 to pick the next-best. While live the
    // most-recent rejection also loops (we're between candidates, awaiting the next);
    // once resolved the final attempt connects to the outcome instead (handled below).
    if (failed && (i < n - 1 || live)) {
      edges.push({
        id: `e-${id}-loop`, source: id, sourceHandle: "loopOut",
        target: "decision", targetHandle: "loopIn",
        label: "rejected → feedback to L3", animated: true, type: "smoothstep",
        data: { stage: resStage },
        style: { stroke: STATUS_COLOR.failed, strokeWidth: 2, strokeDasharray: "5 3" },
        labelStyle: { fill: STATUS_COLOR.failed, fontSize: 9, fontWeight: 600 },
        labelBgStyle: { fill: "#0a1628", fillOpacity: 0.85 },
        markerEnd: { type: MarkerType.ArrowClosed, color: STATUS_COLOR.failed },
      });
    }
  });

  // No resolved outcome node while live — the frontier is the in-progress (or
  // just-rejected, awaiting-next) candidate. The outcome appears only once the
  // placement actually resolves to signed_on / rejected.
  if (!live) {
    const outcomeStage = 3 + 2 * connectIdx;
    const outcomeLabel = decision.outcome_status === "signed_on"
      ? "Signed On"
      : decision.outcome_status === "rejected"
      ? "Rejected"
      : "Pending";
    nodes.push({
      id: "outcome", type: "dgNode", position: { x: 980, y: 30 + connectIdx * ROW },
      data: {
        tag: "Outcome", kind: "outcome", ring: outcomeColor, accent: outcomeColor, glow: true,
        stage: outcomeStage, visible: true,
        label: outcomeLabel,
        sub: decision.compliance_status
          ? `Compliance: ${decision.compliance_status}${decision.compliance_score != null ? ` (${decision.compliance_score}%)` : ""}`
          : undefined,
      },
    });
    edges.push(mkEdge(
      "e-att-o", `att-${connectIdx}`, "outcome",
      accepted ? "signed on" : "rejected", outcomeColor, outcomeStage,
      decision.outcome_status === "pending",
    ));
  }

  return { nodes, edges };
}

function mkEdge(
  id: string, source: string, target: string, label: string, color: string, stage: number, animated = false
): Edge {
  return {
    id, source, target, label, animated,
    data: { stage },
    style: { stroke: color, strokeWidth: 2 },
    labelStyle: { fill: color, fontSize: 9, fontWeight: 600 },
    labelBgStyle: { fill: "#0a1628", fillOpacity: 0.85 },
    markerEnd: { type: MarkerType.ArrowClosed, color },
  };
}
