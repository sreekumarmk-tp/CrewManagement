"""
In-memory state service — single source of truth for all workflow states.
Thread-safe via asyncio.Lock.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from database.models import WorkflowState, WorkflowStatus


class StateService:
    _instance: Optional["StateService"] = None

    def __init__(self):
        self._workflows: Dict[str, WorkflowState] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "StateService":
        if cls._instance is None:
            cls._instance = StateService()
        return cls._instance

    async def create_workflow(self, workflow: WorkflowState) -> WorkflowState:
        async with self._lock:
            self._workflows[workflow.workflow_id] = workflow
        return workflow

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        return self._workflows.get(workflow_id)

    async def update_workflow(self, workflow: WorkflowState) -> WorkflowState:
        async with self._lock:
            workflow.updated_at = datetime.utcnow()
            self._workflows[workflow.workflow_id] = workflow
        return workflow

    async def list_workflows(self, limit: int = 20) -> List[WorkflowState]:
        workflows = list(self._workflows.values())
        workflows.sort(key=lambda w: w.created_at, reverse=True)
        return workflows[:limit]

    async def get_active_workflows(self) -> List[WorkflowState]:
        return [
            w for w in self._workflows.values()
            if w.status in (WorkflowStatus.RUNNING, WorkflowStatus.WAITING)
        ]

    async def delete_workflow(self, workflow_id: str) -> bool:
        async with self._lock:
            if workflow_id in self._workflows:
                del self._workflows[workflow_id]
                return True
        return False

    def get_metrics(self) -> Dict:
        workflows = list(self._workflows.values())
        total = len(workflows)
        completed = sum(1 for w in workflows if w.status == WorkflowStatus.COMPLETED)
        failed = sum(1 for w in workflows if w.status == WorkflowStatus.FAILED)
        active = sum(1 for w in workflows if w.status in (WorkflowStatus.RUNNING, WorkflowStatus.WAITING))

        total_tokens = sum(w.total_tokens for w in workflows)
        total_cost = sum(w.total_cost for w in workflows)

        # Prompt-cache observability (Step 1). The hit rate is over the *cacheable
        # prefix* only: of the prompt-prefix tokens processed across all workflows,
        # what fraction was served from the server-side cache (read) vs. written fresh
        # (creation). Cold first turns write the cache (rate ~0); as the static
        # coordinator/specialist prompts stay byte-stable, later turns read it (rate →100).
        total_cache_read = sum(w.cache_read_tokens for w in workflows)
        total_cache_creation = sum(w.cache_creation_tokens for w in workflows)
        cacheable = total_cache_read + total_cache_creation
        cache_hit_rate = round(total_cache_read / cacheable * 100, 1) if cacheable else 0.0

        durations = []
        for w in workflows:
            if w.completed_at and w.created_at:
                dur = (w.completed_at - w.created_at).total_seconds() * 1000
                durations.append(dur)

        avg_duration = sum(durations) / len(durations) if durations else 0
        success_rate = (completed / total * 100) if total > 0 else 0

        # Per-agent metrics
        agent_metrics: Dict[str, Dict] = {}
        for w in workflows:
            for exec_ in w.agent_executions:
                name = exec_.agent_name
                if name not in agent_metrics:
                    agent_metrics[name] = {
                        "total_runs": 0,
                        "completed": 0,
                        "failed": 0,
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "avg_duration_ms": 0,
                        "durations": [],
                    }
                m = agent_metrics[name]
                m["total_runs"] += 1
                m["total_tokens"] += exec_.tokens_used
                m["total_cost"] += exec_.estimated_cost
                if exec_.status.value == "completed":
                    m["completed"] += 1
                if exec_.status.value == "failed":
                    m["failed"] += 1
                if exec_.duration_ms:
                    m["durations"].append(exec_.duration_ms)

        for name, m in agent_metrics.items():
            durs = m.pop("durations", [])
            m["avg_duration_ms"] = int(sum(durs) / len(durs)) if durs else 0
            m["total_cost"] = round(m["total_cost"], 6)

        return {
            "total_workflows": total,
            "completed_workflows": completed,
            "failed_workflows": failed,
            "active_workflows": active,
            "success_rate": round(success_rate, 1),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "cache_read_tokens": total_cache_read,
            "cache_creation_tokens": total_cache_creation,
            "cache_hit_rate": cache_hit_rate,
            "avg_workflow_duration_ms": int(avg_duration),
            "agent_metrics": agent_metrics,
        }


state_service = StateService.get_instance()
