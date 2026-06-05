"""
Precedent Service (L4) — the placement-history lookup.

Two responsibilities:

* **record_placement(decision)** — when a placement COMPLETES (its decision gets a
  signed_on / rejected outcome), append a flat precedent row to the history store.
* **consult(rank, grade, port)** — called at the START of a sign-off (a matching
  query). Looks up prior placements for the same vacancy profile and returns the
  matches + a summary, with `is_repeat=True` when ≥1 prior placement exists. This
  is what satisfies "Precedent Index consulted on the 2nd+ query."

Both are best-effort: failures are swallowed and logged so they can never break a
workflow turn (same convention as the decision-trace service).
"""
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4

import structlog

from database.precedent_repository import find_precedents, insert_precedent

log = structlog.get_logger()

# broadcast(event_type, agent_name, data) -> Awaitable — same callback shape the
# WorkflowService uses to relay to the WebSocket manager.
Broadcast = Callable[[str, str, Dict[str, Any]], Awaitable[None]]


class PrecedentService:
    async def consult(
        self,
        rank: Optional[str],
        *,
        grade: Optional[str] = None,
        port: Optional[str] = None,
        nationality: Optional[str] = None,
        limit: int = 5,
        broadcast: Optional[Broadcast] = None,
        workflow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Look up prior placements for this vacancy profile. Never raises."""
        result: Dict[str, Any] = {
            "is_repeat": False,
            "matches": [],
            "summary": self._summarize([]),
            "query": {"rank": rank, "grade": grade, "port": port},
            "consulted_at": datetime.utcnow().isoformat(),
        }
        try:
            if rank:
                matches = await find_precedents(rank, port=port, grade=grade, limit=limit)
                result["matches"] = matches
                result["summary"] = self._summarize(matches)
                result["is_repeat"] = len(matches) > 0
            log.info(
                "precedent.consulted",
                rank=rank, port=port,
                matches=len(result["matches"]), is_repeat=result["is_repeat"],
            )
            if broadcast:
                await self._safe_broadcast(broadcast, "precedent_consulted", "Precedent Index", {
                    "workflow_id": workflow_id,
                    "rank": rank, "grade": grade, "port": port,
                    "is_repeat": result["is_repeat"],
                    "count": len(result["matches"]),
                    "summary": result["summary"],
                    "matches": result["matches"],
                    "message": (
                        f"Consulted Precedent Index for {rank} @ {port}: "
                        + (
                            f"{len(result['matches'])} prior placement(s) found"
                            if result["is_repeat"]
                            else "no precedent — first placement for this profile"
                        )
                    ),
                })
        except Exception:
            log.warning("precedent.consult.failed", rank=rank, port=port, exc_info=True)
        return result

    async def record_placement(self, decision: Dict[str, Any]) -> Optional[dict]:
        """Append a completed placement to the history store. Never raises.

        Only signed_on / rejected decisions are recorded — a 'pending' decision is
        not yet a completed placement.
        """
        try:
            status = decision.get("outcome_status")
            if status not in ("signed_on", "rejected"):
                return None
            dep = (decision.get("query_context") or {}).get("departing_crew") or {}
            chosen = decision.get("chosen_crew") or {}
            record = {
                "precedent_id": str(uuid4()),
                "decision_id": decision.get("decision_id"),
                "workflow_id": decision.get("workflow_id"),
                "created_at": datetime.utcnow(),
                "rank": dep.get("rank"),
                "grade": dep.get("grade"),
                "port": dep.get("port"),
                "nationality": dep.get("nationality"),
                "chosen_crew_id": chosen.get("crew_id"),
                "chosen_crew_name": chosen.get("name"),
                "chosen_crew_rank": chosen.get("rank"),
                "confidence_score": decision.get("confidence_score"),
                "outcome_status": status,
                "compliance_status": decision.get("compliance_status"),
                "compliance_score": decision.get("compliance_score"),
            }
            stored = await insert_precedent(record)
            log.info("precedent.recorded", rank=record["rank"], port=record["port"], outcome=status)
            return stored
        except Exception:
            log.warning("precedent.record.failed", exc_info=True)
            return None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _summarize(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(matches)
        signed = sum(1 for m in matches if m.get("outcome_status") == "signed_on")
        rejected = sum(1 for m in matches if m.get("outcome_status") == "rejected")
        scores = [m["compliance_score"] for m in matches if m.get("compliance_score") is not None]
        avg = round(sum(scores) / len(scores), 1) if scores else None
        last = matches[0] if matches else None  # most recent (rows are desc by created_at)
        return {
            "total": total,
            "signed_on": signed,
            "rejected": rejected,
            "avg_compliance_score": avg,
            "last_choice": (
                {"name": last.get("chosen_crew_name"), "outcome": last.get("outcome_status")}
                if last else None
            ),
        }

    async def _safe_broadcast(
        self, broadcast: Broadcast, event_type: str, agent_name: str, data: Dict[str, Any]
    ) -> None:
        try:
            await broadcast(event_type, agent_name, data)
        except Exception:
            pass


precedent_service = PrecedentService()
