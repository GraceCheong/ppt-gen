"""
PPTX → PNG 변환 서버 (PowerPoint COM 사용)

실행 방법:
    pip install -r server/requirements.txt
    uvicorn server.convert_server:app --host 0.0.0.0 --port 8000

Windows + Microsoft PowerPoint가 설치되어 있어야 합니다.
"""

import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from pptx import Presentation

app = FastAPI(title="PPTX Converter", version="1.0.0")

# COM은 단일 스레드에서 직렬로 처리해야 하므로 max_workers=1
_executor = ThreadPoolExecutor(max_workers=1)


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


@app.get("/health")
def health():
    import importlib.util
    com_available = importlib.util.find_spec("comtypes") is not None
    return {"status": "ok", "comtypes": com_available}


@app.post("/convert", response_class=Response)
async def convert(file: UploadFile):
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
