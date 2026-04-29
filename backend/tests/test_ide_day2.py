"""Day 2: Intelligence Activation — tests for filesystem, terminal, and symbol endpoints."""
from __future__ import annotations
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from code4u.interfaces.api.app import app
from code4u.interfaces.api.deps import _auth_manager


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def token() -> str:
    mgr = _auth_manager()
    email = "ide-test@code4u.ai"
    try:
        mgr.register(email, "pass", name="IDE Tester")
    except ValueError:
        pass
    return mgr.authenticate(email, "pass")


@pytest.fixture
def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def workspace(tmp_path):
    """Create a temp project with known files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello():\n    return 'world'\n")
    (tmp_path / "src" / "utils.py").write_text("import os\ndef greet(name):\n    return f'Hello {name}'\n")
    (tmp_path / "README.md").write_text("# Test Project\n")
    (tmp_path / "package.json").write_text('{"name": "test"}\n')
    return str(tmp_path)


class TestFileTree:
    def test_lists_real_files(self, client, headers, workspace):
        resp = client.get(f"/api/v1/projects/files?path={workspace}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tree" in data
        names = {n["name"] for n in data["tree"]}
        assert "src" in names
        assert "README.md" in names

    def test_nested_folder_has_children(self, client, headers, workspace):
        resp = client.get(f"/api/v1/projects/files?path={workspace}", headers=headers)
        tree = resp.json()["tree"]
        src = next(n for n in tree if n["name"] == "src")
        assert src["type"] == "folder"
        child_names = {c["name"] for c in src["children"]}
        assert "main.py" in child_names
        assert "utils.py" in child_names

    def test_invalid_path_returns_404(self, client, headers):
        resp = client.get("/api/v1/projects/files?path=/nonexistent/path", headers=headers)
        assert resp.status_code == 404

    def test_requires_auth(self, client, workspace):
        resp = client.get(f"/api/v1/projects/files?path={workspace}")
        assert resp.status_code == 401


class TestFileContent:
    def test_reads_file_content(self, client, headers, workspace):
        path = os.path.join(workspace, "src", "main.py")
        resp = client.get(f"/api/v1/files/content?path={path}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "def hello()" in data["content"]
        assert data["language"] == "python"

    def test_missing_file_returns_404(self, client, headers, workspace):
        path = os.path.join(workspace, "ghost.py")
        resp = client.get(f"/api/v1/files/content?path={path}", headers=headers)
        assert resp.status_code == 404


class TestFileSave:
    def test_saves_file(self, client, headers, workspace):
        path = os.path.join(workspace, "src", "main.py")
        resp = client.post("/api/v1/files/save", headers=headers, json={
            "path": path,
            "content": "# updated\ndef hello():\n    return 42\n",
        })
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

        with open(path) as f:
            assert "return 42" in f.read()


class TestTerminal:
    def test_executes_command(self, client, headers, workspace):
        resp = client.post("/api/v1/terminal/exec", headers=headers, json={
            "command": "echo hello",
            "cwd": workspace,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "hello" in data["stdout"]
        assert data["exitCode"] == 0

    def test_ls_command(self, client, headers, workspace):
        resp = client.post("/api/v1/terminal/exec", headers=headers, json={
            "command": "ls",
            "cwd": workspace,
        })
        assert resp.status_code == 200
        assert "README.md" in resp.json()["stdout"]

    def test_pwd_command(self, client, headers, workspace):
        resp = client.post("/api/v1/terminal/exec", headers=headers, json={
            "command": "pwd",
            "cwd": workspace,
        })
        assert resp.status_code == 200
        assert workspace in resp.json()["stdout"]

    def test_invalid_cwd_returns_404(self, client, headers):
        resp = client.post("/api/v1/terminal/exec", headers=headers, json={
            "command": "ls",
            "cwd": "/nonexistent",
        })
        assert resp.status_code == 404


class TestSymbolDefinitions:
    def test_indexes_python_workspace(self, client, headers, workspace):
        resp = client.get(
            f"/api/v1/symbols/definitions?workspace={workspace}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "symbols" in data
        symbol_names = {s["name"] for s in data["symbols"]}
        assert "hello" in symbol_names or "greet" in symbol_names

    def test_filter_by_file(self, client, headers, workspace):
        resp = client.get(
            f"/api/v1/symbols/definitions?workspace={workspace}&file=main.py",
            headers=headers,
        )
        assert resp.status_code == 200
        for s in resp.json()["symbols"]:
            assert "main.py" in s["file"]
