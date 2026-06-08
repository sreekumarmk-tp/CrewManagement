import axios from "axios";
import type { CrewMember, WorkflowState, SystemMetrics, ROIMetrics, IntelResult } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// ── Crew ──────────────────────────────────────────────────────────────────────
export const crewApi = {
  getSignOnCrew: () => api.get<CrewMember[]>("/crew/sign-on").then(r => r.data),
  getSignOffCrew: () => api.get<CrewMember[]>("/crew/sign-off").then(r => r.data),
  getCrewMember: (id: string) => api.get<CrewMember>(`/crew/${id}`).then(r => r.data),
};

// ── Workflow ──────────────────────────────────────────────────────────────────
export const workflowApi = {
  initiateSignOff: (crew_id: string, reason?: string) =>
    api.post<{ workflow_id: string; status: string; message: string }>("/workflow/sign-off", {
      crew_id,
      reason,
    }).then(r => r.data),

  initiateSignOn: (workflow_id: string, candidate_crew_id: string) =>
    api.post<{ workflow_id: string; status: string; message: string }>("/workflow/sign-on", {
      workflow_id,
      candidate_crew_id,
    }).then(r => r.data),

  getWorkflow: (id: string) =>
    api.get<WorkflowState>(`/workflow/${id}`).then(r => r.data),

  listWorkflows: (limit?: number) =>
    api.get<WorkflowState[]>("/workflow/", { params: { limit } }).then(r => r.data),

  controlWorkflow: (id: string, action: "pause" | "resume" | "cancel") =>
    api.post(`/workflow/${id}/control`, { action }).then(r => r.data),
};

// ── L3 Intelligence Graph ─────────────────────────────────────────────────────
// The L3 match can run the deterministic backend (~ms) OR the Managed-Agents backend
// (LLM coordinator + 3 sub-agents, which can take 1-2 minutes), so these two calls get
// a generous timeout that overrides the 30s default.
const INTEL_MATCH_TIMEOUT_MS = 180_000;

export const intelligenceApi = {
  // Top-N replacements for a departing crew member (by crew_id).
  match: (crew_id: string, top_n = 3, contract_period_months = 6) =>
    api.post<IntelResult>("/intelligence/match", {
      crew_id, top_n, contract_period_months,
    }, { timeout: INTEL_MATCH_TIMEOUT_MS }).then(r => r.data),

  // Top-N replacements for an explicit vacancy (rank + port), no crew lookup.
  matchContext: (vacated_rank: string, port?: string, top_n = 3, vacated_grade?: string) =>
    api.post<IntelResult>("/intelligence/match-context", {
      vacated_rank, port, top_n, vacated_grade,
    }, { timeout: INTEL_MATCH_TIMEOUT_MS }).then(r => r.data),

  // Sign on the selected (rank-1) replacement candidate: moves them to the onboard
  // pool and records the L3 match score/reason. Returns the sign-on confirmation.
  signOn: (
    crew_id: string,
    score?: number,
    reason?: string,
    vessel?: string,
    workflow_id?: string,
  ) =>
    api.post<{ status: string; pool: string; crew_id: string; name?: string; rank?: string }>(
      "/intelligence/sign-on",
      { crew_id, score, reason, vessel, workflow_id },
    ).then(r => r.data),
};

// ── Monitoring ────────────────────────────────────────────────────────────────
export const monitoringApi = {
  getMetrics: () =>
    api.get<SystemMetrics>("/monitoring/metrics").then(r => r.data),

  getROI: () =>
    api.get<ROIMetrics>("/monitoring/roi").then(r => r.data),

  getActiveWorkflows: () =>
    api.get("/monitoring/workflows/active").then(r => r.data),

  getAgentStatus: () =>
    api.get("/monitoring/agents/status").then(r => r.data),

  getAgentSkills: () =>
    api.get<{ agents: AgentSkills[] }>("/monitoring/agents/skills").then(r => r.data.agents),
};

// Capabilities of each managed agent. `tools` are its functions (custom tools
// like sendMail, or the built-in toolset); `skills` are Anthropic document-skill
// packages (pdf/docx/xlsx) — a separate layer.
export interface AgentSkills {
  key: string;
  name: string;
  tools: string[];
  skills: string[];
}

export default api;
