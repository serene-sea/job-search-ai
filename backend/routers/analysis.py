"""单岗位分析接口；本阶段不保存分析历史，也不开放 Agent 工具。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.db.session import get_db_session
from backend.routers.auth import check_write_request, get_current_user
from backend.services.job_analysis import (
    JobAnalysisResult, RequirementDraft, RequirementExtractionResult,
    align_requirements, build_snapshot, extract_requirements,
)

router = APIRouter(prefix="/api/jobs", tags=["job-analysis"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db_session)]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_version: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    items: list[RequirementDraft] = Field(min_length=1, max_length=12)


@router.post("/{job_id}/requirements/extract", response_model=RequirementExtractionResult,
             dependencies=[Depends(check_write_request)])
def extract_job_requirements(job_id: int, user: CurrentUser,
                             db: Database) -> RequirementExtractionResult:
    # 点击“提取岗位要求”即发起本次模型请求；服务端仍校验登录和岗位归属。
    snapshot = build_snapshot(db, user.id, job_id)
    db.close()
    return extract_requirements(snapshot)


@router.post("/{job_id}/analysis", response_model=JobAnalysisResult,
             dependencies=[Depends(check_write_request)])
def analyze_job(job_id: int, body: AnalysisRequest, user: CurrentUser, db: Database) -> JobAnalysisResult:
    # 点击“按已核对要求分析”即提交本次岗位与个人证据快照。
    snapshot = build_snapshot(db, user.id, job_id)
    if body.snapshot_version != snapshot.version:
        raise HTTPException(status_code=409, detail="岗位或个人资料已变化，请重新提取并核对要求")
    # 本次只读取数据库；先归还连接，再等待外部模型。
    db.close()
    return align_requirements(snapshot, body.items)
