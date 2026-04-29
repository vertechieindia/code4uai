"""Design System Mapper — aligns visual specs to project tokens.

Given a ``VisualManifest`` and the project's design system
(Tailwind config, CSS variables), the mapper:

  1. Matches each hex color to the nearest project-defined token.
  2. Converts pixel/abstract spacing to Tailwind utility classes.
  3. Generates a ``MappedManifest`` with the aligned classes.

This prevents "magic numbers" in the generated code — the AI
uses ``bg-primary`` instead of ``bg-[#3b82f6]``.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from code4u.agents.vision.processor import (
    VisualManifest,
    UIComponent,
    ColorSpec,
    LayoutType,
)

logger = structlog.get_logger("vision_mapper")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TokenMatch:
    """A match between a visual color and a project design token."""
    hex_value: str
    token_name: str
    tailwind_class: str
    distance: float = 0.0
    exact: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hex": self.hex_value,
            "tokenName": self.token_name,
            "tailwindClass": self.tailwind_class,
            "distance": round(self.distance, 2),
            "exact": self.exact,
        }


@dataclass
class MappedComponent:
    """A UI component with project-aligned classes."""
    name: str
    component_type: str = ""
    tailwind_classes: List[str] = field(default_factory=list)
    color_tokens: List[TokenMatch] = field(default_factory=list)
    layout_classes: List[str] = field(default_factory=list)
    spacing_classes: List[str] = field(default_factory=list)
    typography_classes: List[str] = field(default_factory=list)

    @property
    def class_string(self) -> str:
        all_classes = (
            self.layout_classes
            + self.color_tokens_as_classes
            + self.spacing_classes
            + self.typography_classes
            + self.tailwind_classes
        )
        return " ".join(dict.fromkeys(all_classes))

    @property
    def color_tokens_as_classes(self) -> List[str]:
        return [t.tailwind_class for t in self.color_tokens]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "componentType": self.component_type,
            "classString": self.class_string,
            "layoutClasses": self.layout_classes,
            "colorTokens": [t.to_dict() for t in self.color_tokens],
            "spacingClasses": self.spacing_classes,
            "typographyClasses": self.typography_classes,
        }


@dataclass
class MappedManifest:
    """A VisualManifest aligned to the project's design system."""
    components: List[MappedComponent] = field(default_factory=list)
    global_token_matches: List[TokenMatch] = field(default_factory=list)
    unmatched_colors: List[str] = field(default_factory=list)
    dark_mode: bool = False
    config_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "components": [c.to_dict() for c in self.components],
            "globalTokenMatches": [t.to_dict() for t in self.global_token_matches],
            "unmatchedColors": self.unmatched_colors,
            "darkMode": self.dark_mode,
            "configSource": self.config_source,
        }


# ---------------------------------------------------------------------------
# Default Tailwind color palette
# ---------------------------------------------------------------------------

_DEFAULT_TAILWIND_COLORS: Dict[str, str] = {
    "slate-50": "#f8fafc", "slate-100": "#f1f5f9", "slate-200": "#e2e8f0",
    "slate-300": "#cbd5e1", "slate-400": "#94a3b8", "slate-500": "#64748b",
    "slate-600": "#475569", "slate-700": "#334155", "slate-800": "#1e293b",
    "slate-900": "#0f172a", "slate-950": "#020617",
    "gray-50": "#f9fafb", "gray-100": "#f3f4f6", "gray-200": "#e5e7eb",
    "gray-300": "#d1d5db", "gray-400": "#9ca3af", "gray-500": "#6b7280",
    "gray-600": "#4b5563", "gray-700": "#374151", "gray-800": "#1f2937",
    "gray-900": "#111827", "gray-950": "#030712",
    "red-500": "#ef4444", "red-600": "#dc2626",
    "orange-500": "#f97316",
    "yellow-500": "#eab308",
    "green-500": "#22c55e", "green-600": "#16a34a",
    "blue-400": "#60a5fa", "blue-500": "#3b82f6", "blue-600": "#2563eb",
    "blue-700": "#1d4ed8",
    "indigo-500": "#6366f1", "indigo-600": "#4f46e5",
    "purple-500": "#a855f7",
    "pink-500": "#ec4899",
    "white": "#ffffff", "black": "#000000",
}


# ---------------------------------------------------------------------------
# DesignSystemMapper
# ---------------------------------------------------------------------------

class DesignSystemMapper:
    """Maps visual specifications to project design tokens.

    Usage::

        mapper = DesignSystemMapper()
        mapper.load_tailwind_config("/project/tailwind.config.js")
        mapped = mapper.map_manifest(visual_manifest)
        for comp in mapped.components:
            print(comp.class_string)
    """

    MAX_COLOR_DISTANCE = 30.0  # max Euclidean distance to consider a "match"

    def __init__(self) -> None:
        self._color_tokens: Dict[str, str] = dict(_DEFAULT_TAILWIND_COLORS)
        self._custom_tokens: Dict[str, str] = {}
        self._config_source = "default"

    def load_tailwind_config(self, config_path: str) -> int:
        """Parse a tailwind.config.js and extract custom color tokens.

        Returns the number of custom tokens found.
        """
        path = Path(config_path)
        if not path.is_file():
            return 0

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return 0

        custom = self._extract_colors_from_config(content)
        self._custom_tokens.update(custom)
        self._color_tokens.update(custom)
        self._config_source = str(path)

        logger.info("tailwind_config_loaded", path=config_path, custom_tokens=len(custom))
        return len(custom)

    def load_css_variables(self, css_content: str) -> int:
        """Extract CSS custom properties (--color-primary: #xxx)."""
        pattern = re.compile(r"--([a-zA-Z0-9_-]+)\s*:\s*(#[0-9a-fA-F]{3,8})")
        count = 0
        for m in pattern.finditer(css_content):
            name = m.group(1)
            hex_val = m.group(2)
            self._custom_tokens[name] = hex_val
            self._color_tokens[name] = hex_val
            count += 1
        return count

    def add_token(self, name: str, hex_value: str) -> None:
        """Manually register a design token."""
        self._custom_tokens[name] = hex_value
        self._color_tokens[name] = hex_value

    def map_manifest(self, manifest: VisualManifest) -> MappedManifest:
        """Map a VisualManifest to project-aligned classes."""
        mapped = MappedManifest(
            dark_mode=manifest.is_dark_mode,
            config_source=self._config_source,
        )

        # Map global colors
        for color in manifest.global_colors:
            match = self.match_color(color.hex_value, color.role)
            if match:
                mapped.global_token_matches.append(match)
            else:
                mapped.unmatched_colors.append(color.hex_value)

        # Map components
        for comp in manifest.components:
            mapped_comp = self._map_component(comp, manifest.is_dark_mode)
            mapped.components.append(mapped_comp)

        logger.info(
            "manifest_mapped",
            components=len(mapped.components),
            matched=len(mapped.global_token_matches),
            unmatched=len(mapped.unmatched_colors),
        )

        return mapped

    def match_color(self, hex_value: str, role: str = "") -> Optional[TokenMatch]:
        """Find the nearest design token for a hex color.

        Custom tokens are preferred over defaults when distances are equal.
        """
        hex_norm = hex_value.lower().strip()
        best_name = ""
        best_dist = float("inf")
        best_is_custom = False

        for token_name, token_hex in self._color_tokens.items():
            dist = self._color_distance(hex_norm, token_hex.lower())
            is_custom = token_name in self._custom_tokens
            if dist < best_dist or (dist == best_dist and is_custom and not best_is_custom):
                best_dist = dist
                best_name = token_name
                best_is_custom = is_custom

        if best_dist > self.MAX_COLOR_DISTANCE:
            return None

        prefix = self._role_to_prefix(role)
        tw_class = f"{prefix}{best_name}" if prefix else f"text-{best_name}"

        return TokenMatch(
            hex_value=hex_norm,
            token_name=best_name,
            tailwind_class=tw_class,
            distance=best_dist,
            exact=best_dist == 0.0,
        )

    # -- Component mapping ---------------------------------------------------

    def _map_component(self, comp: UIComponent, dark_mode: bool) -> MappedComponent:
        """Map a single UIComponent to Tailwind classes."""
        mc = MappedComponent(name=comp.name, component_type=comp.component_type)

        # Layout classes
        mc.layout_classes = self._layout_to_classes(comp.layout)

        # Color tokens
        for color in comp.colors:
            match = self.match_color(color.hex_value, color.role)
            if match:
                mc.color_tokens.append(match)

        # Spacing classes
        if comp.spacing:
            if comp.spacing.padding:
                mc.spacing_classes.append(f"p-{comp.spacing.padding}")
            if comp.spacing.margin:
                mc.spacing_classes.append(f"m-{comp.spacing.margin}")
            if comp.spacing.gap:
                mc.spacing_classes.append(f"gap-{comp.spacing.gap}")

        # Typography classes
        if comp.typography:
            if comp.typography.font_size:
                mc.typography_classes.append(f"text-{comp.typography.font_size}")
            if comp.typography.font_weight:
                mc.typography_classes.append(f"font-{comp.typography.font_weight}")

        return mc

    def _layout_to_classes(self, layout: LayoutType) -> List[str]:
        """Convert a LayoutType to Tailwind classes."""
        mapping = {
            LayoutType.FLEX_ROW: ["flex", "flex-row"],
            LayoutType.FLEX_COL: ["flex", "flex-col"],
            LayoutType.GRID: ["grid"],
            LayoutType.SIDEBAR: ["flex", "flex-row"],
            LayoutType.STACK: ["flex", "flex-col"],
            LayoutType.UNKNOWN: [],
        }
        return mapping.get(layout, [])

    # -- Color math ----------------------------------------------------------

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Convert '#rrggbb' to (r, g, b)."""
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        if len(h) < 6:
            return (0, 0, 0)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    @staticmethod
    def _color_distance(hex_a: str, hex_b: str) -> float:
        """Euclidean distance between two hex colors in RGB space."""
        r1, g1, b1 = DesignSystemMapper._hex_to_rgb(hex_a)
        r2, g2, b2 = DesignSystemMapper._hex_to_rgb(hex_b)
        return math.sqrt((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2)

    @staticmethod
    def _role_to_prefix(role: str) -> str:
        """Map a color role to a Tailwind class prefix."""
        prefixes = {
            "background": "bg-",
            "text": "text-",
            "primary": "text-",
            "accent": "text-",
            "border": "border-",
        }
        return prefixes.get(role, "text-")

    # -- Tailwind config parsing ---------------------------------------------

    def _extract_colors_from_config(self, content: str) -> Dict[str, str]:
        """Extract color definitions from a tailwind.config.js."""
        colors: Dict[str, str] = {}

        # Pattern: 'token-name': '#hexval' or "token-name": "#hexval"
        pattern = re.compile(
            r"""['"]([a-zA-Z0-9_-]+)['"]\s*:\s*['"](\#[0-9a-fA-F]{3,8})['"]"""
        )
        for m in pattern.finditer(content):
            colors[m.group(1)] = m.group(2)

        return colors
