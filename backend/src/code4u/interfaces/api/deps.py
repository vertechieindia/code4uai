from __future__ import annotations
"""Shared FastAPI dependencies: auth manager singleton, current-user extractor."""
from functools import lru_cache
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from code4u.core.config import get_settings
from code4u.security_compliance.auth.manager import AuthManager

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache()
def _auth_manager() -> AuthManager:
    settings = get_settings()
    return AuthManager(
        jwt_secret=settings.jwt_secret_key.get_secret_value(),
        database_url=settings.database_url,
        use_postgres=settings.auth_persist_users,
    )


def get_auth_manager() -> AuthManager:
    return _auth_manager()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Dict[str, str]:
    """Extract and validate the JWT from the Authorization header.

    Returns the decoded payload dict containing sub, email, tenant_id.
    Raises 401 if missing or invalid.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth = _auth_manager()
    payload = auth.verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload
