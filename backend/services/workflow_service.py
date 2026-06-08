"""
Workflow Service — orchestrates agent execution and state transitions.
Integrates Master Agent with state management and WebSocket events.
"""
import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import structlog

from agents.master_agent import MasterAgent
from database.models import WorkflowState, WorkflowStatus
from database.crew_repository import get_crew_by_id, get_sign_on_crew, update_crew
from services.state_service import state_service
from services.decision_trace_service import decision_trace_service
from services.precedent_service import precedent_service

log = structlog.get_logger()

# L4 #4 — how many ranked candidates the rejection-retry loop will try (top match
# + up to 2 fallbacks) before recording a final rejection.
MAX_SIGNON_ATTEMPTS = 3


class WorkflowService:
    def __init__(self, broadcast_fn: Optional[Callable] = None):
        self.broadcast_fn = broadcast_fn

    async def _event_callback(self, event_type: str, agent_name: str, data: Dict[str, Any]):
        """Relay agent events → WebSocket broadcast."""
        if self.broadcast_fn:
            await self.broadcast_fn({
                "event_type": event_type,
                "agent_name": agent_name,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            })

    async def initiate_sign_off(
        self,
        crew_id: str,
        reason: str = "Contract completion",
    ) -> WorkflowState:
        """
        Trigger the full sign-off workflow.
        Returns immediately after creating the workflow; orchestration runs async.
        """
        # Look up the sign-off crew member
        crew = await get_crew_by_id(crew_id, pool="signoff")
        if not crew:
            raise ValueError(f"Crew member {crew_id} not found in sign-off pool")

        # Create workflow record
        workflow = WorkflowState(
            trigger=f"Sign-off initiated for {crew['name']} ({crew_id})",
            sign_off_crew_id=crew_id,
            sign_off_crew=crew,
            memory={
                "short_term": {
                    "initiated_at": datetime.utcnow().isoformat(),
                    "reason": reason,
                    "sign_off_crew": crew,
                },
                "long_term": {
                    "previous_operations": [],
                },
            },
        )

        await state_service.create_workflow(workflow)

        # Broadcast workflow created
        await self._event_callback("workflow_created", "Master Agent", {
            "workflow_id": workflow.workflow_id,
            "crew_name": crew["name"],
            "rank": crew["rank"],
            "vessel": crew["vessel"],
        })

        # Run orchestration in background
        asyncio.create_task(self._run_sign_off_orchestration(workflow, crew))

        return workflow

    async def _run_sign_off_orchestration(
        self, workflow: WorkflowState, sign_off_crew: Dict[str, Any]
    ):
        try:
            # L4 #2: consult the Precedent Index at the START of the matching query.
            # On the 2nd+ sign-off for the same vacancy profile (rank/grade/port)
            # this returns prior placements. Stashed on the workflow so the captured
            # decision records what the lookup returned.
            precedent = await precedent_service.consult(
                rank=sign_off_crew.get("rank"),
                grade=sign_off_crew.get("grade"),
                port=sign_off_crew.get("port"),
                nationality=sign_off_crew.get("nationality"),
                broadcast=self._event_callback,
                workflow_id=workflow.workflow_id,
            )
            workflow.memory.setdefault("short_term", {})["precedent"] = precedent

            master = MasterAgent(event_callback=self._event_callback)
            updated = await master.orchestrate_sign_off(workflow, sign_off_crew, auto_proceed=True)
            await state_service.update_workflow(updated)

            # L4: capture the placement decision L3 just produced (matched crew +
            # ranked alternatives + agent trajectory) as a persisted Decision trace.
            # Read-only consumer of WorkflowState; best-effort (never raises).
            await decision_trace_service.capture(updated, broadcast=self._event_callback)

            # Persist the sign-off outcome to the crew table: the departing crew
            # member leaves the onboard (signoff) pool and becomes available for
            # sign-on (signon pool).
            crew_id = updated.sign_off_crew_id
            if crew_id:
                row = await update_crew(crew_id, pool="signon", status="Signed Off")
                if row:
                    log.info("sign_off.crew_pool_updated", crew_id=crew_id, pool="signon")
                    await self._event_callback("crew_updated", "Master Agent", {
                        "workflow_id": updated.workflow_id,
                        "crew_id": crew_id,
                        "pool": "signon",
                        "status": "Signed Off",
                    })
                else:
                    log.warning("sign_off.crew_not_found_for_update", crew_id=crew_id)

            # Auto-chain: validate the matched replacement's documents via Compliance,
            # and on a pass/warning add them to the onboard (signoff) pool so they
            # appear in the Sign-Off tab.
            await self._auto_compliance_and_signon(master, updated, sign_off_crew)

            log.info("sign_off.orchestration.complete", workflow_id=workflow.workflow_id)
        except Exception as exc:
            log.error("sign_off.orchestration.error", error=str(exc))
            workflow.status = WorkflowStatus.FAILED
            await state_service.update_workflow(workflow)
            await self._event_callback("workflow_failed", "Master Agent", {
                "workflow_id": workflow.workflow_id,
                "error": str(exc),
            })

    async def _auto_compliance_and_signon(
        self, master: MasterAgent, workflow: WorkflowState, sign_off_crew: Dict[str, Any]
    ) -> None:
        """After matching, run Compliance on the ranked candidates IN ORDER until one
        clears (L4 #4 rejection-retry loop). The top match is tried first; on a
        compliance failure the next-best ranked alternative (which already carries
        the Phase-3 precedent boost) is tried, up to MAX_SIGNON_ATTEMPTS. The first
        pass/warning signs that crew on; only when every attempt fails is a final
        rejection recorded. Runs on the SAME coordinator session as Phase 1.
        """
        # Candidates to try, best-first. ranked_candidates is the boosted/sorted list;
        # fall back to the single top match if it's absent.
        ranked = (workflow.crew_match_result or {}).get("ranked_candidates") or []
        if not ranked and workflow.matched_crew:
            ranked = [workflow.matched_crew]
        queue = ranked[:MAX_SIGNON_ATTEMPTS]
        if not queue:
            log.warning("auto_compliance.no_match", workflow_id=workflow.workflow_id)
            return

        port = (sign_off_crew or {}).get("port", "Singapore")
        attempts: list = []
        winner: Optional[Dict[str, Any]] = None  # {profile, status, score, warnings, recommendation, subgraph}

        for idx, cand in enumerate(queue):
            cid = cand.get("crew_id")
            # Full document set (passport/medical/visa/STCW) lives on the signon-pool row.
            profile = await get_crew_by_id(cid, pool="signon")
            if not profile and cid == (workflow.matched_crew or {}).get("crew_id"):
                profile = dict(workflow.matched_crew or {})
            if not profile:
                log.warning("auto_compliance.candidate_not_found", crew_id=cid)
                continue

            is_retry = idx > 0
            await self._event_callback("auto_compliance", "Master Agent", {
                "workflow_id": workflow.workflow_id,
                "candidate_id": cid,
                "candidate_name": profile.get("name"),
                "candidate_rank": profile.get("rank"),
                "match_confidence": cand.get("confidence_score"),
                "match_reasons": cand.get("match_reasons", []),
                "attempt": idx + 1,
                "is_retry": is_retry,
                "message": (
                    (f"Retry {idx + 1}/{len(queue)}: validating next-best candidate "
                     f"{profile.get('name')} after a compliance rejection")
                    if is_retry else
                    f"Sharing {profile.get('name')}'s documents with Compliance for validation"
                ),
            })

            updated = await master.orchestrate_compliance(workflow, profile, port)
            await state_service.update_workflow(updated)

            report = (updated.compliance_result or {}).get("compliance_report") or {}
            # The context subgraph the Compliance Agent reasoned over — streamed to the UI.
            subgraph = (updated.compliance_result or {}).get("compliance_subgraph")
            status = report.get("overall_status", "unknown")
            score = report.get("compliance_score")
            warnings = report.get("warnings", []) or []
            failures = report.get("failures", []) or []
            recommendation = report.get("recommendation")

            attempts.append({
                "order": idx + 1,
                "crew_id": cid,
                "name": profile.get("name"),
                "rank": profile.get("rank"),
                "compliance_status": status,
                "compliance_score": score,
                "failures": failures,
                "warnings": warnings,
            })

            # Pass rule: 'passed' or 'warning' (conditional) signs the crew on.
            if status in ("passed", "warning"):
                winner = {
                    "profile": profile, "status": status, "score": score,
                    "warnings": warnings, "recommendation": recommendation, "subgraph": subgraph,
                }
                break

            # Failed this candidate. If alternatives remain, announce the retry;
            # otherwise fall through to the final rejection below.
            log.info("auto_compliance.attempt_rejected", crew_id=cid, status=status, attempt=idx + 1)
            if idx < len(queue) - 1:
                await self._event_callback("sign_on_attempt_rejected", "Compliance Agent", {
                    "workflow_id": workflow.workflow_id,
                    "crew_id": cid,
                    "crew_name": profile.get("name"),
                    "crew_rank": profile.get("rank"),
                    "compliance_status": status,
                    "compliance_score": score,
                    "failures": failures,
                    "attempt": idx + 1,
                    "subgraph": subgraph,
                    "message": (
                        f"{profile.get('name')} did not clear compliance ({status}) — "
                        f"retrying with the next-best candidate"
                    ),
                })

        if winner is not None:
            profile = winner["profile"]
            cid = profile.get("crew_id")
            chosen_crew = {
                "crew_id": cid, "name": profile.get("name"), "rank": profile.get("rank"),
                "grade": profile.get("grade"), "port": profile.get("port"),
                "nationality": profile.get("nationality"),
            }
            # L4: stamp the decision's outcome (closes the trace's loop) with the
            # full attempt journey, overriding the chosen crew when a FALLBACK won;
            # then append the completed placement to the Precedent Index (#2).
            updated_decision = await decision_trace_service.record_outcome(
                workflow.workflow_id,
                outcome_status="signed_on",
                compliance_status=winner["status"],
                compliance_score=winner["score"],
                outcome_reasons=winner["warnings"],
                attempts=attempts,
                chosen_crew=chosen_crew,
                chosen_crew_id=cid,
                broadcast=self._event_callback,
            )
            if updated_decision:
                await precedent_service.record_placement(updated_decision)
            row = await update_crew(cid, pool="signoff", status="Onboard")
            if row:
                retried = len(attempts) > 1
                log.info("auto_compliance.signed_on", crew_id=cid, status=winner["status"], attempts=len(attempts))
                await self._event_callback("crew_signed_on", "Compliance Agent", {
                    "workflow_id": workflow.workflow_id,
                    "crew_id": cid,
                    "crew_name": profile.get("name"),
                    "crew_rank": profile.get("rank"),
                    "compliance_status": winner["status"],
                    "compliance_score": winner["score"],
                    "warnings": winner["warnings"],
                    "recommendation": winner["recommendation"],
                    "subgraph": winner["subgraph"],
                    "attempts": attempts,
                    "message": (
                        f"{profile.get('name')} cleared compliance "
                        f"({winner['status']}, {winner['score']}%)"
                        + (f" on attempt {len(attempts)}" if retried else "")
                        + " — added to onboard crew (Sign-Off tab)"
                    ),
                })
            else:
                log.warning("auto_compliance.signon_crew_not_found", crew_id=cid)
            return

        # Every attempt failed — record a final rejection with the full journey.
        last = attempts[-1] if attempts else {}
        log.info("auto_compliance.rejected", workflow_id=workflow.workflow_id, attempts=len(attempts))
        exhausted = len(attempts) > 1
        outcome_reasons = list(last.get("failures") or [])
        if exhausted:
            outcome_reasons = [f"All {len(attempts)} candidates failed compliance"] + outcome_reasons
        updated_decision = await decision_trace_service.record_outcome(
            workflow.workflow_id,
            outcome_status="rejected",
            compliance_status=last.get("compliance_status"),
            compliance_score=last.get("compliance_score"),
            outcome_reasons=outcome_reasons,
            attempts=attempts,
            broadcast=self._event_callback,
        )
        if updated_decision:
            await precedent_service.record_placement(updated_decision)
        await self._event_callback("sign_on_rejected", "Compliance Agent", {
            "workflow_id": workflow.workflow_id,
            "crew_id": last.get("crew_id"),
            "crew_name": last.get("name"),
            "crew_rank": last.get("rank"),
            "compliance_status": last.get("compliance_status"),
            "compliance_score": last.get("compliance_score"),
            "failures": last.get("failures") or [],
            "attempts": attempts,
            "message": (
                f"No candidate cleared compliance after {len(attempts)} attempt(s) — not signed on"
                if exhausted else
                f"{last.get('name')} did not clear compliance "
                f"({last.get('compliance_status')}) — not signed on"
            ),
        })

    async def initiate_sign_on(
        self,
        workflow_id: str,
        candidate_crew_id: str,
    ) -> WorkflowState:
        """
        Triggered when user clicks 'Sign On' for the matched candidate.
        Activates the Compliance Agent.
        """
        workflow = await state_service.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Get candidate profile (could be from sign-on pool or matched crew)
        candidate = await get_crew_by_id(candidate_crew_id, pool="signon")
        if not candidate:
            # Try the matched crew data
            candidate = workflow.matched_crew
        if not candidate:
            raise ValueError(f"Candidate {candidate_crew_id} not found")

        port = workflow.sign_off_crew.get("port", "Singapore") if workflow.sign_off_crew else "Singapore"

        # Update memory with sign-on context
        if workflow.memory.get("short_term"):
            workflow.memory["short_term"]["sign_on_candidate"] = candidate
            workflow.memory["short_term"]["sign_on_initiated_at"] = datetime.utcnow().isoformat()

        await state_service.update_workflow(workflow)

        await self._event_callback("sign_on_initiated", "Master Agent", {
            "workflow_id": workflow_id,
            "candidate_name": candidate.get("name"),
            "candidate_id": candidate_crew_id,
        })

        # Run compliance orchestration in background
        asyncio.create_task(
            self._run_compliance_orchestration(workflow, candidate, port)
        )

        return workflow

    async def _run_compliance_orchestration(
        self,
        workflow: WorkflowState,
        candidate: Dict[str, Any],
        port: str,
    ):
        try:
            master = MasterAgent(event_callback=self._event_callback)
            updated = await master.orchestrate_compliance(workflow, candidate, port)
            await state_service.update_workflow(updated)
            log.info("compliance.orchestration.complete", workflow_id=workflow.workflow_id)
        except Exception as exc:
            log.error("compliance.orchestration.error", error=str(exc))
            workflow.status = WorkflowStatus.FAILED
            await state_service.update_workflow(workflow)
            await self._event_callback("workflow_failed", "Master Agent", {
                "workflow_id": workflow.workflow_id,
                "error": str(exc),
            })

    async def pause_workflow(self, workflow_id: str) -> WorkflowState:
        workflow = await state_service.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        workflow.status = WorkflowStatus.PAUSED
        await self._event_callback("workflow_paused", "Master Agent", {"workflow_id": workflow_id})
        return await state_service.update_workflow(workflow)

    async def resume_workflow(self, workflow_id: str) -> WorkflowState:
        workflow = await state_service.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        workflow.status = WorkflowStatus.RUNNING
        await self._event_callback("workflow_resumed", "Master Agent", {"workflow_id": workflow_id})
        return await state_service.update_workflow(workflow)

    async def cancel_workflow(self, workflow_id: str) -> WorkflowState:
        workflow = await state_service.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        workflow.status = WorkflowStatus.CANCELLED
        await self._event_callback("workflow_cancelled", "Master Agent", {"workflow_id": workflow_id})
        return await state_service.update_workflow(workflow)
# end of WorkflowService
