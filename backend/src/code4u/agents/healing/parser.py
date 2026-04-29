"""Stack Trace Parser — multi-language error extraction.

Ingests raw stderr / test runner output from:
  - Python (pytest / standard traceback)
  - JavaScript / TypeScript (Jest, Node.js)
  - Go (go test)

Extracts structured ``ParsedError`` objects containing the error
type, message, and a list of ``ErrorFrame`` entries (file, line,
function, code snippet).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    GO = "go"
    UNKNOWN = "unknown"


@dataclass
class ErrorFrame:
    """One frame in a parsed stack trace."""
    file_path: str
    line_number: int
    function_name: str = ""
    code_snippet: str = ""
    column: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "functionName": self.function_name,
            "codeSnippet": self.code_snippet,
            "column": self.column,
        }


@dataclass
class ParsedError:
    """A single error extracted from test runner output."""
    error_type: str
    message: str
    language: Language = Language.UNKNOWN
    frames: List[ErrorFrame] = field(default_factory=list)
    raw_text: str = ""
    test_name: str = ""
    test_file: str = ""

    @property
    def failing_frame(self) -> Optional[ErrorFrame]:
        """The frame most likely to contain the bug (last user frame)."""
        return self.frames[-1] if self.frames else None

    @property
    def failing_file(self) -> str:
        f = self.failing_frame
        return f.file_path if f else ""

    @property
    def failing_line(self) -> int:
        f = self.failing_frame
        return f.line_number if f else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "errorType": self.error_type,
            "message": self.message,
            "language": self.language.value,
            "frames": [f.to_dict() for f in self.frames],
            "testName": self.test_name,
            "testFile": self.test_file,
            "failingFile": self.failing_file,
            "failingLine": self.failing_line,
        }


class StackTraceParser:
    """Multi-language stack trace parser.

    Usage::

        parser = StackTraceParser()
        errors = parser.parse(stderr_output)
        for err in errors:
            print(err.error_type, err.failing_file, err.failing_line)
    """

    def parse(self, output: str) -> List[ParsedError]:
        """Parse raw test output and return all detected errors."""
        errors: List[ParsedError] = []

        py_errors = self._parse_python(output)
        if py_errors:
            errors.extend(py_errors)

        js_errors = self._parse_javascript(output)
        if js_errors:
            errors.extend(js_errors)

        go_errors = self._parse_go(output)
        if go_errors:
            errors.extend(go_errors)

        return errors

    def detect_language(self, output: str) -> Language:
        """Detect the dominant language from test output."""
        if "Traceback (most recent call last):" in output:
            return Language.PYTHON
        if re.search(r"(at\s+\S+\s+\(|ReferenceError|TypeError:)", output):
            return Language.JAVASCRIPT
        if re.search(r"(FAIL\s+\S+|panic:|goroutine\s+\d+)", output):
            return Language.GO
        return Language.UNKNOWN

    # -- Python --------------------------------------------------------------

    def _parse_python(self, output: str) -> List[ParsedError]:
        """Parse Python tracebacks (pytest / standard)."""
        errors: List[ParsedError] = []

        # Pattern 1: Standard Python traceback
        tb_blocks = re.split(r"Traceback \(most recent call last\):", output)
        for block in tb_blocks[1:]:  # skip content before first traceback
            err = self._parse_python_traceback(block)
            if err:
                errors.append(err)

        # Pattern 2: pytest short-form errors (E   NameError: ...)
        if not errors:
            errors.extend(self._parse_pytest_short(output))

        # Extract test names from pytest output
        test_match = re.search(r"FAILED\s+(\S+::(\S+))", output)
        if test_match and errors:
            errors[-1].test_name = test_match.group(2)
            errors[-1].test_file = test_match.group(1).split("::")[0]

        return errors

    def _parse_python_traceback(self, block: str) -> Optional[ParsedError]:
        """Parse a single Python traceback block."""
        frames: List[ErrorFrame] = []

        # Extract frames: File "...", line N, in ...
        frame_pattern = re.compile(
            r'File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+(\S+))?'
        )
        lines = block.splitlines()

        i = 0
        while i < len(lines):
            m = frame_pattern.search(lines[i])
            if m:
                snippet = ""
                if i + 1 < len(lines):
                    candidate = lines[i + 1].strip()
                    if candidate and not candidate.startswith("File "):
                        snippet = candidate
                frames.append(ErrorFrame(
                    file_path=m.group(1),
                    line_number=int(m.group(2)),
                    function_name=m.group(3) or "",
                    code_snippet=snippet,
                ))
            i += 1

        # Extract error type and message (last non-empty line(s))
        error_type = ""
        message = ""
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and not frame_pattern.search(line):
                if ":" in stripped and not stripped.startswith("File"):
                    parts = stripped.split(":", 1)
                    error_type = parts[0].strip()
                    message = parts[1].strip() if len(parts) > 1 else ""
                    break

        if not error_type and not frames:
            return None

        return ParsedError(
            error_type=error_type,
            message=message,
            language=Language.PYTHON,
            frames=frames,
            raw_text=block.strip(),
        )

    def _parse_pytest_short(self, output: str) -> List[ParsedError]:
        """Parse pytest short error lines (E   SomeError: message)."""
        errors: List[ParsedError] = []

        # Look for "E   ErrorType: message" pattern
        pattern = re.compile(r"^E\s+(\w+Error|\w+Exception|\w+Warning):\s*(.+)$", re.MULTILINE)
        for m in pattern.finditer(output):
            # Try to find the file/line from surrounding context
            preceding = output[:m.start()]
            file_match = re.search(
                r"(\S+\.py):(\d+):", preceding[max(0, len(preceding) - 500):]
            )
            frame = None
            if file_match:
                frame = ErrorFrame(
                    file_path=file_match.group(1),
                    line_number=int(file_match.group(2)),
                )

            err = ParsedError(
                error_type=m.group(1),
                message=m.group(2).strip(),
                language=Language.PYTHON,
                frames=[frame] if frame else [],
            )
            errors.append(err)

        return errors

    # -- JavaScript / TypeScript ---------------------------------------------

    def _parse_javascript(self, output: str) -> List[ParsedError]:
        """Parse JavaScript/TypeScript errors (Jest, Node.js)."""
        errors: List[ParsedError] = []

        # Pattern: ReferenceError: X is not defined
        #            at functionName (file:line:col)
        error_pattern = re.compile(
            r"(\w+Error|\w+Exception):\s*(.+?)(?:\n|$)"
        )
        frame_pattern = re.compile(
            r"at\s+(?:(\S+)\s+)?\(?([^:()]+):(\d+):(\d+)\)?"
        )

        for em in error_pattern.finditer(output):
            err_type = em.group(1)
            err_msg = em.group(2).strip()

            # Skip if this looks like a Python error we already parsed
            if "Traceback" in output[:em.start()]:
                continue

            frames: List[ErrorFrame] = []
            remainder = output[em.end():]
            for fm in frame_pattern.finditer(remainder[:1000]):
                frames.append(ErrorFrame(
                    file_path=fm.group(2),
                    line_number=int(fm.group(3)),
                    function_name=fm.group(1) or "",
                    column=int(fm.group(4)),
                ))
                if len(frames) >= 10:
                    break

            if frames:
                errors.append(ParsedError(
                    error_type=err_type,
                    message=err_msg,
                    language=Language.JAVASCRIPT,
                    frames=frames,
                ))

        # Jest-specific: "FAIL src/test.js" + test name
        fail_match = re.search(r"FAIL\s+(\S+)", output)
        if fail_match and errors:
            errors[-1].test_file = fail_match.group(1)

        test_match = re.search(r"●\s+(.+?)(?:\n|$)", output)
        if test_match and errors:
            errors[-1].test_name = test_match.group(1).strip()

        return errors

    # -- Go ------------------------------------------------------------------

    def _parse_go(self, output: str) -> List[ParsedError]:
        """Parse Go test failures and panics."""
        errors: List[ParsedError] = []

        # Pattern 1: panic: runtime error: ...
        panic_pattern = re.compile(r"panic:\s*(.+?)(?:\n|$)")
        goroutine_frame = re.compile(r"(\S+\.go):(\d+)")

        for pm in panic_pattern.finditer(output):
            frames: List[ErrorFrame] = []
            remainder = output[pm.end():]
            for fm in goroutine_frame.finditer(remainder[:2000]):
                frames.append(ErrorFrame(
                    file_path=fm.group(1),
                    line_number=int(fm.group(2)),
                ))
                if len(frames) >= 10:
                    break

            errors.append(ParsedError(
                error_type="panic",
                message=pm.group(1).strip(),
                language=Language.GO,
                frames=frames,
            ))

        # Pattern 2: --- FAIL: TestName (duration)
        #   file_test.go:42: error message
        fail_pattern = re.compile(
            r"---\s+FAIL:\s+(\S+)\s+\([\d.]+s\)"
        )
        go_err_line = re.compile(
            r"\s+(\S+\.go):(\d+):\s+(.+)"
        )

        for fm in fail_pattern.finditer(output):
            test_name = fm.group(1)
            remainder = output[fm.end():fm.end() + 1000]
            for em in go_err_line.finditer(remainder):
                errors.append(ParsedError(
                    error_type="TestFailure",
                    message=em.group(3).strip(),
                    language=Language.GO,
                    frames=[ErrorFrame(
                        file_path=em.group(1),
                        line_number=int(em.group(2)),
                    )],
                    test_name=test_name,
                ))
                break

        # Pattern 3: FAIL <package> line
        pkg_fail = re.search(r"FAIL\s+(\S+)", output)
        if pkg_fail and errors:
            errors[-1].test_file = pkg_fail.group(1)

        return errors
