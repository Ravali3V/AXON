"""FastAPI routes the backend calls to trigger audits.

POST /v1/audits/run — start a new Tier 1 audit.
POST /v1/audits/rescore — scoring-only re-run after manual overrides.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel, Field

from ..pipeline.orchestrator import run_audit, run_rescore

router = APIRouter(tags=["audits"])


class RunAuditRequest(BaseModel):
    auditId: str = Field(min_length=36, max_length=36)
    orgId: str = Field(min_length=36, max_length=36)
    brandName: str = Field(min_length=1, max_length=200)


class RescoreRequest(BaseModel):
    auditId: str = Field(min_length=36, max_length=36)
    orgId: str = Field(min_length=36, max_length=36)
    version: int = Field(ge=1)


@router.post("/audits/run", status_code=status.HTTP_202_ACCEPTED)
async def run_audit_endpoint(
    body: RunAuditRequest,
    background: BackgroundTasks,
) -> dict[str, str]:
    # Accept the job and run in the background. Progress goes to audit_events + SSE.
    background.add_task(_run_audit_task, body.auditId, body.orgId, body.brandName)
    return {"status": "accepted", "auditId": body.auditId}


@router.post("/audits/rescore", status_code=status.HTTP_202_ACCEPTED)
async def rescore_endpoint(
    body: RescoreRequest,
    background: BackgroundTasks,
) -> dict[str, str]:
    background.add_task(_rescore_task, body.auditId, body.orgId, body.version)
    return {"status": "accepted", "auditId": body.auditId}


async def _run_audit_task(audit_id: str, org_id: str, brand_name: str) -> None:
    try:
        await run_audit(audit_id=audit_id, org_id=org_id, brand_name=brand_name)
    except Exception:  # pragma: no cover — orchestrator logs + marks failed
        pass


async def _rescore_task(audit_id: str, org_id: str, version: int) -> None:
    try:
        await run_rescore(audit_id=audit_id, org_id=org_id, version=version)
    except Exception:  # pragma: no cover
        pass
