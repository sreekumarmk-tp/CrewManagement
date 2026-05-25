"""
Metrics collector — wraps optional Langfuse and in-memory metrics.
"""
import time
from typing import Any, Dict, Optional
from config import settings

try:
    from langfuse import Langfuse
    _langfuse_available = True
except ImportError:
    _langfuse_available = False


class MetricsCollector:
    def __init__(self):
        self._langfuse: Optional[Any] = None
        self._traces: Dict[str, Any] = {}

        if _langfuse_available and settings.langfuse_secret_key:
            try:
                self._langfuse = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
            except Exception:
                pass

    def start_trace(self, workflow_id: str, name: str, metadata: Dict = {}):
        self._traces[workflow_id] = {
            "name": name,
            "start_time": time.time(),
            "metadata": metadata,
            "spans": [],
        }
        if self._langfuse:
            try:
                trace = self._langfuse.trace(name=name, id=workflow_id, metadata=metadata)
                self._traces[workflow_id]["langfuse_trace"] = trace
            except Exception:
                pass

    def end_trace(self, workflow_id: str, output: Dict = {}):
        if workflow_id in self._traces:
            trace = self._traces[workflow_id]
            trace["end_time"] = time.time()
            trace["duration_s"] = trace["end_time"] - trace["start_time"]
            if self._langfuse and "langfuse_trace" in trace:
                try:
                    trace["langfuse_trace"].update(output=output)
                except Exception:
                    pass

    def log_agent_span(
        self,
        workflow_id: str,
        agent_name: str,
        input_data: Dict,
        output_data: Dict,
        tokens: int,
        cost: float,
    ):
        if workflow_id in self._traces:
            self._traces[workflow_id]["spans"].append({
                "agent": agent_name,
                "input": input_data,
                "output": output_data,
                "tokens": tokens,
                "cost": cost,
                "timestamp": time.time(),
            })


metrics_collector = MetricsCollector()
