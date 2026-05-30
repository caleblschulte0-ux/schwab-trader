"""Shared Schwab session helpers: token persistence + authenticated client.

The schwab-trader library handles the OAuth mechanics (building the auth URL,
exchanging the code, refreshing the access token), but it keeps tokens in
memory only. This module adds the missing piece: it saves tokens to a
token.json file and loads them back, so you authenticate once and reuse the
session across runs.

How Schwab's tokens work:
  * access_token  -> short-lived (~30 minutes). Used on every API call.
  * refresh_token -> long-lived (~7 days). Used to silently mint new access
                     tokens. After ~7 days you must log in through the browser
                     again (run auth_setup.py).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from schwab import SchwabAuth, SchwabClient

from config import Settings, load_settings


def _save_tokens(auth: SchwabAuth, token_path: str) -> None:
    """Write the current tokens to disk as JSON."""
    expiry = auth.token_expiry
    data = {
        "access_token": auth.access_token,
        "refresh_token": auth.refresh_token,
        "token_expiry": expiry.isoformat() if expiry else None,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    # Write atomically-ish, then lock down permissions (owner read/write only).
    with open(token_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass  # e.g. on filesystems that don't support chmod


def _load_tokens(auth: SchwabAuth, token_path: str) -> bool:
    """Load tokens from disk into the auth object. Returns True if found."""
    if not os.path.exists(token_path):
        return False
    with open(token_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    auth.access_token = data.get("access_token")
    auth.refresh_token = data.get("refresh_token")
    expiry = data.get("token_expiry")
    if expiry:
        parsed = datetime.fromisoformat(expiry)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        auth.token_expiry = parsed
    return auth.access_token is not None


def _wrap_token_saving(auth: SchwabAuth, token_path: str) -> None:
    """Patch the auth object so any token update is also saved to disk.

    The library refreshes the access token automatically inside
    ensure_valid_token(); by wrapping the internal _update_tokens hook we make
    sure that refreshed tokens get persisted without any extra calls.
    """
    original_update = auth._update_tokens

    def update_and_save(token_data):
        original_update(token_data)
        _save_tokens(auth, token_path)

    auth._update_tokens = update_and_save  # type: ignore[method-assign]


def build_auth(settings: Optional[Settings] = None) -> SchwabAuth:
    """Create a SchwabAuth wired up for on-disk token persistence."""
    settings = settings or load_settings()
    auth = SchwabAuth(
        client_id=settings.app_key,
        client_secret=settings.app_secret,
        redirect_uri=settings.callback_url,
    )
    _wrap_token_saving(auth, settings.token_path)
    return auth


def save_tokens(auth: SchwabAuth, settings: Optional[Settings] = None) -> None:
    """Public helper to persist the current tokens (used by auth_setup.py)."""
    settings = settings or load_settings()
    _save_tokens(auth, settings.token_path)


def get_client(settings: Optional[Settings] = None) -> SchwabClient:
    """Return an authenticated SchwabClient, loading cached tokens from disk.

    Raises a friendly error if you haven't run the one-time browser login yet.
    """
    settings = settings or load_settings()
    auth = build_auth(settings)

    if not _load_tokens(auth, settings.token_path):
        raise RuntimeError(
            f"No saved tokens found at {settings.token_path!r}. "
            "Run `python auth_setup.py` first to log in."
        )

    # Proactively refresh if the access token is stale. If the refresh token
    # itself has expired (~7 days), this raises and you must re-run auth_setup.
    try:
        auth.ensure_valid_token()
    except Exception as exc:  # noqa: BLE001 - surface a clear next step
        raise RuntimeError(
            "Could not refresh your access token (the refresh token may have "
            "expired after ~7 days). Run `python auth_setup.py` to log in again.\n"
            f"Original error: {exc}"
        ) from exc

    return SchwabClient(
        client_id=settings.app_key,
        client_secret=settings.app_secret,
        redirect_uri=settings.callback_url,
        auth=auth,
    )
