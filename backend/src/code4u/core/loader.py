"""Dynamic Plugin Loader — discovers and loads custom agents at runtime.

Scans these directories for ``.py`` files containing subclasses of
``AbstractAgent``:

  1. ``~/.code4u/plugins/``      — user-global plugins.
  2. ``<workspace>/.code4u/plugins/`` — project-local plugins.

Project-local plugins override global ones with the same ``name``.

Usage::

    from code4u.core.loader import PluginLoader

    loader = PluginLoader()
    agents = loader.discover()
    for agent in agents:
        print(agent.manifest.name, agent.manifest.icon)

    # Register all into a SwarmController:
    loader.register_into(controller)
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import structlog

from code4u.agents.base import AbstractAgent, AgentManifest

logger = structlog.get_logger("plugin_loader")


# ---------------------------------------------------------------------------
# Marketplace manifest schema
# ---------------------------------------------------------------------------

MARKETPLACE_MANIFEST_KEYS = {
    "name", "version", "description", "author", "agents", "recipes",
}


def parse_marketplace_manifest(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a marketplace manifest.json."""
    result: Dict[str, Any] = {
        "name": data.get("name", "unnamed"),
        "version": data.get("version", "0.0.0"),
        "description": data.get("description", ""),
        "author": data.get("author", ""),
        "agents": data.get("agents", []),
        "recipes": data.get("recipes", []),
        "valid": True,
    }

    if not result["name"] or not isinstance(result["name"], str):
        result["valid"] = False
        result["error"] = "Missing or invalid 'name'"

    return result


# ---------------------------------------------------------------------------
# PluginLoader
# ---------------------------------------------------------------------------

class PluginLoader:
    """Discovers and loads ``AbstractAgent`` subclasses from plugin dirs."""

    GLOBAL_DIR = Path.home() / ".code4u" / "plugins"
    LOCAL_DIR_NAME = ".code4u/plugins"

    def __init__(self, workspace_path: str = "") -> None:
        self._workspace = workspace_path
        self._agents: Dict[str, AbstractAgent] = {}
        self._errors: List[Dict[str, str]] = []

    @property
    def agents(self) -> Dict[str, AbstractAgent]:
        return dict(self._agents)

    @property
    def errors(self) -> List[Dict[str, str]]:
        return list(self._errors)

    def discover(self) -> List[AbstractAgent]:
        """Discover agents from both global and local plugin dirs.

        Project-local plugins override global ones with the same name.
        """
        self._agents.clear()
        self._errors.clear()

        # Global plugins
        if self.GLOBAL_DIR.is_dir():
            self._scan_directory(self.GLOBAL_DIR, source="global")

        # Project-local plugins (override globals)
        if self._workspace:
            local_dir = Path(self._workspace) / self.LOCAL_DIR_NAME
            if local_dir.is_dir():
                self._scan_directory(local_dir, source="local")

        logger.info(
            "plugins_discovered",
            count=len(self._agents),
            errors=len(self._errors),
            sources=[a.manifest.name for a in self._agents.values()],
        )

        return list(self._agents.values())

    def register_into(self, controller: Any) -> int:
        """Register all discovered agents into a SwarmController.

        Custom agents with higher ``priority`` override defaults.
        Returns the number of agents registered.
        """
        count = 0
        for agent in self._agents.values():
            fn = self._wrap_agent(agent)
            controller.register_agent(agent.agent_type, fn)
            count += 1

            logger.info(
                "plugin_registered",
                name=agent.name,
                agent_type=agent.agent_type.value,
                icon=agent.manifest.icon,
            )

        return count

    def load_from_file(self, file_path: str) -> Optional[AbstractAgent]:
        """Load a single agent from a Python file."""
        path = Path(file_path)
        if not path.is_file() or path.suffix != ".py":
            return None

        agents = self._load_module_agents(path)
        if agents:
            agent = agents[0]
            self._agents[agent.name] = agent
            return agent
        return None

    def install_from_manifest(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Install agents/recipes from a marketplace manifest."""
        parsed = parse_marketplace_manifest(manifest_data)
        if not parsed["valid"]:
            return parsed

        installed_recipes = 0
        for recipe_data in parsed.get("recipes", []):
            try:
                from code4u.core.recipes import Recipe, RecipeRegistry
                recipe = Recipe.from_dict(recipe_data)
                registry = RecipeRegistry()
                registry.register(recipe)
                installed_recipes += 1
            except Exception as exc:
                self._errors.append({
                    "source": "manifest",
                    "error": f"Recipe install failed: {exc}",
                })

        parsed["installedRecipes"] = installed_recipes
        parsed["installedAgents"] = 0  # agents from manifest require .py files

        return parsed

    # -- Internal ------------------------------------------------------------

    def _scan_directory(self, directory: Path, source: str = "") -> None:
        """Scan a directory for .py files containing AbstractAgent subclasses."""
        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            agents = self._load_module_agents(py_file)
            for agent in agents:
                self._agents[agent.name] = agent
                logger.debug(
                    "plugin_found",
                    name=agent.name,
                    source=source,
                    file=str(py_file),
                )

    def _load_module_agents(self, py_file: Path) -> List[AbstractAgent]:
        """Import a .py file and return all AbstractAgent subclasses found."""
        module_name = f"code4u_plugin_{py_file.stem}"
        agents: List[AbstractAgent] = []

        try:
            spec = importlib.util.spec_from_file_location(module_name, str(py_file))
            if spec is None or spec.loader is None:
                return agents

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, AbstractAgent)
                    and attr is not AbstractAgent
                    and hasattr(attr, "manifest")
                ):
                    try:
                        instance = attr()
                        agents.append(instance)
                    except Exception as exc:
                        self._errors.append({
                            "source": str(py_file),
                            "class": attr_name,
                            "error": str(exc),
                        })

        except Exception as exc:
            self._errors.append({
                "source": str(py_file),
                "error": str(exc),
            })
            logger.warning("plugin_load_error", file=str(py_file), error=str(exc))
        finally:
            sys.modules.pop(module_name, None)

        return agents

    @staticmethod
    def _wrap_agent(agent: AbstractAgent):
        """Wrap an AbstractAgent instance into the AgentFn signature."""
        from code4u.agents.orchestrator.models import HandoffPayload

        def agent_fn(task, handoffs):
            return agent.run(task, handoffs)

        return agent_fn
