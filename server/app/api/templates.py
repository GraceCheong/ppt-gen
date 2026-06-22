"""템플릿 목록 조회, 프리뷰, 업로드 API."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from server.app import state
from server.app.services.template_preview_service import (
    PreviewUnavailableError,
    get_template_thumbnail,
)
from server.app.services.template_service import (
    _server_template_dir,
    list_template_names,
    resolve_template_path,
)
from server.app.services.template_validator import validate_template
from server.app.services.settings_service import (
    get_default_template,
    set_default_template,
)

logger = logging.getLogger("ppt_gen.server")
router = APIRouter()


def _sanitize_filename(name: str) -> str:
    """경로 조작을 방지하고 파일명만 남긴다."""
    name = os.path.basename(name)
    name = re.sub(r"[^\w\s가-힣().\-]", "_", name)
    return name.strip() or "template.pptx"


# ── 목록 ────────────────────────────────────────────────────────────────────

@router.get("/api/templates")
def list_templates():
    try:
        names = list_template_names()
    except Exception as e:
        raise HTTPException(500, detail=f"템플릿 목록 조회 실패: {e}")
    return {"templates": names, "count": len(names)}


# ── 기본 템플릿 ─────────────────────────────────────────────────────────────
# 주의: /default 경로는 /{template_id}/preview 보다 먼저 등록해야 함

@router.get("/api/templates/default")
def get_default():
    return {"template_id": get_default_template()}


@router.put("/api/templates/default")
async def set_default(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, detail=f"JSON 형식이 올바르지 않습니다: {e}")

    template_id = str(data.get("template_id") or "").strip() or None

    if template_id:
        try:
            resolve_template_path(template_id)
        except FileNotFoundError:
            raise HTTPException(404, detail=f"템플릿 '{template_id}'을 찾을 수 없습니다.")

    set_default_template(template_id)
    logger.info("[template/default] 기본 템플릿 설정: %s", template_id)
    return {"template_id": template_id}


# ── 프리뷰 ──────────────────────────────────────────────────────────────────

@router.get("/api/templates/{template_id}/preview")
async def template_preview(template_id: str):
    try:
        template_path = resolve_template_path(template_id)
    except FileNotFoundError:
        raise HTTPException(404, detail=f"템플릿 '{template_id}'을 찾을 수 없습니다.")

    try:
        loop = asyncio.get_running_loop()
        data, mime = await loop.run_in_executor(
            state.executor,
            get_template_thumbnail,
            template_path,
        )
    except PreviewUnavailableError as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.warning("[template/preview] 실패 template_id=%s: %s", template_id, e)
        raise HTTPException(500, detail=f"프리뷰 생성 실패: {e}")

    return Response(
        content=data,
        media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ── 업로드 ──────────────────────────────────────────────────────────────────

@router.post("/api/templates/upload")
async def upload_template(file: UploadFile = File(...)):
    """템플릿 PPTX 업로드.

    호환성을 검사한 후 서버에 저장한다.
    - 호환 불가: HTTP 422 + issues/warnings/layout_names
    - 호환 가능: HTTP 200 + template_id/filename
    """
    filename = file.filename or "template.pptx"
    if not filename.lower().endswith(".pptx"):
        raise HTTPException(400, detail=".pptx 파일만 업로드할 수 있습니다.")

    data = await file.read()
    if not data:
        raise HTTPException(400, detail="업로드된 파일이 비어 있습니다.")

    # 임시 파일로 검증
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pptx")
    try:
        os.close(tmp_fd)
        with open(tmp_path, "wb") as f:
            f.write(data)

        # 호환성 검사 (동기이므로 executor에서 실행)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            state.executor,
            validate_template,
            tmp_path,
        )

        if not result.compatible:
            return JSONResponse(
                status_code=422,
                content={
                    "compatible": False,
                    "issues": result.issues,
                    "warnings": result.warnings,
                    "layout_names": result.layout_names,
                },
            )

        # 호환 가능 → 템플릿 디렉터리에 저장
        safe_name = _sanitize_filename(filename)
        dest = os.path.join(_server_template_dir(), safe_name)
        shutil.copy2(tmp_path, dest)
        logger.info("[template/upload] 저장 완료: %s", safe_name)

        template_id = re.sub(r"\.pptx$", "", safe_name, flags=re.IGNORECASE)
        return {
            "compatible": True,
            "template_id": template_id,
            "filename": safe_name,
            "warnings": result.warnings,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
