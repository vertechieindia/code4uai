"""Refactor Recipe Engine — YAML-defined custom transformations.

Allows teams to codify "Tribal Knowledge" into reusable recipes.
A Lead Architect can drop a ``.yaml`` file into their repo's
``.code4u/recipes/`` directory, and every developer gets the
transformation as a CLI command or VS Code action.

Recipe discovery order:
  1. ``~/.code4u/recipes/*.yaml`` — user-global recipes.
  2. ``./.code4u/recipes/*.yaml`` — project-local recipes.

Schema example::

    id: convert-format-to-fstring
    name: Convert to f-strings
    description: Replace old % and .format() strings with f-strings.
    version: "1.0"
    tags: [python, modernize, strings]
    selector:
      file_glob: "*.py"
      symbol_regex: null
      exclude_glob: "test_*.py"
    prompt_template: |
      Convert all old-style string formatting (% operator and .format())
      to f-strings in the following Python file.  Preserve all semantics
      and handle edge cases (e.g. dictionary unpacking, multi-line).
    severity: suggestion
    auto_fix: false
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
import structlog

logger = structlog.get_logger("recipes")


# ---------------------------------------------------------------------------
# Recipe data model
# ---------------------------------------------------------------------------

@dataclass
class RecipeSelector:
    """Defines which files and symbols a recipe targets."""
    file_glob: str = "*"
    symbol_regex: Optional[str] = None
    exclude_glob: Optional[str] = None
    language: Optional[str] = None

    def matches_file(self, file_path: str) -> bool:
        """Check if a file path matches this selector."""
        name = Path(file_path).name
        rel = str(file_path)

        if self.exclude_glob and (
            fnmatch.fnmatch(name, self.exclude_glob)
            or fnmatch.fnmatch(rel, self.exclude_glob)
        ):
            return False

        if self.file_glob == "*":
            return True

        return (
            fnmatch.fnmatch(name, self.file_glob)
            or fnmatch.fnmatch(rel, self.file_glob)
        )

    def matches_symbol(self, symbol_name: str) -> bool:
        """Check if a symbol name matches this selector's regex."""
        if not self.symbol_regex:
            return True
        return bool(re.search(self.symbol_regex, symbol_name))

    def filter_files(self, file_paths: List[str]) -> List[str]:
        """Return only the files that match this selector."""
        return [f for f in file_paths if self.matches_file(f)]

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"fileGlob": self.file_glob}
        if self.symbol_regex:
            d["symbolRegex"] = self.symbol_regex
        if self.exclude_glob:
            d["excludeGlob"] = self.exclude_glob
        if self.language:
            d["language"] = self.language
        return d


@dataclass
class Recipe:
    """A single refactoring recipe loaded from YAML."""
    id: str
    name: str
    description: str
    prompt_template: str
    selector: RecipeSelector = field(default_factory=RecipeSelector)
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    severity: str = "suggestion"
    auto_fix: bool = False
    source_path: Optional[str] = None

    @property
    def is_project_local(self) -> bool:
        """True if loaded from ./.code4u/recipes/ (not global)."""
        if not self.source_path:
            return False
        return "/.code4u/recipes/" in self.source_path and str(
            Path.home()
        ) not in self.source_path

    def build_intent(self, extra_context: str = "") -> str:
        """Build the full intent string from the prompt template."""
        intent = self.prompt_template.strip()
        if extra_context:
            intent = f"{intent}\n\nAdditional context: {extra_context}"
        return intent

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "severity": self.severity,
            "autoFix": self.auto_fix,
            "selector": self.selector.to_dict(),
            "source": self.source_path or "",
            "isProjectLocal": self.is_project_local,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.summary(),
            "promptTemplate": self.prompt_template,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any], source_path: Optional[str] = None) -> "Recipe":
        """Construct a Recipe from a parsed YAML dictionary."""
        sel_data = data.get("selector", {})
        if isinstance(sel_data, str):
            sel_data = {"file_glob": sel_data}

        selector = RecipeSelector(
            file_glob=sel_data.get("file_glob", sel_data.get("fileGlob", "*")),
            symbol_regex=sel_data.get("symbol_regex", sel_data.get("symbolRegex")),
            exclude_glob=sel_data.get("exclude_glob", sel_data.get("excludeGlob")),
            language=sel_data.get("language"),
        )

        return Recipe(
            id=data.get("id", ""),
            name=data.get("name", data.get("id", "unnamed")),
            description=data.get("description", ""),
            prompt_template=data.get("prompt_template", data.get("promptTemplate", "")),
            selector=selector,
            version=str(data.get("version", "1.0")),
            tags=data.get("tags", []),
            severity=data.get("severity", "suggestion"),
            auto_fix=data.get("auto_fix", data.get("autoFix", False)),
            source_path=source_path,
        )

    @staticmethod
    def from_yaml(yaml_path: str) -> "Recipe":
        """Load a single recipe from a YAML file."""
        path = Path(yaml_path)
        if not path.is_file():
            raise FileNotFoundError(f"Recipe not found: {yaml_path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Invalid recipe format in {yaml_path}")
        return Recipe.from_dict(data, source_path=str(path.resolve()))


# ---------------------------------------------------------------------------
# RecipeRegistry — auto-discovery and lookup
# ---------------------------------------------------------------------------

_GLOBAL_RECIPE_DIR = Path.home() / ".code4u" / "recipes"

class RecipeRegistry:
    """Discovers and manages refactoring recipes from YAML files.

    Scans two directories:
      1. ``~/.code4u/recipes/``  — user-global recipes.
      2. ``<workspace>/.code4u/recipes/`` — project-local recipes.

    Project-local recipes take precedence (override) over global ones
    when both share the same ``id``.
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self._recipes: Dict[str, Recipe] = {}
        self._workspace_path = workspace_path
        self._loaded = False

    def load(self) -> None:
        """Discover and load all recipes from global + project directories."""
        self._recipes.clear()

        self._scan_directory(_GLOBAL_RECIPE_DIR)

        if self._workspace_path:
            project_dir = Path(self._workspace_path) / ".code4u" / "recipes"
            self._scan_directory(project_dir)

        self._loaded = True
        logger.info("recipes_loaded", count=len(self._recipes))

    def _scan_directory(self, directory: Path) -> None:
        """Load all *.yaml and *.yml files from a directory."""
        if not directory.is_dir():
            return
        for yaml_file in sorted(directory.iterdir()):
            if yaml_file.suffix not in (".yaml", ".yml"):
                continue
            try:
                recipe = Recipe.from_yaml(str(yaml_file))
                if not recipe.id:
                    recipe.id = yaml_file.stem
                self._recipes[recipe.id] = recipe
                logger.debug("recipe_loaded", id=recipe.id, source=str(yaml_file))
            except Exception as exc:
                logger.warning(
                    "recipe_load_failed",
                    file=str(yaml_file),
                    error=str(exc)[:200],
                )

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def get(self, recipe_id: str) -> Optional[Recipe]:
        """Look up a recipe by its ID."""
        self.ensure_loaded()
        return self._recipes.get(recipe_id)

    def list_recipes(self) -> List[Recipe]:
        """Return all loaded recipes, sorted by ID."""
        self.ensure_loaded()
        return sorted(self._recipes.values(), key=lambda r: r.id)

    def list_by_tag(self, tag: str) -> List[Recipe]:
        """Return recipes that include a specific tag."""
        self.ensure_loaded()
        return [r for r in self._recipes.values() if tag in r.tags]

    def register(self, recipe: Recipe) -> None:
        """Manually register a recipe (e.g., from an API call)."""
        self._recipes[recipe.id] = recipe
        self._loaded = True

    @property
    def count(self) -> int:
        self.ensure_loaded()
        return len(self._recipes)

    def filter_files_for_recipe(
        self, recipe_id: str, all_files: List[str]
    ) -> List[str]:
        """Apply a recipe's selector to filter a file list."""
        recipe = self.get(recipe_id)
        if not recipe:
            return all_files
        return recipe.selector.filter_files(all_files)
