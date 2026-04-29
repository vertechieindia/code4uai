from __future__ import annotations
"""Identity management: password hashing, JWT tokens, user store, secret providers.

Uses passlib (bcrypt) for password security and python-jose (HS256) for JWTs.
The user store is in-memory for development; swap for a DB adapter in production.

Secret providers:
  - ``EnvSecretProvider``   — reads from environment variables (default).
  - ``VaultSecretProvider`` — reads from HashiCorp Vault (mock for now).
  - ``AWSSecretProvider``   — reads from AWS Secrets Manager (mock for now).
"""
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = structlog.get_logger("auth.manager")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


# ---------------------------------------------------------------------------
# Secret Provider abstraction
# ---------------------------------------------------------------------------

class SecretProvider(ABC):
    """Interface for fetching secrets from different backends."""

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...


class EnvSecretProvider(SecretProvider):
    """Reads secrets from environment variables.

    Maps logical key names to env vars:
      ``jwt_secret`` -> ``CODE4U_JWT_SECRET``
      ``github_token`` -> ``GITHUB_TOKEN``
    """

    _PREFIX = "CODE4U_"

    _KEY_MAP: Dict[str, str] = {
        "jwt_secret": "CODE4U_JWT_SECRET",
        "github_token": "GITHUB_TOKEN",
        "github_client_id": "GITHUB_CLIENT_ID",
        "github_client_secret": "GITHUB_CLIENT_SECRET",
        "slack_webhook_url": "SLACK_WEBHOOK_URL",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "database_url": "DATABASE_URL",
        "redis_url": "REDIS_URL",
    }

    def get_secret(self, key: str) -> Optional[str]:
        env_key = self._KEY_MAP.get(key, f"{self._PREFIX}{key.upper()}")
        value = os.environ.get(env_key)
        if value:
            logger.debug("secret_resolved", key=key, provider="env")
        return value

    def provider_name(self) -> str:
        return "env"


class VaultSecretProvider(SecretProvider):
    """Mock HashiCorp Vault integration.

    In production, this would use ``hvac`` to talk to a real Vault instance.
    """

    def __init__(
        self,
        vault_addr: str = "",
        vault_token: str = "",
        mount_path: str = "secret/data/code4u",
    ):
        self._addr = vault_addr or os.environ.get("VAULT_ADDR", "")
        self._token = vault_token or os.environ.get("VAULT_TOKEN", "")
        self._mount = mount_path
        self._cache: Dict[str, str] = {}

    def get_secret(self, key: str) -> Optional[str]:
        if key in self._cache:
            return self._cache[key]

        if not self._addr:
            logger.debug("vault_not_configured", key=key)
            return None

        # In production: hvac.Client(url=self._addr, token=self._token)
        #   .secrets.kv.v2.read_secret_version(path="code4u")[key]
        logger.info("vault_secret_fetch", key=key, addr=self._addr)
        return None

    def provider_name(self) -> str:
        return "vault"


class AWSSecretProvider(SecretProvider):
    """Mock AWS Secrets Manager integration.

    In production, this would use ``boto3`` to fetch from AWS SM.
    """

    def __init__(self, region: str = "", secret_id: str = "code4u/secrets"):
        self._region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._secret_id = secret_id
        self._cache: Dict[str, str] = {}

    def get_secret(self, key: str) -> Optional[str]:
        if key in self._cache:
            return self._cache[key]

        # In production: boto3.client("secretsmanager", region_name=self._region)
        #   .get_secret_value(SecretId=self._secret_id)["SecretString"][key]
        logger.info("aws_sm_secret_fetch", key=key, region=self._region)
        return None

    def provider_name(self) -> str:
        return "aws"


class ChainedSecretProvider(SecretProvider):
    """Tries multiple providers in order until one returns a value."""

    def __init__(self, providers: list[SecretProvider]):
        self._providers = providers

    def get_secret(self, key: str) -> Optional[str]:
        for p in self._providers:
            val = p.get_secret(key)
            if val is not None:
                logger.info("secret_resolved", key=key, provider=p.provider_name())
                return val
        logger.warning("secret_not_found", key=key)
        return None

    def provider_name(self) -> str:
        return "chained"


def create_secret_provider() -> SecretProvider:
    """Factory: build the appropriate secret provider chain from environment.

    Priority: Vault > AWS SM > Environment variables.
    """
    providers: list[SecretProvider] = []

    if os.environ.get("VAULT_ADDR"):
        providers.append(VaultSecretProvider())

    if os.environ.get("AWS_SECRET_ID") or os.environ.get("AWS_REGION"):
        providers.append(AWSSecretProvider())

    providers.append(EnvSecretProvider())

    if len(providers) == 1:
        return providers[0]
    return ChainedSecretProvider(providers)


@dataclass
class UserRecord:
    user_id: str
    email: str
    hashed_password: str
    name: str = ""
    company: str = ""
    tenant_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_active: bool = True


class JWTManager:
    """Sign and verify HS256 JSON Web Tokens."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self._secret = secret_key
        self._algorithm = algorithm

    def create_token(
        self,
        data: Dict[str, str],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        to_encode: dict = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=DEFAULT_TOKEN_EXPIRE_MINUTES))
        to_encode["exp"] = expire
        return jwt.encode(to_encode, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> Optional[Dict[str, str]]:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
            return payload
        except JWTError:
            logger.warning("jwt_decode_failed")
            return None


class AuthManager:
    """Manages user registration, login, and token lifecycle.

    In-memory store for dev; production would use SQLAlchemy / asyncpg.
    Secrets are resolved through the ``SecretProvider`` chain so that
    JWT signing keys, API tokens, and other credentials are never
    hardcoded or stored in plain .env files in production.
    """

    def __init__(self, jwt_secret: str = "", secret_provider: Optional[SecretProvider] = None):
        self._secret_provider = secret_provider or create_secret_provider()

        # Resolve JWT secret: explicit arg > provider > fallback
        resolved_secret = jwt_secret
        if not resolved_secret:
            resolved_secret = self._secret_provider.get_secret("jwt_secret") or ""
        if not resolved_secret:
            resolved_secret = "code4u-dev-secret-change-in-production"
            logger.warning("using_fallback_jwt_secret")

        self._jwt = JWTManager(resolved_secret)
        self._users: Dict[str, UserRecord] = {}  # email -> UserRecord
        logger.info(
            "auth_manager_initialised",
            secret_provider=self._secret_provider.provider_name(),
        )

    def get_secret(self, key: str) -> Optional[str]:
        """Expose the provider chain for other services that need secrets."""
        return self._secret_provider.get_secret(key)

    # ── Registration ──────────────────────────────────────────────

    def register(
        self,
        email: str,
        password: str,
        name: str = "",
        company: str = "",
    ) -> UserRecord:
        if email in self._users:
            raise ValueError("email_already_registered")

        user = UserRecord(
            user_id=str(uuid.uuid4()),
            email=email,
            hashed_password=pwd_context.hash(password),
            name=name,
            company=company,
            tenant_id=f"tenant_{uuid.uuid4().hex[:8]}",
        )
        self._users[email] = user
        logger.info("user_registered", email=email, tenant_id=user.tenant_id)
        return user

    # ── Login ─────────────────────────────────────────────────────

    def authenticate(self, email: str, password: str) -> Optional[str]:
        """Validate credentials and return a signed JWT, or None."""
        user = self._users.get(email)
        if not user or not pwd_context.verify(password, user.hashed_password):
            logger.warning("auth_failed", email=email)
            return None

        token = self._jwt.create_token({
            "sub": user.user_id,
            "email": user.email,
            "tenant_id": user.tenant_id,
        })
        logger.info("auth_success", email=email)
        return token

    # ── Token verification ────────────────────────────────────────

    def verify_token(self, token: str) -> Optional[Dict[str, str]]:
        return self._jwt.decode_token(token)

    # ── Lookup ────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        return self._users.get(email)

    def get_user_by_id(self, user_id: str) -> Optional[UserRecord]:
        for u in self._users.values():
            if u.user_id == user_id:
                return u
        return None
