from __future__ import annotations
"""Authentication routes: register, login, token refresh, user info, OAuth."""
import os
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from code4u.interfaces.api.deps import get_auth_manager, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory store for linked GitHub accounts: user_id → github_info
_github_tokens: Dict[str, Dict[str, Any]] = {}

# GitHub SSO CSRF state → unix timestamp (dev; use Redis for multi-instance)
_github_sso_states: Dict[str, float] = {}
_GITHUB_SSO_STATE_TTL_SEC = 600.0


def _cleanup_github_sso_states() -> None:
    now = time.time()
    expired = [k for k, t in _github_sso_states.items() if now - t > _GITHUB_SSO_STATE_TTL_SEC]
    for k in expired:
        del _github_sso_states[k]


# Google OAuth CSRF state → unix timestamp (dev; use Redis for multi-instance)
_google_oauth_states: Dict[str, float] = {}
_GOOGLE_STATE_TTL_SEC = 600.0


def _cleanup_google_oauth_states() -> None:
    now = time.time()
    expired = [k for k, t in _google_oauth_states.items() if now - t > _GOOGLE_STATE_TTL_SEC]
    for k in expired:
        del _google_oauth_states[k]


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""
    company: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    tenant_id: str
    name: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    company: str
    tenant_id: str


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, request: Request):
    from code4u.interfaces.api.deps import _auth_manager
    auth = _auth_manager()
    try:
        user = auth.register(
            email=body.email,
            password=body.password,
            name=body.name,
            company=body.company,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Email already registered")

    token = auth.authenticate(body.email, body.password)
    return AuthResponse(
        token=token,
        user_id=user.user_id,
        email=user.email,
        tenant_id=user.tenant_id,
        name=user.name,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request):
    from code4u.interfaces.api.deps import _auth_manager
    auth = _auth_manager()
    token = auth.authenticate(body.email, body.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = auth.get_user_by_email(body.email)
    return AuthResponse(
        token=token,
        user_id=user.user_id,
        email=user.email,
        tenant_id=user.tenant_id,
        name=user.name,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    from code4u.interfaces.api.deps import _auth_manager
    auth = _auth_manager()
    user = auth.get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        company=user.company,
        tenant_id=user.tenant_id,
    )


# ---------------------------------------------------------------------------
# Google OAuth (Sign in with Google → app JWT)
# ---------------------------------------------------------------------------


@router.get("/google/login")
async def google_oauth_login():
    """Redirect browser to Google's consent screen."""
    from code4u.core.config import get_settings

    settings = get_settings()
    cid = (settings.google_client_id or "").strip()
    secret = settings.google_client_secret.get_secret_value() or ""
    if not cid or not secret:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )

    _cleanup_google_oauth_states()
    state = secrets.token_urlsafe(32)
    _google_oauth_states[state] = time.time()

    params = {
        "client_id": cid,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback")
async def google_oauth_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
):
    """Exchange authorization code, upsert user, redirect to SPA with JWT in URL fragment."""
    from code4u.core.config import get_settings

    settings = get_settings()
    success_base = (settings.google_oauth_success_redirect or "http://localhost:3000/login").rstrip(
        "#"
    )

    def _fail_redirect(msg: str) -> RedirectResponse:
        return RedirectResponse(
            url=f"{success_base}?oauth_error={quote(msg, safe='')}",
            status_code=302,
        )

    if error:
        return _fail_redirect(error_description or error)
    if not code or not state:
        return _fail_redirect("missing_code_or_state")

    _cleanup_google_oauth_states()
    if state not in _google_oauth_states:
        return _fail_redirect("invalid_or_expired_state")
    del _google_oauth_states[state]

    cid = (settings.google_client_id or "").strip()
    secret = settings.google_client_secret.get_secret_value() or ""
    if not cid or not secret:
        return _fail_redirect("google_not_configured")

    token_body = {
        "code": code,
        "client_id": cid,
        "client_secret": secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data=token_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20.0,
        )

    if token_res.status_code != 200:
        return _fail_redirect("token_exchange_failed")

    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        err = token_data.get("error_description", token_data.get("error", "no_access_token"))
        return _fail_redirect(str(err))

    async with httpx.AsyncClient() as client:
        user_res = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )

    if user_res.status_code != 200:
        return _fail_redirect("userinfo_failed")

    profile = user_res.json()
    if not profile.get("email_verified", False):
        return _fail_redirect("email_not_verified")

    email = (profile.get("email") or "").strip().lower()
    if not email:
        return _fail_redirect("no_email")

    name = (profile.get("name") or "").strip() or email.split("@", 1)[0]

    from code4u.interfaces.api.deps import _auth_manager

    auth = _auth_manager()
    try:
        user = auth.get_or_create_oauth_user(email=email, name=name)
    except ValueError as e:
        if "email_already_registered" in str(e).lower() or "already" in str(e).lower():
            return _fail_redirect("registration_conflict")
        return _fail_redirect(str(e))

    jwt_token = auth.mint_token_for_user(user)
    # Fragment avoids sending JWT to server logs on navigation; frontend strips it immediately.
    return RedirectResponse(url=f"{success_base}#c4u_token={jwt_token}", status_code=302)


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

@router.get("/github/login")
async def github_oauth_login(flow: str = ""):
    """Start GitHub OAuth.

    - ``?flow=sso`` — browser redirect for Sign in with GitHub (JWT + redirect to SPA login).
    - default — JSON ``{ url, clientId }`` for Connect Repo (``state=code4u``, includes ``repo`` scope).
    """
    from code4u.core.config import get_settings

    settings = get_settings()
    client_id = (settings.github_client_id or "").strip()
    client_secret = settings.github_client_secret.get_secret_value() or ""

    if not client_id:
        raise HTTPException(
            status_code=501,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID in .env",
        )

    if flow.strip().lower() == "sso":
        if not client_secret:
            raise HTTPException(
                status_code=501,
                detail="GitHub SSO requires GITHUB_CLIENT_SECRET in .env",
            )
        _cleanup_github_sso_states()
        state = secrets.token_urlsafe(32)
        _github_sso_states[state] = time.time()
        scope = "read:user user:email"
        params = {
            "client_id": client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": scope,
            "state": state,
        }
        gh_url = "https://github.com/login/oauth/authorize?" + urlencode(params)
        return RedirectResponse(url=gh_url, status_code=302)

    scope = "repo read:user user:email"
    gh_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope={scope}"
        f"&state=code4u"
    )
    return {"url": gh_url, "clientId": client_id}


async def _github_exchange_code(settings, code: str) -> tuple[str, dict]:
    """Return (access_token, token_json) or raise HTTPException."""
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret.get_secret_value(),
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )

    if token_res.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to exchange code with GitHub")

    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        err = token_data.get("error_description", token_data.get("error", "Unknown"))
        raise HTTPException(status_code=400, detail=f"GitHub token error: {err}")
    return access_token, token_data


@router.get("/github/callback")
async def github_oauth_callback(code: str = "", state: str = "", error: str = ""):
    """GitHub OAuth callback: SSO (``state`` server-issued) or Connect Repo (``state=code4u``)."""
    from code4u.core.config import get_settings

    settings = get_settings()
    success_base = (
        settings.github_oauth_success_redirect or settings.google_oauth_success_redirect
    ).rstrip("#")

    def _sso_fail(msg: str) -> RedirectResponse:
        return RedirectResponse(
            url=f"{success_base}?oauth_error={quote(msg, safe='')}",
            status_code=302,
        )

    is_sso = state in _github_sso_states

    if error:
        if is_sso:
            del _github_sso_states[state]
            return _sso_fail(error)
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {error}")
    if not code:
        if is_sso and state in _github_sso_states:
            del _github_sso_states[state]
            return _sso_fail("missing_code")
        raise HTTPException(status_code=400, detail="Missing authorization code")

    if is_sso:
        del _github_sso_states[state]
        if not settings.github_client_secret.get_secret_value():
            return _sso_fail("github_secret_not_configured")

        try:
            access_token, token_data = await _github_exchange_code(settings, code)
        except HTTPException as e:
            return _sso_fail(e.detail if isinstance(e.detail, str) else "token_exchange_failed")

        async with httpx.AsyncClient() as client:
            user_res = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
            emails_res = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )

        if user_res.status_code != 200:
            return _sso_fail("github_user_failed")

        gh_user = user_res.json()
        email_pick = ""
        if emails_res.status_code == 200:
            for row in emails_res.json():
                if row.get("primary") and row.get("verified"):
                    email_pick = (row.get("email") or "").strip().lower()
                    break
            if not email_pick:
                for row in emails_res.json():
                    if row.get("verified"):
                        email_pick = (row.get("email") or "").strip().lower()
                        break
        if not email_pick and gh_user.get("email"):
            email_pick = str(gh_user.get("email", "")).strip().lower()
        if not email_pick:
            return _sso_fail("no_verified_email")

        name = (gh_user.get("name") or "").strip() or str(gh_user.get("login") or "").strip()
        if not name:
            name = email_pick.split("@", 1)[0]

        from code4u.interfaces.api.deps import _auth_manager

        auth = _auth_manager()
        try:
            user = auth.get_or_create_oauth_user(email=email_pick, name=name)
        except ValueError as e:
            return _sso_fail(str(e))

        jwt_token = auth.mint_token_for_user(user)
        return RedirectResponse(url=f"{success_base}#c4u_token={jwt_token}", status_code=302)

    # ── Legacy: Connect Repo (state must be code4u) ─────────────────
    if state != "code4u":
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    access_token, token_data = await _github_exchange_code(settings, code)

    async with httpx.AsyncClient() as client:
        user_res = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )

    if user_res.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub user info")

    gh_user = user_res.json()
    github_info = {
        "access_token": access_token,
        "github_username": gh_user.get("login", ""),
        "github_id": gh_user.get("id"),
        "avatar_url": gh_user.get("avatar_url", ""),
        "name": gh_user.get("name", ""),
        "email": gh_user.get("email", ""),
        "token_scope": token_data.get("scope", ""),
    }

    _github_tokens["__latest__"] = github_info

    return {
        "status": "connected",
        "github_username": github_info["github_username"],
        "avatar_url": github_info["avatar_url"],
        "name": github_info["name"],
        "scope": github_info["token_scope"],
    }


@router.post("/github/link")
async def link_github_to_user(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Link a previously obtained GitHub token to the current user."""
    latest = _github_tokens.get("__latest__")
    if not latest:
        raise HTTPException(status_code=400, detail="No GitHub token available. Complete OAuth first.")

    user_id = current_user.get("sub", "")
    _github_tokens[user_id] = latest
    return {
        "status": "linked",
        "user_id": user_id,
        "github_username": latest["github_username"],
    }


@router.get("/github/status")
async def github_status(current_user: dict = Depends(get_current_user)):
    """Check if the current user has a linked GitHub account."""
    user_id = current_user.get("sub", "")
    info = _github_tokens.get(user_id) or _github_tokens.get("__latest__")
    if not info:
        return {"connected": False}
    return {
        "connected": True,
        "github_username": info.get("github_username", ""),
        "avatar_url": info.get("avatar_url", ""),
        "name": info.get("name", ""),
    }


@router.get("/github/repos")
async def list_github_repos(
    current_user: dict = Depends(get_current_user),
    page: int = 1,
    per_page: int = 30,
):
    """List the authenticated user's GitHub repositories."""
    user_id = current_user.get("sub", "")
    info = _github_tokens.get(user_id) or _github_tokens.get("__latest__")
    if not info or not info.get("access_token"):
        raise HTTPException(status_code=401, detail="GitHub not connected")

    import httpx

    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.github.com/user/repos",
            params={
                "sort": "updated",
                "direction": "desc",
                "per_page": per_page,
                "page": page,
                "type": "all",
            },
            headers={
                "Authorization": f"Bearer {info['access_token']}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15,
        )

    if res.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to list GitHub repos")

    repos = res.json()
    return {
        "repos": [
            {
                "name": r.get("name", ""),
                "full_name": r.get("full_name", ""),
                "owner": r.get("owner", {}).get("login", ""),
                "private": r.get("private", False),
                "clone_url": r.get("clone_url", ""),
                "html_url": r.get("html_url", ""),
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "stars": r.get("stargazers_count", 0),
                "updated_at": r.get("updated_at", ""),
                "default_branch": r.get("default_branch", "main"),
            }
            for r in repos
        ],
        "page": page,
        "per_page": per_page,
    }


def get_github_token(user_id: str = "") -> Optional[str]:
    """Utility to get GitHub token for a user (used by other modules)."""
    info = _github_tokens.get(user_id) or _github_tokens.get("__latest__")
    if info:
        return info.get("access_token")
    return os.environ.get("CODE4U_GITHUB_TOKEN")
