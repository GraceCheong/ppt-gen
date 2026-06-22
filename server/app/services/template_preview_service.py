"""템플릿 썸네일 생성 및 캐싱."""
from __future__ import annotations

import os
import zipfile

from server.app.config import ROOT_DIR


class PreviewUnavailableError(Exception):
    pass


def _cache_dir() -> str:
    path = os.path.join(ROOT_DIR, "out", "thumbnails")
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path(template_path: str) -> str:
    mtime = int(os.path.getmtime(template_path))
    name = os.path.splitext(os.path.basename(template_path))[0]
    return os.path.join(_cache_dir(), f"{name}_{mtime}.png")


def _extract_embedded(pptx_path: str) -> tuple[bytes, str] | None:
    """PPTX ZIP에서 docProps 내장 썸네일 추출. 없으면 None."""
    candidates = [
        ("docProps/thumbnail.jpeg", "image/jpeg"),
        ("docProps/thumbnail.jpg", "image/jpeg"),
        ("docProps/thumbnail.png", "image/png"),
    ]
    try:
        with zipfile.ZipFile(pptx_path) as z:
            names = set(z.namelist())
            for entry, mime in candidates:
                if entry in names:
                    data = z.read(entry)
                    if data:
                        return data, mime
    except Exception:
        pass
    return None


def _render_with_com(pptx_path: str, png_path: str, width_px: int = 800) -> None:
    """PowerPoint COM으로 첫 슬라이드를 PNG로 렌더링. COM 불가 시 예외."""
    import comtypes
    import comtypes.client
    from pptx import Presentation
    from powerpoint_com import create_powerpoint_application, open_presentation_hidden

    prs = Presentation(pptx_path)
    w, h = prs.slide_width, prs.slide_height
    height_px = int(width_px * h / w)

    pptx_abs = os.path.abspath(pptx_path)
    png_abs = os.path.abspath(png_path)

    comtypes.CoInitialize()
    try:
        ppt = create_powerpoint_application(comtypes.client)
        try:
            prs_com = open_presentation_hidden(ppt, pptx_abs)
            try:
                prs_com.Slides(1).Export(png_abs, "PNG", width_px, height_px)
            finally:
                prs_com.Close()
        finally:
            ppt.Quit()
    finally:
        comtypes.CoUninitialize()


def get_template_thumbnail(template_path: str) -> tuple[bytes, str]:
    """(bytes, mime_type) 반환.

    우선순위:
    1. PPTX 내장 썸네일 (빠름)
    2. 디스크 캐시 (COM 렌더 결과)
    3. PowerPoint COM 렌더링 (느림, 캐시 저장)

    모두 실패하면 PreviewUnavailableError.
    """
    # 1. 내장 썸네일
    result = _extract_embedded(template_path)
    if result:
        return result

    # 2. 디스크 캐시
    cache = _cache_path(template_path)
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return f.read(), "image/png"

    # 3. COM 렌더링
    try:
        _render_with_com(template_path, cache)
    except ImportError as e:
        raise PreviewUnavailableError(f"PowerPoint COM 모듈 없음: {e}")
    except Exception as e:
        raise PreviewUnavailableError(f"COM 렌더링 실패: {e}")

    if not os.path.exists(cache):
        raise PreviewUnavailableError("PNG 출력 파일이 생성되지 않았습니다.")

    with open(cache, "rb") as f:
        return f.read(), "image/png"
