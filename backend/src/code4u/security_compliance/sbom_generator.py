"""Software Bill of Materials (SBOM) Generator.

Generates CycloneDX 1.5 JSON format SBOMs by analyzing project
dependency manifests (package.json, requirements.txt, go.mod,
pyproject.toml, Cargo.toml, pom.xml).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger("sbom_generator")

# Known license mapping for popular packages
_KNOWN_LICENSES: Dict[str, Dict[str, str]] = {
    "npm": {
        "lodash": "MIT",
        "express": "MIT",
        "react": "MIT",
        "axios": "MIT",
        "next": "MIT",
        "vue": "MIT",
        "typescript": "Apache-2.0",
        "webpack": "MIT",
        "jest": "MIT",
        "eslint": "MIT",
    },
    "pypi": {
        "django": "BSD-3-Clause",
        "flask": "BSD-3-Clause",
        "requests": "Apache-2.0",
        "numpy": "BSD-3-Clause",
        "pillow": "HPND",
        "pyyaml": "MIT",
        "urllib3": "MIT",
    },
    "cargo": {
        "serde": "MIT",
        "tokio": "MIT",
        "reqwest": "MIT",
    },
    "maven": {
        "spring-boot": "Apache-2.0",
        "slf4j": "MIT",
    },
}


@dataclass
class SBOMComponent:
    """A single SBOM component (dependency)."""

    name: str
    version: str
    type: str  # library, framework, application
    purl: str  # Package URL
    ecosystem: str  # npm, pypi, go, cargo, maven
    license_id: str  # SPDX identifier
    scope: str  # required, optional, dev
    hashes: List[Dict[str, str]] = field(default_factory=list)
    manifest: str = ""

    def to_cyclonedx_dict(self) -> Dict[str, Any]:
        """Convert to CycloneDX component dict."""
        comp: Dict[str, Any] = {
            "type": self.type,
            "name": self.name,
            "version": self.version,
            "purl": self.purl,
        }
        if self.license_id and self.license_id != "NOASSERTION":
            comp["licenses"] = [{"license": {"id": self.license_id}}]
        if self.hashes:
            comp["hashes"] = self.hashes
        if self.manifest:
            comp["properties"] = [{"name": "manifest", "value": self.manifest}]
        return comp


class SBOMGenerator:
    """Generate CycloneDX 1.5 SBOM from workspace or code map."""

    def __init__(self, tool_name: str = "code4u.ai", tool_version: str = "1.0.0") -> None:
        self.tool_name = tool_name
        self.tool_version = tool_version

    def generate_from_workspace(self, workspace_path: str) -> Dict[str, Any]:
        """Scan all manifest files and return CycloneDX 1.5 JSON."""
        components: List[SBOMComponent] = []
        project_name = os.path.basename(os.path.abspath(workspace_path)) or "unknown"

        manifest_files = [
            ("package.json", self._parse_package_json),
            ("requirements.txt", self._parse_requirements_txt),
            ("pyproject.toml", self._parse_pyproject_toml),
            ("go.mod", self._parse_go_mod),
            ("Cargo.toml", self._parse_cargo_toml),
            ("pom.xml", self._parse_pom_xml),
        ]

        for filename, parser in manifest_files:
            filepath = os.path.join(workspace_path, filename)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    comps = parser(content)
                    for c in comps:
                        c.manifest = filename
                        components.append(c)
                except Exception as e:
                    logger.warning("sbom_parse_failed", file=filename, error=str(e))

        return self._build_bom(components, project_name)

    def generate_from_code_map(
        self, code_map: Dict[str, str], project_name: str = ""
    ) -> Dict[str, Any]:
        """Generate SBOM from code content strings (when workspace isn't on disk)."""
        components: List[SBOMComponent] = []
        proj = project_name or "code4u-project"

        parsers: Dict[str, Any] = {
            "package.json": self._parse_package_json,
            "requirements.txt": self._parse_requirements_txt,
            "pyproject.toml": self._parse_pyproject_toml,
            "go.mod": self._parse_go_mod,
            "Cargo.toml": self._parse_cargo_toml,
            "pom.xml": self._parse_pom_xml,
        }

        for filepath, content in code_map.items():
            basename = os.path.basename(filepath)
            if basename in parsers:
                try:
                    comps = parsers[basename](content)
                    for c in comps:
                        c.manifest = basename
                        components.append(c)
                except Exception as e:
                    logger.warning("sbom_parse_failed", file=filepath, error=str(e))

        return self._build_bom(components, proj)

    def _build_bom(
        self, components: List[SBOMComponent], project_name: str
    ) -> Dict[str, Any]:
        """Build CycloneDX 1.5 JSON structure."""
        comp_dicts = [c.to_cyclonedx_dict() for c in components]
        root_bom_ref = f"pkg:generic/{project_name}@0.0.0"
        dependencies: List[Dict[str, Any]] = [
            {"ref": root_bom_ref, "dependsOn": [c.purl for c in components]}
        ] if components else []

        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tools": [
                    {
                        "vendor": "code4u.ai",
                        "name": self.tool_name,
                        "version": self.tool_version,
                    }
                ],
                "component": {
                    "type": "application",
                    "name": project_name,
                    "version": "0.0.0",
                    "bom-ref": root_bom_ref,
                },
            },
            "components": comp_dicts,
            "dependencies": dependencies,
        }

    def _parse_package_json(self, content: str) -> List[SBOMComponent]:
        """Parse package.json dependencies and devDependencies."""
        components: List[SBOMComponent] = []
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return components

        for section, scope in [("dependencies", "required"), ("devDependencies", "dev")]:
            deps = data.get(section, {})
            for name, ver in deps.items():
                ver_clean = re.sub(r"[^0-9.]", "", str(ver).lstrip("^~>=<! ")) or "0.0.0"
                purl = f"pkg:npm/{name}@{ver_clean}"
                license_id = self._guess_license(name, "npm")
                components.append(
                    SBOMComponent(
                        name=name,
                        version=ver_clean,
                        type="library",
                        purl=purl,
                        ecosystem="npm",
                        license_id=license_id,
                        scope=scope,
                        manifest="package.json",
                    )
                )
        return components

    def _parse_requirements_txt(self, content: str) -> List[SBOMComponent]:
        """Parse requirements.txt."""
        components: List[SBOMComponent] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = re.match(r"([a-zA-Z0-9_\-\.]+)\s*([><=!~]*)\s*([\d\.]*)", line)
            if m:
                name = m.group(1)
                ver = m.group(3) or "0.0.0"
                purl = f"pkg:pypi/{name}@{ver}"
                license_id = self._guess_license(name, "pypi")
                components.append(
                    SBOMComponent(
                        name=name,
                        version=ver,
                        type="library",
                        purl=purl,
                        ecosystem="pypi",
                        license_id=license_id,
                        scope="required",
                        manifest="requirements.txt",
                    )
                )
        return components

    def _parse_pyproject_toml(self, content: str) -> List[SBOMComponent]:
        """Parse pyproject.toml using toml or fallback regex."""
        components: List[SBOMComponent] = []
        try:
            import toml
            data = toml.loads(content)
        except Exception:
            data = self._parse_pyproject_regex(content)

        project = data.get("project", data)
        deps_list: List[str] = []
        deps_list.extend(project.get("dependencies", []))
        opt_deps = project.get("optional-dependencies", {})
        if isinstance(opt_deps, dict):
            for extra_deps in opt_deps.values():
                if isinstance(extra_deps, list):
                    deps_list.extend(extra_deps)

        for dep in deps_list:
            if isinstance(dep, str):
                m = re.match(r"([a-zA-Z0-9_\-\.]+)\s*([><=!~]*)\s*([\d\.]*)", dep)
                if m:
                    name = m.group(1)
                    ver = m.group(3) or "0.0.0"
                    purl = f"pkg:pypi/{name}@{ver}"
                    license_id = self._guess_license(name, "pypi")
                    components.append(
                        SBOMComponent(
                            name=name,
                            version=ver,
                            type="library",
                            purl=purl,
                            ecosystem="pypi",
                            license_id=license_id,
                            scope="required",
                            manifest="pyproject.toml",
                        )
                    )
        return components

    def _parse_pyproject_regex(self, content: str) -> Dict[str, Any]:
        """Fallback regex parse for pyproject.toml."""
        data: Dict[str, Any] = {"project": {"dependencies": [], "optional-dependencies": {}}}
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("[project]") or stripped.startswith("[tool."):
                in_deps = False
            if "dependencies" in stripped and "=" in stripped:
                in_deps = True
                continue
            if in_deps and stripped:
                m = re.search(r'"([a-zA-Z0-9_\-\.]+)\s*[^"]*"', stripped)
                if m:
                    data["project"]["dependencies"].append(m.group(1))
        return data

    def _parse_go_mod(self, content: str) -> List[SBOMComponent]:
        """Parse go.mod."""
        components: List[SBOMComponent] = []
        in_require = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "require (":
                in_require = True
                continue
            if in_require and stripped == ")":
                in_require = False
                continue
            if in_require and stripped and not stripped.startswith("//"):
                parts = stripped.split()
                if len(parts) >= 2:
                    name = parts[0]
                    ver = parts[1].lstrip("v")
                    purl = f"pkg:golang/{name}@{ver}"
                    license_id = self._guess_license(name, "go")
                    components.append(
                        SBOMComponent(
                            name=name,
                            version=ver,
                            type="library",
                            purl=purl,
                            ecosystem="go",
                            license_id=license_id,
                            scope="required",
                            manifest="go.mod",
                        )
                    )
        return components

    def _parse_cargo_toml(self, content: str) -> List[SBOMComponent]:
        """Parse Cargo.toml."""
        components: List[SBOMComponent] = []
        try:
            import toml
            data = toml.loads(content)
        except Exception:
            return components

        for section in ("dependencies", "dev-dependencies"):
            deps = data.get(section, {})
            if not isinstance(deps, dict):
                continue
            scope = "dev" if section == "dev-dependencies" else "required"
            for name, spec in deps.items():
                if isinstance(spec, str):
                    ver = re.sub(r"[^0-9.]", "", spec) or "0.0.0"
                elif isinstance(spec, dict):
                    ver = spec.get("version", "0.0.0")
                else:
                    ver = "0.0.0"
                purl = f"pkg:cargo/{name}@{ver}"
                license_id = self._guess_license(name, "cargo")
                components.append(
                    SBOMComponent(
                        name=name,
                        version=str(ver),
                        type="library",
                        purl=purl,
                        ecosystem="cargo",
                        license_id=license_id,
                        scope=scope,
                        manifest="Cargo.toml",
                    )
                )
        return components

    def _parse_pom_xml(self, content: str) -> List[SBOMComponent]:
        """Parse pom.xml with basic regex."""
        components: List[SBOMComponent] = []
        # Match <groupId>...</groupId><artifactId>...</artifactId><version>...</version>
        dep_pattern = re.compile(
            r"<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>\s*(?:<version>([^<]*)</version>)?",
            re.DOTALL,
        )
        for m in dep_pattern.finditer(content):
            group = m.group(1).strip()
            artifact = m.group(2).strip()
            ver = (m.group(3) or "0.0.0").strip()
            if "${" in ver:
                ver = "0.0.0"
            name = f"{group}:{artifact}"
            purl = f"pkg:maven/{group}/{artifact}@{ver}"
            license_id = self._guess_license(artifact, "maven")
            components.append(
                SBOMComponent(
                    name=name,
                    version=ver,
                    type="library",
                    purl=purl,
                    ecosystem="maven",
                    license_id=license_id,
                    scope="required",
                    manifest="pom.xml",
                )
            )
        return components

    def _guess_license(self, name: str, ecosystem: str) -> str:
        """Known license mapping for popular packages."""
        name_lower = name.lower().replace("-", "_")
        for pkg, lic in _KNOWN_LICENSES.get(ecosystem, {}).items():
            if pkg.lower().replace("-", "_") in name_lower or name_lower in pkg.lower():
                return lic
        return "NOASSERTION"
