import datetime
import logging
import os
import shutil
import subprocess
import sys
import tempfile

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Pt

from ppt_builder import set_editable_text
from powerpoint_com import create_powerpoint_application, open_presentation_hidden

logger = logging.getLogger(__name__)

_TITLE_FONT = "Diphylleia"
_TITLE_FONT_SIZE = Pt(32)

# 52 natural text colors, one per ISO week of the year.
# Ordered to follow a seasonal progression (winter → spring → summer → autumn → winter).
_WEEK_HEX_COLORS = [
    # Winter (weeks 1–8)
    "#5C6E82", "#6B7280", "#5E6E78", "#667289", "#6E6A82", "#587076", "#6A6E7A", "#5E6A72",
    # Early Spring (weeks 9–17)
    "#6A8260", "#7A8A62", "#6E9070", "#7A9470", "#8A946A", "#9A9460", "#A08A58", "#A8825A",
    "#A87868",
    # Spring Bloom (weeks 18–26)
    "#B07278", "#A87080", "#A06E8A", "#8E6E94", "#7A70A0", "#6A78A8", "#6082A8", "#5A8AA4",
    "#5A9096",
    # Summer (weeks 27–35)
    "#5A946A", "#6A9460", "#7A9458", "#909A58", "#A09A52", "#A88C50", "#B07E50", "#B07260",
    "#B06860",
    # Early Autumn (weeks 36–44)
    "#A86060", "#A05868", "#98587A", "#8A6090", "#7A6898", "#6C6E98", "#687088", "#706878",
    "#887068",
    # Late Autumn / Winter (weeks 45–52)
    "#906858", "#987060", "#A07860", "#A08068", "#989070", "#888A70", "#78886A", "#6A7E78",
]


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def get_week_color(date=None):
    """Return (week_number, RGBColor) for the ISO week of the given date (today if None)."""
    if date is None:
        date = datetime.date.today()
    week_num = date.isocalendar()[1]
    r, g, b = _hex_to_rgb(_WEEK_HEX_COLORS[(week_num - 1) % len(_WEEK_HEX_COLORS)])
    return week_num, RGBColor(r, g, b)


def _get_alt_text(shape):
    try:
        return shape._element.nvSpPr.cNvPr.get("descr", "") or ""
    except AttributeError:
        return ""


def _apply_color(shape, rgb_color):
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            run.font.color.rgb = rgb_color


def build_songlist_pptx(template_path, song_titles, output_pptx_path):
    """Fill the songlist card template with song titles and apply the week color."""
    week_num, rgb = get_week_color()

    prs = Presentation(template_path)
    slide = prs.slides[0]

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue

        alt = _get_alt_text(shape)

        # Fill song title slots: alt text "곡 1", "곡 2", ...
        if alt.startswith("곡"):
            rest = alt[1:].strip()
            if rest.isdigit():
                idx = int(rest) - 1
                title = song_titles[idx] if idx < len(song_titles) else ""
                set_editable_text(shape, title)
                total_runs = sum(len(para.runs) for para in shape.text_frame.paragraphs)
                logger.debug(
                    "[폰트설정] shape=%r alt=%r title=%r paragraphs=%d total_runs=%d",
                    shape.name, alt, title,
                    len(shape.text_frame.paragraphs), total_runs,
                )
                if total_runs == 0:
                    logger.warning(
                        "[폰트설정 실패] shape=%r alt=%r: runs가 없어 폰트를 적용할 수 없습니다. "
                        "set_editable_text 이후 텍스트 프레임에 run이 생성되지 않았습니다.",
                        shape.name, alt,
                    )
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        try:
                            run.font.name = _TITLE_FONT
                            run.font.size = _TITLE_FONT_SIZE
                            # 한글 텍스트는 Latin이 아닌 East Asian 폰트를 참조하므로
                            # <a:ea typeface> 도 명시적으로 설정해야 적용됨
                            rPr = run._r.get_or_add_rPr()
                            ea_elem = rPr.find(qn("a:ea"))
                            if ea_elem is None:
                                ea_elem = etree.SubElement(rPr, qn("a:ea"))
                            ea_elem.set("typeface", _TITLE_FONT)
                            logger.debug(
                                "[폰트설정 성공] shape=%r run text=%r font.name=%r font.size=%s",
                                shape.name, run.text, run.font.name, run.font.size,
                            )
                        except Exception as e:
                            logger.error(
                                "[폰트설정 오류] shape=%r run text=%r: %s",
                                shape.name, run.text, e,
                                exc_info=True,
                            )

        # Apply week color to "song" and "list" shapes
        if alt.lower() in ("song", "list"):
            _apply_color(shape, rgb)

    prs.save(output_pptx_path)
    return week_num


def _slide_px(pptx_path, long_edge_px=2000):
    prs = Presentation(pptx_path)
    w_emu, h_emu = prs.slide_width, prs.slide_height
    if w_emu >= h_emu:
        return long_edge_px, int(long_edge_px * h_emu / w_emu)
    return int(long_edge_px * w_emu / h_emu), long_edge_px


def find_libreoffice():
    """Return path to LibreOffice executable, or None if not found."""
    if sys.platform == "win32":
        candidates = [
            shutil.which("soffice"),
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            shutil.which("soffice"),
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ]
    else:
        candidates = [shutil.which("soffice"), shutil.which("libreoffice")]

    return next((c for c in candidates if c and os.path.isfile(c)), None)


def _export_via_libreoffice(pptx_path, png_path):
    lo = find_libreoffice()
    if not lo:
        return False

    pptx_abs = os.path.abspath(pptx_path)
    png_abs = os.path.abspath(png_path)
    output_dir = os.path.dirname(png_abs)

    result = subprocess.run(
        [lo, "--headless", "--norestore", "--convert-to", "png", "--outdir", output_dir, pptx_abs],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        return False

    # LibreOffice names output as <input_stem>.png
    generated = os.path.join(output_dir, os.path.splitext(os.path.basename(pptx_abs))[0] + ".png")
    if os.path.exists(generated) and os.path.abspath(generated) != png_abs:
        os.replace(generated, png_abs)

    return os.path.exists(png_abs)


def _export_via_com(pptx_path, png_path, long_edge_px=None):
    import comtypes
    import comtypes.client

    pptx_abs = os.path.abspath(pptx_path)
    png_abs = os.path.abspath(png_path)
    last_error = None

    long_edges = (long_edge_px,) if long_edge_px else (2000, 1600, 1280)
    for export_long_edge_px in long_edges:
        width_px, height_px = _slide_px(pptx_path, long_edge_px=export_long_edge_px)

        comtypes.CoInitialize()
        try:
            powerpoint = create_powerpoint_application(comtypes.client)
            try:
                prs_com = open_presentation_hidden(powerpoint, pptx_abs)
                try:
                    prs_com.Slides(1).Export(png_abs, "PNG", width_px, height_px)
                    if os.path.exists(png_abs):
                        return
                finally:
                    prs_com.Close()
            finally:
                powerpoint.Quit()
        except Exception as e:
            last_error = e
        finally:
            comtypes.CoUninitialize()

    if last_error is not None:
        raise last_error
    raise RuntimeError("PowerPoint COM PNG 변환에 실패했습니다.")


def _export_via_server(pptx_path, png_path, server_url):
    import requests

    url = server_url.rstrip("/") + "/convert"
    with open(pptx_path, "rb") as f:
        response = requests.post(
            url,
            files={"file": ("input.pptx", f, "application/octet-stream")},
            timeout=30,
        )
    response.raise_for_status()

    with open(png_path, "wb") as f:
        f.write(response.content)


def export_pptx_to_png(pptx_path, png_path, server_url=None, long_edge_px=None, skip_com=False):
    """Export the first slide to PNG.

    Priority:
      1. Conversion server (if server_url provided)
      2. Local PowerPoint COM (Windows only, unless skip_com=True)
      3. LibreOffice (if installed locally)
    """
    errors = []

    if server_url:
        try:
            _export_via_server(pptx_path, png_path, server_url)
            logger.info("PNG 변환 완료 [method=server url=%s]", server_url)
            return
        except Exception as e:
            errors.append(f"서버 변환 실패: {e}")

    if sys.platform == "win32" and not skip_com:
        try:
            _export_via_com(pptx_path, png_path, long_edge_px=long_edge_px)
            logger.info("PNG 변환 완료 [method=PowerPoint COM]")
            return
        except Exception as e:
            errors.append(f"로컬 PowerPoint 변환 실패: {e}")

    if _export_via_libreoffice(pptx_path, png_path):
        logger.info("PNG 변환 완료 [method=LibreOffice]")
        return

    errors.append("LibreOffice를 찾을 수 없거나 PNG 변환에 실패했습니다.")

    detail = "\n".join(f"- {message}" for message in errors)
    raise RuntimeError(
        "PPT를 PNG로 변환할 수 없습니다.\n"
        f"{detail}\n\n"
        "서버가 응답하지 않으면 로컬 PowerPoint로 변환을 시도합니다. "
        "로컬 PowerPoint도 사용할 수 없다면 LibreOffice를 설치하세요:\n"
        "https://www.libreoffice.org/download/download-libreoffice/"
    )


def build_songlist_card(template_path, song_titles, output_png_path, server_url=None, skip_com=False):
    """Build the songlist card and export it as PNG. Returns the ISO week number used."""
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        week_num = build_songlist_pptx(template_path, song_titles, tmp_path)
        export_pptx_to_png(tmp_path, output_png_path, server_url=server_url, skip_com=skip_com)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return week_num
