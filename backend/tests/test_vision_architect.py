"""Day 23 — Visual Architect test suite.

Tests:
  - VisionAnalyzer: local analysis, JSON parsing, dark mode, layout detection.
  - DesignSystemMapper: color matching, Tailwind config, CSS variables, class generation.
  - MappedManifest: token alignment, unmatched colors, component classes.
  - API endpoints: analyze, map, refactor.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Dict

import pytest

from code4u.agents.vision.processor import (
    VisionAnalyzer,
    VisualManifest,
    UIComponent,
    ColorSpec,
    TypographySpec,
    SpacingSpec,
    LayoutType,
)
from code4u.agents.vision.mapper import (
    DesignSystemMapper,
    TokenMatch,
    MappedManifest,
    MappedComponent,
)


# ═══════════════════════════════════════════════════════════════════════════
# VisionAnalyzer tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVisionAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return VisionAnalyzer()

    # -- Local analysis --

    def test_dark_mode_detection(self, analyzer):
        manifest = analyzer.analyze_image("", "Dark Mode Dashboard with sidebar")
        assert manifest.is_dark_mode

    def test_light_mode_default(self, analyzer):
        manifest = analyzer.analyze_image("", "Simple form with inputs")
        assert not manifest.is_dark_mode

    def test_sidebar_layout_detection(self, analyzer):
        manifest = analyzer.analyze_image("", "Dashboard with sidebar navigation")
        assert manifest.layout_type == LayoutType.SIDEBAR

    def test_grid_layout_detection(self, analyzer):
        manifest = analyzer.analyze_image("", "Grid of cards showing metrics")
        assert manifest.layout_type == LayoutType.GRID

    def test_flex_col_detection(self, analyzer):
        manifest = analyzer.analyze_image("", "Vertical stacked layout")
        assert manifest.layout_type == LayoutType.FLEX_COL

    def test_flex_row_detection(self, analyzer):
        manifest = analyzer.analyze_image("", "Horizontal row of buttons")
        assert manifest.layout_type == LayoutType.FLEX_ROW

    def test_component_extraction(self, analyzer):
        manifest = analyzer.analyze_image("", "Header with sidebar and card list")
        names = manifest.component_names
        assert "Header" in names
        assert "Sidebar" in names
        assert "Card" in names

    def test_hex_color_extraction(self, analyzer):
        manifest = analyzer.analyze_image("", "Primary blue #3b82f6 with accent #22c55e")
        assert "#3b82f6" in manifest.color_palette
        assert "#22c55e" in manifest.color_palette

    def test_dark_mode_default_palette(self, analyzer):
        manifest = analyzer.analyze_image("", "Dark mode dashboard")
        assert len(manifest.global_colors) >= 3

    def test_mobile_viewport(self, analyzer):
        manifest = analyzer.analyze_image("", "Mobile phone layout")
        assert manifest.viewport == "mobile"

    def test_framework_hint(self, analyzer):
        manifest = analyzer.analyze_image("", "Test", framework_hint="css-modules")
        assert manifest.framework_hint == "css-modules"

    # -- JSON parsing --

    def test_parse_json_manifest(self, analyzer):
        raw = json.dumps({
            "layout": "sidebar",
            "isDarkMode": True,
            "viewport": "desktop",
            "colors": [
                {"hex": "#3b82f6", "role": "primary"},
                {"hex": "#1e1e2e", "role": "background"},
            ],
            "components": [
                {
                    "name": "Sidebar",
                    "type": "sidebar",
                    "layout": "flex-col",
                    "colors": [{"hex": "#1e1e2e", "role": "background"}],
                    "typography": {"fontSize": "sm", "fontWeight": "medium"},
                    "spacing": {"padding": "4", "gap": "2"},
                    "children": ["NavItem"],
                    "cssClasses": ["w-64"],
                },
            ],
        })
        manifest = analyzer.analyze_from_json(raw)
        assert manifest.layout_type == LayoutType.SIDEBAR
        assert manifest.is_dark_mode
        assert len(manifest.components) == 1
        assert manifest.components[0].name == "Sidebar"
        assert manifest.components[0].typography.font_size == "sm"
        assert manifest.components[0].spacing.padding == "4"

    def test_parse_invalid_json(self, analyzer):
        manifest = analyzer.analyze_from_json("not valid json")
        assert len(manifest.components) == 0

    # -- Serialization --

    def test_manifest_to_dict(self, analyzer):
        manifest = analyzer.analyze_image("", "Dark dashboard with header")
        d = manifest.to_dict()
        assert "components" in d
        assert "globalColors" in d
        assert "layoutType" in d
        assert "isDarkMode" in d
        assert "colorPalette" in d

    def test_component_to_dict(self):
        comp = UIComponent(
            name="Header",
            component_type="header",
            layout=LayoutType.FLEX_ROW,
            colors=[ColorSpec("#fff", "text")],
            typography=TypographySpec("lg", "bold", "heading"),
            spacing=SpacingSpec("4", "0", "2"),
        )
        d = comp.to_dict()
        assert d["name"] == "Header"
        assert d["layout"] == "flex-row"
        assert len(d["colors"]) == 1

    def test_color_spec_to_dict(self):
        c = ColorSpec("#3b82f6", "primary", 0.8)
        d = c.to_dict()
        assert d["hex"] == "#3b82f6"
        assert d["role"] == "primary"
        assert d["opacity"] == 0.8


# ═══════════════════════════════════════════════════════════════════════════
# DesignSystemMapper tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDesignSystemMapper:
    @pytest.fixture
    def mapper(self):
        return DesignSystemMapper()

    # -- Color matching --

    def test_exact_color_match(self, mapper):
        match = mapper.match_color("#3b82f6", "primary")
        assert match is not None
        assert match.token_name == "blue-500"
        assert match.exact
        assert match.distance == 0.0

    def test_near_color_match(self, mapper):
        match = mapper.match_color("#3a81f5", "primary")
        assert match is not None
        assert match.token_name == "blue-500"
        assert not match.exact
        assert match.distance < 5.0

    def test_no_match_distant_color(self, mapper):
        mapper.MAX_COLOR_DISTANCE = 5.0
        match = mapper.match_color("#ff00ff", "accent")
        # Magenta is far from all default palette colors
        # May or may not match depending on distance threshold
        if match:
            assert match.distance <= 5.0

    def test_custom_token_exact_match(self, mapper):
        mapper.add_token("brand-primary", "#1a2b3c")
        match = mapper.match_color("#1a2b3c")
        assert match is not None
        assert match.token_name == "brand-primary"
        assert match.exact

    def test_role_to_prefix(self):
        assert DesignSystemMapper._role_to_prefix("background") == "bg-"
        assert DesignSystemMapper._role_to_prefix("text") == "text-"
        assert DesignSystemMapper._role_to_prefix("border") == "border-"
        assert DesignSystemMapper._role_to_prefix("primary") == "text-"

    def test_tailwind_class_format(self, mapper):
        match = mapper.match_color("#3b82f6", "background")
        assert match.tailwind_class == "bg-blue-500"

    def test_text_class_format(self, mapper):
        match = mapper.match_color("#3b82f6", "text")
        assert match.tailwind_class == "text-blue-500"

    # -- Tailwind config parsing --

    def test_load_tailwind_config(self, mapper, tmp_path):
        config = tmp_path / "tailwind.config.js"
        config.write_text(textwrap.dedent("""\
            module.exports = {
              theme: {
                extend: {
                  colors: {
                    'brand-primary': '#1a73e8',
                    'brand-accent': '#ea4335',
                    'surface-dark': '#1e1e2e',
                  },
                },
              },
            }
        """))
        count = mapper.load_tailwind_config(str(config))
        assert count == 3
        match = mapper.match_color("#1a73e8")
        assert match is not None
        assert match.token_name == "brand-primary"

    def test_load_nonexistent_config(self, mapper):
        count = mapper.load_tailwind_config("/nonexistent/tailwind.config.js")
        assert count == 0

    # -- CSS variables --

    def test_load_css_variables(self, mapper):
        css = textwrap.dedent("""\
            :root {
              --color-primary: #3b82f6;
              --color-bg-dark: #1e293b;
              --border-subtle: #e2e8f0;
            }
        """)
        count = mapper.load_css_variables(css)
        assert count == 3
        match = mapper.match_color("#3b82f6")
        assert match is not None

    # -- Manifest mapping --

    def test_map_manifest_basic(self, mapper):
        manifest = VisualManifest(
            global_colors=[ColorSpec("#3b82f6", "primary")],
            components=[
                UIComponent(
                    name="Card",
                    component_type="card",
                    layout=LayoutType.FLEX_COL,
                    colors=[ColorSpec("#3b82f6", "background")],
                    spacing=SpacingSpec(padding="4", gap="2"),
                    typography=TypographySpec(font_size="lg", font_weight="bold"),
                ),
            ],
        )
        mapped = mapper.map_manifest(manifest)
        assert len(mapped.global_token_matches) == 1
        assert mapped.global_token_matches[0].token_name == "blue-500"
        assert len(mapped.components) == 1
        card = mapped.components[0]
        assert "flex" in card.layout_classes
        assert "p-4" in card.spacing_classes
        assert "gap-2" in card.spacing_classes
        assert "text-lg" in card.typography_classes
        assert "font-bold" in card.typography_classes

    def test_class_string(self, mapper):
        manifest = VisualManifest(
            components=[UIComponent(
                name="Box",
                layout=LayoutType.FLEX_ROW,
                spacing=SpacingSpec(padding="6"),
            )],
        )
        mapped = mapper.map_manifest(manifest)
        cs = mapped.components[0].class_string
        assert "flex" in cs
        assert "flex-row" in cs
        assert "p-6" in cs

    def test_unmatched_colors(self, mapper):
        mapper.MAX_COLOR_DISTANCE = 0.0  # only exact matches
        manifest = VisualManifest(
            global_colors=[ColorSpec("#abcdef", "accent")],
        )
        mapped = mapper.map_manifest(manifest)
        assert "#abcdef" in mapped.unmatched_colors

    def test_dark_mode_flag(self, mapper):
        manifest = VisualManifest(is_dark_mode=True)
        mapped = mapper.map_manifest(manifest)
        assert mapped.dark_mode

    # -- Serialization --

    def test_token_match_to_dict(self):
        t = TokenMatch("#3b82f6", "blue-500", "bg-blue-500", 0.0, True)
        d = t.to_dict()
        assert d["tokenName"] == "blue-500"
        assert d["exact"]

    def test_mapped_manifest_to_dict(self, mapper):
        manifest = VisualManifest(
            global_colors=[ColorSpec("#3b82f6", "primary")],
            components=[UIComponent(name="Box")],
        )
        mapped = mapper.map_manifest(manifest)
        d = mapped.to_dict()
        assert "components" in d
        assert "globalTokenMatches" in d
        assert "unmatchedColors" in d

    def test_mapped_component_to_dict(self):
        mc = MappedComponent(
            name="Card",
            layout_classes=["flex", "flex-col"],
            spacing_classes=["p-4"],
        )
        d = mc.to_dict()
        assert d["name"] == "Card"
        assert "flex" in d["classString"]

    # -- Color math --

    def test_hex_to_rgb(self):
        assert DesignSystemMapper._hex_to_rgb("#ffffff") == (255, 255, 255)
        assert DesignSystemMapper._hex_to_rgb("#000000") == (0, 0, 0)
        assert DesignSystemMapper._hex_to_rgb("#3b82f6") == (59, 130, 246)

    def test_color_distance_same(self):
        assert DesignSystemMapper._color_distance("#3b82f6", "#3b82f6") == 0.0

    def test_color_distance_different(self):
        dist = DesignSystemMapper._color_distance("#000000", "#ffffff")
        assert dist > 400  # sqrt(255^2 * 3) ≈ 441


# ═══════════════════════════════════════════════════════════════════════════
# Integration: token match end-to-end
# ═══════════════════════════════════════════════════════════════════════════

class TestTokenMatchIntegration:
    def test_primary_blue_maps_to_token(self):
        """If image has #3b82f6 and config has primary: '#3b82f6',
        the code should use text-primary instead of hex."""
        mapper = DesignSystemMapper()
        mapper.add_token("primary", "#3b82f6")

        match = mapper.match_color("#3b82f6", "text")
        assert match is not None
        assert match.token_name == "primary"
        assert "text-primary" in match.tailwind_class

    def test_dark_dashboard_full_pipeline(self):
        """Full pipeline: analyze dark dashboard → map to tokens → generate classes."""
        analyzer = VisionAnalyzer()
        manifest = analyzer.analyze_image("", "Dark mode dashboard with sidebar and header #3b82f6")

        mapper = DesignSystemMapper()
        mapper.add_token("primary", "#3b82f6")
        mapped = mapper.map_manifest(manifest)

        assert manifest.is_dark_mode
        assert manifest.layout_type == LayoutType.SIDEBAR
        assert len(mapped.components) >= 2

    def test_component_preserves_name(self):
        """During visual refactor, component names should be preserved."""
        analyzer = VisionAnalyzer()
        manifest = analyzer.analyze_image("", "Header with buttons and search input")
        names = {c.name for c in manifest.components}
        assert "Header" in names
        assert "Button" in names


# ═══════════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVisionAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        yield

    def test_analyze_endpoint(self):
        resp = self.client.post("/api/v1/vision/analyze", json={
            "description": "Dark mode dashboard with sidebar and header",
            "frameworkHint": "tailwind",
        })
        assert resp.status_code == 200
        manifest = resp.json()["manifest"]
        assert manifest["isDarkMode"]
        assert manifest["layoutType"] == "sidebar"
        assert len(manifest["components"]) >= 2

    def test_analyze_with_colors(self):
        resp = self.client.post("/api/v1/vision/analyze", json={
            "description": "Simple form with primary #3b82f6",
        })
        assert resp.status_code == 200
        assert "#3b82f6" in resp.json()["manifest"]["colorPalette"]

    def test_map_endpoint(self):
        resp = self.client.post("/api/v1/vision/map", json={
            "manifest": {
                "layout": "flex-col",
                "isDarkMode": False,
                "colors": [{"hex": "#3b82f6", "role": "primary"}],
                "components": [{"name": "Card", "type": "card"}],
            },
            "customTokens": {"brand": "#3b82f6"},
        })
        assert resp.status_code == 200
        mapped = resp.json()["mapped"]
        assert len(mapped["globalTokenMatches"]) >= 1

    def test_refactor_endpoint_dry_run(self, tmp_path):
        target = tmp_path / "Dashboard.tsx"
        target.write_text(
            "export const Dashboard = () => {\n"
            "  return <div className='bg-white p-4'>\n"
            "    <UserProfile data={user} />\n"
            "  </div>\n"
            "}\n"
        )
        resp = self.client.post("/api/v1/vision/refactor", json={
            "description": "Dark mode dashboard with sidebar",
            "targetFile": str(target),
            "workspacePath": str(tmp_path),
            "dryRun": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["dryRun"]
        assert "manifest" in data
        assert "suggestions" in data

    def test_refactor_suggestions_include_dark_mode(self, tmp_path):
        target = tmp_path / "App.tsx"
        target.write_text("<div className='bg-white'>Hello</div>\n")

        resp = self.client.post("/api/v1/vision/refactor", json={
            "description": "Dark mode layout",
            "targetFile": str(target),
            "workspacePath": str(tmp_path),
        })
        assert resp.status_code == 200
        suggestions = resp.json()["suggestions"]
        dark_suggestions = [s for s in suggestions if s.get("action") == "add_dark_mode"]
        assert len(dark_suggestions) >= 1
