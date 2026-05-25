"""
Specialist registry + agent/coordinator configuration for Managed Agents.

Two responsibilities:

1. **Setup-time config** (`specialist_agent_configs`, `coordinator_agent_config`):
   the persisted-agent definitions handed to `client.beta.agents.create(...)` by
   `scripts/setup_managed_agents.py`. Each specialist's existing system prompt and
   tool schemas are reused verbatim; the coordinator is a multiagent agent whose
   roster is the four specialist agent IDs.

2. **Runtime routing** (`SpecialistRegistry`): per workflow phase, instantiate the
   specialist objects so their tool logic (`_execute_tool`) and result extraction
   (`_validate_and_format`) can resolve the `agent.custom_tool_use` events that the
   hosted coordinator/sub-agents emit. Tool names are globally unique across the
   four specialists, so a single name→agent map is sufficient to route a call.
"""
from typing import Any, Callable, Dict, List, Optional

import structlog

from agents.base_agent import BaseAgent
from agents.compliance_agent import ComplianceAgent
from agents.crew_matching_agent import CrewMatchingAgent
from agents.notification_agent import NotificationAgent
from agents.travel_agent import TravelAgent
from config import settings

log = structlog.get_logger()

# Stable keys → specialist class. The keys are persisted in managed_agents.json
# and used to name the agents so setup is idempotent/reproducible.
SPECIALIST_CLASSES: Dict[str, type] = {
    "crew_matching": CrewMatchingAgent,
    "travel": TravelAgent,
    "notification": NotificationAgent,
    "compliance": ComplianceAgent,
}

# Keys delegated to in each phase of the workflow.
PHASE1_KEYS = ["crew_matching", "travel", "notification"]
PHASE2_KEYS = ["compliance", "notification"]

COORDINATOR_NAME = "Master Agent"

COORDINATOR_SYSTEM_ROLE = """You are the Master Orchestration Agent for an autonomous maritime crew \
sign-on / sign-off system. You are the ROUTER and COORDINATOR only — you NEVER perform \
business logic yourself. You delegate to specialist sub-agents and synthesize their results.

Your roster of specialist sub-agents:
- crew_matching : finds and ranks the best replacement crew member from the sign-on pool
- travel        : arranges sign-off travel (flight ticket, port clearance, travel summary)
- notification  : sends notifications to the Captain, Shore Manager, and crew
- compliance    : validates documents and port restrictions for an incoming crew member

How to operate:
1. Do exactly what the CURRENT user message asks — no more. The workflow is run in two
   phases across two separate user messages, with a human approval step in between.
2. PHASE 1 (sign-off request): delegate to crew_matching, travel, and notification IN
   PARALLEL (spawn them in the same turn). When all three report back, summarize the
   replacement candidate, travel arrangements, and notifications sent, then STOP. Do NOT
   run a compliance check yet — wait for the user to confirm the sign-on.
3. PHASE 2 (sign-on confirmed): delegate to compliance for the confirmed candidate, then to
   notification to announce the compliance outcome and final sign-on decision. Summarize and stop.

Delegate everything, track everything, and never invent crew, travel, or compliance data —
that is the specialists' job. Keep your own messages concise and operational."""


def specialist_agent_configs() -> List[Dict[str, Any]]:
    """Persisted-agent definitions for each specialist (one-time setup)."""
    configs: List[Dict[str, Any]] = []
    for key, cls in SPECIALIST_CLASSES.items():
        inst: BaseAgent = cls()
        configs.append(
            {
                "key": key,
                "name": inst.name,
                "model": settings.claude_model,
                "system": inst.system_prompt(),
                "tools": inst.custom_tool_defs(),
            }
        )
    return configs


def coordinator_agent_config(roster_agent_ids: List[str]) -> Dict[str, Any]:
    """Persisted coordinator definition. `roster_agent_ids` are the 4 specialist IDs.

    The coordinator MUST carry the agent toolset — that is the documented surface
    through which it operates and delegates to its roster. A coordinator created
    with no tools cannot spawn sub-agents; it just replies with text.
    """
    return {
        "name": COORDINATOR_NAME,
        "model": settings.claude_model,
        "system": COORDINATOR_SYSTEM_ROLE,
        "tools": [{"type": "agent_toolset_20260401"}],
        "multiagent": {
            "type": "coordinator",
            "agents": [{"type": "agent", "id": aid} for aid in roster_agent_ids],
        },
    }


class SpecialistRegistry:
    """
    Per-phase set of specialist instances used to resolve custom-tool calls and
    extract structured results. Instantiated fresh for each phase so per-run tool
    state and `AgentExecution` records stay isolated.
    """

    def __init__(self, keys: List[str], event_callback: Optional[Callable] = None):
        self.event_callback = event_callback
        self.agents: Dict[str, BaseAgent] = {
            key: SPECIALIST_CLASSES[key](event_callback=event_callback) for key in keys
        }
        # tool name → specialist key (names are unique across specialists)
        self._tool_owner: Dict[str, str] = {}
        for key, agent in self.agents.items():
            for tool_name in agent.tool_names:
                self._tool_owner[tool_name] = key

    def owner_of(self, tool_name: str) -> Optional[BaseAgent]:
        key = self._tool_owner.get(tool_name)
        return self.agents.get(key) if key else None

    async def route(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Resolve one custom-tool call to the owning specialist's implementation."""
        agent = self.owner_of(tool_name)
        if agent is None:
            log.warning("registry.unknown_tool", tool=tool_name)
            return {"error": f"No specialist owns tool '{tool_name}'"}
        return await agent.handle_tool_use(tool_name, tool_input)

    async def finalize(self, final_text: str, context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Run each specialist's result extraction. Returns {key: structured_result}."""
        results: Dict[str, Dict[str, Any]] = {}
        for key, agent in self.agents.items():
            results[key] = await agent.finalize(final_text, context)
        return results
