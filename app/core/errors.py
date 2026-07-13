from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(self, message: str, status: int = 500, details: Any | None = None):
        self.message = message
        self.status = status
        self.details = details
        super().__init__(message)
