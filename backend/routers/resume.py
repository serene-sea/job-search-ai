"""当前简历文本：临时上传、本地提取、人工修订和确认。"""

from io import BytesIO
from pathlib import Path
from typing import Annotated
from zipfile import BadZipFile, ZipFile
from datetime import datetime

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy.orm import Session

from backend.db.models import Resume, User
from backend.db.session import get_db_session
from backend.routers.auth import check_upload_request, check_write_request, get_current_user, utc_now

router = APIRouter(prefix="/api/resume", tags=["resume"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db_session)]
max_upload_bytes = 10 * 1024 * 1024
max_resume_chars = 200_000


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_filename: str | None
    source_format: str | None
    raw_extracted_text: str
    reviewed_text: str
    confirmed_at: datetime | None
    updated_at: datetime


class ResumeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewed_text: str = Field(max_length=max_resume_chars)

    @field_validator("reviewed_text")
    @classmethod
    def normalize_lines(cls, value: str) -> str:
        return value.replace("\r\n", "\n").replace("\r", "\n")


def extract_pdf(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        raise HTTPException(status_code=422, detail="加密 PDF 暂不支持，请导出未加密文件或手动粘贴文本")
    if len(reader.pages) > 30:
        raise HTTPException(status_code=413, detail="PDF 页数超过 30 页，请换一份简历")
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def extract_docx(data: bytes) -> str:
    # DOCX 是 ZIP 容器；先限制展开后的体积，避免异常压缩包占用过多内存。
    with ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 300 or sum(item.file_size for item in entries) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="DOCX 内容过大，请换一份简历")
    document = Document(BytesIO(data))
    pieces: list[str] = []
    for item in document.iter_inner_content():
        if hasattr(item, "text"):
            text = item.text.strip()
            if text:
                pieces.append(text)
        elif hasattr(item, "rows"):
            for row in item.rows:
                line = " | ".join(cell.text.strip() for cell in row.cells)
                if line.strip(" |"):
                    pieces.append(line)
    return "\n".join(pieces).strip()


def extract_resume(data: bytes, suffix: str) -> str:
    """只解析用户传入的文件字节，不调用外部模型或保存原件。"""

    try:
        if suffix == ".pdf":
            if not data.startswith(b"%PDF"):
                raise ValueError("文件内容不是 PDF")
            text = extract_pdf(data)
        elif suffix == ".docx":
            text = extract_docx(data)
        else:
            # 文本简历优先按 UTF-8 读取；旧中文编码可按 GB18030 读取。
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = data.decode("gb18030")
            text = text.strip()
    except HTTPException:
        raise
    except (ValueError, UnicodeError, BadZipFile, OSError, KeyError, TypeError,
            PdfReadError, PackageNotFoundError) as exc:
        raise HTTPException(status_code=422, detail="文件无法提取文字，请检查格式或直接粘贴文本") from exc
    if len(text) > max_resume_chars:
        raise HTTPException(status_code=413, detail="提取文字过长，请精简简历后重试")
    return text


@router.get("", response_model=ResumeOut | None)
def get_resume(user: CurrentUser, db: Database, response: Response) -> Resume | None:
    response.headers["Cache-Control"] = "no-store"
    return db.get(Resume, user.id)


@router.post("/upload", response_model=ResumeOut, dependencies=[Depends(check_upload_request)])
async def upload_resume(file: Annotated[UploadFile, File()], user: CurrentUser,
                        db: Database, response: Response) -> Resume:
    response.headers["Cache-Control"] = "no-store"
    # 原文件名只作为显示信息，不用作服务器路径。
    filename = Path((file.filename or "").replace("\\", "/")).name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        await file.close()
        detail = "旧 .doc 请先转换为 DOCX；仅支持 PDF、DOCX、TXT" if suffix == ".doc" else "仅支持 PDF、DOCX、TXT"
        raise HTTPException(status_code=415, detail=detail)
    try:
        data = await file.read(max_upload_bytes + 1)
    finally:
        await file.close()
    if len(data) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="文件不能超过 10 MB")
    if not data:
        raise HTTPException(status_code=422, detail="文件是空的")
    text = extract_resume(data, suffix)
    resume = db.get(Resume, user.id)
    if resume is None:
        resume = Resume(user_id=user.id)
        db.add(resume)
    resume.source_filename = filename[:255]
    resume.source_format = suffix[1:]
    resume.raw_extracted_text = text
    resume.reviewed_text = text
    resume.confirmed_at = None
    resume.updated_at = utc_now()
    db.commit()
    db.refresh(resume)
    return resume


@router.patch("", response_model=ResumeOut, dependencies=[Depends(check_write_request)])
def save_draft(body: ResumeDraft, user: CurrentUser, db: Database, response: Response) -> Resume:
    response.headers["Cache-Control"] = "no-store"
    resume = db.get(Resume, user.id)
    if resume is None:
        if not body.reviewed_text.strip():
            raise HTTPException(status_code=422, detail="请先上传简历或粘贴文字")
        resume = Resume(user_id=user.id, source_filename=None, source_format=None, raw_extracted_text="")
        db.add(resume)
    resume.reviewed_text = body.reviewed_text
    # 修订后必须重新核对；未来 Agent 不会读取未确认的新稿。
    resume.confirmed_at = None
    resume.updated_at = utc_now()
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/confirm", response_model=ResumeOut, dependencies=[Depends(check_write_request)])
def confirm_resume(user: CurrentUser, db: Database, response: Response) -> Resume:
    response.headers["Cache-Control"] = "no-store"
    resume = db.get(Resume, user.id)
    if resume is None or not resume.reviewed_text.strip():
        raise HTTPException(status_code=422, detail="请先填写并保存简历文字")
    resume.confirmed_at = utc_now()
    resume.updated_at = resume.confirmed_at
    db.commit()
    db.refresh(resume)
    return resume


@router.delete("", status_code=204, dependencies=[Depends(check_write_request)])
def delete_resume(user: CurrentUser, db: Database) -> None:
    resume = db.get(Resume, user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="简历不存在")
    db.delete(resume)
    db.commit()
