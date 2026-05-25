"""Workflow API routes — sign-off, sign-on, control."""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional

from database.models import (
    InitiateSignOffRequest, InitiateSignOnRequest,
    WorkflowControlRequest, WorkflowState
)
from services.workflow_service import WorkflowService
from services.state_service import state_service
from api.websockets.workflow_ws import manager

router = APIRouter(prefix="/workflow", tags=["workflow"])


def get_workflow_service() -> WorkflowService:
    async def broadcast(msg: dict):
        await manager.broadcast(msg)
    return WorkflowService(broadcast_fn=broadcast)


@router.post("/sign-off", response_model=dict)
async def initiate_sign_off(request: InitiateSignOffRequest):
    """
    Trigger the sign-off workflow for a crew member.
    Activates Master Agent → Crew Matching + Travel + Notification in parallel.
    """
    try:
        service = get_workflow_service()
        workflow = await service.initiate_sign_off(
            crew_id=request.crew_id,
            reason=request.reason or "Contract completion",
        )
        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status,
            "message": f"Sign-off workflow initiated for crew {request.crew_id}",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sign-on", response_model=dict)
async def initiate_sign_on(request: InitiateSignOnRequest):
    """
    Trigger the sign-on / compliance workflow.
    Activates Master Agent → Compliance Agent.
    """
    try:
        service = get_workflow_service()
        workflow = await service.initiate_sign_on(
            workflow_id=request.workflow_id,
            candidate_crew_id=request.candidate_crew_id,
        )
        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status,
            "message": f"Sign-on workflow initiated for candidate {request.candidate_crew_id}",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[dict])
async def list_workflows(limit: int = 20):
    workflows = await state_service.list_workflows(limit=limit)
    return [_serialize_workflow(w) for w in workflows]


@router.get("/{workflow_id}", response_model=dict)
async def get_workflow(workflow_id: str):
    workflow = await state_service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return _serialize_workflow(workflow)


@router.post("/{workflow_id}/control", response_model=dict)
async def control_workflow(workflow_id: str, request: WorkflowControlRequest):
    """Pause, resume, cancel or retry a workflow."""
    service = get_workflow_service()
    action = request.action.lower()

    try:
        if action == "pause":
            wf = await service.pause_workflow(workflow_id)
        elif action == "resume":
            wf = await service.resume_workflow(workflow_id)
        elif action == "cancel":
            wf = await service.cancel_workflow(workflow_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        return {"workflow_id": workflow_id, "status": wf.status, "action": action}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _serialize_workflow(w: WorkflowState) -> dict:
    d = w.model_dump()
    # Convert datetime objects to ISO strings
    for key in ["created_at", "updated_at", "completed_at"]:
        if d.get(key):
            d[key] = d[key].isoformat() if hasattr(d[key], "isoformat") else d[key]
    return d
