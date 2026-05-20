import json
import os

import requests


PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class PptServerUnavailable(RuntimeError):
    pass


class PptServerResponseError(RuntimeError):
    pass


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
        raise PptServerUnavailable(str(exc)) from exc

    if response.status_code in (404, 405) or response.status_code >= 500:
        raise PptServerUnavailable(
            f"서버 오류 {response.status_code}: {_response_detail(response)}"
        )
    if response.status_code >= 400:
        raise PptServerResponseError(
            f"서버 요청 오류 {response.status_code}: {_response_detail(response)}"
        )

    return response


def generate_pptx_via_server(
    server_url,
    template_path,
    sequence_entries,
    lyrics_by_title,
    max_lines_per_slide,
    output_pptx_path,
):
    payload = {
        "sequence_entries": [
            {"title": title, "sequence": sequence}
            for title, sequence in sequence_entries
        ],
        "lyrics_by_title": lyrics_by_title,
        "max_lines_per_slide": max_lines_per_slide,
    }
    response = _post_template(server_url, "/generate-ppt", template_path, payload)

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
    response = _post_template(
        server_url,
        "/songlist-card",
        template_path,
        {"song_titles": song_titles},
        timeout=40,
    )

    output_dir = os.path.dirname(os.path.abspath(output_png_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_png_path, "wb") as output_file:
        output_file.write(response.content)

    week_num = response.headers.get("X-Week-Number")
    return int(week_num) if week_num and week_num.isdigit() else None
