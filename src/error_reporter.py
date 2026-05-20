import datetime as _datetime
import platform
import socket
import sys
import threading
import traceback

import requests


REPORT_ENDPOINT = "/client-error-report"
MAX_TEXT_LENGTH = 12000
MAX_LOG_LINES = 30


def _trim(value, limit=MAX_TEXT_LENGTH):
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[trimmed]"


def format_exception(exc, tb=None):
    if tb is None:
        tb = getattr(exc, "__traceback__", None)
    return "".join(traceback.format_exception(type(exc), exc, tb))


def build_error_report(
    context,
    message,
    traceback_text="",
    extra=None,
    log_tail=None,
):
    return {
        "reported_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "context": _trim(context, 300),
        "message": _trim(message, 1000),
        "traceback": _trim(traceback_text),
        "extra": extra if isinstance(extra, dict) else {},
        "log_tail": list(log_tail or [])[-MAX_LOG_LINES:],
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "frozen": bool(getattr(sys, "frozen", False)),
            "hostname": socket.gethostname(),
        },
    }


def send_error_report(server_url, report):
    url = server_url.rstrip("/") + REPORT_ENDPOINT
    response = requests.post(url, json=report, timeout=(2, 5))
    response.raise_for_status()


def report_error_async(server_url, context, message, traceback_text="", extra=None, log_tail=None):
    report = build_error_report(
        context=context,
        message=message,
        traceback_text=traceback_text,
        extra=extra,
        log_tail=log_tail,
    )

    def run():
        try:
            send_error_report(server_url, report)
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()
    return report
