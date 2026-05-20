import os
import shutil
import subprocess
import sys
import tempfile

from pptx import Presentation

from ppt_builder import append_lyrics_to_ppt
from songlist_builder import build_songlist_card, _find_libreoffice


class NoLyricsError(ValueError):
    pass


class LocalOfficeUnavailable(RuntimeError):
    pass


def build_integrated_pptx(
    template_path,
    sequence_entries,
    lyrics_by_title,
    output_pptx_path,
    max_lines_per_slide=2,
):
    prs = Presentation(template_path)
    appended_count = 0
    skipped_titles = []

    for song_title, sequence_str in sequence_entries:
        raw_lyrics = str(lyrics_by_title.get(song_title, "") or "")
        if not raw_lyrics.strip():
            skipped_titles.append(song_title)
            continue

        append_lyrics_to_ppt(
            prs,
            song_title,
            raw_lyrics,
            sequence_str,
            max_lines_per_slide,
        )
        appended_count += 1

    if appended_count == 0:
        raise NoLyricsError("생성할 가사가 없습니다.")

    output_dir = os.path.dirname(os.path.abspath(output_pptx_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    prs.save(output_pptx_path)
    return {
        "appended_count": appended_count,
        "skipped_titles": skipped_titles,
    }


def _save_pptx_via_powerpoint_com(source_pptx_path, output_pptx_path):
    if sys.platform != "win32":
        raise RuntimeError("PowerPoint COM은 Windows에서만 사용할 수 있습니다.")

    import comtypes
    import comtypes.client

    source_abs = os.path.abspath(source_pptx_path)
    output_abs = os.path.abspath(output_pptx_path)
    output_dir = os.path.dirname(output_abs)
    os.makedirs(output_dir, exist_ok=True)
    fd, temp_output = tempfile.mkstemp(suffix=".pptx", dir=output_dir)
    os.close(fd)
    os.remove(temp_output)

    comtypes.CoInitialize()
    try:
        powerpoint = comtypes.client.CreateObject("PowerPoint.Application")
        powerpoint.Visible = 1
        try:
            prs_com = powerpoint.Presentations.Open(source_abs, ReadOnly=-1, WithWindow=0)
            try:
                # 24 = ppSaveAsOpenXMLPresentation (.pptx)
                prs_com.SaveAs(temp_output, 24)
            finally:
                prs_com.Close()
        finally:
            powerpoint.Quit()
    finally:
        comtypes.CoUninitialize()

    if not os.path.exists(temp_output):
        raise RuntimeError("PowerPoint COM 저장 결과 파일을 찾을 수 없습니다.")
    os.replace(temp_output, output_abs)


def _save_pptx_via_libreoffice(source_pptx_path, output_pptx_path):
    lo = _find_libreoffice()
    if not lo:
        return False

    source_abs = os.path.abspath(source_pptx_path)
    output_abs = os.path.abspath(output_pptx_path)
    output_dir = os.path.dirname(output_abs)
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        temp_source = os.path.join(tmp, "source.pptx")
        shutil.copyfile(source_abs, temp_source)
        result = subprocess.run(
            [lo, "--headless", "--convert-to", "pptx", "--outdir", output_dir, temp_source],
            capture_output=True,
            timeout=90,
        )
        if result.returncode != 0:
            return False

    generated = os.path.join(output_dir, "source.pptx")
    if not os.path.exists(generated):
        return False

    if os.path.abspath(generated) != output_abs:
        os.replace(generated, output_abs)
    return os.path.exists(output_abs)


def build_integrated_pptx_with_local_office(
    template_path,
    sequence_entries,
    lyrics_by_title,
    output_pptx_path,
    max_lines_per_slide=2,
):
    """Build a PPTX locally and finalize it with PowerPoint COM, then LibreOffice if needed."""
    errors = []

    with tempfile.TemporaryDirectory() as tmp:
        draft_path = os.path.join(tmp, "draft.pptx")
        result = build_integrated_pptx(
            template_path,
            sequence_entries,
            lyrics_by_title,
            draft_path,
            max_lines_per_slide,
        )

        try:
            _save_pptx_via_powerpoint_com(draft_path, output_pptx_path)
            result["method"] = "PowerPoint COM"
            return result
        except Exception as e:
            errors.append(f"로컬 PowerPoint COM 저장 실패: {e}")

        if _save_pptx_via_libreoffice(draft_path, output_pptx_path):
            result["method"] = "LibreOffice"
            return result

    errors.append("LibreOffice를 찾을 수 없거나 PPTX 저장에 실패했습니다.")
    detail = "\n".join(f"- {message}" for message in errors)
    raise LocalOfficeUnavailable(
        "로컬에서 PPT를 생성할 수 없습니다.\n"
        f"{detail}\n\n"
        "PowerPoint가 설치되어 있지 않다면 LibreOffice를 설치하세요:\n"
        "https://www.libreoffice.org/download/download-libreoffice/"
    )


def build_songlist_card_png(template_path, song_titles, output_png_path):
    output_dir = os.path.dirname(os.path.abspath(output_png_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    return build_songlist_card(template_path, song_titles, output_png_path)
