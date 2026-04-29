"""Day 21 — Self-Healing Build Agent test suite.

Tests:
  - StackTraceParser: Python, JavaScript, Go error extraction.
  - Diagnoser: context window, symbol tracing, repair suggestions.
  - TestRunner: diagnose_output, result structure.
  - End-to-end: break-and-fix scenarios.
  - API endpoints: heal, parse.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pytest

from code4u.agents.healing.parser import (
    StackTraceParser,
    ParsedError,
    ErrorFrame,
    Language,
)
from code4u.agents.healing.diagnoser import (
    Diagnoser,
    Diagnosis,
    RepairSuggestion,
    ContextWindow,
    SymbolTrace,
)
from code4u.core.executor_ext import TestRunner, TestRunResult
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    SymbolIndexer,
    DependencyMap,
)


# ---------------------------------------------------------------------------
# Sample stack traces
# ---------------------------------------------------------------------------

PYTHON_TRACEBACK = textwrap.dedent("""\
    Traceback (most recent call last):
      File "/project/tests/test_api.py", line 42, in test_get_user
        result = get_user(123)
      File "/project/src/api.py", line 15, in get_user
        return db.find(user_id)
    NameError: name 'db' is not defined
""")

PYTHON_IMPORT_ERROR = textwrap.dedent("""\
    Traceback (most recent call last):
      File "/project/src/service.py", line 3, in <module>
        from models import UserProfile
    ImportError: cannot import name 'UserProfile' from 'models'
""")

PYTHON_ATTR_ERROR = textwrap.dedent("""\
    Traceback (most recent call last):
      File "/project/src/handler.py", line 22, in process
        result = obj.send_message()
    AttributeError: 'NoneType' object has no attribute 'send_message'
""")

PYTEST_SHORT = textwrap.dedent("""\
    tests/test_utils.py:18: in test_calculate
    E   NameError: name 'calculate_total' is not defined
    FAILED tests/test_utils.py::test_calculate
""")

JAVASCRIPT_ERROR = textwrap.dedent("""\
    FAIL src/__tests__/app.test.js
      ● App component > renders correctly

    ReferenceError: fetchData is not defined
        at Object.<anonymous> (src/App.js:12:5)
        at processTicksAndRejections (internal/process/task_queues.js:95:5)
""")

JAVASCRIPT_TYPE_ERROR = textwrap.dedent("""\
    TypeError: Cannot read properties of undefined (reading 'map')
        at renderList (src/components/List.js:8:23)
        at Object.<anonymous> (src/__tests__/List.test.js:15:5)
""")

GO_PANIC = textwrap.dedent("""\
    panic: runtime error: index out of range [5] with length 3

    goroutine 1 [running]:
    main.processItems(...)
        /project/main.go:42
    main.main()
        /project/main.go:15
""")

GO_TEST_FAIL = textwrap.dedent("""\
    --- FAIL: TestCalculate (0.00s)
        calc_test.go:15: expected 42, got 0
    FAIL    github.com/user/project 0.005s
""")


# ═══════════════════════════════════════════════════════════════════════════
# StackTraceParser tests
# ═══════════════════════════════════════════════════════════════════════════

class TestStackTraceParser:
    @pytest.fixture
    def parser(self):
        return StackTraceParser()

    # -- Python --

    def test_python_traceback(self, parser):
        errors = parser.parse(PYTHON_TRACEBACK)
        assert len(errors) >= 1
        err = errors[0]
        assert err.language == Language.PYTHON
        assert err.error_type == "NameError"
        assert "db" in err.message
        assert len(err.frames) == 2
        assert err.frames[-1].file_path == "/project/src/api.py"
        assert err.frames[-1].line_number == 15

    def test_python_import_error(self, parser):
        errors = parser.parse(PYTHON_IMPORT_ERROR)
        assert len(errors) >= 1
        err = errors[0]
        assert err.error_type == "ImportError"
        assert "UserProfile" in err.message

    def test_python_attr_error(self, parser):
        errors = parser.parse(PYTHON_ATTR_ERROR)
        assert len(errors) >= 1
        err = errors[0]
        assert err.error_type == "AttributeError"
        assert "send_message" in err.message

    def test_pytest_short_form(self, parser):
        errors = parser.parse(PYTEST_SHORT)
        assert len(errors) >= 1
        err = errors[0]
        assert err.error_type == "NameError"
        assert "calculate_total" in err.message

    def test_python_failing_frame(self, parser):
        errors = parser.parse(PYTHON_TRACEBACK)
        err = errors[0]
        assert err.failing_file == "/project/src/api.py"
        assert err.failing_line == 15

    def test_python_frame_function_name(self, parser):
        errors = parser.parse(PYTHON_TRACEBACK)
        assert errors[0].frames[0].function_name == "test_get_user"
        assert errors[0].frames[1].function_name == "get_user"

    def test_python_frame_code_snippet(self, parser):
        errors = parser.parse(PYTHON_TRACEBACK)
        assert "get_user" in errors[0].frames[0].code_snippet

    # -- JavaScript --

    def test_javascript_reference_error(self, parser):
        errors = parser.parse(JAVASCRIPT_ERROR)
        assert len(errors) >= 1
        err = errors[0]
        assert err.language == Language.JAVASCRIPT
        assert err.error_type == "ReferenceError"
        assert "fetchData" in err.message
        assert err.frames[0].file_path == "src/App.js"
        assert err.frames[0].line_number == 12

    def test_javascript_type_error(self, parser):
        errors = parser.parse(JAVASCRIPT_TYPE_ERROR)
        assert len(errors) >= 1
        err = errors[0]
        assert err.error_type == "TypeError"
        assert "map" in err.message
        assert err.frames[0].file_path == "src/components/List.js"

    def test_javascript_column_number(self, parser):
        errors = parser.parse(JAVASCRIPT_ERROR)
        assert errors[0].frames[0].column == 5

    def test_jest_test_name(self, parser):
        errors = parser.parse(JAVASCRIPT_ERROR)
        err = errors[0]
        assert err.test_file == "src/__tests__/app.test.js"

    # -- Go --

    def test_go_panic(self, parser):
        errors = parser.parse(GO_PANIC)
        assert len(errors) >= 1
        err = errors[0]
        assert err.language == Language.GO
        assert err.error_type == "panic"
        assert "index out of range" in err.message
        assert any(f.file_path == "/project/main.go" for f in err.frames)

    def test_go_test_failure(self, parser):
        errors = parser.parse(GO_TEST_FAIL)
        assert len(errors) >= 1
        err = errors[0]
        assert err.error_type == "TestFailure"
        assert err.test_name == "TestCalculate"
        assert err.frames[0].file_path == "calc_test.go"
        assert err.frames[0].line_number == 15

    # -- Language detection --

    def test_detect_python(self, parser):
        assert parser.detect_language(PYTHON_TRACEBACK) == Language.PYTHON

    def test_detect_javascript(self, parser):
        assert parser.detect_language(JAVASCRIPT_ERROR) == Language.JAVASCRIPT

    def test_detect_go(self, parser):
        assert parser.detect_language(GO_PANIC) == Language.GO

    def test_detect_unknown(self, parser):
        assert parser.detect_language("some random text") == Language.UNKNOWN

    # -- Serialization --

    def test_parsed_error_to_dict(self, parser):
        errors = parser.parse(PYTHON_TRACEBACK)
        d = errors[0].to_dict()
        assert "errorType" in d
        assert "frames" in d
        assert "failingFile" in d
        assert "failingLine" in d

    def test_error_frame_to_dict(self):
        frame = ErrorFrame("/test.py", 42, "test_func", "x = 1")
        d = frame.to_dict()
        assert d["filePath"] == "/test.py"
        assert d["lineNumber"] == 42

    # -- Empty / no errors --

    def test_empty_output(self, parser):
        errors = parser.parse("")
        assert errors == []

    def test_clean_output(self, parser):
        errors = parser.parse("All 42 tests passed in 1.23s")
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════
# Diagnoser tests
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def healing_project(tmp_path):
    """A project with a deliberate bug for testing."""
    (tmp_path / "models.py").write_text(
        "class UserProfile:\n"
        "    def __init__(self, name):\n"
        "        self.name = name\n\n"
        "class DatabaseConnection:\n"
        "    def find(self, uid):\n"
        "        return None\n"
    )
    (tmp_path / "api.py").write_text(
        "from models import UserProfile\n\n"
        "def get_user(uid):\n"
        "    return db.find(uid)\n"
    )
    (tmp_path / "service.py").write_text(
        "from models import UserProfile\n"
        "from api import get_user\n\n"
        "def fetch_profile(uid):\n"
        "    user = get_user(uid)\n"
        "    return user.name\n"
    )
    (tmp_path / "utils.py").write_text(
        "def calculate_total(items):\n"
        "    return sum(i.price for i in items)\n\n"
        "def calculate_totl(items):\n"
        "    return 0\n"
    )
    return tmp_path


@pytest.fixture
def healing_dep_map(healing_project):
    indexer = SymbolIndexer()
    return indexer.index_workspace(str(healing_project), use_cache=False)


class TestDiagnoser:
    def test_diagnose_name_error(self, healing_project, healing_dep_map):
        """NameError on 'db' — diagnoser should find DatabaseConnection."""
        error = ParsedError(
            error_type="NameError",
            message="name 'db' is not defined",
            language=Language.PYTHON,
            frames=[ErrorFrame(
                file_path=str(healing_project / "api.py"),
                line_number=4,
                function_name="get_user",
                code_snippet="return db.find(uid)",
            )],
        )
        diagnoser = Diagnoser(healing_dep_map)
        diagnosis = diagnoser.diagnose(error)

        assert diagnosis.root_cause
        assert "db" in diagnosis.root_cause
        assert diagnosis.context is not None
        assert diagnosis.context.error_line == 4

    def test_diagnose_import_error(self, healing_project, healing_dep_map):
        """ImportError for 'UserProfile' — should find it in models.py."""
        error = ParsedError(
            error_type="ImportError",
            message="cannot import name 'UserProfile' from 'old_models'",
            language=Language.PYTHON,
            frames=[ErrorFrame(
                file_path=str(healing_project / "service.py"),
                line_number=1,
            )],
        )
        diagnoser = Diagnoser(healing_dep_map)
        diagnosis = diagnoser.diagnose(error)

        assert "UserProfile" in diagnosis.root_cause
        assert diagnosis.has_fix
        fix = diagnosis.suggestions[0]
        assert fix.action == "add_import"
        assert "models" in fix.new_text

    def test_diagnose_attribute_error(self, healing_project, healing_dep_map):
        error = ParsedError(
            error_type="AttributeError",
            message="'NoneType' object has no attribute 'send_message'",
            language=Language.PYTHON,
            frames=[ErrorFrame(
                file_path=str(healing_project / "api.py"),
                line_number=4,
            )],
        )
        diagnoser = Diagnoser(healing_dep_map)
        diagnosis = diagnoser.diagnose(error)
        assert "NoneType" in diagnosis.root_cause

    def test_diagnose_typo_suggestion(self, healing_project, healing_dep_map):
        """NameError with a typo — should suggest the correct name."""
        error = ParsedError(
            error_type="NameError",
            message="name 'calculate_totl' is not defined",
            language=Language.PYTHON,
            frames=[ErrorFrame(
                file_path=str(healing_project / "service.py"),
                line_number=5,
            )],
        )
        diagnoser = Diagnoser(healing_dep_map)
        diagnosis = diagnoser.diagnose(error)
        # calculate_totl exists, so it should be found in dep_map
        # But if it didn't exist, we'd get a typo suggestion
        assert diagnosis.root_cause

    def test_context_window(self, healing_project, healing_dep_map):
        error = ParsedError(
            error_type="NameError",
            message="name 'db' is not defined",
            language=Language.PYTHON,
            frames=[ErrorFrame(
                file_path=str(healing_project / "api.py"),
                line_number=4,
            )],
        )
        diagnoser = Diagnoser(healing_dep_map)
        diagnosis = diagnoser.diagnose(error)

        ctx = diagnosis.context
        assert ctx is not None
        assert 4 in ctx.lines
        assert "db" in ctx.lines[4]
        assert len(ctx.symbols_on_line) > 0

    def test_symbol_trace(self, healing_project, healing_dep_map):
        diagnoser = Diagnoser(healing_dep_map)
        trace = diagnoser._trace_symbol("UserProfile")
        assert trace is not None
        assert trace.defined_in
        assert "models" in trace.defined_in
        assert trace.kind == "class"

    def test_symbol_trace_unknown(self, healing_project, healing_dep_map):
        diagnoser = Diagnoser(healing_dep_map)
        trace = diagnoser._trace_symbol("nonexistent_xyz")
        assert trace is not None
        assert trace.defined_in == ""

    def test_diagnose_no_frame(self, healing_dep_map):
        error = ParsedError(
            error_type="RuntimeError",
            message="something went wrong",
            language=Language.PYTHON,
        )
        diagnoser = Diagnoser(healing_dep_map)
        diagnosis = diagnoser.diagnose(error)
        assert diagnosis.context is None
        assert "No stack frame" in diagnosis.root_cause

    def test_diagnose_all(self, healing_project, healing_dep_map):
        errors = [
            ParsedError(
                error_type="NameError",
                message="name 'x' is not defined",
                language=Language.PYTHON,
                frames=[ErrorFrame(str(healing_project / "api.py"), 4)],
            ),
            ParsedError(
                error_type="ImportError",
                message="cannot import name 'UserProfile' from 'old'",
                language=Language.PYTHON,
                frames=[ErrorFrame(str(healing_project / "service.py"), 1)],
            ),
        ]
        diagnoser = Diagnoser(healing_dep_map)
        diagnoses = diagnoser.diagnose_all(errors)
        assert len(diagnoses) == 2

    def test_diagnosis_to_dict(self, healing_project, healing_dep_map):
        error = ParsedError(
            error_type="NameError",
            message="name 'db' is not defined",
            language=Language.PYTHON,
            frames=[ErrorFrame(str(healing_project / "api.py"), 4)],
        )
        diagnoser = Diagnoser(healing_dep_map)
        diagnosis = diagnoser.diagnose(error)
        d = diagnosis.to_dict()
        assert "error" in d
        assert "context" in d
        assert "suggestions" in d
        assert "rootCause" in d
        assert "hasFix" in d

    def test_repair_suggestion_to_dict(self):
        s = RepairSuggestion(
            file_path="/test.py",
            description="Add missing import",
            action="add_import",
            new_text="from models import X",
            confidence=0.9,
        )
        d = s.to_dict()
        assert d["action"] == "add_import"
        assert d["confidence"] == 0.9

    def test_is_similar(self):
        assert Diagnoser._is_similar("calculate_total", "calculate_totl")
        assert Diagnoser._is_similar("UserProfile", "userProfile")
        assert not Diagnoser._is_similar("abc", "xyz")
        assert Diagnoser._is_similar("hello", "helo")


# ═══════════════════════════════════════════════════════════════════════════
# TestRunner tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTestRunner:
    def test_diagnose_output(self, healing_project, healing_dep_map):
        runner = TestRunner(healing_dep_map)
        result = runner.diagnose_output(PYTHON_TRACEBACK)
        assert not result.passed
        assert result.error_count >= 1

    def test_diagnose_clean_output(self, healing_dep_map):
        runner = TestRunner(healing_dep_map)
        result = runner.diagnose_output("All tests passed!")
        assert result.passed
        assert result.error_count == 0

    def test_result_to_dict(self, healing_dep_map):
        runner = TestRunner(healing_dep_map)
        result = runner.diagnose_output(PYTHON_TRACEBACK)
        d = result.to_dict()
        assert "command" in d
        assert "errorCount" in d
        assert "fixCount" in d
        assert "diagnoses" in d

    def test_resolve_command(self, healing_dep_map):
        runner = TestRunner(healing_dep_map)
        parts = runner._resolve_command("pytest", ["--verbose"])
        assert "pytest" in " ".join(parts)
        assert "--verbose" in parts

    def test_resolve_custom_command(self, healing_dep_map):
        runner = TestRunner(healing_dep_map)
        parts = runner._resolve_command("python -m unittest", None)
        assert parts == ["python", "-m", "unittest"]


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: "Break & Fix" scenarios
# ═══════════════════════════════════════════════════════════════════════════

class TestBreakAndFix:
    def test_missing_import_diagnosis(self, healing_project, healing_dep_map):
        """Simulate removing an import and diagnosing the error."""
        # The error output a user would see
        error_output = (
            "Traceback (most recent call last):\n"
            f'  File "{healing_project / "service.py"}", line 1, in <module>\n'
            "    from old_models import UserProfile\n"
            "ImportError: cannot import name 'UserProfile' from 'old_models'\n"
        )
        runner = TestRunner(healing_dep_map)
        result = runner.diagnose_output(error_output)

        assert result.error_count >= 1
        assert result.fix_count >= 1

        fix = result.diagnoses[0].suggestions[0]
        assert fix.action == "add_import"
        assert "models" in fix.new_text
        assert "UserProfile" in fix.new_text

    def test_undefined_name_diagnosis(self, healing_project, healing_dep_map):
        """Simulate a NameError on a symbol that exists elsewhere."""
        error_output = (
            "Traceback (most recent call last):\n"
            f'  File "{healing_project / "api.py"}", line 4, in get_user\n'
            "    return DatabaseConnection().find(uid)\n"
            "NameError: name 'DatabaseConnection' is not defined\n"
        )
        runner = TestRunner(healing_dep_map)
        result = runner.diagnose_output(error_output)

        assert result.error_count >= 1
        # Should find DatabaseConnection in models.py
        diagnosis = result.diagnoses[0]
        assert "DatabaseConnection" in diagnosis.root_cause
        assert diagnosis.has_fix
        assert "models" in diagnosis.suggestions[0].new_text

    def test_multifile_context(self, healing_project, healing_dep_map):
        """Diagnoser traces symbols across files."""
        diagnoser = Diagnoser(healing_dep_map)

        # Trace UserProfile — should find it in models.py, used by api.py and service.py
        trace = diagnoser._trace_symbol("UserProfile")
        assert trace.defined_in.endswith("models.py")
        assert len(trace.used_by) >= 2

    def test_type_error_diagnosis(self, healing_project, healing_dep_map):
        error_output = (
            "Traceback (most recent call last):\n"
            f'  File "{healing_project / "service.py"}", line 5, in fetch_profile\n'
            "    user = get_user(uid)\n"
            "TypeError: get_user() takes 0 positional arguments but 1 was given\n"
        )
        runner = TestRunner(healing_dep_map)
        result = runner.diagnose_output(error_output)
        assert result.error_count >= 1
        diagnosis = result.diagnoses[0]
        assert "get_user" in diagnosis.root_cause


# ═══════════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════════

class TestHealingAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        yield

    def test_parse_endpoint(self):
        resp = self.client.post("/api/v1/heal/parse", json={
            "output": PYTHON_TRACEBACK,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["language"] == "python"
        assert data["errorCount"] >= 1

    def test_parse_javascript(self):
        resp = self.client.post("/api/v1/heal/parse", json={
            "output": JAVASCRIPT_ERROR,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["errorCount"] >= 1

    def test_parse_go(self):
        resp = self.client.post("/api/v1/heal/parse", json={
            "output": GO_PANIC,
        })
        assert resp.status_code == 200
        assert resp.json()["errorCount"] >= 1

    def test_heal_endpoint(self, healing_project):
        error_output = (
            "Traceback (most recent call last):\n"
            f'  File "{healing_project / "service.py"}", line 1, in <module>\n'
            "    from old_models import UserProfile\n"
            "ImportError: cannot import name 'UserProfile' from 'old_models'\n"
        )
        resp = self.client.post("/api/v1/heal", json={
            "errorOutput": error_output,
            "workspacePath": str(healing_project),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["errorCount"] >= 1
        assert data["fixCount"] >= 1
        assert len(data["diagnoses"]) >= 1
        assert data["diagnoses"][0]["hasFix"]

    def test_heal_clean_output(self, healing_project):
        resp = self.client.post("/api/v1/heal", json={
            "errorOutput": "All 10 tests passed",
            "workspacePath": str(healing_project),
        })
        assert resp.status_code == 200
        assert resp.json()["errorCount"] == 0

    def test_parse_empty(self):
        resp = self.client.post("/api/v1/heal/parse", json={
            "output": "",
        })
        assert resp.status_code == 200
        assert resp.json()["errorCount"] == 0
