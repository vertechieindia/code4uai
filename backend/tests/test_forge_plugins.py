"""Day 26 — Forge & Plugin Ecosystem test suite.

Tests:
  - AbstractAgent: contract, manifest, can_handle.
  - PluginLoader: discovery, loading, registration, error handling.
  - ForgeAgent: pattern detection, recipe generation, YAML output.
  - Marketplace: manifest parsing, recipe installation.
  - CLI integration: agents list, forge, install.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List

import pytest

from code4u.agents.base import AbstractAgent, AgentManifest
from code4u.agents.orchestrator.models import (
    AgentType,
    HandoffPayload,
    SubTask,
    TaskStatus,
)
from code4u.agents.meta.forge import (
    ForgeAgent,
    ForgedRecipe,
    CodePattern,
    _detect_import_patterns,
    _detect_decorator_patterns,
    _detect_error_handling,
    _detect_naming_patterns,
    _detect_structure_patterns,
)
from code4u.core.loader import (
    PluginLoader,
    parse_marketplace_manifest,
)


# ═══════════════════════════════════════════════════════════════════════════
# Sample plugin for testing
# ═══════════════════════════════════════════════════════════════════════════

_SAMPLE_PLUGIN_CODE = textwrap.dedent("""\
    from code4u.agents.base import AbstractAgent, AgentManifest
    from code4u.agents.orchestrator.models import AgentType, HandoffPayload, SubTask

    class HelloAgent(AbstractAgent):
        manifest = AgentManifest(
            name="hello",
            agent_type=AgentType.REFACTOR,
            version="1.0.0",
            description="A test plugin that says hello.",
            icon="👋",
            capabilities=["greeting"],
            priority=5,
        )

        def run(self, task, handoffs):
            return HandoffPayload(
                source_task_id=task.id,
                agent_type=AgentType.REFACTOR,
                data={"message": "Hello from plugin!"},
            )
""")

_SAMPLE_SOURCE_CODE = textwrap.dedent("""\
    from __future__ import annotations

    import ast
    import re
    from dataclasses import dataclass, field
    from typing import Any, Dict, List, Optional
    from enum import Enum

    import structlog

    logger = structlog.get_logger("sample")


    class ErrorType(str, Enum):
        SYNTAX = "syntax"
        RUNTIME = "runtime"


    class SampleError(ValueError):
        pass


    @dataclass
    class SampleModel:
        name: str
        value: int = 0
        items: List[str] = field(default_factory=list)

        @property
        def display_name(self) -> str:
            return self.name.upper()

        def to_dict(self) -> Dict[str, Any]:
            return {"name": self.name, "value": self.value}


    def _private_helper(x: int) -> int:
        try:
            return x * 2
        except ValueError as exc:
            raise SampleError(str(exc))


    def _another_private(data: str) -> str:
        return data.strip()


    def public_function(items: List[str]) -> Dict[str, Any]:
        \\"\\"\\"Process items and return results.\\"\\"\\"
        return {"count": len(items)}
""")


# ═══════════════════════════════════════════════════════════════════════════
# AbstractAgent tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAbstractAgent:
    def test_manifest_to_dict(self):
        m = AgentManifest(
            name="test",
            agent_type=AgentType.VISION,
            version="1.2.3",
            icon="👁",
            capabilities=["vision", "ui"],
        )
        d = m.to_dict()
        assert d["name"] == "test"
        assert d["agentType"] == "vision"
        assert d["version"] == "1.2.3"
        assert d["capabilities"] == ["vision", "ui"]

    def test_concrete_agent(self):
        class TestAgent(AbstractAgent):
            manifest = AgentManifest(name="test", agent_type=AgentType.GRAPH)
            def run(self, task, handoffs):
                return HandoffPayload(task.id, AgentType.GRAPH, {"ok": True})

        agent = TestAgent()
        assert agent.name == "test"
        assert agent.agent_type == AgentType.GRAPH
        task = SubTask(agent_type=AgentType.GRAPH)
        assert agent.can_handle(task)

    def test_can_handle_mismatch(self):
        class TestAgent(AbstractAgent):
            manifest = AgentManifest(name="test", agent_type=AgentType.VISION)
            def run(self, task, handoffs):
                return HandoffPayload(task.id, AgentType.VISION, {})

        agent = TestAgent()
        task = SubTask(agent_type=AgentType.GRAPH)
        assert not agent.can_handle(task)

    def test_to_dict(self):
        class TestAgent(AbstractAgent):
            manifest = AgentManifest(name="test", agent_type=AgentType.HEAL, icon="🩹")
            def run(self, task, handoffs):
                return HandoffPayload(task.id, AgentType.HEAL, {})

        agent = TestAgent()
        d = agent.to_dict()
        assert d["name"] == "test"
        assert d["icon"] == "🩹"


# ═══════════════════════════════════════════════════════════════════════════
# PluginLoader tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPluginLoader:
    def test_discover_empty(self, tmp_path):
        loader = PluginLoader(workspace_path=str(tmp_path))
        loader.GLOBAL_DIR = tmp_path / "global_plugins"
        agents = loader.discover()
        assert agents == []

    def test_discover_plugin(self, tmp_path):
        plugin_dir = tmp_path / ".code4u" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "hello_agent.py").write_text(_SAMPLE_PLUGIN_CODE)

        loader = PluginLoader(workspace_path=str(tmp_path))
        loader.GLOBAL_DIR = tmp_path / "global_doesnt_exist"
        agents = loader.discover()
        assert len(agents) == 1
        assert agents[0].name == "hello"
        assert agents[0].manifest.icon == "👋"

    def test_load_from_file(self, tmp_path):
        plugin_file = tmp_path / "hello_agent.py"
        plugin_file.write_text(_SAMPLE_PLUGIN_CODE)

        loader = PluginLoader()
        agent = loader.load_from_file(str(plugin_file))
        assert agent is not None
        assert agent.name == "hello"

    def test_load_nonexistent_file(self):
        loader = PluginLoader()
        agent = loader.load_from_file("/nonexistent/agent.py")
        assert agent is None

    def test_load_non_py_file(self, tmp_path):
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("not a plugin")

        loader = PluginLoader()
        agent = loader.load_from_file(str(txt_file))
        assert agent is None

    def test_skip_underscore_files(self, tmp_path):
        plugin_dir = tmp_path / ".code4u" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "__init__.py").write_text("# init")
        (plugin_dir / "_private.py").write_text(_SAMPLE_PLUGIN_CODE)

        loader = PluginLoader(workspace_path=str(tmp_path))
        loader.GLOBAL_DIR = tmp_path / "nope"
        agents = loader.discover()
        assert len(agents) == 0

    def test_local_overrides_global(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        local_dir = tmp_path / "project" / ".code4u" / "plugins"
        local_dir.mkdir(parents=True)

        # Same agent name, different versions
        global_code = _SAMPLE_PLUGIN_CODE.replace('version="1.0.0"', 'version="0.9.0"')
        (global_dir / "hello_agent.py").write_text(global_code)
        (local_dir / "hello_agent.py").write_text(_SAMPLE_PLUGIN_CODE)

        loader = PluginLoader(workspace_path=str(tmp_path / "project"))
        loader.GLOBAL_DIR = global_dir
        agents = loader.discover()
        assert len(agents) == 1
        assert agents[0].manifest.version == "1.0.0"  # local wins

    def test_register_into_controller(self, tmp_path):
        from code4u.agents.orchestrator.controller import SwarmController

        plugin_file = tmp_path / "hello_agent.py"
        plugin_file.write_text(_SAMPLE_PLUGIN_CODE)

        loader = PluginLoader()
        loader.load_from_file(str(plugin_file))
        controller = SwarmController()
        count = loader.register_into(controller)
        assert count == 1

        # Verify the plugin runs
        task = SubTask(id="t1", agent_type=AgentType.REFACTOR)
        graph_mod = __import__("code4u.agents.orchestrator.models", fromlist=["TaskGraph"])
        graph = graph_mod.TaskGraph(goal="test")
        graph.add_task(task)
        result = controller.execute_sync(graph)
        assert result.is_success
        assert result.tasks[0].result.data["message"] == "Hello from plugin!"

    def test_bad_plugin_records_error(self, tmp_path):
        plugin_dir = tmp_path / ".code4u" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "bad_agent.py").write_text("raise RuntimeError('broken')")

        loader = PluginLoader(workspace_path=str(tmp_path))
        loader.GLOBAL_DIR = tmp_path / "nope"
        agents = loader.discover()
        assert len(agents) == 0
        assert len(loader.errors) >= 1

    def test_agents_property(self, tmp_path):
        plugin_file = tmp_path / "hello_agent.py"
        plugin_file.write_text(_SAMPLE_PLUGIN_CODE)

        loader = PluginLoader()
        loader.load_from_file(str(plugin_file))
        assert "hello" in loader.agents


# ═══════════════════════════════════════════════════════════════════════════
# Pattern detection tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPatternDetection:
    def test_detect_future_annotations(self):
        patterns = _detect_import_patterns("from __future__ import annotations\nimport os")
        names = [p.name for p in patterns]
        assert "future_annotations" in names

    def test_detect_structlog(self):
        patterns = _detect_import_patterns("import structlog\nlogger = structlog.get_logger()")
        names = [p.name for p in patterns]
        assert "structured_logging" in names

    def test_detect_typing(self):
        patterns = _detect_import_patterns("from typing import Dict, List, Optional")
        names = [p.name for p in patterns]
        assert "type_hints" in names

    def test_detect_dataclass(self):
        patterns = _detect_decorator_patterns("@dataclass\nclass Foo:\n    pass\n@dataclass\nclass Bar:\n    pass")
        assert any(p.name == "dataclass_models" and p.frequency == 2 for p in patterns)

    def test_detect_property(self):
        patterns = _detect_decorator_patterns("    @property\n    def x(self):\n        return 1")
        assert any(p.name == "property_accessors" for p in patterns)

    def test_detect_custom_exceptions(self):
        patterns = _detect_error_handling("class MyError(ValueError):\n    pass")
        assert any(p.name == "custom_exceptions" for p in patterns)

    def test_detect_specific_except(self):
        patterns = _detect_error_handling("    try:\n        x()\n    except ValueError as e:\n        pass")
        assert any(p.name == "specific_except" for p in patterns)

    def test_detect_snake_case(self):
        import ast
        tree = ast.parse("def hello_world():\n    pass\ndef another_func():\n    pass")
        patterns = _detect_naming_patterns(tree)
        assert any(p.name == "snake_case_functions" for p in patterns)

    def test_detect_pascal_case_classes(self):
        import ast
        tree = ast.parse("class MyClass:\n    pass\nclass AnotherOne:\n    pass")
        patterns = _detect_naming_patterns(tree)
        assert any(p.name == "pascal_case_classes" for p in patterns)

    def test_detect_private_prefix(self):
        import ast
        tree = ast.parse("def _helper():\n    pass\ndef _internal():\n    pass\ndef public():\n    pass")
        patterns = _detect_naming_patterns(tree)
        assert any(p.name == "private_prefix" for p in patterns)

    def test_detect_to_dict(self):
        import ast
        source = "class X:\n    def to_dict(self):\n        return {}"
        tree = ast.parse(source)
        patterns = _detect_structure_patterns(source, tree)
        assert any(p.name == "to_dict_serialization" for p in patterns)

    def test_detect_docstrings(self):
        import ast
        source = '""\"Module doc.\"\"\"\ndef f():\n    \"\"\"Func doc.\"\"\"\n    pass'
        tree = ast.parse(source)
        patterns = _detect_structure_patterns(source, tree)
        assert any(p.name == "docstrings" for p in patterns)


# ═══════════════════════════════════════════════════════════════════════════
# ForgeAgent tests
# ═══════════════════════════════════════════════════════════════════════════

class TestForgeAgent:
    @pytest.fixture
    def forge(self):
        return ForgeAgent()

    def test_forge_from_file(self, forge, tmp_path):
        sample = tmp_path / "sample.py"
        sample.write_text(_SAMPLE_SOURCE_CODE)
        result = forge.forge_from_file(str(sample))
        assert result.id == "forged-sample"
        assert len(result.patterns) >= 3
        assert result.language == "python"

    def test_forge_from_source(self, forge):
        result = forge.forge_from_source(
            "from __future__ import annotations\n@dataclass\nclass Foo:\n    x: int = 0\n",
            "test.py",
        )
        assert "forged" in result.tags
        assert result.selector_glob == "*.py"

    def test_forge_nonexistent_file(self, forge):
        with pytest.raises(FileNotFoundError):
            forge.forge_from_file("/nonexistent/file.py")

    def test_recipe_yaml_output(self, forge, tmp_path):
        sample = tmp_path / "sample.py"
        sample.write_text("from __future__ import annotations\n@dataclass\nclass X:\n    pass")
        result = forge.forge_from_file(str(sample))
        yaml = result.recipe_yaml
        assert "id: forged-sample" in yaml
        assert "selector:" in yaml
        assert "prompt_template:" in yaml

    def test_recipe_dict_output(self, forge):
        result = forge.forge_from_source("x = 1", "test.py")
        d = result.recipe_dict
        assert "id" in d
        assert "prompt_template" in d
        assert "selector" in d

    def test_recipe_save(self, forge, tmp_path):
        result = forge.forge_from_source("x = 1", "test.py")
        out = result.save(str(tmp_path / "test_recipe.yaml"))
        assert Path(out).is_file()
        content = Path(out).read_text()
        assert "id:" in content

    def test_forged_recipe_to_dict(self, forge):
        result = forge.forge_from_source(
            "import structlog\nlogger = structlog.get_logger()",
            "app.py",
        )
        d = result.to_dict()
        assert d["id"] == "forged-app"
        assert len(d["patterns"]) >= 1
        assert d["language"] == "python"

    def test_code_pattern_to_dict(self):
        p = CodePattern("test", "import", "Test desc", r"\btest\b", "test()", 3)
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["frequency"] == 3

    def test_detect_language_ts(self, forge):
        assert forge._detect_language(Path("app.tsx")) == "typescript"
        assert forge._detect_language(Path("app.js")) == "javascript"
        assert forge._detect_language(Path("main.go")) == "go"

    def test_full_pattern_coverage(self, forge, tmp_path):
        sample = tmp_path / "full.py"
        sample.write_text(_SAMPLE_SOURCE_CODE)
        result = forge.forge_from_file(str(sample))
        pattern_names = {p.name for p in result.patterns}
        assert "future_annotations" in pattern_names
        assert "structured_logging" in pattern_names
        assert "dataclass_models" in pattern_names
        assert "custom_exceptions" in pattern_names


# ═══════════════════════════════════════════════════════════════════════════
# Marketplace tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMarketplace:
    def test_parse_valid_manifest(self):
        data = {
            "name": "code4u-security-pack",
            "version": "1.0.0",
            "description": "Security recipes for Python",
            "author": "Team",
            "agents": [],
            "recipes": [
                {
                    "id": "no-eval",
                    "name": "No Eval",
                    "description": "Ban eval()",
                    "prompt_template": "Remove eval() calls",
                    "selector": {"file_glob": "*.py"},
                },
            ],
        }
        result = parse_marketplace_manifest(data)
        assert result["valid"]
        assert result["name"] == "code4u-security-pack"

    def test_parse_invalid_manifest(self):
        result = parse_marketplace_manifest({"name": ""})
        assert not result["valid"]

    def test_install_from_manifest(self):
        data = {
            "name": "test-pack",
            "version": "0.1.0",
            "recipes": [
                {
                    "id": "test-recipe",
                    "name": "Test Recipe",
                    "description": "A test",
                    "prompt_template": "Do something",
                    "selector": {"file_glob": "*.py"},
                },
            ],
        }
        loader = PluginLoader()
        result = loader.install_from_manifest(data)
        assert result["valid"]
        assert result["installedRecipes"] == 1

    def test_install_empty_manifest(self):
        data = {"name": "empty", "version": "1.0.0", "recipes": []}
        loader = PluginLoader()
        result = loader.install_from_manifest(data)
        assert result["valid"]
        assert result["installedRecipes"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Integration: plugin + swarm
# ═══════════════════════════════════════════════════════════════════════════

class TestPluginSwarmIntegration:
    def test_plugin_executes_in_swarm(self, tmp_path):
        from code4u.agents.orchestrator.controller import SwarmController
        from code4u.agents.orchestrator.models import TaskGraph

        plugin_file = tmp_path / "hello_agent.py"
        plugin_file.write_text(_SAMPLE_PLUGIN_CODE)

        loader = PluginLoader()
        loader.load_from_file(str(plugin_file))

        controller = SwarmController()
        loader.register_into(controller)

        graph = TaskGraph(goal="test plugin")
        graph.add_task(SubTask(id="t1", agent_type=AgentType.REFACTOR))
        result = controller.execute_sync(graph)
        assert result.is_success
        assert result.tasks[0].result.data["message"] == "Hello from plugin!"

    def test_forge_then_install(self, tmp_path):
        from code4u.core.recipes import RecipeRegistry

        forge = ForgeAgent()
        sample = tmp_path / "auth.py"
        sample.write_text(textwrap.dedent("""\
            from __future__ import annotations
            import structlog
            logger = structlog.get_logger("auth")

            @dataclass
            class AuthResult:
                success: bool
                token: str = ""
        """))
        recipe = forge.forge_from_file(str(sample))

        # Save and verify
        out_path = str(tmp_path / "forged.yaml")
        recipe.save(out_path)
        assert Path(out_path).is_file()
        assert "forged-auth" in Path(out_path).read_text()
