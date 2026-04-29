from __future__ import annotations
"""Core utilities for code4u.ai backend."""
from code4u.core.config import Settings, get_settings
from code4u.core.logging import configure_logging, get_logger
from code4u.core.recipes import Recipe, RecipeRegistry, RecipeSelector
from code4u.core.watcher import WorkspaceWatcher, PartialReindexJob
from code4u.core.presence import PresenceManager, get_presence_manager, FileLockedError
from code4u.core.staging import StagingArea, StagedChange, get_staging_area
from code4u.core.nexus import NexusContext, GlobalRegistry, RepoInfo, ExternalEdge
__all__ = [
    "Settings", "get_settings", "configure_logging", "get_logger",
    "Recipe", "RecipeRegistry", "RecipeSelector",
    "WorkspaceWatcher", "PartialReindexJob",
    "PresenceManager", "get_presence_manager", "FileLockedError",
    "StagingArea", "StagedChange", "get_staging_area",
    "NexusContext", "GlobalRegistry", "RepoInfo", "ExternalEdge",
]

