"""악보 드라이브 API 라우터."""
from __future__ import annotations

import io
import zipfile

import urllib.parse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from server.app.api.deps import require_user
from server.app.config import (
    ALLOWED_SHEET_MIME_EXACT,
    ALLOWED_SHEET_MIME_PREFIXES,
    MAX_UPLOAD_BYTES,
)
from server.app.models.auth import AuthContext
from server.app.services import sheet_service
from server.app.services import gdrive_sync

router = APIRouter(prefix="/api/sheets")


def _check_mime(mime_type: str) -> bool:
    if mime_type in ALLOWED_SHEET_MIME_EXACT:
        return True
    for prefix in ALLOWED_SHEET_MIME_PREFIXES:
        if mime_type.startswith(prefix):
            return True
    return False


# ── is_super 노출 (경로 충돌 방지를 위해 /{file_id} 앞에 배치) ───────────────────

@router.get("/me")
def get_me(ctx: AuthContext = Depends(require_user)):
    return {
        "user_id": ctx.user_id,
        "is_super": sheet_service.is_super(ctx.user_id),
    }


# ── Google Drive 동기화 ─────────────────────────────────────────────────────────

@router.get("/sync/status")
def get_sync_status(ctx: AuthContext = Depends(require_user)):
    return gdrive_sync.sync_status()


@router.post("/sync")
def trigger_sync(ctx: AuthContext = Depends(require_user)):
    import threading
    threading.Thread(target=gdrive_sync.sync_once, daemon=True).start()
    return {"message": "동기화가 시작되었습니다."}


# ── 검색 ────────────────────────────────────────────────────────────────────────

@router.get("/search")
def search_sheets(
    q: str = "",
    key_root: str | None = None,
    key_mode: str | None = None,
    folder_id: str | None = None,
    extension: str | None = None,
    is_event_only: bool | None = None,
    has_key: bool | None = None,
    uploaded_by: str | None = None,
    sort_by: str = "uploaded_at",
    sort_dir: str = "desc",
    ctx: AuthContext = Depends(require_user),
):
    items = sheet_service.search_sheets(
        q=q, key_root=key_root, key_mode=key_mode, folder_id=folder_id,
        extension=extension, is_event_only=is_event_only, has_key=has_key,
        uploaded_by=uploaded_by, sort_by=sort_by, sort_dir=sort_dir,
    )
    return {"items": items, "count": len(items)}


# ── 업로드 ─────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_sheet(
    file: UploadFile = File(...),
    title: str = Form(...),
    key_root: str = Form(...),
    key_mode: str = Form(...),
    page_number: int = Form(1),
    page_count: int | None = Form(None),
    folder_id: str | None = Form(None),
    on_conflict: str = Form("error"),
    ctx: AuthContext = Depends(require_user),
):
    mime_type = file.content_type or ""
    if not _check_mime(mime_type):
        raise HTTPException(400, detail=f"허용되지 않는 파일 형식입니다: {mime_type}")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, detail="빈 파일은 업로드할 수 없습니다.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            detail=f"파일 크기가 제한({MAX_UPLOAD_BYTES // 1024 // 1024}MB)을 초과합니다.",
        )

    if on_conflict not in ("error", "replace", "version"):
        on_conflict = "error"

    result = sheet_service.upload_sheet(
        display_title=title,
        key_root=key_root,
        key_mode=key_mode,
        page_number=page_number,
        page_count=page_count,
        folder_id=folder_id or None,
        file_bytes=file_bytes,
        original_filename=file.filename or "upload",
        mime_type=mime_type,
        uploaded_by=ctx.user_id,
        on_conflict=on_conflict,
    )
    return result


# ── 휴지통 (경로 충돌 방지를 위해 {file_id} 앞에 배치) ───────────────────────────

@router.get("/trash")
def list_trash(q: str = "", ctx: AuthContext = Depends(require_user)):
    items = sheet_service.list_trash(q)
    return {"items": items, "count": len(items)}


# ── 폴더 ────────────────────────────────────────────────────────────────────────

@router.get("/folders")
def list_folders(parent_id: str | None = None, ctx: AuthContext = Depends(require_user)):
    items = sheet_service.list_folders(parent_id)
    return {"items": items}


@router.post("/folders")
async def create_folder(request: Request, ctx: AuthContext = Depends(require_user)):
    data = await request.json()
    name = str(data.get("name") or "").strip()
    parent_id = data.get("parent_id") or None
    if not name:
        raise HTTPException(400, detail="폴더 이름을 입력하세요.")
    folder = sheet_service.create_folder(name, parent_id, created_by=ctx.user_id)
    return folder


@router.patch("/folders/{folder_id}")
async def rename_folder(folder_id: str, request: Request, ctx: AuthContext = Depends(require_user)):
    data = await request.json()
    name = str(data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, detail="폴더 이름을 입력하세요.")
    try:
        folder = sheet_service.rename_folder(folder_id, name)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return folder


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: str, ctx: AuthContext = Depends(require_user)):
    sheet_service.delete_folder(folder_id, deleted_by=ctx.user_id)
    return {"ok": True}


@router.post("/folders/{folder_id}/restore")
def restore_folder(folder_id: str, ctx: AuthContext = Depends(require_user)):
    try:
        sheet_service.restore_folder(folder_id)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return {"ok": True}


@router.delete("/folders/{folder_id}/permanent")
def permanent_delete_folder(folder_id: str, ctx: AuthContext = Depends(require_user)):
    if not sheet_service.is_super(ctx.user_id):
        raise HTTPException(403, detail="super 계정만 완전 삭제할 수 있습니다.")
    try:
        sheet_service.permanent_delete_folder(folder_id, by_user=ctx.user_id)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return {"ok": True}


# ── 곡 DB 연동 ──────────────────────────────────────────────────────────────────

@router.get("/by-song/{title_key}")
def get_sheets_by_song(title_key: str, ctx: AuthContext = Depends(require_user)):
    items = sheet_service.get_sheets_by_song(title_key)
    return {"items": items}


@router.post("/by-titles")
async def get_sheets_by_titles(request: Request, ctx: AuthContext = Depends(require_user)):
    data = await request.json()
    title_keys = data.get("title_keys") or []
    result = sheet_service.get_sheets_by_titles(title_keys)
    return result


@router.get("/by-song/{title_key}/download")
def download_sheets_by_song_key(
    title_key: str,
    key_root: str = "",
    key_mode: str = "",
    ctx: AuthContext = Depends(require_user),
):
    try:
        files = sheet_service.download_sheets_by_song_key(title_key, key_root, key_mode)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

    if not files:
        raise HTTPException(404, detail="해당 악보를 찾을 수 없습니다.")

    if len(files) == 1:
        data, filename, mime = files[0]
        return Response(
            content=data,
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # 복수 파일 → ZIP
    key_display = sheet_service.format_key(key_root, key_mode)
    zip_name = f"{title_key}_{key_display}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (data, filename, _mime) in enumerate(files, start=1):
            # 파일명 중복 방지: 순서 prefix
            arcname = f"{i:02d}_{filename}"
            zf.writestr(arcname, data)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


# ── 개별 파일 ──────────────────────────────────────────────────────────────────

@router.get("/{file_id}")
def get_sheet(file_id: str, ctx: AuthContext = Depends(require_user)):
    sheet = sheet_service.get_sheet(file_id)
    if not sheet:
        raise HTTPException(404, detail="악보를 찾을 수 없습니다.")
    return sheet


def _content_disposition(disposition: str, filename: str) -> str:
    encoded = urllib.parse.quote(filename, safe="")
    return f"{disposition}; filename*=UTF-8''{encoded}"


@router.get("/{file_id}/download")
def download_sheet(file_id: str, ctx: AuthContext = Depends(require_user)):
    try:
        data, filename, mime = sheet_service.download_sheet(file_id)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": _content_disposition("attachment", filename)},
    )


@router.get("/{file_id}/preview")
def preview_sheet(file_id: str, ctx: AuthContext = Depends(require_user)):
    try:
        data, filename, mime = sheet_service.download_sheet(file_id)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": _content_disposition("inline", filename)},
    )


@router.patch("/{file_id}")
async def update_sheet(file_id: str, request: Request, ctx: AuthContext = Depends(require_user)):
    data = await request.json()
    try:
        is_event_only = data.get("is_event_only")
        updated = sheet_service.update_sheet_meta(
            file_id=file_id,
            display_title=data.get("display_title"),
            key_root=data.get("key_root"),
            key_mode=data.get("key_mode"),
            page_number=data.get("page_number"),
            page_count=data.get("page_count"),
            is_event_only=bool(is_event_only) if is_event_only is not None else None,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return updated


@router.delete("/{file_id}")
def delete_sheet(file_id: str, ctx: AuthContext = Depends(require_user)):
    try:
        sheet_service.delete_sheet(file_id, deleted_by=ctx.user_id)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return {"ok": True}


@router.post("/{file_id}/restore")
def restore_sheet(file_id: str, ctx: AuthContext = Depends(require_user)):
    try:
        result = sheet_service.restore_sheet(file_id)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    return result


@router.delete("/{file_id}/permanent")
def permanent_delete_sheet(file_id: str, ctx: AuthContext = Depends(require_user)):
    if not sheet_service.is_super(ctx.user_id):
        raise HTTPException(403, detail="super 계정만 완전 삭제할 수 있습니다.")
    try:
        sheet_service.permanent_delete_sheet(file_id, by_user=ctx.user_id)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return {"ok": True}
