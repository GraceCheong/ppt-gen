"""이메일 발송 서비스 — SMTP 미설정 시 발송을 건너뛰고 로그만 남긴다."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from server.app.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
    SMTP_USE_TLS,
)

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    """이메일을 발송한다. SMTP 미설정이거나 수신자가 없으면 발송을 건너뛰고 False를 반환한다."""
    if not SMTP_HOST or not to:
        logger.warning("SMTP 미설정 또는 수신자 없음 — 이메일 발송 생략 (to=%s, subject=%s)", to, subject)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("이메일 발송 실패 (to=%s, subject=%s)", to, subject)
        return False
