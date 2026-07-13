from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def _tls_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _build_sender() -> str:
    from_name = settings.smtp_from_name.strip() if settings.smtp_from_name else "ZenU"
    from_email = settings.smtp_from_email or ""
    if from_name:
        return f"{from_name} <{from_email}>"
    return from_email


def _smtp_login_password() -> str:
    # Gmail app passwords are often shown/pasted with spaces every 4 chars.
    # Normalizing here avoids subtle auth failures.
    return (settings.smtp_password or "").replace(" ", "").strip()


def verify_smtp_connection() -> dict:
    if not settings.smtp_configured:
        return {
            "ok": False,
            "configured": False,
            "message": "SMTP is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_FROM_EMAIL and credentials if required.",
        }

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_use_tls:
                server.starttls(context=_tls_context())
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, _smtp_login_password())

        return {
            "ok": True,
            "configured": True,
            "message": "SMTP connection verified",
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "tls": settings.smtp_use_tls,
        }
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "message": f"SMTP verification failed: {exc}",
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "tls": settings.smtp_use_tls,
        }


def send_password_reset_email(to_email: str, reset_url: str):
    msg = EmailMessage()
    msg["Subject"] = "Reset your ZenU password"
    msg["From"] = _build_sender()
    msg["To"] = to_email

    text_body = (
        "We received a request to reset your ZenU password.\n\n"
        f"Reset your password: {reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )

    html_body = f"""
    <html>
      <body style=\"font-family: Arial, sans-serif; line-height: 1.6;\">
        <h2>Reset your ZenU password</h2>
        <p>We received a request to reset your ZenU password.</p>
        <p>
          <a href=\"{reset_url}\" style=\"display:inline-block;padding:10px 14px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;\">
            Reset Password
          </a>
        </p>
        <p>If you didn't request this, you can safely ignore this email.</p>
      </body>
    </html>
    """.strip()

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.ehlo()
        if settings.smtp_use_tls:
            server.starttls(context=_tls_context())
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, _smtp_login_password())
        server.send_message(msg)
