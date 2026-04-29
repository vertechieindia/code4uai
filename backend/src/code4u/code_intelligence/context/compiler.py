from __future__ import annotations
"""Context compiler for code4u.ai.

Compiles structured context from:
- Knowledge Graph traversal
- Impact analysis
- Ownership data
- Constraints and rules

Day 3: File-based symbol resolution. Exact name match; 0 or >1 matches fail.
Day 4: Direct file-level dependency traversal by symbol name substring. No KG/LLM.
Day 5: Ownership resolution via CODEOWNERS. Last-match-wins; no enforcement.
Day 6: Context assembly from resolved symbol, dependents, ownership. Immutable blast-radius object.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import fnmatch
import os
import re
import structlog

logger = structlog.get_logger("context.compiler")


# ----- Day 3: Symbol resolution (strict, file-only) -----

@dataclass
class ResolvedSymbol:
    """Single resolved symbol. Returned only when exactly one match exists."""
    name: str
    kind: str  # function | class | method | variable | interface | type | enum
    file_path: str
    start_line: int
    end_line: int
    language: str


class SymbolNotFoundError(Exception):
    """Raised when symbol_name has zero matches in file. Do not guess."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class AmbiguousSymbolError(Exception):
    """Raised when symbol_name has more than one match in file. Do not pick first."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


def _day3_read_file(file_path: str) -> str:
    """Read file contents from disk. Raises if file missing or not a file."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not p.is_file():
        raise ValueError(f"Not a file: {file_path}")
    return p.read_text()


def _day3_extract_candidates_python(content: str) -> List[Tuple[str, str, int, int]]:
    """
    Full language-aware parsing for Python using the ast module.
    Extracts: function (incl. async), class, method (inside class), variable (top-level assign).
    Returns (name, kind, start_line, end_line). end_lineno used when available (Python 3.8+).
    """
    import ast
    candidates: List[Tuple[str, str, int, int]] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    def end_line(node: ast.AST) -> int:
        if hasattr(node, "end_lineno") and node.end_lineno is not None:
            return node.end_lineno
        return node.lineno

    def visit_function(node: ast.FunctionDef, kind: str) -> None:
        candidates.append((node.name, kind, node.lineno, end_line(node)))

    def visit_class(node: ast.ClassDef) -> None:
        candidates.append((node.name, "class", node.lineno, end_line(node)))
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                visit_function(item, "method")
            elif isinstance(item, ast.AsyncFunctionDef):
                visit_function(item, "method")

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            visit_function(node, "function")
        elif isinstance(node, ast.AsyncFunctionDef):
            visit_function(node, "function")
        elif isinstance(node, ast.ClassDef):
            visit_class(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store):
                    candidates.append((target.id, "variable", node.lineno, end_line(node)))
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.target.ctx, ast.Store):
                candidates.append((node.target.id, "variable", node.lineno, end_line(node)))

    return candidates


def _day3_extract_candidates_ts_js(content: str) -> List[Tuple[str, str, int, int]]:
    """
    Full explicit language-aware parsing for TypeScript/JavaScript.
    No AST library; explicit regex patterns for every supported construct.
    Supported kinds: function, class, method, variable, interface, type, enum.
    """
    candidates: List[Tuple[str, str, int, int]] = []
    lines = content.splitlines()
    num_lines = len(lines)

    # Explicit patterns (order matters: function-like const before variable const)
    PATTERNS: List[Tuple[str, str, re.Pattern]] = [
        # Top-level / exported function (named)
        ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(")),
        # Class
        ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)\s*[\s{<]")),
        # TypeScript: interface
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+(\w+)\s*[\s{<]")),
        # TypeScript: type alias
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+(\w+)\s*=")),
        # TypeScript: enum
        ("enum", re.compile(r"^\s*(?:export\s+)?enum\s+(\w+)\s*[\s{]")),
        # Arrow / function assigned to const (must come before generic const variable)
        ("function", re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\s*\([^)]*\)\s*=>")),
        ("function", re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\s*function\s*\(")),
        # const binding (variable)
        ("variable", re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*=")),
        # let binding (variable)
        ("variable", re.compile(r"^\s*let\s+(\w+)\s*=")),
        # var binding (variable)
        ("variable", re.compile(r"^\s*var\s+(\w+)\s*=")),
    ]

    for i, line in enumerate(lines):
        one_based = i + 1
        for kind, pattern in PATTERNS:
            m = pattern.match(line)
            if m:
                name = m.group(1)
                candidates.append((name, kind, one_based, one_based))
                break

    # Explicit method detection: inside class body (indented lines after "class X {")
    in_class = False
    class_indent = -1
    for i, line in enumerate(lines):
        one_based = i + 1
        stripped = line.lstrip()
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        if in_class:
            if indent == class_indent and stripped.startswith("}"):
                in_class = False
                continue
            if indent > class_indent:
                method_match = re.match(
                    r"\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*[\s:{]",
                    line
                )
                if method_match:
                    candidates.append((method_match.group(1), "method", one_based, one_based))
                get_set_match = re.match(r"\s*(?:get|set)\s+(\w+)\s*\(", line)
                if get_set_match:
                    candidates.append((get_set_match.group(1), "method", one_based, one_based))
        if re.match(r"^\s*(?:export\s+)?(?:default\s+)?class\s+\w+", line):
            in_class = True
            class_indent = indent

    if not candidates:
        return candidates
    candidates.sort(key=lambda c: (c[2], c[0]))
    # Compute end_line: next symbol start - 1, or last line of file
    result: List[Tuple[str, str, int, int]] = []
    for j, (name, kind, start, _) in enumerate(candidates):
        if j + 1 < len(candidates):
            end = candidates[j + 1][2] - 1
        else:
            end = num_lines
        result.append((name, kind, start, end))
    return result


def resolve_symbol(file_path: str, symbol_name: str, language: str) -> ResolvedSymbol:
    """
    Resolve exactly one symbol in the given file. File-based only; no other files, KG, or LLM.
    Exact case-sensitive name match. 0 matches → SymbolNotFoundError; >1 → AmbiguousSymbolError.
    """
    content = _day3_read_file(file_path)
    if language == "python":
        candidates = _day3_extract_candidates_python(content)
    elif language in ("typescript", "javascript"):
        candidates = _day3_extract_candidates_ts_js(content)
    else:
        candidates = []
    matches = [c for c in candidates if c[0] == symbol_name]
    if len(matches) == 0:
        raise SymbolNotFoundError(
            message=f"Symbol '{symbol_name}' not found in {file_path}"
        )
    if len(matches) > 1:
        raise AmbiguousSymbolError(
            message=f"Multiple symbols named '{symbol_name}' found in {file_path}"
        )
    name, kind, start_line, end_line = matches[0]
    return ResolvedSymbol(
        name=name,
        kind=kind,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language=language,
    )


# ----- Day 4: Dependency traversal (mechanical, substring-only) -----

_DAY4_SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"})

_DAY4_EXTENSIONS_BY_LANGUAGE: Dict[str, Tuple[str, ...]] = {
    "python": (".py",),
    "javascript": (".js",),
    "typescript": (".ts", ".tsx",),
}


def get_direct_dependencies(resolved_symbol: ResolvedSymbol, repo_root: str) -> List[str]:
    """
    Given a ResolvedSymbol, return file paths (relative to repo_root) that contain
    the symbol name as a case-sensitive substring. Defining file is excluded.
    No KG, embeddings, or LLMs. Deterministic order (sorted).
    """
    # 1. Validate resolved_symbol fields
    if not hasattr(resolved_symbol, "name") or resolved_symbol.name is None:
        raise ValueError("resolved_symbol.name is required")
    if not hasattr(resolved_symbol, "file_path") or resolved_symbol.file_path is None:
        raise ValueError("resolved_symbol.file_path is required")
    if not hasattr(resolved_symbol, "language") or resolved_symbol.language is None:
        raise ValueError("resolved_symbol.language is required")
    symbol_name = str(resolved_symbol.name).strip()
    if not symbol_name:
        raise ValueError("resolved_symbol.name must be non-empty")

    # 2. Validate repo_root
    repo_path = Path(repo_root)
    if not repo_path.exists():
        raise FileNotFoundError(f"repo_root does not exist: {repo_root}")
    if not repo_path.is_dir():
        raise NotADirectoryError(f"repo_root is not a directory: {repo_root}")
    repo_resolved = repo_path.resolve()

    language = resolved_symbol.language
    if language not in _DAY4_EXTENSIONS_BY_LANGUAGE:
        return []
    allowed_extensions = _DAY4_EXTENSIONS_BY_LANGUAGE[language]

    defining_path = Path(resolved_symbol.file_path)
    if not defining_path.is_absolute():
        defining_path = (repo_resolved / resolved_symbol.file_path).resolve()
    else:
        defining_path = defining_path.resolve()

    dependent_relative_paths: List[str] = []

    # 3. Walk repository files under repo_root (do not follow symlinks)
    for dirpath, dirnames, filenames in os.walk(repo_root, followlinks=False):
        dirpath_resolved = Path(dirpath).resolve()
        if not str(dirpath_resolved).startswith(str(repo_resolved)):
            continue
        # 4. Filter directories: skip excluded and hidden
        dirnames[:] = [
            d for d in dirnames
            if d not in _DAY4_SKIP_DIRS and not d.startswith(".")
        ]
        for filename in filenames:
            suf = Path(filename).suffix.lower()
            if suf not in allowed_extensions:
                continue
            full_path = dirpath_resolved / filename
            if full_path.is_symlink():
                continue
            if not full_path.is_file():
                continue
            if full_path.resolve() == defining_path:
                continue
            try:
                content = full_path.read_text(encoding="utf-8")
            except Exception as e:
                raise OSError(f"Could not read file {full_path}: {e}") from e
            if symbol_name in content:
                try:
                    rel = full_path.relative_to(repo_resolved)
                except ValueError:
                    continue
                dependent_relative_paths.append(rel.as_posix())

    # 5. Sort results deterministically
    dependent_relative_paths.sort()
    return dependent_relative_paths


# ----- Day 5: Ownership resolution (CODEOWNERS, last-match-wins) -----

_DAY5_CODEOWNERS_LOCATIONS = (
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
)


def _day5_find_codeowners(repo_root: str) -> Optional[Path]:
    """Return first existing CODEOWNERS path under repo_root, or None."""
    repo_path = Path(repo_root)
    if not repo_path.exists() or not repo_path.is_dir():
        raise NotADirectoryError(f"repo_root is not a directory: {repo_root}")
    for rel in _DAY5_CODEOWNERS_LOCATIONS:
        candidate = repo_path / rel
        if candidate.is_file():
            return candidate
    return None


def _day5_parse_codeowners(file_path: Path) -> List[Tuple[str, List[str]]]:
    """Parse CODEOWNERS into list of (pattern, owners). Raises on parse/read error."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise OSError(f"Could not read CODEOWNERS {file_path}: {e}") from e
    rules: List[Tuple[str, List[str]]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        comment_pos = line.find("#")
        if comment_pos >= 0:
            line = line[:comment_pos].strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
        pattern = parts[0]
        owners = parts[1:]
        rules.append((pattern, list(owners)))
    return rules


def _day5_pattern_matches(path: str, pattern: str) -> bool:
    """Simple glob: pattern matches path (relative to repo root). Last-match semantics applied by caller."""
    path = path.strip()
    pattern = pattern.strip()
    if pattern == "*":
        return True
    if pattern.startswith("/"):
        pattern = pattern[1:]
    pattern = pattern.rstrip("/")
    if not pattern:
        return True
    if path == pattern:
        return True
    if path.startswith(pattern + "/"):
        return True
    if "*" in pattern:
        return fnmatch.fnmatch(path, pattern)
    return False


def resolve_ownership(affected_files: List[str], repo_root: str) -> Dict[str, List[str]]:
    """
    Given affected file paths (relative to repo_root), return file_path → owners.
    Owners from CODEOWNERS; last matching rule wins. Unowned → [].
    No enforcement; no default owners.
    """
    repo_path = Path(repo_root)
    if not repo_path.exists():
        raise FileNotFoundError(f"repo_root does not exist: {repo_root}")
    if not repo_path.is_dir():
        raise NotADirectoryError(f"repo_root is not a directory: {repo_root}")

    result: Dict[str, List[str]] = {f: [] for f in affected_files}

    codeowners_path = _day5_find_codeowners(repo_root)
    if codeowners_path is None:
        return result

    try:
        rules = _day5_parse_codeowners(codeowners_path)
    except Exception:
        raise

    for f in affected_files:
        if f is None or not isinstance(f, str):
            raise ValueError(f"Invalid file path in affected_files: {f!r}")
        path = f.strip()
        owners_for_file: List[str] = []
        for pattern, rule_owners in rules:
            if _day5_pattern_matches(path, pattern):
                owners_for_file = list(rule_owners)
        result[f] = owners_for_file

    return result


# ----- Day 6: Context assembly (composition only, immutable) -----
# ----- Day 7: Context freeze & contract lock (immutable, documented, guarded) -----

"""
RefactorBlastContext — Contract (Day 7 lock)

What it represents:
  The full blast radius of a refactor: one resolved symbol, its defining file,
  all affected files (defining + dependents), ownership per file, and blast-radius
  metrics (file_count, has_cross_owner). Assembled once from ResolvedSymbol,
  dependent_files, and ownership_map; no recomputation.

Guarantees:
  - Immutable: frozen dataclass; no mutable defaults; stored collections are
    immutable (tuples) so downstream cannot mutate context.
  - Complete: is_complete is always True at construction and cannot be changed.
  - Authoritative: downstream must not recompute, add lazy fields, or ignore
    context fields.

What it does NOT do:
  - Does not enforce permissions or approvals.
  - Does not validate beyond assembly requirements (ownership present for each
    affected file). Does not perform symbol resolution, dependency traversal, or
    CODEOWNERS parsing — those are inputs to assembly only.
"""


@dataclass(frozen=True)
class RefactorBlastContext:
    """
    Assembled refactor context with full blast radius. Immutable and complete.
    Built only via assemble_refactor_context(...) from resolved_symbol,
    dependent_files, and ownership_map. Do not mutate; do not reassemble.
    """
    symbol: ResolvedSymbol
    defining_file: str
    affected_files: Tuple[str, ...]
    _ownership: Tuple[Tuple[str, Tuple[str, ...]], ...]
    _blast_radius: Tuple[Tuple[str, Any], ...]
    is_complete: bool = True

    @property
    def ownership(self) -> Dict[str, List[str]]:
        """Read-only ownership (copy). Do not mutate."""
        return {path: list(owners) for path, owners in self._ownership}

    @property
    def blast_radius(self) -> Dict[str, Any]:
        """Read-only blast_radius (copy). Do not mutate."""
        return dict(self._blast_radius)


def assemble_refactor_context(
    resolved_symbol: ResolvedSymbol,
    dependent_files: List[str],
    ownership_map: Dict[str, List[str]],
) -> RefactorBlastContext:
    """
    Assemble final refactor context from already-computed parts.
    No recomputation. Affected files = defining file first, then dependents sorted.
    Every affected file must exist in ownership_map. Blast radius computed explicitly.
    Raises if inputs appear already assembled (e.g. RefactorBlastContext passed).
    """
    if resolved_symbol is None:
        raise ValueError("resolved_symbol is required")
    if dependent_files is None:
        raise ValueError("dependent_files is required")
    if ownership_map is None:
        raise ValueError("ownership_map is required")
    if isinstance(resolved_symbol, RefactorBlastContext):
        raise ValueError("resolved_symbol must be ResolvedSymbol; context already assembled")
    if not isinstance(resolved_symbol, ResolvedSymbol):
        raise ValueError("resolved_symbol must be a ResolvedSymbol instance")

    defining_file = resolved_symbol.file_path
    dependents_sorted = sorted(dependent_files)
    affected_files = [defining_file] + dependents_sorted

    for f in affected_files:
        if f not in ownership_map:
            raise ValueError(f"Affected file missing from ownership_map: {f!r}")

    ownership_subset = {f: list(ownership_map[f]) for f in affected_files}

    non_empty_sets: set = set()
    for f in affected_files:
        owners = ownership_map[f]
        if owners:
            non_empty_sets.add(tuple(sorted(owners)))
    has_cross_owner = len(non_empty_sets) > 1

    blast_radius_tuple = (("file_count", len(affected_files)), ("has_cross_owner", has_cross_owner))
    ownership_tuple = tuple((path, tuple(ownership_subset[path])) for path in affected_files)

    return RefactorBlastContext(
        symbol=resolved_symbol,
        defining_file=defining_file,
        affected_files=tuple(affected_files),
        _ownership=ownership_tuple,
        _blast_radius=blast_radius_tuple,
        is_complete=True,
    )


def _codeowners_repo_root(workspace_path: str) -> str:
    """Return workspace path as repo root for impact (single-repo default)."""
    return (Path(workspace_path).resolve()).as_posix()


def _load_owner_teams_from_codeowners(workspace_path: str, primary_file_path: str) -> List[str]:
    """Load owner teams from CODEOWNERS if present."""
    root = Path(workspace_path)
    for codeowners in [root / "CODEOWNERS", root / ".github" / "CODEOWNERS", root / "docs" / "CODEOWNERS"]:
        if not codeowners.is_file():
            continue
        try:
            content = codeowners.read_text()
            rel = Path(primary_file_path).resolve().relative_to(root.resolve()).as_posix()
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                pattern, *owners = parts
                if pattern.startswith("/"):
                    pattern = pattern[1:]
                if not pattern or rel.startswith(pattern) or pattern == "*":
                    return [o.lstrip("@") for o in owners if o.startswith("@")][:10]
        except Exception:
            continue
    return []


def _infer_breaking(task_type: str, intent: str) -> bool:
    """Infer if the task is likely breaking from type and intent."""
    if task_type in ("schema_evolution", "delete"):
        return True
    intent_lower = intent.lower()
    if any(w in intent_lower for w in ["breaking", "remove", "delete", "rename api", "change contract"]):
        return True
    return False


def _resolve_import_to_paths(imp: str, primary_path: Path, root: Path, language: str) -> List[Path]:
    """Resolve an import specifier to candidate file paths under workspace."""
    candidates: List[Path] = []
    imp = imp.strip().strip("'\"").split(";")[0].strip()
    if not imp:
        return []
    if language in ("typescript", "javascript"):
        base = primary_path.parent
        if imp.startswith("."):
            resolved = (base / imp).resolve()
        else:
            resolved = root / "node_modules" / imp
        for ext in ("", ".ts", ".tsx", ".js", ".jsx"):
            candidates.append(Path(str(resolved) + ext))
        candidates.append(resolved / "index.ts")
        candidates.append(resolved / "index.tsx")
        candidates.append(resolved / "index.js")
    elif language == "python":
        mod = imp.replace(".", os.sep)
        candidates.append(root / f"{mod}.py")
        candidates.append(root / mod / "__init__.py")
    return candidates


@dataclass
class RefactorContext:
    """
    Day-2 refactor context: real file + symbol only.
    No fake placeholders. Built from disk read + intent.
    """
    target_file: str
    target_symbol: str
    language: str
    file_content: str
    intent: str


@dataclass
class FileContext:
    """Context for a single file."""
    path: str
    language: str
    content: str
    symbols: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)


@dataclass
class CompiledContext:
    """
    Fully compiled context for LLM consumption.
    
    This is what gets sent to the LLM, NOT raw code dumps.
    """
    # Intent
    intent: str
    task_type: str
    
    # Scope
    primary_file: FileContext
    related_files: list[FileContext] = field(default_factory=list)
    
    # Metadata
    language: str = "typescript"
    frameworks: List[str] = field(default_factory=list)
    
    # Constraints
    constraints: List[str] = field(default_factory=list)
    
    # Impact
    affected_components: List[str] = field(default_factory=list)
    affected_repositories: List[str] = field(default_factory=list)
    owner_teams: List[str] = field(default_factory=list)
    
    # Flags
    breaking_change: bool = False
    requires_migration: bool = False
    
    def to_llm_context(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM prompt."""
        return {
            "language": self.language,
            "frameworks": self.frameworks,
            "file_path": self.primary_file.path,
            "affected_components": self.affected_components,
            "owner_teams": self.owner_teams,
            "breaking_change": self.breaking_change,
        }
    
    @property
    def estimated_tokens(self) -> int:
        """Estimate token count for routing."""
        # Rough estimate: 1 token ≈ 4 chars
        total_chars = len(self.primary_file.content)
        total_chars += sum(len(f.content) for f in self.related_files)
        total_chars += len(self.intent) + len(str(self.constraints))
        return total_chars // 4


class ContextCompiler:
    """Compile context from various sources.

    The compiler NEVER loads entire repositories.
    It selects ONLY what's needed based on:
    - Symbol dependencies (via DependencyMap or substring scan)
    - API contracts
    - Ownership boundaries

    If a ``DependencyMap`` is provided, dependency discovery uses the
    pre-built import index (O(1) lookup) instead of the O(n) substring
    walk in ``get_direct_dependencies``.
    """

    def __init__(
        self,
        knowledge_graph: Optional[Any] = None,
        dependency_map: Optional[Any] = None,
    ):
        self.logger = logger
        self._kg = knowledge_graph
        self._dep_map = dependency_map

    async def compile_refactor_context(
        self,
        intent: str,
        primary_file_path: str,
        workspace_path: str,
    ) -> RefactorContext:
        """
        Build refactor context from real filesystem. No mocks.
        - Reads target file from disk (raises on failure).
        - Resolves target symbol from intent (string match acceptable).
        Returns RefactorContext with target_symbol, target_file, language.
        """
        if not primary_file_path or not primary_file_path.strip():
            raise ValueError("primary_file_path is required")
        content = await self._read_file_strict(primary_file_path)
        language = self._detect_language(primary_file_path)
        target_symbol = self._resolve_symbol_from_intent(intent, content, language)
        return RefactorContext(
            target_file=primary_file_path,
            target_symbol=target_symbol,
            language=language,
            file_content=content,
            intent=intent,
        )

    async def compile_refactor_blast_context(
        self,
        intent: str,
        primary_file_path: str,
        workspace_path: str,
    ) -> RefactorBlastContext:
        """Build ``RefactorBlastContext`` for the full pipeline.

        Steps:
          1. Resolve the primary file path against the workspace.
          2. Read the file and detect the language.
          3. Extract the target symbol name from the intent.
          4. Resolve the symbol definition in the file.
          5. Find dependent files — via ``DependencyMap`` (if available)
             or fallback to substring-based ``get_direct_dependencies``.
          6. Resolve CODEOWNERS ownership.
          7. Assemble the immutable ``RefactorBlastContext``.

        Returns immutable blast context with absolute-path affected_files.
        """
        if not primary_file_path or not primary_file_path.strip():
            raise ValueError("primary_file_path is required")
        if not workspace_path or not str(workspace_path).strip():
            raise ValueError("workspace_path is required")

        repo_resolved = Path(workspace_path).resolve()
        p = Path(primary_file_path)
        path_to_read = (repo_resolved / p) if not p.is_absolute() else p
        content = await self._read_file_strict(str(path_to_read.resolve()))
        language = self._detect_language(primary_file_path)
        symbol_name = self._resolve_symbol_from_intent(intent, content, language)
        if not symbol_name or not str(symbol_name).strip():
            raise ValueError("Could not resolve symbol name from intent")

        defining_abs = str(path_to_read.resolve())
        resolved = resolve_symbol(defining_abs, symbol_name, language)

        # -- Dependency discovery --
        if self._dep_map is not None and self._dep_map.has_symbol(symbol_name):
            dependents_abs = [
                f for f in self._dep_map.get_dependents(symbol_name)
                if f != defining_abs
            ]
            self.logger.info(
                "deps_from_index",
                symbol=symbol_name,
                count=len(dependents_abs),
            )
        else:
            dependents_rel = get_direct_dependencies(resolved, workspace_path)
            dependents_abs = [
                str(repo_resolved / dp) for dp in dependents_rel
            ]

        # -- Ownership --
        # In multi-root scenarios, some dependents may live outside the
        # primary workspace root.  Make paths relative when possible; use
        # absolute paths as-is when the file is in a different root.
        def _safe_rel(abs_path: str) -> str:
            try:
                return Path(abs_path).relative_to(repo_resolved).as_posix()
            except ValueError:
                return abs_path

        defining_rel = _safe_rel(defining_abs)
        dependents_rel_for_ownership = [_safe_rel(d) for d in dependents_abs]
        affected_rel = [defining_rel] + sorted(dependents_rel_for_ownership)
        ownership_map_rel = resolve_ownership(affected_rel, workspace_path)

        # Map ownership back to absolute paths
        ownership_abs: Dict[str, List[str]] = {}
        for k, v in ownership_map_rel.items():
            if Path(k).is_absolute():
                ownership_abs[k] = list(v)
            else:
                ownership_abs[str(repo_resolved / k)] = list(v)

        return assemble_refactor_context(resolved, dependents_abs, ownership_abs)

    async def compile(
        self,
        intent: str,
        primary_file_path: str,
        workspace_path: str,
        selection: Dict[str, int] | None = None
    ) -> CompiledContext:
        """
        Compile context for a refactoring operation.
        
        Args:
            intent: What the user wants to do
            primary_file_path: The main file being edited
            workspace_path: Root of the workspace
            selection: Optional {start, end} line selection
        """
        self.logger.info(
            "compiling_context",
            intent=intent,
            file=primary_file_path
        )
        
        # Read primary file
        primary_content = await self._read_file(primary_file_path)
        if selection:
            lines = primary_content.split("\n")
            primary_content = "\n".join(
                lines[selection["start"]:selection["end"] + 1]
            )
        
        # Detect language and frameworks
        language = self._detect_language(primary_file_path)
        frameworks = self._detect_frameworks(primary_content, language)
        
        # Create primary file context
        primary_file = FileContext(
            path=primary_file_path,
            language=language,
            content=primary_content,
            symbols=self._extract_symbols(primary_content, language),
            imports=self._extract_imports(primary_content, language),
            exports=self._extract_exports(primary_content, language),
        )
        
        # Find related files (based on imports and usage)
        related_files = await self._find_related_files(
            primary_file, workspace_path
        )
        
        # Determine task type from intent
        task_type = self._classify_task(intent)
        
        # Build constraints based on context
        constraints = self._build_constraints(
            task_type, language, frameworks
        )
        
        affected_components = list(primary_file.exports)
        affected_repositories: List[str] = []
        owner_teams: List[str] = []

        if self._kg:
            try:
                from code4u.code_intelligence.knowledge_graph.models import NodeType, RelationType
                nodes = self._kg.find_nodes(file_path=primary_file_path)
                if nodes:
                    node_id = nodes[0].id
                    impact = self._kg.analyze_impact(node_id, max_depth=5)
                    affected_repositories = list(set(impact.impacted_files))[:20]
                    owner_teams = list(impact.requires_approval_from or impact.impacted_teams)
                    if impact.impacted_functions:
                        affected_components = list(set(affected_components) | set(impact.impacted_functions))[:50]
            except Exception as e:
                self.logger.warning("kg_impact_failed", error=str(e))
        if not affected_repositories:
            affected_repositories = [_codeowners_repo_root(workspace_path)]
        if not owner_teams:
            owner_teams = _load_owner_teams_from_codeowners(workspace_path, primary_file_path)

        return CompiledContext(
            intent=intent,
            task_type=task_type,
            primary_file=primary_file,
            related_files=related_files,
            language=language,
            frameworks=frameworks,
            constraints=constraints,
            affected_components=affected_components,
            affected_repositories=affected_repositories,
            owner_teams=owner_teams,
            breaking_change=_infer_breaking(task_type, intent),
        )
    
    async def _read_file(self, path: str) -> str:
        """Read file content (returns empty string on error)."""
        try:
            return Path(path).read_text()
        except Exception:
            return ""

    async def _read_file_strict(self, path: str) -> str:
        """Read file from disk. Raises on failure (no fake content)."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Target file not found: {path}")
        if not p.is_file():
            raise ValueError(f"Not a file: {path}")
        return p.read_text()

    def _resolve_symbol_from_intent(self, intent: str, file_content: str, language: str) -> str:
        """Resolve symbol name from intent (string match acceptable for Day 2)."""
        import re
        intent_lower = intent.strip().lower()
        if "rename" in intent_lower and " to " in intent_lower:
            parts = intent.strip().split()
            for i, w in enumerate(parts):
                if w.lower() == "to" and i >= 1:
                    return parts[i - 1]
            if len(parts) >= 2:
                return parts[1]
        if "symbol" in intent_lower or "refactor" in intent_lower:
            for word in intent.split():
                if len(word) > 1 and word.isidentifier():
                    symbols = self._extract_symbols(file_content, language)
                    if word in symbols:
                        return word
        symbols = self._extract_symbols(file_content, language)
        return symbols[0] if symbols else ""
    
    def _detect_language(self, path: str) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".ts": "typescript", ".tsx": "typescript",
            ".js": "javascript", ".jsx": "javascript",
            ".py": "python",
            ".go": "go",
            ".rs": "rust",
        }
        from pathlib import Path
        ext = Path(path).suffix.lower()
        return ext_map.get(ext, "unknown")
    
    def _detect_frameworks(self, content: str, language: str) -> List[str]:
        """Detect frameworks from imports."""
        frameworks = []
        
        if language in ("typescript", "javascript"):
            if "from 'react'" in content or "from \"react\"" in content:
                frameworks.append("react")
            if "from 'next'" in content:
                frameworks.append("nextjs")
            if "@nestjs" in content:
                frameworks.append("nestjs")
        
        if language == "python":
            if "from fastapi" in content or "import fastapi" in content:
                frameworks.append("fastapi")
            if "from pydantic" in content:
                frameworks.append("pydantic")
            if "from django" in content:
                frameworks.append("django")
        
        return frameworks
    
    def _extract_symbols(self, content: str, language: str) -> List[str]:
        """Extract symbol names from code."""
        symbols = []
        import re
        
        if language in ("typescript", "javascript"):
            # Functions and classes
            patterns = [
                r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
                r"(?:export\s+)?class\s+(\w+)",
                r"(?:export\s+)?(?:const|let|var)\s+(\w+)",
                r"(?:export\s+)?interface\s+(\w+)",
                r"(?:export\s+)?type\s+(\w+)",
            ]
            for pattern in patterns:
                symbols.extend(re.findall(pattern, content))
        
        elif language == "python":
            patterns = [
                r"^def\s+(\w+)",
                r"^class\s+(\w+)",
                r"^(\w+)\s*=",
            ]
            for pattern in patterns:
                symbols.extend(re.findall(pattern, content, re.MULTILINE))
        
        return list(set(symbols))
    
    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements."""
        imports = []
        import re
        
        if language in ("typescript", "javascript"):
            pattern = r"import\s+.*?from\s+['\"](.+?)['\"]"
            imports = re.findall(pattern, content)
        
        elif language == "python":
            patterns = [
                r"^from\s+(\S+)\s+import",
                r"^import\s+(\S+)",
            ]
            for pattern in patterns:
                imports.extend(re.findall(pattern, content, re.MULTILINE))
        
        return imports
    
    def _extract_exports(self, content: str, language: str) -> List[str]:
        """Extract exported symbols."""
        exports = []
        import re
        
        if language in ("typescript", "javascript"):
            pattern = r"export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type)\s+(\w+)"
            exports = re.findall(pattern, content)
        
        elif language == "python":
            # Python: Look for __all__ or public functions
            all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", content, re.DOTALL)
            if all_match:
                exports = re.findall(r"['\"](\w+)['\"]", all_match.group(1))
            else:
                # Public functions (not starting with _)
                exports = [s for s in self._extract_symbols(content, language) if not s.startswith("_")]
        
        return exports
    
    async def _find_related_files(
        self,
        primary: FileContext,
        workspace_path: str
    ) -> list[FileContext]:
        """Find files related to the primary file via Knowledge Graph or import resolution."""
        related: List[FileContext] = []
        root = Path(workspace_path)
        primary_path = Path(primary.path)

        if self._kg:
            try:
                from code4u.code_intelligence.knowledge_graph.models import NodeType, RelationType
                nodes = self._kg.find_nodes(file_path=primary.path)
                seen_paths: set[str] = {primary.path}
                for node in nodes:
                    for rel in self._kg.get_outgoing(node.id, RelationType.IMPORTS):
                        target = self._kg.get_node(rel.target_id)
                        if target and target.file_path and target.file_path not in seen_paths:
                            seen_paths.add(target.file_path)
                            content = await self._read_file(target.file_path)
                            lang = self._detect_language(target.file_path)
                            related.append(FileContext(
                                path=target.file_path,
                                language=lang,
                                content=content,
                                symbols=self._extract_symbols(content, lang),
                                imports=self._extract_imports(content, lang),
                                exports=self._extract_exports(content, lang),
                            ))
                    for rel in self._kg.get_outgoing(node.id, RelationType.DEPENDS_ON):
                        target = self._kg.get_node(rel.target_id)
                        if target and target.file_path and target.file_path not in seen_paths:
                            seen_paths.add(target.file_path)
                            content = await self._read_file(target.file_path)
                            lang = self._detect_language(target.file_path)
                            related.append(FileContext(
                                path=target.file_path,
                                language=lang,
                                content=content,
                                symbols=self._extract_symbols(content, lang),
                                imports=self._extract_imports(content, lang),
                                exports=self._extract_exports(content, lang),
                            ))
                return related[:15]
            except Exception as e:
                self.logger.warning("kg_related_files_failed", error=str(e))

        for imp in primary.imports[:20]:
            candidate_paths = _resolve_import_to_paths(imp, primary_path, root, primary.language)
            for p in candidate_paths:
                if p == primary.path:
                    continue
                if not p.exists() or not p.is_file():
                    continue
                try:
                    content = await self._read_file(str(p))
                    if not content:
                        continue
                    path_str = str(p)
                    lang = self._detect_language(path_str)
                    related.append(FileContext(
                        path=path_str,
                        language=lang,
                        content=content,
                        symbols=self._extract_symbols(content, lang),
                        imports=self._extract_imports(content, lang),
                        exports=self._extract_exports(content, lang),
                    ))
                except Exception:
                    continue
        return related[:15]
    
    def _classify_task(self, intent: str) -> str:
        """Classify the task type from user intent."""
        intent_lower = intent.lower()
        
        if any(w in intent_lower for w in ["rename", "change name"]):
            return "rename"
        if any(w in intent_lower for w in ["extract", "pull out"]):
            return "extract_function"
        if any(w in intent_lower for w in ["inline", "merge"]):
            return "inline"
        if any(w in intent_lower for w in ["move", "relocate"]):
            return "move"
        if any(w in intent_lower for w in ["add field", "new property"]):
            return "schema_evolution"
        if any(w in intent_lower for w in ["delete", "remove"]):
            return "delete"
        
        return "refactor"
    
    def _build_constraints(
        self,
        task_type: str,
        language: str,
        frameworks: List[str]
    ) -> List[str]:
        """Build constraints for the task."""
        constraints = [
            "Preserve existing functionality",
            "Maintain type safety",
            "Follow existing code style",
        ]
        
        if task_type == "rename":
            constraints.append("Update all references within scope")
        
        if task_type == "schema_evolution":
            constraints.extend([
                "Ensure backward compatibility if possible",
                "Flag breaking changes explicitly",
            ])
        
        if "react" in frameworks:
            constraints.append("Preserve React component lifecycle")
        
        if "fastapi" in frameworks:
            constraints.extend([
                "Preserve Pydantic model validation",
                "Maintain async/await correctness",
            ])
        
        return constraints

