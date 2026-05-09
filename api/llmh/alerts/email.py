from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from llmh.config import get_settings


async def send_email(*, to_address: str, subject: str, body: str) -> dict:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=settings.smtp_starttls,
    )
    return {"ok": True}
