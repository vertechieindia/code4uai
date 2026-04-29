from __future__ import annotations
"""Authentication routes: register, login, token refresh, user info, OAuth."""
import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from code4u.interfaces.api.deps import get_auth_manager, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory store for linked GitHub accounts: user_id → github_info
_github_tokens: Dict[str, Dict[str, Any]] = {}


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
# GitHub OAuth
# ---------------------------------------------------------------------------

@router.get("/github/login")
async def github_oauth_login():
    """Redirect the user to GitHub's OAuth authorization page."""
    from code4u.core.config import get_settings
    settings = get_settings()
    client_id = settings.github_client_id

    if not client_id:
        raise HTTPException(
            status_code=501,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID in .env",
        )

    scope = "repo read:user user:email"
    gh_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope={scope}"
        f"&state=code4u"
    )
    return {"url": gh_url, "clientId": client_id}


@router.get("/github/callback")
async def github_oauth_callback(code: str = "", state: str = "", error: str = ""):
    """Exchange the GitHub authorization code for an access token."""
    if error:
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    from code4u.core.config import get_settings
    settings = get_settings()

    import httpx

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
