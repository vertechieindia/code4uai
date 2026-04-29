"""Recipe Forge — AI-powered recipe generation from code samples.

The ``ForgeAgent`` analyzes a "perfect" piece of code and generates
a Recipe (YAML) that teaches other agents how to replicate that
style pattern across the codebase.

Usage::

    forge = ForgeAgent()
    result = forge.forge_from_file("/path/to/auth.py")
    print(result.recipe_yaml)
    result.save("~/.code4u/recipes/auth_pattern.yaml")
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("forge_agent")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CodePattern:
    """A detected code pattern within a sample."""
    name: str
    pattern_type: str  # "import", "decorator", "error_handling", "naming", "structure"
    description: str
    regex: str = ""
    example: str = ""
    frequency: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.pattern_type,
            "description": self.description,
            "regex": self.regex,
            "example": self.example,
            "frequency": self.frequency,
        }


@dataclass
class ForgedRecipe:
    """The output of the Forge — a generated Recipe specification."""
    id: str
    name: str
    description: str
    source_file: str = ""
    patterns: List[CodePattern] = field(default_factory=list)
    selector_glob: str = "*.py"
    prompt_template: str = ""
    tags: List[str] = field(default_factory=list)
    language: str = "python"

    @property
    def recipe_yaml(self) -> str:
        """Generate YAML representation of this recipe."""
        lines = [
            f"id: {self.id}",
            f"name: {self.name}",
            f"description: |",
        ]
        for desc_line in self.description.split("\n"):
            lines.append(f"  {desc_line}")

        lines.append(f"language: {self.language}")
        lines.append(f"selector:")
        lines.append(f"  file_glob: \"{self.selector_glob}\"")

        if self.tags:
            lines.append(f"tags: [{', '.join(self.tags)}]")

        lines.append(f"prompt_template: |")
        for tmpl_line in self.prompt_template.split("\n"):
            lines.append(f"  {tmpl_line}")

        return "\n".join(lines)

    @property
    def recipe_dict(self) -> Dict[str, Any]:
        """Dict suitable for ``Recipe.from_dict()``."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "selector": {"file_glob": self.selector_glob},
            "prompt_template": self.prompt_template,
            "tags": self.tags,
            "version": "1.0.0",
            "auto_fix": False,
        }

    def save(self, path: str) -> str:
        """Save the recipe YAML to a file."""
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.recipe_yaml, encoding="utf-8")
        return str(p)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sourceFile": self.source_file,
            "patterns": [p.to_dict() for p in self.patterns],
            "selectorGlob": self.selector_glob,
            "promptTemplate": self.prompt_template,
            "tags": self.tags,
            "language": self.language,
        }


# ---------------------------------------------------------------------------
# Pattern detectors
# ---------------------------------------------------------------------------

def _detect_import_patterns(source: str) -> List[CodePattern]:
    """Detect import style patterns."""
    patterns: List[CodePattern] = []

    if re.search(r"from __future__ import annotations", source):
        patterns.append(CodePattern(
            name="future_annotations",
            pattern_type="import",
            description="Uses 'from __future__ import annotations' for PEP 604 type hints.",
            regex=r"from __future__ import annotations",
            frequency=1,
        ))

    structlog_matches = re.findall(r"import structlog|from structlog", source)
    if structlog_matches:
        patterns.append(CodePattern(
            name="structured_logging",
            pattern_type="import",
            description="Uses structlog for structured logging.",
            regex=r"(?:import structlog|from structlog)",
            example="import structlog\nlogger = structlog.get_logger()",
        ))

    typing_matches = re.findall(r"from typing import (.+)", source)
    if typing_matches:
        types = ", ".join(typing_matches)
        patterns.append(CodePattern(
            name="type_hints",
            pattern_type="import",
            description=f"Uses typing imports: {types[:80]}.",
            regex=r"from typing import",
        ))

    return patterns


def _detect_decorator_patterns(source: str) -> List[CodePattern]:
    """Detect decorator usage patterns."""
    patterns: List[CodePattern] = []

    dataclass_count = len(re.findall(r"@dataclass", source))
    if dataclass_count:
        patterns.append(CodePattern(
            name="dataclass_models",
            pattern_type="decorator",
            description=f"Uses @dataclass for data models ({dataclass_count} found).",
            regex=r"@dataclass",
            frequency=dataclass_count,
        ))

    property_count = len(re.findall(r"@property", source))
    if property_count:
        patterns.append(CodePattern(
            name="property_accessors",
            pattern_type="decorator",
            description=f"Uses @property for computed attributes ({property_count} found).",
            regex=r"@property",
            frequency=property_count,
        ))

    return patterns


def _detect_error_handling(source: str) -> List[CodePattern]:
    """Detect error handling patterns."""
    patterns: List[CodePattern] = []

    custom_exc = re.findall(r"class (\w+)\((?:Exception|BaseException|ValueError|RuntimeError)\)", source)
    if custom_exc:
        patterns.append(CodePattern(
            name="custom_exceptions",
            pattern_type="error_handling",
            description=f"Defines custom exceptions: {', '.join(custom_exc[:5])}.",
            regex=r"class \w+\((?:Exception|BaseException|ValueError|RuntimeError)\)",
            frequency=len(custom_exc),
        ))

    try_blocks = len(re.findall(r"^\s+try:", source, re.MULTILINE))
    specific_except = len(re.findall(r"except \w+", source))
    if try_blocks and specific_except:
        patterns.append(CodePattern(
            name="specific_except",
            pattern_type="error_handling",
            description=f"Uses specific exception handling ({specific_except} typed except blocks).",
            frequency=specific_except,
        ))

    return patterns


def _detect_naming_patterns(tree: ast.AST) -> List[CodePattern]:
    """Detect naming convention patterns via AST."""
    patterns: List[CodePattern] = []

    func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    snake_funcs = sum(1 for n in func_names if re.match(r"^[a-z_][a-z0-9_]*$", n))
    if snake_funcs > 0 and snake_funcs == len(func_names):
        patterns.append(CodePattern(
            name="snake_case_functions",
            pattern_type="naming",
            description="All functions use snake_case naming.",
        ))

    pascal_classes = sum(1 for n in class_names if re.match(r"^[A-Z][a-zA-Z0-9]*$", n))
    if pascal_classes > 0 and pascal_classes == len(class_names):
        patterns.append(CodePattern(
            name="pascal_case_classes",
            pattern_type="naming",
            description="All classes use PascalCase naming.",
        ))

    private_funcs = sum(1 for n in func_names if n.startswith("_") and not n.startswith("__"))
    if private_funcs >= 2:
        patterns.append(CodePattern(
            name="private_prefix",
            pattern_type="naming",
            description=f"Uses underscore prefix for private methods ({private_funcs} found).",
            frequency=private_funcs,
        ))

    return patterns


def _detect_structure_patterns(source: str, tree: ast.AST) -> List[CodePattern]:
    """Detect structural patterns."""
    patterns: List[CodePattern] = []

    if re.search(r'""".*?"""', source, re.DOTALL):
        docstring_count = len(re.findall(r'"""', source)) // 2
        if docstring_count >= 2:
            patterns.append(CodePattern(
                name="docstrings",
                pattern_type="structure",
                description=f"Uses docstrings for documentation ({docstring_count} found).",
                frequency=docstring_count,
            ))

    if re.search(r"def to_dict\(self\)", source):
        patterns.append(CodePattern(
            name="to_dict_serialization",
            pattern_type="structure",
            description="Uses to_dict() method for serialization (camelCase JSON convention).",
            regex=r"def to_dict\(self\)",
        ))

    if re.search(r"__slots__", source):
        patterns.append(CodePattern(
            name="slots_optimization",
            pattern_type="structure",
            description="Uses __slots__ for memory optimization.",
            regex=r"__slots__",
        ))

    enum_classes = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            (isinstance(b, ast.Attribute) and b.attr in ("Enum", "str"))
            or (isinstance(b, ast.Name) and b.id == "Enum")
            for b in node.bases
        )
    ]
    if enum_classes:
        patterns.append(CodePattern(
            name="enum_constants",
            pattern_type="structure",
            description=f"Uses Enum classes for constants: {', '.join(enum_classes[:5])}.",
            frequency=len(enum_classes),
        ))

    return patterns


# ---------------------------------------------------------------------------
# ForgeAgent
# ---------------------------------------------------------------------------

class ForgeAgent:
    """Analyzes code samples and generates Recipes.

    Usage::

        forge = ForgeAgent()
        result = forge.forge_from_file("src/api/auth.py")
        print(result.recipe_yaml)
    """

    def forge_from_file(self, file_path: str) -> ForgedRecipe:
        """Analyze a file and generate a Recipe."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Sample file not found: {file_path}")

        source = path.read_text(encoding="utf-8")
        language = self._detect_language(path)
        return self.forge_from_source(source, str(path), language)

    def forge_from_source(
        self,
        source: str,
        source_path: str = "",
        language: str = "python",
    ) -> ForgedRecipe:
        """Analyze source code and generate a Recipe."""
        patterns: List[CodePattern] = []

        # Regex-based pattern detection
        patterns.extend(_detect_import_patterns(source))
        patterns.extend(_detect_decorator_patterns(source))
        patterns.extend(_detect_error_handling(source))

        # AST-based detection (Python only)
        if language == "python":
            try:
                tree = ast.parse(source)
                patterns.extend(_detect_naming_patterns(tree))
                patterns.extend(_detect_structure_patterns(source, tree))
            except SyntaxError:
                pass

        # Build recipe
        base_name = Path(source_path).stem if source_path else "forged"
        recipe_id = f"forged-{base_name}"

        desc_parts = [f"Pattern extracted from {Path(source_path).name}:" if source_path else "Extracted patterns:"]
        for p in patterns:
            desc_parts.append(f"  - {p.description}")

        prompt = self._build_prompt_template(patterns)

        selector = f"*.{language[:2]}" if language != "python" else "*.py"

        tags = list({p.pattern_type for p in patterns})
        tags.append("forged")

        recipe = ForgedRecipe(
            id=recipe_id,
            name=f"{base_name.replace('_', ' ').title()} Pattern",
            description="\n".join(desc_parts),
            source_file=source_path,
            patterns=patterns,
            selector_glob=selector,
            prompt_template=prompt,
            tags=sorted(tags),
            language=language,
        )

        logger.info(
            "recipe_forged",
            id=recipe_id,
            patterns=len(patterns),
            source=source_path,
        )

        return recipe

    def _build_prompt_template(self, patterns: List[CodePattern]) -> str:
        """Generate a prompt template from detected patterns."""
        rules = []
        for p in patterns:
            rules.append(f"- {p.description}")
            if p.regex:
                rules.append(f"  Pattern: `{p.regex}`")
            if p.example:
                rules.append(f"  Example: {p.example.split(chr(10))[0]}")

        return textwrap.dedent(f"""\
            Refactor the code to follow these patterns:
            {chr(10).join(rules)}

            Ensure all changes maintain backward compatibility.
            Do not change function signatures or public APIs.""")

    @staticmethod
    def _detect_language(path: Path) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".css": "css",
        }
        return ext_map.get(path.suffix, "python")
