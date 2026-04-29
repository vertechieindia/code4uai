"""Admin API — recipe governance and global configuration.

Endpoints:
  - ``GET  /admin/recipes``             — list all recipes with status.
  - ``PATCH /admin/recipes/{id}/toggle`` — enable/disable a recipe globally.
  - ``GET  /admin/recipes/disabled``     — list disabled recipe IDs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger("admin")

router = APIRouter()

_DISABLED_FILE = Path.home() / ".code4u" / "disabled_recipes.json"


# ---------------------------------------------------------------------------
# Disabled recipe registry (persisted to disk)
# ---------------------------------------------------------------------------

def _load_disabled() -> Set[str]:
    """Load the set of globally disabled recipe IDs."""
    if not _DISABLED_FILE.is_file():
        return set()
    try:
        data = json.loads(_DISABLED_FILE.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()


def _save_disabled(disabled: Set[str]) -> None:
    """Persist the disabled set to disk."""
    _DISABLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DISABLED_FILE.write_text(
        json.dumps(sorted(disabled), indent=2),
        encoding="utf-8",
    )


def is_recipe_disabled(recipe_id: str) -> bool:
    """Check if a recipe is globally disabled."""
    return recipe_id in _load_disabled()


def get_disabled_recipes() -> Set[str]:
    """Return the full set of disabled recipe IDs."""
    return _load_disabled()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ToggleRequest(BaseModel):
    enabled: bool = Field(..., description="True to enable, False to disable.")


# ---------------------------------------------------------------------------
# PATCH /admin/recipes/{id}/toggle
# ---------------------------------------------------------------------------

@router.patch("/admin/recipes/{recipe_id}/toggle")
async def toggle_recipe(recipe_id: str, request: ToggleRequest):
    """Enable or disable a recipe globally for all automated PR reviews.

    When disabled, the recipe will be skipped by the GitHubReviewer
    even if it's present in the YAML files.  The YAML file itself
    is not modified — the toggle is stored centrally.
    """
    disabled = _load_disabled()

    if request.enabled:
        disabled.discard(recipe_id)
        action = "enabled"
    else:
        disabled.add(recipe_id)
        action = "disabled"

    _save_disabled(disabled)

    logger.info("recipe_toggled", recipe_id=recipe_id, action=action)

    return {
        "recipeId": recipe_id,
        "enabled": request.enabled,
        "action": action,
        "totalDisabled": len(disabled),
    }


# ---------------------------------------------------------------------------
# GET /admin/recipes
# ---------------------------------------------------------------------------

@router.get("/admin/recipes")
async def list_recipes_with_status(workspacePath: Optional[str] = None):
    """List all recipes with their enabled/disabled status."""
    from code4u.core.recipes import RecipeRegistry

    registry = RecipeRegistry(workspace_path=workspacePath or ".")
    registry.load()

    disabled = _load_disabled()
    recipes = registry.list_recipes()

    return {
        "recipes": [
            {
                **r.summary(),
                "enabled": r.id not in disabled,
            }
            for r in recipes
        ],
        "totalDisabled": len(disabled),
    }


# ---------------------------------------------------------------------------
# GET /admin/recipes/disabled
# ---------------------------------------------------------------------------

@router.get("/admin/recipes/disabled")
async def list_disabled_recipes():
    """Return the list of globally disabled recipe IDs."""
    disabled = _load_disabled()
    return {
        "disabled": sorted(disabled),
        "count": len(disabled),
    }
