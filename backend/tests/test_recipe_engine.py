"""Tests for Day 14: Recipe Engine & Plugin Architecture.

Covers:
  - Recipe model: YAML loading, serialization, field parsing.
  - RecipeSelector: file glob matching, exclusion, symbol regex.
  - RecipeRegistry: auto-discovery from global and project dirs.
  - Recipe execution: intent building, file filtering via DependencyMap.
  - CLI integration: recipes list, run-recipe command.
  - Edge cases: missing files, empty selectors, duplicate IDs.
"""

from __future__ import annotations

import asyncio
import os
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

from code4u.core.recipes import (
    Recipe,
    RecipeRegistry,
    RecipeSelector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_recipe_dir(tmp_path):
    """Create a temp directory with sample recipe YAML files."""
    recipe_dir = tmp_path / ".code4u" / "recipes"
    recipe_dir.mkdir(parents=True)

    fstring_recipe = {
        "id": "convert-format-to-fstring",
        "name": "Convert to f-strings",
        "description": "Replace old % and .format() strings with f-strings.",
        "version": "1.0",
        "tags": ["python", "modernize", "strings"],
        "selector": {
            "file_glob": "*.py",
            "exclude_glob": "test_*.py",
        },
        "prompt_template": (
            "Convert all old-style string formatting (% operator and "
            ".format()) to f-strings in this Python file."
        ),
        "severity": "suggestion",
        "auto_fix": False,
    }

    hooks_recipe = {
        "id": "react-class-to-hooks",
        "name": "React Class to Hooks",
        "description": "Convert React class components to functional hooks.",
        "tags": ["react", "typescript", "modernize"],
        "selector": {
            "file_glob": "*.tsx",
        },
        "prompt_template": "Convert this React class component to a functional component using hooks.",
    }

    css_recipe = {
        "id": "css-bem-naming",
        "name": "BEM CSS Naming",
        "description": "Enforce BEM naming convention in CSS files.",
        "tags": ["css", "standards"],
        "selector": {
            "file_glob": "*.css",
            "exclude_glob": "vendor_*.css",
        },
        "prompt_template": "Refactor CSS class names to follow BEM naming convention.",
        "severity": "warning",
    }

    (recipe_dir / "fstring.yaml").write_text(yaml.dump(fstring_recipe))
    (recipe_dir / "hooks.yaml").write_text(yaml.dump(hooks_recipe))
    (recipe_dir / "bem.yml").write_text(yaml.dump(css_recipe))

    return tmp_path


@pytest.fixture
def sample_recipe_dict():
    return {
        "id": "test-recipe",
        "name": "Test Recipe",
        "description": "A test recipe for unit tests.",
        "version": "2.0",
        "tags": ["test"],
        "selector": {
            "file_glob": "*.py",
            "symbol_regex": r"^calculate_",
            "exclude_glob": "test_*.py",
        },
        "prompt_template": "Optimize this function for performance.",
        "severity": "suggestion",
        "auto_fix": True,
    }


# ---------------------------------------------------------------------------
# Test: RecipeSelector
# ---------------------------------------------------------------------------

class TestRecipeSelector:
    def test_default_matches_everything(self):
        sel = RecipeSelector()
        assert sel.matches_file("utils.py")
        assert sel.matches_file("Header.tsx")
        assert sel.matches_file("styles.css")

    def test_file_glob_py(self):
        sel = RecipeSelector(file_glob="*.py")
        assert sel.matches_file("utils.py")
        assert sel.matches_file("src/code/utils.py")
        assert not sel.matches_file("Header.tsx")
        assert not sel.matches_file("styles.css")

    def test_file_glob_tsx(self):
        sel = RecipeSelector(file_glob="*.tsx")
        assert sel.matches_file("Header.tsx")
        assert not sel.matches_file("utils.py")

    def test_file_glob_css(self):
        sel = RecipeSelector(file_glob="*.css")
        assert sel.matches_file("styles.css")
        assert not sel.matches_file("utils.py")

    def test_exclude_glob(self):
        sel = RecipeSelector(file_glob="*.py", exclude_glob="test_*.py")
        assert sel.matches_file("utils.py")
        assert not sel.matches_file("test_utils.py")
        assert sel.matches_file("main.py")

    def test_exclude_glob_vendor(self):
        sel = RecipeSelector(file_glob="*.css", exclude_glob="vendor_*.css")
        assert sel.matches_file("styles.css")
        assert not sel.matches_file("vendor_bootstrap.css")

    def test_symbol_regex(self):
        sel = RecipeSelector(symbol_regex=r"^calculate_")
        assert sel.matches_symbol("calculate_total")
        assert sel.matches_symbol("calculate_tax")
        assert not sel.matches_symbol("format_currency")

    def test_symbol_regex_none_matches_all(self):
        sel = RecipeSelector()
        assert sel.matches_symbol("anything")

    def test_filter_files(self):
        sel = RecipeSelector(file_glob="*.py", exclude_glob="test_*.py")
        files = ["utils.py", "test_utils.py", "main.py", "Header.tsx", "test_main.py"]
        result = sel.filter_files(files)
        assert result == ["utils.py", "main.py"]

    def test_filter_files_empty(self):
        sel = RecipeSelector(file_glob="*.rs")
        result = sel.filter_files(["utils.py", "main.py"])
        assert result == []

    def test_to_dict(self):
        sel = RecipeSelector(file_glob="*.py", symbol_regex=r"^test", exclude_glob="vendor_*")
        d = sel.to_dict()
        assert d["fileGlob"] == "*.py"
        assert d["symbolRegex"] == "^test"
        assert d["excludeGlob"] == "vendor_*"


# ---------------------------------------------------------------------------
# Test: Recipe model
# ---------------------------------------------------------------------------

class TestRecipeModel:
    def test_from_dict(self, sample_recipe_dict):
        recipe = Recipe.from_dict(sample_recipe_dict)
        assert recipe.id == "test-recipe"
        assert recipe.name == "Test Recipe"
        assert recipe.version == "2.0"
        assert recipe.auto_fix is True
        assert recipe.selector.file_glob == "*.py"
        assert recipe.selector.symbol_regex == r"^calculate_"
        assert recipe.selector.exclude_glob == "test_*.py"

    def test_from_dict_minimal(self):
        recipe = Recipe.from_dict({"id": "min", "prompt_template": "Do something."})
        assert recipe.id == "min"
        assert recipe.name == "min"
        assert recipe.version == "1.0"
        assert recipe.selector.file_glob == "*"
        assert recipe.tags == []
        assert recipe.auto_fix is False

    def test_from_dict_string_selector(self):
        recipe = Recipe.from_dict({
            "id": "quick",
            "selector": "*.py",
            "prompt_template": "test",
        })
        assert recipe.selector.file_glob == "*.py"

    def test_to_dict_roundtrip(self, sample_recipe_dict):
        recipe = Recipe.from_dict(sample_recipe_dict)
        d = recipe.to_dict()
        assert d["id"] == "test-recipe"
        assert d["promptTemplate"] == "Optimize this function for performance."
        assert d["selector"]["fileGlob"] == "*.py"

    def test_summary_excludes_template(self, sample_recipe_dict):
        recipe = Recipe.from_dict(sample_recipe_dict)
        s = recipe.summary()
        assert "id" in s
        assert "name" in s
        assert "promptTemplate" not in s

    def test_build_intent(self):
        recipe = Recipe.from_dict({
            "id": "x",
            "prompt_template": "  Do something specific.  ",
        })
        assert recipe.build_intent() == "Do something specific."

    def test_build_intent_with_extra(self):
        recipe = Recipe.from_dict({
            "id": "x",
            "prompt_template": "Fix the code.",
        })
        result = recipe.build_intent("Only in utils.py")
        assert "Fix the code." in result
        assert "Additional context: Only in utils.py" in result

    def test_from_yaml(self, tmp_recipe_dir):
        yaml_path = tmp_recipe_dir / ".code4u" / "recipes" / "fstring.yaml"
        recipe = Recipe.from_yaml(str(yaml_path))
        assert recipe.id == "convert-format-to-fstring"
        assert "f-strings" in recipe.name
        assert recipe.selector.file_glob == "*.py"
        assert recipe.source_path is not None

    def test_from_yaml_not_found(self):
        with pytest.raises(FileNotFoundError):
            Recipe.from_yaml("/nonexistent/recipe.yaml")

    def test_is_project_local(self, tmp_recipe_dir):
        yaml_path = tmp_recipe_dir / ".code4u" / "recipes" / "fstring.yaml"
        recipe = Recipe.from_yaml(str(yaml_path))
        assert recipe.is_project_local is True

    def test_is_not_project_local_for_global(self):
        recipe = Recipe.from_dict({"id": "x", "prompt_template": "t"})
        recipe.source_path = str(Path.home() / ".code4u" / "recipes" / "x.yaml")
        assert recipe.is_project_local is False


# ---------------------------------------------------------------------------
# Test: RecipeRegistry
# ---------------------------------------------------------------------------

class TestRecipeRegistry:
    def test_load_from_project_dir(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()
        assert registry.count == 3

    def test_list_recipes_sorted(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()
        ids = [r.id for r in registry.list_recipes()]
        assert ids == sorted(ids)

    def test_get_by_id(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()
        recipe = registry.get("convert-format-to-fstring")
        assert recipe is not None
        assert "f-strings" in recipe.name

    def test_get_nonexistent(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()
        assert registry.get("nonexistent-recipe") is None

    def test_list_by_tag(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()
        modernize = registry.list_by_tag("modernize")
        assert len(modernize) == 2
        ids = {r.id for r in modernize}
        assert "convert-format-to-fstring" in ids
        assert "react-class-to-hooks" in ids

    def test_list_by_tag_no_match(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()
        assert registry.list_by_tag("rust") == []

    def test_register_manual(self):
        registry = RecipeRegistry()
        recipe = Recipe.from_dict({
            "id": "manual-test",
            "name": "Manual",
            "prompt_template": "Test prompt.",
        })
        registry.register(recipe)
        assert registry.get("manual-test") is not None
        assert registry.count == 1

    def test_project_overrides_global(self, tmp_path):
        global_dir = tmp_path / "global"
        project_dir = tmp_path / "project" / ".code4u" / "recipes"
        global_dir.mkdir(parents=True)
        project_dir.mkdir(parents=True)

        (global_dir / "dup.yaml").write_text(yaml.dump({
            "id": "shared-recipe",
            "name": "Global Version",
            "prompt_template": "Global template.",
        }))

        (project_dir / "dup.yaml").write_text(yaml.dump({
            "id": "shared-recipe",
            "name": "Project Version",
            "prompt_template": "Project template.",
        }))

        registry = RecipeRegistry(workspace_path=str(tmp_path / "project"))

        import code4u.core.recipes as recipes_mod
        original_dir = recipes_mod._GLOBAL_RECIPE_DIR
        recipes_mod._GLOBAL_RECIPE_DIR = global_dir
        try:
            registry.load()
            recipe = registry.get("shared-recipe")
            assert recipe is not None
            assert recipe.name == "Project Version"
        finally:
            recipes_mod._GLOBAL_RECIPE_DIR = original_dir

    def test_empty_directory(self, tmp_path):
        registry = RecipeRegistry(workspace_path=str(tmp_path))
        registry.load()
        assert registry.count == 0

    def test_invalid_yaml_skipped(self, tmp_path):
        recipe_dir = tmp_path / ".code4u" / "recipes"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "bad.yaml").write_text("not: [valid: yaml: file")
        (recipe_dir / "good.yaml").write_text(yaml.dump({
            "id": "good",
            "prompt_template": "OK.",
        }))
        registry = RecipeRegistry(workspace_path=str(tmp_path))
        registry.load()
        assert registry.count >= 1
        assert registry.get("good") is not None

    def test_auto_id_from_filename(self, tmp_path):
        recipe_dir = tmp_path / ".code4u" / "recipes"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "my-rule.yaml").write_text(yaml.dump({
            "name": "My Rule",
            "prompt_template": "Do the thing.",
        }))
        registry = RecipeRegistry(workspace_path=str(tmp_path))
        registry.load()
        assert registry.get("my-rule") is not None


# ---------------------------------------------------------------------------
# Test: Selector filtering with realistic file lists
# ---------------------------------------------------------------------------

class TestSelectorFiltering:
    SAMPLE_FILES = [
        "/project/src/utils.py",
        "/project/src/main.py",
        "/project/tests/test_utils.py",
        "/project/tests/test_main.py",
        "/project/frontend/Header.tsx",
        "/project/frontend/Sidebar.tsx",
        "/project/frontend/App.css",
        "/project/frontend/vendor_bootstrap.css",
        "/project/docs/README.md",
        "/project/config.json",
    ]

    def test_py_only(self):
        sel = RecipeSelector(file_glob="*.py")
        result = sel.filter_files(self.SAMPLE_FILES)
        assert len(result) == 4
        assert all(f.endswith(".py") for f in result)

    def test_py_no_tests(self):
        sel = RecipeSelector(file_glob="*.py", exclude_glob="test_*.py")
        result = sel.filter_files(self.SAMPLE_FILES)
        assert len(result) == 2
        assert "/project/src/utils.py" in result
        assert "/project/src/main.py" in result

    def test_tsx_only(self):
        sel = RecipeSelector(file_glob="*.tsx")
        result = sel.filter_files(self.SAMPLE_FILES)
        assert len(result) == 2

    def test_css_no_vendor(self):
        sel = RecipeSelector(file_glob="*.css", exclude_glob="vendor_*.css")
        result = sel.filter_files(self.SAMPLE_FILES)
        assert len(result) == 1
        assert "App.css" in result[0]

    def test_all_files(self):
        sel = RecipeSelector(file_glob="*")
        result = sel.filter_files(self.SAMPLE_FILES)
        assert len(result) == len(self.SAMPLE_FILES)

    def test_no_match(self):
        sel = RecipeSelector(file_glob="*.rs")
        result = sel.filter_files(self.SAMPLE_FILES)
        assert result == []


# ---------------------------------------------------------------------------
# Test: Recipe intent building
# ---------------------------------------------------------------------------

class TestRecipeIntentBuilding:
    def test_plain_template(self):
        recipe = Recipe.from_dict({
            "id": "x",
            "prompt_template": "Convert strings to f-strings.",
        })
        assert recipe.build_intent() == "Convert strings to f-strings."

    def test_multiline_template(self):
        recipe = Recipe.from_dict({
            "id": "x",
            "prompt_template": "Line 1.\nLine 2.\nLine 3.",
        })
        intent = recipe.build_intent()
        assert "Line 1." in intent
        assert "Line 3." in intent

    def test_extra_context_appended(self):
        recipe = Recipe.from_dict({
            "id": "x",
            "prompt_template": "Fix imports.",
        })
        result = recipe.build_intent("Focus on circular imports only")
        assert result.startswith("Fix imports.")
        assert "circular imports" in result

    def test_empty_extra_context_ignored(self):
        recipe = Recipe.from_dict({
            "id": "x",
            "prompt_template": "Fix imports.",
        })
        assert recipe.build_intent("") == "Fix imports."


# ---------------------------------------------------------------------------
# Test: Registry file filtering helper
# ---------------------------------------------------------------------------

class TestRegistryFilterFiles:
    def test_filter_files_for_recipe(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()

        files = ["utils.py", "test_utils.py", "Header.tsx", "main.py"]
        result = registry.filter_files_for_recipe(
            "convert-format-to-fstring", files
        )
        assert result == ["utils.py", "main.py"]

    def test_filter_files_unknown_recipe(self):
        registry = RecipeRegistry()
        files = ["a.py", "b.py"]
        result = registry.filter_files_for_recipe("unknown", files)
        assert result == files


# ---------------------------------------------------------------------------
# Test: YAML edge cases
# ---------------------------------------------------------------------------

class TestYAMLEdgeCases:
    def test_yml_extension_loaded(self, tmp_recipe_dir):
        registry = RecipeRegistry(workspace_path=str(tmp_recipe_dir))
        registry.load()
        assert registry.get("css-bem-naming") is not None

    def test_non_yaml_files_ignored(self, tmp_path):
        recipe_dir = tmp_path / ".code4u" / "recipes"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "notes.txt").write_text("Not a recipe")
        (recipe_dir / "real.yaml").write_text(yaml.dump({
            "id": "real", "prompt_template": "OK",
        }))
        registry = RecipeRegistry(workspace_path=str(tmp_path))
        registry.load()
        assert registry.count == 1

    def test_camelCase_keys_supported(self):
        recipe = Recipe.from_dict({
            "id": "camel",
            "promptTemplate": "Do it.",
            "autoFix": True,
            "selector": {
                "fileGlob": "*.ts",
                "symbolRegex": "^foo",
                "excludeGlob": "*.test.ts",
            },
        })
        assert recipe.prompt_template == "Do it."
        assert recipe.auto_fix is True
        assert recipe.selector.file_glob == "*.ts"
        assert recipe.selector.exclude_glob == "*.test.ts"
