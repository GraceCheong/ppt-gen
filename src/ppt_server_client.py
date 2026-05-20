import json
import os

import requests


PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PPT_GENERATOR_VERSION = "direct-python-pptx-v4"


class PptServerUnavailable(RuntimeError):
    pass


class PptServerEndpointUnavailable(PptServerUnavailable):
    pass


class PptServerResponseError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _response_detail(response):
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]

    if isinstance(data, dict) and data.get("detail"):
        return str(data["detail"])
    return response.text[:300]


def _post_template(server_url, endpoint, template_path, payload, timeout=20):
    url = server_url.rstrip("/") + endpoint
    try:
        with open(template_path, "rb") as template_file:
            response = requests.post(
                url,
                data={"payload": json.dumps(payload, ensure_ascii=False)},
                files={
                    "template": (
                        os.path.basename(template_path),
                        template_file,
                        PPTX_MEDIA_TYPE,
                    )
                },
                timeout=(2, timeout),
            )
    except requests.RequestException as exc:
        raise PptServerUnavailable(f"endpoint={endpoint}, 네트워크 오류: {exc}") from exc

    if response.status_code in (404, 405):
        raise PptServerEndpointUnavailable(
            f"endpoint={endpoint}, 서버 오류 {response.status_code}: {_response_detail(response)}"
        )
    if response.status_code >= 500:
        raise PptServerResponseError(
            f"endpoint={endpoint}, 서버 처리 오류 {response.status_code}: {_response_detail(response)}",
            status_code=response.status_code,
        )
    if response.status_code >= 400:
        raise PptServerResponseError(
            f"endpoint={endpoint}, 서버 요청 오류 {response.status_code}: {_response_detail(response)}",
            status_code=response.status_code,
        )

    return response


def generate_pptx_via_server(
    server_url,
    template_path,
    sequence_entries,
    lyrics_by_title,
    max_lines_per_slide,
    output_pptx_path,
    max_chars_per_line=18,
    lyrics_font_size=None,
):
    payload = {
        "sequence_entries": [
            {"title": title, "sequence": sequence}
            for title, sequence in sequence_entries
        ],
        "lyrics_by_title": lyrics_by_title,
        "max_lines_per_slide": max_lines_per_slide,
        "max_chars_per_line": max_chars_per_line,
        "lyrics_font_size": lyrics_font_size,
    }
    response = _post_template(server_url, "/generate-ppt", template_path, payload)
    generator = response.headers.get("X-PORR-Generator", "")
    if generator != PPT_GENERATOR_VERSION:
        raise PptServerUnavailable(
            "endpoint=/generate-ppt, 서버 생성기가 최신 버전이 아닙니다. "
            f"generator={generator or 'missing'}"
        )

    output_dir = os.path.dirname(os.path.abspath(output_pptx_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_pptx_path, "wb") as output_file:
        output_file.write(response.content)

    appended_count = response.headers.get("X-Appended-Count")
    return int(appended_count) if appended_count and appended_count.isdigit() else None


def generate_songlist_card_via_server(
    server_url,
    template_path,
    song_titles,
    output_png_path,
):
    response = None
    last_error = None
    # Older deployed servers may expose a different songlist endpoint.
    for endpoint in (
        "/songlist-card",
        "/songlist",
        "/songlist_card",
        "/generate-songlist-card",
    ):
        try:
            response = _post_template(
                server_url,
                endpoint,
                template_path,
                {"song_titles": song_titles},
                timeout=90,
            )
            break
        except PptServerEndpointUnavailable as exc:
            last_error = exc

    if response is None:
        raise last_error or PptServerUnavailable("송리스트 카드 요청에 실패했습니다.")

    output_dir = os.path.dirname(os.path.abspath(output_png_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_png_path, "wb") as output_file:
        output_file.write(response.content)

    week_num = response.headers.get("X-Week-Number")
    return int(week_num) if week_num and week_num.isdigit() else None
