from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class OAuthStartRecord:
    code_verifier: str
    created_at: float


@dataclass
class OAuthTicketRecord:
    access_token: str
    refresh_token: str
    expires_in: int | None
    user_payload: dict[str, Any]
    created_at: float


_lock = threading.Lock()
_oauth_starts: dict[str, OAuthStartRecord] = {}
_oauth_tickets: dict[str, OAuthTicketRecord] = {}

_START_TTL_SEC = 600
_TICKET_TTL_SEC = 120


def _purge_locked(now: float) -> None:
    expired_starts = [k for k, v in _oauth_starts.items() if now - v.created_at > _START_TTL_SEC]
    for k in expired_starts:
        _oauth_starts.pop(k, None)
    expired_tickets = [k for k, v in _oauth_tickets.items() if now - v.created_at > _TICKET_TTL_SEC]
    for k in expired_tickets:
        _oauth_tickets.pop(k, None)


def save_oauth_start(state: str, code_verifier: str) -> None:
    now = time.time()
    with _lock:
        _purge_locked(now)
        _oauth_starts[state] = OAuthStartRecord(code_verifier=code_verifier, created_at=now)


def pop_oauth_start(state: str) -> OAuthStartRecord | None:
    now = time.time()
    with _lock:
        _purge_locked(now)
        return _oauth_starts.pop(state, None)


def create_oauth_ticket(
    *,
    access_token: str,
    refresh_token: str,
    expires_in: int | None,
    user_payload: dict[str, Any],
) -> str:
    ticket = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        _purge_locked(now)
        _oauth_tickets[ticket] = OAuthTicketRecord(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user_payload=user_payload,
            created_at=now,
        )
    return ticket


def pop_oauth_ticket(ticket: str) -> OAuthTicketRecord | None:
    now = time.time()
    with _lock:
        _purge_locked(now)
        return _oauth_tickets.pop(ticket, None)
