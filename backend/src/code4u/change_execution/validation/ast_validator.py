from __future__ import annotations
"""AST-based validation for code4u.ai.

Ensures generated code is syntactically valid and preserves structure.
"""
import ast
from dataclasses import dataclass
from typing import List, Optional
import structlog

logger = structlog.get_logger("validation.ast")


@dataclass
class ASTValidationResult:
    """Result of AST validation."""
    valid: bool
    error: Optional[str] = None
    original_symbols: List[str] | None = None
    new_symbols: List[str] | None = None
    removed_symbols: List[str] | None = None
    added_symbols: List[str] | None = None


class ASTValidator:
    """
    Validate code using AST analysis.
    
    Checks:
    - Syntax validity
    - Symbol preservation (no accidental deletions)
    - Type annotation consistency
    """
    
    def validate_python(self, code: str) -> ASTValidationResult:
        """Validate Python code syntax."""
        try:
            tree = ast.parse(code)
            symbols = self._extract_python_symbols(tree)
            
            return ASTValidationResult(
                valid=True,
                original_symbols=symbols
            )
            
        except SyntaxError as e:
            return ASTValidationResult(
                valid=False,
                error=f"Syntax error at line {e.lineno}: {e.msg}"
            )
    
    def validate_python_change(
        self,
        original: str,
        modified: str,
        allow_removals: bool = False
    ) -> ASTValidationResult:
        """
        Validate a Python code change.
        
        Ensures:
        - Modified code is syntactically valid
        - No symbols accidentally removed (unless allowed)
        """
        try:
            original_tree = ast.parse(original)
            modified_tree = ast.parse(modified)
            
            original_symbols = set(self._extract_python_symbols(original_tree))
            modified_symbols = set(self._extract_python_symbols(modified_tree))
            
            removed = original_symbols - modified_symbols
            added = modified_symbols - original_symbols
            
            if removed and not allow_removals:
                return ASTValidationResult(
                    valid=False,
                    error=f"Symbols removed: {', '.join(removed)}",
                    original_symbols=list(original_symbols),
                    new_symbols=list(modified_symbols),
                    removed_symbols=list(removed),
                    added_symbols=list(added)
                )
            
            return ASTValidationResult(
                valid=True,
                original_symbols=list(original_symbols),
                new_symbols=list(modified_symbols),
                removed_symbols=list(removed),
                added_symbols=list(added)
            )
            
        except SyntaxError as e:
            return ASTValidationResult(
                valid=False,
                error=f"Syntax error in modified code: {e.msg}"
            )
    
    def validate_typescript(self, code: str) -> ASTValidationResult:
        """
        Validate TypeScript code.
        
        Uses a simple heuristic check for now.
        Production would integrate with TypeScript compiler API.
        """
        # Basic structure checks
        issues = []
        
        # Check for balanced braces
        if code.count("{") != code.count("}"):
            return ASTValidationResult(
                valid=False,
                error="Unbalanced braces"
            )
        
        if code.count("(") != code.count(")"):
            return ASTValidationResult(
                valid=False,
                error="Unbalanced parentheses"
            )
        
        if code.count("[") != code.count("]"):
            return ASTValidationResult(
                valid=False,
                error="Unbalanced brackets"
            )
        
        # Extract symbols using regex
        symbols = self._extract_typescript_symbols(code)
        
        return ASTValidationResult(
            valid=True,
            original_symbols=symbols
        )
    
    def _extract_python_symbols(self, tree: ast.AST) -> List[str]:
        """Extract symbol names from Python AST."""
        symbols = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(f"function:{node.name}")
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(f"async_function:{node.name}")
            elif isinstance(node, ast.ClassDef):
                symbols.append(f"class:{node.name}")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        symbols.append(f"import:{alias.name}")
                else:
                    for alias in node.names:
                        symbols.append(f"from_import:{node.module}.{alias.name}")
        
        return symbols
    
    def _extract_typescript_symbols(self, code: str) -> List[str]:
        """Extract symbol names from TypeScript using regex."""
        import re
        symbols = []
        
        # Functions
        for match in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", code):
            symbols.append(f"function:{match.group(1)}")
        
        # Arrow functions assigned to const
        for match in re.finditer(r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>", code):
            symbols.append(f"const_function:{match.group(1)}")
        
        # Classes
        for match in re.finditer(r"(?:export\s+)?class\s+(\w+)", code):
            symbols.append(f"class:{match.group(1)}")
        
        # Interfaces
        for match in re.finditer(r"(?:export\s+)?interface\s+(\w+)", code):
            symbols.append(f"interface:{match.group(1)}")
        
        # Types
        for match in re.finditer(r"(?:export\s+)?type\s+(\w+)", code):
            symbols.append(f"type:{match.group(1)}")
        
        return symbols
    
    def check_type_consistency(
        self,
        code: str,
        language: str
    ) -> List[str]:
        """
        Check for type annotation consistency.
        
        Returns list of warnings.
        """
        warnings = []
        
        if language == "python":
            warnings.extend(self._check_python_types(code))
        elif language in ("typescript", "javascript"):
            warnings.extend(self._check_typescript_types(code))
        
        return warnings
    
    def _check_python_types(self, code: str) -> List[str]:
        """Check Python type annotations."""
        warnings = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check for missing return type
                    if node.returns is None and not node.name.startswith("_"):
                        warnings.append(
                            f"Function '{node.name}' missing return type annotation"
                        )
                    
                    # Check for missing argument types
                    for arg in node.args.args:
                        if arg.annotation is None and arg.arg != "self":
                            warnings.append(
                                f"Argument '{arg.arg}' in '{node.name}' missing type"
                            )
                            
        except SyntaxError:
            pass
        
        return warnings
    
    def _check_typescript_types(self, code: str) -> List[str]:
        """Check TypeScript type annotations."""
        import re
        warnings = []
        
        # Check for 'any' type usage
        any_matches = list(re.finditer(r":\s*any\b", code))
        if any_matches:
            warnings.append(
                f"Found {len(any_matches)} uses of 'any' type"
            )
        
        # Check for missing return types on exported functions
        export_funcs = re.finditer(
            r"export\s+(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*{",
            code
        )
        for match in export_funcs:
            if ":" not in match.group():
                warnings.append(
                    f"Exported function '{match.group(1)}' may be missing return type"
                )
        
        return warnings

