"""Vision Processor — multimodal image analysis.

Takes an image (base64 or path) and produces a ``VisualManifest``
describing the UI's layout, colors, typography, spacing, and
component boundaries.

Supports two backends:
  1. **LLM Vision** — sends the image to Gemini 1.5 Pro / GPT-4o
     with a system prompt to deconstruct the UI into structured JSON.
  2. **Local Analysis** — deterministic fallback that extracts colors
     from the image description and applies heuristic layout detection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("vision_processor")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class LayoutType(str, Enum):
    FLEX_ROW = "flex-row"
    FLEX_COL = "flex-col"
    GRID = "grid"
    STACK = "stack"
    SIDEBAR = "sidebar"
    UNKNOWN = "unknown"


@dataclass
class ColorSpec:
    """A color extracted from the visual analysis."""
    hex_value: str
    role: str = ""  # "primary", "background", "text", "accent", "border"
    opacity: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hex": self.hex_value,
            "role": self.role,
            "opacity": self.opacity,
        }


@dataclass
class TypographySpec:
    """Typography details extracted from the visual analysis."""
    font_size: str = ""  # "sm", "base", "lg", "xl", "2xl", etc.
    font_weight: str = ""  # "normal", "medium", "semibold", "bold"
    role: str = ""  # "heading", "subheading", "body", "caption"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fontSize": self.font_size,
            "fontWeight": self.font_weight,
            "role": self.role,
        }


@dataclass
class SpacingSpec:
    """Spacing details for a component."""
    padding: str = ""  # e.g. "4", "6", "8" (tailwind scale)
    margin: str = ""
    gap: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"padding": self.padding, "margin": self.margin, "gap": self.gap}


@dataclass
class UIComponent:
    """A UI component identified in the image."""
    name: str
    component_type: str = ""  # "card", "button", "header", "sidebar", "list", "input"
    layout: LayoutType = LayoutType.UNKNOWN
    colors: List[ColorSpec] = field(default_factory=list)
    typography: Optional[TypographySpec] = None
    spacing: Optional[SpacingSpec] = None
    children: List[str] = field(default_factory=list)
    css_classes: List[str] = field(default_factory=list)
    bounds: Dict[str, float] = field(default_factory=dict)  # x, y, w, h (normalized 0-1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "componentType": self.component_type,
            "layout": self.layout.value,
            "colors": [c.to_dict() for c in self.colors],
            "typography": self.typography.to_dict() if self.typography else None,
            "spacing": self.spacing.to_dict() if self.spacing else None,
            "children": self.children,
            "cssClasses": self.css_classes,
            "bounds": self.bounds,
        }


@dataclass
class VisualManifest:
    """Complete visual specification of a UI screenshot."""
    components: List[UIComponent] = field(default_factory=list)
    global_colors: List[ColorSpec] = field(default_factory=list)
    layout_type: LayoutType = LayoutType.UNKNOWN
    is_dark_mode: bool = False
    viewport: str = "desktop"  # "mobile", "tablet", "desktop"
    framework_hint: str = ""  # "tailwind", "css-modules", "styled-components"
    raw_description: str = ""

    @property
    def color_palette(self) -> List[str]:
        return [c.hex_value for c in self.global_colors]

    @property
    def component_names(self) -> List[str]:
        return [c.name for c in self.components]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "components": [c.to_dict() for c in self.components],
            "globalColors": [c.to_dict() for c in self.global_colors],
            "layoutType": self.layout_type.value,
            "isDarkMode": self.is_dark_mode,
            "viewport": self.viewport,
            "frameworkHint": self.framework_hint,
            "colorPalette": self.color_palette,
            "componentNames": self.component_names,
        }


# ---------------------------------------------------------------------------
# LLM prompt for vision analysis
# ---------------------------------------------------------------------------

_VISION_SYSTEM_PROMPT = """\
You are a UI analysis expert. Deconstruct the provided UI screenshot into
a structured JSON manifest. Identify:

1. **Layout**: Is it flex-row, flex-col, grid, sidebar, or stacked?
2. **Components**: List each distinct UI region (header, sidebar, card, button, list, input, etc.)
3. **Colors**: Extract all significant hex codes and label them (primary, background, text, accent, border)
4. **Typography**: Identify font sizes and weights for headings, body, captions
5. **Spacing**: Estimate padding, margin, and gap values in Tailwind scale (1-12)
6. **Dark Mode**: Is this a dark or light theme?

Return valid JSON only, no markdown fences. Schema:
{
  "layout": "flex-row|flex-col|grid|sidebar|stack",
  "isDarkMode": true/false,
  "viewport": "mobile|tablet|desktop",
  "colors": [{"hex": "#...", "role": "primary|background|text|accent|border"}],
  "components": [
    {
      "name": "ComponentName",
      "type": "card|button|header|sidebar|list|input|container",
      "layout": "flex-row|flex-col|grid|stack",
      "colors": [{"hex": "#...", "role": "..."}],
      "typography": {"fontSize": "sm|base|lg|xl|2xl", "fontWeight": "normal|medium|bold"},
      "spacing": {"padding": "4", "gap": "2"},
      "children": ["ChildName"],
      "cssClasses": ["suggested-tailwind-class"]
    }
  ]
}
"""


# ---------------------------------------------------------------------------
# VisionAnalyzer
# ---------------------------------------------------------------------------

class VisionAnalyzer:
    """Analyzes UI screenshots and produces structured ``VisualManifest``s.

    Usage::

        analyzer = VisionAnalyzer()
        manifest = analyzer.analyze_image(image_base64, "Dashboard screenshot")
        for comp in manifest.components:
            print(comp.name, comp.layout, comp.colors)
    """

    def analyze_image(
        self,
        image_base64: str,
        description: str = "",
        *,
        framework_hint: str = "tailwind",
    ) -> VisualManifest:
        """Analyze an image and produce a VisualManifest.

        Attempts LLM vision first; falls back to local heuristics.
        """
        manifest = self._try_llm_analysis(image_base64, description)
        if manifest is None:
            manifest = self._local_analysis(description)

        manifest.framework_hint = framework_hint
        manifest.raw_description = description

        logger.info(
            "vision_analyzed",
            components=len(manifest.components),
            colors=len(manifest.global_colors),
            layout=manifest.layout_type.value,
            dark_mode=manifest.is_dark_mode,
        )

        return manifest

    def analyze_from_json(self, raw_json: str) -> VisualManifest:
        """Parse a raw JSON manifest (e.g., from an LLM response)."""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return VisualManifest()
        return self._parse_manifest_json(data)

    # -- LLM backend ---------------------------------------------------------

    def _try_llm_analysis(self, image_base64: str, description: str) -> Optional[VisualManifest]:
        """Try to analyze via a multimodal LLM (Gemini/GPT-4o)."""
        # In production this calls the SmartRouter with vision capability.
        # For now, return None to fall back to local analysis.
        return None

    # -- Local heuristic analysis --------------------------------------------

    def _local_analysis(self, description: str) -> VisualManifest:
        """Deterministic fallback using description keywords."""
        desc_lower = description.lower()
        manifest = VisualManifest()

        # Layout detection
        if any(kw in desc_lower for kw in ["sidebar", "side bar", "side panel"]):
            manifest.layout_type = LayoutType.SIDEBAR
        elif any(kw in desc_lower for kw in ["grid", "cards", "tiles"]):
            manifest.layout_type = LayoutType.GRID
        elif any(kw in desc_lower for kw in ["column", "vertical", "stacked"]):
            manifest.layout_type = LayoutType.FLEX_COL
        elif any(kw in desc_lower for kw in ["row", "horizontal", "inline"]):
            manifest.layout_type = LayoutType.FLEX_ROW
        else:
            manifest.layout_type = LayoutType.FLEX_COL

        # Dark mode detection
        manifest.is_dark_mode = any(
            kw in desc_lower for kw in ["dark", "night", "black background"]
        )

        # Color extraction from hex codes in description
        hex_matches = re.findall(r"#[0-9a-fA-F]{6}", description)
        for i, hex_val in enumerate(hex_matches):
            role = "primary" if i == 0 else ("accent" if i == 1 else "background")
            manifest.global_colors.append(ColorSpec(hex_value=hex_val, role=role))

        # Default palette for dark mode
        if manifest.is_dark_mode and not manifest.global_colors:
            manifest.global_colors = [
                ColorSpec(hex_value="#1e1e2e", role="background"),
                ColorSpec(hex_value="#cdd6f4", role="text"),
                ColorSpec(hex_value="#89b4fa", role="primary"),
                ColorSpec(hex_value="#a6e3a1", role="accent"),
                ColorSpec(hex_value="#313244", role="border"),
            ]

        # Component extraction from keywords
        component_kws = {
            "header": "header", "navbar": "header", "nav": "header",
            "sidebar": "sidebar", "menu": "sidebar",
            "card": "card", "panel": "card",
            "button": "button", "btn": "button",
            "list": "list", "table": "list",
            "input": "input", "form": "input", "search": "input",
            "footer": "footer",
            "dashboard": "container",
            "chart": "card", "graph": "card",
        }
        seen = set()
        for kw, comp_type in component_kws.items():
            if kw in desc_lower and comp_type not in seen:
                comp = UIComponent(
                    name=comp_type.capitalize(),
                    component_type=comp_type,
                    layout=LayoutType.FLEX_COL if comp_type in ("card", "sidebar") else LayoutType.FLEX_ROW,
                )
                if manifest.is_dark_mode:
                    comp.colors = [
                        ColorSpec("#1e1e2e", "background"),
                        ColorSpec("#cdd6f4", "text"),
                    ]
                manifest.components.append(comp)
                seen.add(comp_type)

        # Viewport detection
        if any(kw in desc_lower for kw in ["mobile", "phone", "small screen"]):
            manifest.viewport = "mobile"
        elif any(kw in desc_lower for kw in ["tablet", "ipad"]):
            manifest.viewport = "tablet"

        return manifest

    # -- JSON parsing --------------------------------------------------------

    def _parse_manifest_json(self, data: Dict[str, Any]) -> VisualManifest:
        """Parse a raw JSON dict into a VisualManifest."""
        manifest = VisualManifest()

        layout_str = data.get("layout", "unknown")
        try:
            manifest.layout_type = LayoutType(layout_str)
        except ValueError:
            manifest.layout_type = LayoutType.UNKNOWN

        manifest.is_dark_mode = data.get("isDarkMode", False)
        manifest.viewport = data.get("viewport", "desktop")

        for c in data.get("colors", []):
            manifest.global_colors.append(ColorSpec(
                hex_value=c.get("hex", ""),
                role=c.get("role", ""),
            ))

        for comp_data in data.get("components", []):
            comp = UIComponent(
                name=comp_data.get("name", ""),
                component_type=comp_data.get("type", ""),
            )
            layout_val = comp_data.get("layout", "unknown")
            try:
                comp.layout = LayoutType(layout_val)
            except ValueError:
                comp.layout = LayoutType.UNKNOWN

            for c in comp_data.get("colors", []):
                comp.colors.append(ColorSpec(hex_value=c.get("hex", ""), role=c.get("role", "")))

            typo = comp_data.get("typography")
            if typo:
                comp.typography = TypographySpec(
                    font_size=typo.get("fontSize", ""),
                    font_weight=typo.get("fontWeight", ""),
                )

            spacing = comp_data.get("spacing")
            if spacing:
                comp.spacing = SpacingSpec(
                    padding=str(spacing.get("padding", "")),
                    margin=str(spacing.get("margin", "")),
                    gap=str(spacing.get("gap", "")),
                )

            comp.children = comp_data.get("children", [])
            comp.css_classes = comp_data.get("cssClasses", [])
            manifest.components.append(comp)

        return manifest
