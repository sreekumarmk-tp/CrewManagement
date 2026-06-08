// Shared L3 Intelligence-match runners.
//
// Both the Sign-Off tab (analyse a departing crew member) and the Intelligence panel
// (ad-hoc rank/port) drive the same pipeline: start the run → call the supervisor →
// store the result → the agent signs on the rank-1 pick → land on the Shortlist tab.
import toast from "react-hot-toast";

import { useWorkflowStore } from "@/store/workflowStore";
import { intelligenceApi } from "@/lib/api";
import type { CrewMember, IntelResult } from "@/types";

// After a match resolves: persist it, and (when matched) have the agent sign on #1.
async function finalize(result: IntelResult): Promise<void> {
  const s = useWorkflowStore.getState();
  s.setIntelResult(result); // authoritative; the live trace already arrived via WS

  if (result.status === "no_crew_found") {
    s.setActiveTab("shortlist"); // show the graceful dead-end where the shortlist lives
    return;
  }

  const top = result.candidates.find((c) => c.rank_position === 1) ?? result.candidates[0];
  if (result.status !== "matched" || !top) return;

  s.setActiveTab("shortlist");
  s.setIntelSigningOn(true);
  try {
    await intelligenceApi.signOn(
      top.crew_id,
      top.score,
      top.rationale?.[0],
      (result.context as { vessel?: string })?.vessel,
      result.workflow_id ?? undefined,
    );
    s.setIntelSignedOn(top.crew_id);
    toast.success(`Agent signed on ${top.name} (#1)`);
  } catch (err: unknown) {
    s.setIntelSigningOn(false);
    toast.error(err instanceof Error ? err.message : "Auto sign-on failed");
  }
}

function fail(err: unknown): void {
  const msg = err instanceof Error ? err.message : "Intelligence match failed";
  toast.error(msg);
  useWorkflowStore.getState().setIntelResult({
    status: "error", context: {}, candidates: [], notifications: [], reports: [],
    message: msg, pool_size: 0, disqualified: 0,
    timing: { first_event_ms: 0, total_ms: 0 },
  });
}

/**
 * Analyse a signed-off crew member and shortlist replacements (L3 `match` by crew_id).
 * The supervisor derives the vacancy (rank, grade, vessel, port) from THIS person's
 * record, then delegates to the three investigators.
 */
export async function runIntelByCrew(crew: CrewMember): Promise<void> {
  const s = useWorkflowStore.getState();
  s.startIntelRun(crew.rank, crew.port, {
    crewId: crew.crew_id, name: crew.name, rank: crew.rank, vessel: crew.vessel, port: crew.port,
  });
  try {
    const result = await intelligenceApi.match(crew.crew_id, 3);
    await finalize(result);
  } catch (err) {
    fail(err);
  }
}

/** Ad-hoc match for an explicit vacancy (rank + port), no departing crew member. */
export async function runIntelByContext(rank: string, port?: string): Promise<void> {
  const s = useWorkflowStore.getState();
  s.startIntelRun(rank, port, null);
  try {
    const result = await intelligenceApi.matchContext(rank, port, 3);
    await finalize(result);
  } catch (err) {
    fail(err);
  }
}
