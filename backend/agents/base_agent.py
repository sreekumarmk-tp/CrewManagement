"""
BaseAgent — specialist definition + tool provider for Claude Managed Agents.

Each subclass declares its system prompt (`role`) and a set of tool schemas
(`tools`) plus the implementation of those tools (`_execute_tool`). Under the
Managed Agents architecture these tools are registered as **custom tools** on a
persisted agent: the hosted agent loop runs on Anthropic's orchestration layer
and, whenever it calls one of these tools, an `agent.custom_tool_use` event is
delivered to our orchestrator, which executes `_execute_tool(...)` here and sends
the result back as a `user.custom_tool_result` event.

This class therefore no longer drives its own `messages.create` loop — the loop
is owned by Anthropic. It is a *tool provider*: it owns the schemas, the local
tool logic, the per-run execution record, and the result-extraction logic
(`_validate_and_format`). The session plumbing lives in `agents/managed/`.
"""
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

import structlog

from database.models import AgentExecution, AgentStatus, ToolCall

log = structlog.get_logger()

# Sonnet cost per million tokens (input/output) — used for best-effort cost
# attribution from span.model_request_end events.
COST_PER_INPUT_TOKEN = 3.0 / 1_000_000
COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000


class BaseAgent(ABC):
    """
    Abstract base for all maritime crew management specialist agents.

    A subclass is instantiated *per workflow phase* so that any per-run tool
    state (e.g. NotificationAgent's accumulated messages) and the
    `AgentExecution` record stay isolated to one run.
    """

    def __init__(
        self,
        name: str,
        role: str,
        tools: List[Dict[str, Any]],
        event_callback: Optional[Callable] = None,
    ):
        self.name = name
        self.role = role
        self.tools = tools
        self.event_callback = event_callback
        self.execution: AgentExecution = AgentExecution(
            agent_name=name,
            agent_type=self.__class__.__name__,
            status=AgentStatus.PENDING,
        )

    # ── Managed Agents configuration surface ──────────────────────────────────

    def custom_tool_defs(self) -> List[Dict[str, Any]]:
        """Tool schemas in the `type: "custom"` shape expected by agents.create()."""
        return [{"type": "custom", **t} for t in self.tools]

    @property
    def tool_names(self) -> Set[str]:
        return {t["name"] for t in self.tools}

    def system_prompt(self) -> str:
        return self._build_system_prompt()

    # ── Tool execution (called by the session driver on custom_tool_use) ───────

    async def handle_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute one custom tool call and record it on the execution. Returns the
        tool output (to be sent back as a user.custom_tool_result).
        """
        if self.execution.status == AgentStatus.PENDING:
            self.execution.status = AgentStatus.RUNNING
            self.execution.start_time = datetime.utcnow()

        t0 = time.monotonic()
        try:
            output = await self._maybe_await(self._execute_tool(tool_name, tool_input))
        except Exception as exc:  # surface tool errors back to the model
            log.error("tool.error", agent=self.name, tool=tool_name, error=str(exc))
            output = {"error": f"{tool_name} failed: {exc}"}
        duration_ms = int((time.monotonic() - t0) * 1000)

        self.execution.tool_calls.append(
            ToolCall(
                tool_name=tool_name,
                input=tool_input,
                output=output,
                duration_ms=duration_ms,
            )
        )
        await self._emit(
            "tool_called",
            {
                "tool": tool_name,
                "input": tool_input,
                "output": output,
                "duration_ms": duration_ms,
            },
        )
        return output

    async def finalize(self, final_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run result extraction and close out the execution record."""
        result = await self._maybe_await(self._validate_and_format(final_text, context))
        self.execution.status = AgentStatus.COMPLETED
        self.execution.end_time = datetime.utcnow()
        self.execution.output_data = result
        if self.execution.start_time:
            self.execution.duration_ms = int(
                (self.execution.end_time - self.execution.start_time).total_seconds() * 1000
            )
        return result

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Best-effort token/cost attribution from model_usage events."""
        self.execution.tokens_used += input_tokens + output_tokens
        self.execution.estimated_cost += (
            input_tokens * COST_PER_INPUT_TOKEN + output_tokens * COST_PER_OUTPUT_TOKEN
        )

    # ── Overridable hooks ─────────────────────────────────────────────────────

    @abstractmethod
    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Each agent implements its own tool dispatch (may be sync or async)."""
        ...

    @abstractmethod
    async def _validate_and_format(
        self, raw_text: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse the agent's tool history / final text into a structured result."""
        ...

    def _build_system_prompt(self) -> str:
        return (
            f"{self.role}\n\n"
            "Always respond in structured, professional language. "
            "When using tools, call them one at a time and wait for the result. "
            "Provide a final summary after completing all tasks."
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if hasattr(value, "__await__"):
            return await value
        return value

    async def _emit(self, event_type: str, data: Dict[str, Any]):
        if self.event_callback:
            try:
                await self.event_callback(
                    event_type=event_type,
                    agent_name=self.name,
                    data={**data, "execution_id": self.execution.agent_id},
                )
            except Exception:
                pass

    def get_execution_summary(self) -> Dict[str, Any]:
        return {
            "agent_id": self.execution.agent_id,
            "agent_name": self.name,
            "status": self.execution.status,
            "current_task": self.execution.current_task,
            "tool_calls": [tc.model_dump() for tc in self.execution.tool_calls],
            "tokens_used": self.execution.tokens_used,
            "estimated_cost": round(self.execution.estimated_cost, 6),
            "duration_ms": self.execution.duration_ms,
            "confidence_score": self.execution.confidence_score,
            "error_message": self.execution.error_message,
        }
