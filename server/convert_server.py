"""
PPT 생성/변환 서버

실행 방법:
    pip install -r server/requirements.txt
    uvicorn server.convert_server:app --host 0.0.0.0 --port 8000

PNG 변환에는 Windows + Microsoft PowerPoint 또는 LibreOffice가 필요합니다.
"""

import asyncio
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pptx import Presentation

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from constants import ASSETS_DIR_NAME, TEMPLATE_DIR_NAME, TEMPLATE_DOWNLOAD_URL
from ppt_service import LocalOfficeUnavailable, NoLyricsError, build_integrated_pptx, build_songlist_card_png

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
TEMPLATE_SYNC_INTERVAL_SECONDS = 10 * 60

app = FastAPI(title="PO,RR PPT Server", version="1.1.0")

# COM은 단일 스레드에서 직렬로 처리해야 하므로 max_workers=1
_executor = ThreadPoolExecutor(max_workers=1)
_template_executor = ThreadPoolExecutor(max_workers=1)
_template_sync_task: asyncio.Task | None = None


def _server_template_dir() -> str:
    path = os.path.join(ROOT_DIR, ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _server_template_files() -> set[str]:
    template_dir = _server_template_dir()
    result = set()
    for root, _, files in os.walk(template_dir):
        for file_name in files:
            if file_name.lower().endswith(".pptx"):
                result.add(os.path.abspath(os.path.join(root, file_name)))
    return result


def _sync_templates_once() -> list[str]:
    import gdown

    template_dir = _server_template_dir()
    before = _server_template_files()

    try:
        gdown.download_folder(
            TEMPLATE_DOWNLOAD_URL,
            output=template_dir,
            quiet=True,
            use_cookies=False,
            resume=True,
            remaining_ok=True,
        )
    except TypeError:
        gdown.download_folder(
            TEMPLATE_DOWNLOAD_URL,
            output=template_dir,
            quiet=True,
            use_cookies=False,
            resume=True,
        )

    after = _server_template_files()
    return sorted(os.path.basename(path) for path in after - before)


async def _template_sync_loop() -> None:
    while True:
        try:
            loop = asyncio.get_event_loop()
            added = await loop.run_in_executor(_template_executor, _sync_templates_once)
            if added:
                print(f"[template-sync] 새 템플릿 {len(added)}개 다운로드: {', '.join(added)}")
            else:
                print("[template-sync] 새 템플릿 없음")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[template-sync] 템플릿 확인 실패: {e}")

        await asyncio.sleep(TEMPLATE_SYNC_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_template_sync() -> None:
    global _template_sync_task
    if _template_sync_task is None or _template_sync_task.done():
        _template_sync_task = asyncio.create_task(_template_sync_loop())


@app.on_event("shutdown")
async def stop_template_sync() -> None:
    if _template_sync_task is not None:
        _template_sync_task.cancel()


def _slide_px(pptx_path: str, long_edge_px: int = 2000) -> tuple[int, int]:
    prs = Presentation(pptx_path)
    w, h = prs.slide_width, prs.slide_height
    if w >= h:
        return long_edge_px, int(long_edge_px * h / w)
    return int(long_edge_px * w / h), long_edge_px


def _convert_sync(pptx_path: str, png_path: str) -> None:
    """PowerPoint COM API로 첫 번째 슬라이드를 PNG로 변환합니다."""
    import comtypes
    import comtypes.client

    width_px, height_px = _slide_px(pptx_path)
    pptx_abs = os.path.abspath(pptx_path)
    png_abs = os.path.abspath(png_path)

    comtypes.CoInitialize()
    try:
        ppt = comtypes.client.CreateObject("PowerPoint.Application")
        ppt.Visible = 1
        try:
            prs_com = ppt.Presentations.Open(pptx_abs, ReadOnly=-1, WithWindow=0)
            try:
                prs_com.Slides(1).Export(png_abs, "PNG", width_px, height_px)
            finally:
                prs_com.Close()
        finally:
            ppt.Quit()
    finally:
        comtypes.CoUninitialize()


async def _save_upload(upload: UploadFile, path: str) -> None:
    data = await upload.read()
    if not data:
        raise HTTPException(400, detail="업로드된 파일이 비어 있습니다.")

    with open(path, "wb") as f:
        f.write(data)


def _load_payload(payload: str) -> dict:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise HTTPException(400, detail=f"payload JSON 형식이 올바르지 않습니다: {e}")

    if not isinstance(data, dict):
        raise HTTPException(400, detail="payload는 JSON object여야 합니다.")
    return data


def _sequence_entries_from_payload(data: dict) -> list[tuple[str, str]]:
    entries = data.get("sequence_entries")
    if not isinstance(entries, list) or not entries:
        raise HTTPException(400, detail="sequence_entries가 비어 있습니다.")

    parsed = []
    for index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            raise HTTPException(400, detail=f"{index}번째 sequence entry가 올바르지 않습니다.")

        title = str(item.get("title", "")).strip()
        sequence = str(item.get("sequence", "")).strip()
        if not title or not sequence:
            raise HTTPException(400, detail=f"{index}번째 곡 제목 또는 진행 순서가 비어 있습니다.")
        parsed.append((title, sequence))

    return parsed


@app.get("/health")
def health():
    import importlib.util
    com_available = importlib.util.find_spec("comtypes") is not None
    return {"status": "ok", "comtypes": com_available}


@app.post("/convert", response_class=Response)
async def convert(file: UploadFile = File(...)):
    """PPTX 파일을 받아 첫 번째 슬라이드를 PNG로 변환해 반환합니다."""
    if not (file.filename or "").lower().endswith(".pptx"):
        raise HTTPException(400, detail="PPTX 파일만 허용됩니다.")

    data = await file.read()

    with tempfile.TemporaryDirectory() as tmp:
        pptx_path = os.path.join(tmp, "input.pptx")
        png_path = os.path.join(tmp, "output.png")

        with open(pptx_path, "wb") as f:
            f.write(data)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_executor, _convert_sync, pptx_path, png_path)
        except Exception as e:
            raise HTTPException(500, detail=f"변환 실패: {e}")

        if not os.path.exists(png_path):
            raise HTTPException(500, detail="PNG 출력 파일을 찾을 수 없습니다.")

        with open(png_path, "rb") as f:
            png_data = f.read()

    return Response(content=png_data, media_type="image/png")


@app.post("/generate-ppt", response_class=Response)
async def generate_ppt(payload: str = Form(...), template: UploadFile = File(...)):
    """템플릿과 레파토리/가사 데이터를 받아 PPTX 파일을 생성해 반환합니다."""
    if not (template.filename or "").lower().endswith(".pptx"):
        raise HTTPException(400, detail="PPTX 템플릿만 허용됩니다.")

    data = _load_payload(payload)
    sequence_entries = _sequence_entries_from_payload(data)
    lyrics_by_title = data.get("lyrics_by_title") or {}
    if not isinstance(lyrics_by_title, dict):
        raise HTTPException(400, detail="lyrics_by_title은 JSON object여야 합니다.")

    try:
        max_lines_per_slide = int(data.get("max_lines_per_slide") or 2)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="max_lines_per_slide는 숫자여야 합니다.")

    with tempfile.TemporaryDirectory() as tmp:
        template_path = os.path.join(tmp, "template.pptx")
        output_path = os.path.join(tmp, "output.pptx")
        await _save_upload(template, template_path)

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _executor,
                build_integrated_pptx,
                template_path,
                sequence_entries,
                lyrics_by_title,
                output_path,
                max_lines_per_slide,
            )
        except NoLyricsError as e:
            raise HTTPException(400, detail=str(e))
        except Exception as e:
            raise HTTPException(500, detail=f"PPT 생성 실패: {e}")

        if not os.path.exists(output_path):
            raise HTTPException(500, detail="PPTX 출력 파일을 찾을 수 없습니다.")

        with open(output_path, "rb") as f:
            pptx_data = f.read()

    return Response(
        content=pptx_data,
        media_type=PPTX_MEDIA_TYPE,
        headers={"X-Appended-Count": str(result["appended_count"])},
    )


@app.post("/songlist-card", response_class=Response)
async def songlist_card(payload: str = Form(...), template: UploadFile = File(...)):
    """송리스트 템플릿과 곡 제목 목록을 받아 PNG 카드를 생성해 반환합니다."""
    if not (template.filename or "").lower().endswith(".pptx"):
        raise HTTPException(400, detail="PPTX 템플릿만 허용됩니다.")

    data = _load_payload(payload)
    song_titles = data.get("song_titles")
    if not isinstance(song_titles, list):
        raise HTTPException(400, detail="song_titles는 list여야 합니다.")
    song_titles = [str(title).strip() for title in song_titles if str(title).strip()]
    if not song_titles:
        raise HTTPException(400, detail="song_titles가 비어 있습니다.")

    with tempfile.TemporaryDirectory() as tmp:
        template_path = os.path.join(tmp, "songlist_template.pptx")
        png_path = os.path.join(tmp, "songlist_card.png")
        await _save_upload(template, template_path)

        try:
            loop = asyncio.get_event_loop()
            week_num = await loop.run_in_executor(
                _executor,
                build_songlist_card_png,
                template_path,
                song_titles,
                png_path,
            )
        except LocalOfficeUnavailable as e:
            raise HTTPException(503, detail=f"송리스트 카드 생성 실패(로컬 오피스 사용 불가): {e}")
        except Exception as e:
            raise HTTPException(500, detail=f"송리스트 카드 생성 실패: {e}")

        if not os.path.exists(png_path):
            raise HTTPException(500, detail="PNG 출력 파일을 찾을 수 없습니다.")

        with open(png_path, "rb") as f:
            png_data = f.read()

    return Response(
        content=png_data,
        media_type="image/png",
        headers={"X-Week-Number": str(week_num)},
    )
