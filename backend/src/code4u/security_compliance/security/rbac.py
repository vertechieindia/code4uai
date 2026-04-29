from __future__ import annotations
"""Role-Based Access Control for code4u.ai.

RBAC on Intents - who can refactor what.
Includes RequiresApproval decorator for multi-user approval gates.
"""
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
import hashlib
import time
import structlog

logger = structlog.get_logger("security.rbac")


class Permission(str, Enum):
    """Permissions for code4u.ai operations."""
    # Read operations
    VIEW_CODE = "view_code"
    VIEW_GRAPH = "view_graph"
    VIEW_IMPACT = "view_impact"
    
    # Write operations
    REFACTOR = "refactor"
    RENAME = "rename"
    EXTRACT = "extract"
    DELETE = "delete"
    
    # API operations
    MODIFY_PUBLIC_API = "modify_public_api"
    ADD_API = "add_api"
    DEPRECATE_API = "deprecate_api"
    
    # Schema operations
    MODIFY_SCHEMA = "modify_schema"
    MIGRATE_SCHEMA = "migrate_schema"
    
    # Admin operations
    APPROVE_BREAKING_CHANGE = "approve_breaking_change"
    OVERRIDE_OWNERSHIP = "override_ownership"
    MANAGE_TEAM = "manage_team"


@dataclass
class Role:
    """A role with associated permissions."""
    name: str
    permissions: set[Permission]
    description: str = ""
    
    # Scope restrictions
    allowed_paths: List[str] | None = None  # None = all paths
    allowed_teams: List[str] | None = None


# Predefined roles
PREDEFINED_ROLES = {
    "viewer": Role(
        name="viewer",
        permissions={
            Permission.VIEW_CODE,
            Permission.VIEW_GRAPH,
            Permission.VIEW_IMPACT,
        },
        description="Read-only access"
    ),
    "developer": Role(
        name="developer",
        permissions={
            Permission.VIEW_CODE,
            Permission.VIEW_GRAPH,
            Permission.VIEW_IMPACT,
            Permission.REFACTOR,
            Permission.RENAME,
            Permission.EXTRACT,
        },
        description="Standard developer access"
    ),
    "senior_developer": Role(
        name="senior_developer",
        permissions={
            Permission.VIEW_CODE,
            Permission.VIEW_GRAPH,
            Permission.VIEW_IMPACT,
            Permission.REFACTOR,
            Permission.RENAME,
            Permission.EXTRACT,
            Permission.DELETE,
            Permission.MODIFY_SCHEMA,
        },
        description="Senior developer with schema access"
    ),
    "tech_lead": Role(
        name="tech_lead",
        permissions={
            Permission.VIEW_CODE,
            Permission.VIEW_GRAPH,
            Permission.VIEW_IMPACT,
            Permission.REFACTOR,
            Permission.RENAME,
            Permission.EXTRACT,
            Permission.DELETE,
            Permission.MODIFY_PUBLIC_API,
            Permission.ADD_API,
            Permission.MODIFY_SCHEMA,
            Permission.APPROVE_BREAKING_CHANGE,
        },
        description="Tech lead with API and approval rights"
    ),
    "admin": Role(
        name="admin",
        permissions=set(Permission),  # All permissions
        description="Full administrative access"
    ),
}


@dataclass
class UserPermissions:
    """Permissions for a specific user."""
    user_id: str
    roles: list[Role] = field(default_factory=list)
    direct_permissions: set[Permission] = field(default_factory=set)
    
    # Team membership
    team_ids: List[str] = field(default_factory=list)
    
    @property
    def all_permissions(self) -> set[Permission]:
        """Get all permissions from roles and direct grants."""
        perms = set(self.direct_permissions)
        for role in self.roles:
            perms.update(role.permissions)
        return perms
    
    def has_permission(self, permission: Permission) -> bool:
        return permission in self.all_permissions


class RBACPolicy:
    """
    RBAC policy enforcement.
    
    Controls who can perform what operations.
    """
    
    def __init__(self):
        self._user_permissions: dict[str, UserPermissions] = {}
    
    def set_user_permissions(self, permissions: UserPermissions) -> None:
        """Set permissions for a user."""
        self._user_permissions[permissions.user_id] = permissions
        
        logger.info(
            "user_permissions_set",
            user_id=permissions.user_id,
            roles=[r.name for r in permissions.roles],
            permission_count=len(permissions.all_permissions)
        )
    
    def get_user_permissions(self, user_id: str) -> UserPermissions:
        """Get permissions for a user."""
        return self._user_permissions.get(
            user_id,
            UserPermissions(user_id=user_id)  # Empty permissions
        )
    
    def check_permission(
        self,
        user_id: str,
        permission: Permission,
        context: Dict[str, Any] | None = None
    ) -> tuple[bool, str]:
        """
        Check if user has permission.
        
        Returns (allowed, reason).
        """
        user_perms = self.get_user_permissions(user_id)
        
        if not user_perms.has_permission(permission):
            logger.warning(
                "permission_denied",
                user_id=user_id,
                permission=permission.value
            )
            return False, f"Missing permission: {permission.value}"
        
        # Check path restrictions if context provided
        if context and "file_paths" in context:
            for role in user_perms.roles:
                if role.allowed_paths:
                    for path in context["file_paths"]:
                        if not any(path.startswith(ap) for ap in role.allowed_paths):
                            return False, f"Path not allowed: {path}"
        
        logger.info(
            "permission_granted",
            user_id=user_id,
            permission=permission.value
        )
        
        return True, "Allowed"
    
    def check_intent(
        self,
        user_id: str,
        intent: str,
        is_breaking_change: bool = False,
        file_paths: List[str] | None = None
    ) -> tuple[bool, str]:
        """
        Check if user can perform an intent.
        
        Maps intents to permissions and checks.
        """
        # Map intent to required permission
        intent_permissions = {
            "refactor": Permission.REFACTOR,
            "rename": Permission.RENAME,
            "extract": Permission.EXTRACT,
            "delete": Permission.DELETE,
            "add_api": Permission.ADD_API,
            "modify_api": Permission.MODIFY_PUBLIC_API,
            "migrate_schema": Permission.MIGRATE_SCHEMA,
        }
        
        permission = intent_permissions.get(intent, Permission.REFACTOR)
        
        # Check base permission
        allowed, reason = self.check_permission(
            user_id,
            permission,
            {"file_paths": file_paths} if file_paths else None
        )
        
        if not allowed:
            return False, reason
        
        # Check breaking change approval if needed
        if is_breaking_change:
            allowed, reason = self.check_permission(
                user_id,
                Permission.APPROVE_BREAKING_CHANGE
            )
            if not allowed:
                return False, "Breaking changes require APPROVE_BREAKING_CHANGE permission"
        
        return True, "Allowed"
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a predefined role to a user."""
        role = PREDEFINED_ROLES.get(role_name)
        if not role:
            return False
        
        perms = self._user_permissions.get(
            user_id,
            UserPermissions(user_id=user_id)
        )
        
        if role not in perms.roles:
            perms.roles.append(role)
        
        self._user_permissions[user_id] = perms
        
        logger.info("role_assigned", user_id=user_id, role=role_name)
        return True


# ---------------------------------------------------------------------------
# Approval Gate System
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRequest:
    """Tracks a pending approval for high-risk changes."""
    id: str
    job_id: str
    requested_by: str
    reason: str
    file_count: int
    is_production_critical: bool
    status: str = "pending"  # pending | approved | rejected
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    signature: Optional[str] = None

    def approve(self, approver_id: str) -> None:
        if approver_id == self.requested_by:
            raise PermissionError("Cannot self-approve; a different user must approve")
        self.status = "approved"
        self.approved_by = approver_id
        self.approved_at = time.time()
        self.signature = hashlib.sha256(
            f"{self.id}:{approver_id}:{self.approved_at}".encode()
        ).hexdigest()
        logger.info("approval_granted", approval_id=self.id, approver=approver_id)

    def reject(self, rejector_id: str, reason: str = "") -> None:
        self.status = "rejected"
        self.rejected_by = rejector_id
        self.rejection_reason = reason
        logger.info("approval_rejected", approval_id=self.id, rejector=rejector_id)


class ApprovalGateManager:
    """Manages approval gates for high-risk refactors.

    A refactor requires approval when:
    - The project is marked production-critical AND the change touches >10 files
    - The Sentinel flagged high-risk security findings
    - A breaking change is detected
    """

    FILE_THRESHOLD = 10

    def __init__(self) -> None:
        self._pending: Dict[str, ApprovalRequest] = {}
        self._history: List[ApprovalRequest] = []

    def needs_approval(
        self,
        file_count: int,
        is_production_critical: bool = False,
        is_breaking_change: bool = False,
        sentinel_risk: str = "low",
    ) -> bool:
        if is_production_critical and file_count > self.FILE_THRESHOLD:
            return True
        if is_breaking_change:
            return True
        if sentinel_risk in ("high", "critical"):
            return True
        return False

    def create_request(
        self,
        job_id: str,
        requested_by: str,
        reason: str,
        file_count: int,
        is_production_critical: bool = False,
    ) -> ApprovalRequest:
        req_id = hashlib.sha256(
            f"{job_id}:{requested_by}:{time.time()}".encode()
        ).hexdigest()[:16]

        req = ApprovalRequest(
            id=req_id,
            job_id=job_id,
            requested_by=requested_by,
            reason=reason,
            file_count=file_count,
            is_production_critical=is_production_critical,
        )
        self._pending[req_id] = req
        logger.info("approval_requested", approval_id=req_id, job_id=job_id)
        return req

    def approve(self, approval_id: str, approver_id: str) -> ApprovalRequest:
        req = self._pending.get(approval_id)
        if not req:
            raise ValueError(f"Approval request {approval_id} not found")
        req.approve(approver_id)
        self._history.append(req)
        del self._pending[approval_id]
        return req

    def reject(self, approval_id: str, rejector_id: str, reason: str = "") -> ApprovalRequest:
        req = self._pending.get(approval_id)
        if not req:
            raise ValueError(f"Approval request {approval_id} not found")
        req.reject(rejector_id, reason)
        self._history.append(req)
        del self._pending[approval_id]
        return req

    def get_pending(self) -> List[ApprovalRequest]:
        return list(self._pending.values())

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._pending.get(approval_id) or next(
            (r for r in self._history if r.id == approval_id), None
        )


_approval_manager: Optional[ApprovalGateManager] = None


def get_approval_manager() -> ApprovalGateManager:
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalGateManager()
    return _approval_manager


def requires_approval(
    reason: str = "High-risk change",
    file_threshold: int = 10,
) -> Callable:
    """Decorator that flags operations as requiring multi-user approval.

    When the decorated function returns a result with `file_count` > threshold,
    it injects an approval requirement into the response.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            if isinstance(result, dict):
                fc = result.get("file_count", result.get("fileCount", 0))
                prod_critical = result.get("production_critical", False)
                mgr = get_approval_manager()

                if mgr.needs_approval(
                    file_count=fc,
                    is_production_critical=prod_critical,
                ):
                    result["approval_required"] = True
                    result["approval_reason"] = reason
                    result["approval_threshold"] = file_threshold
                    logger.info(
                        "approval_gate_triggered",
                        file_count=fc,
                        reason=reason,
                    )

            return result
        return wrapper
    return decorator

