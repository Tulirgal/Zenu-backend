from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    node_env: str = os.getenv("NODE_ENV", "development")
    port: int = int(os.getenv("PORT", "3001"))
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    cookie_domain: str | None = os.getenv("COOKIE_DOMAIN") or None
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    access_token_cookie_name: str = os.getenv("ACCESS_TOKEN_COOKIE_NAME", "sb-access-token")
    refresh_token_cookie_name: str = os.getenv("REFRESH_TOKEN_COOKIE_NAME", "sb-refresh-token")
    frontend_url: str = os.getenv("FRONTEND_URL", "")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    status_debug_key: str | None = os.getenv("STATUS_DEBUG_KEY") or None
    smtp_host: str | None = os.getenv("SMTP_HOST") or None
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME") or None
    smtp_password: str | None = os.getenv("SMTP_PASSWORD") or None
    smtp_from_email: str | None = os.getenv("SMTP_FROM_EMAIL") or None
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME", "ZenU")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
    reset_password_url_base: str | None = os.getenv("RESET_PASSWORD_URL_BASE") or None
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID") or None
    google_client_secret: str | None = os.getenv("GOOGLE_CLIENT_SECRET") or None
    # Optional explicit override. Default: {request.base_url}api/auth/callback
    google_redirect_uri: str | None = os.getenv("GOOGLE_REDIRECT_URI") or None

    @property
    def is_production(self) -> bool:
        return self.node_env == "production"

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def frontend_origins(self) -> list[str]:
        if not self.frontend_url:
            return []
        return [
            item.strip().rstrip("/")
            for item in self.frontend_url.split(",")
            if item.strip()
        ]

    @property
    def smtp_configured(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_port > 0
            and self.smtp_from_email
            and (not self.smtp_username or self.smtp_password)
        )


settings = Settings()
