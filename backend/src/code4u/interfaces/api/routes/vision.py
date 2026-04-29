"""Vision API — visual analysis, design-system mapping, visual refactor.

Endpoints:
  - ``POST /vision/analyze``   — analyze an image and return a VisualManifest.
  - ``POST /vision/map``       — map a manifest to project design tokens.
  - ``POST /vision/refactor``  — analyze image + generate code diff.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.agents.vision.processor import VisionAnalyzer, VisualManifest
from code4u.agents.vision.mapper import DesignSystemMapper, MappedManifest

router = APIRouter()


class AnalyzeRequest(BaseModel):
    imageBase64: str = Field("", description="Base64-encoded image.")
    description: str = Field("", description="Text description of the target UI.")
    frameworkHint: str = Field("tailwind", description="CSS framework.")


class MapRequest(BaseModel):
    manifest: Dict = Field(..., description="Raw VisualManifest JSON.")
    tailwindConfigPath: str = Field("", description="Path to tailwind.config.js.")
    cssVariables: str = Field("", description="Raw CSS with custom properties.")
    customTokens: Dict[str, str] = Field(default_factory=dict)


class VisualRefactorRequest(BaseModel):
    imageBase64: str = Field("", description="Base64-encoded image of the target UI.")
    description: str = Field("", description="Text description of the target UI.")
    targetFile: str = Field("", description="Path to the file to refactor.")
    workspacePath: str = Field("", description="Workspace root path.")
    tailwindConfigPath: str = Field("", description="Path to tailwind.config.js.")
    dryRun: bool = Field(True, description="Preview only; no disk writes.")


@router.post("/vision/analyze")
async def analyze_image(request: AnalyzeRequest):
    """Analyze an image and return a structured VisualManifest."""
    analyzer = VisionAnalyzer()
    manifest = analyzer.analyze_image(
        image_base64=request.imageBase64,
        description=request.description,
        framework_hint=request.frameworkHint,
    )
    return {"manifest": manifest.to_dict()}


@router.post("/vision/map")
async def map_to_tokens(request: MapRequest):
    """Map a VisualManifest to project design tokens."""
    analyzer = VisionAnalyzer()
    manifest = analyzer.analyze_from_json(
        json_module_import_json_dumps(request.manifest)
    )

    mapper = DesignSystemMapper()
    if request.tailwindConfigPath:
        mapper.load_tailwind_config(request.tailwindConfigPath)
    if request.cssVariables:
        mapper.load_css_variables(request.cssVariables)
    for name, hex_val in request.customTokens.items():
        mapper.add_token(name, hex_val)

    mapped = mapper.map_manifest(manifest)
    return {"mapped": mapped.to_dict()}


@router.post("/vision/refactor")
async def visual_refactor(request: VisualRefactorRequest):
    """Analyze an image and generate a code diff for the target file."""
    from pathlib import Path

    # Step 1: Analyze the image
    analyzer = VisionAnalyzer()
    manifest = analyzer.analyze_image(
        image_base64=request.imageBase64,
        description=request.description,
    )

    # Step 2: Map to design tokens
    mapper = DesignSystemMapper()
    if request.tailwindConfigPath:
        mapper.load_tailwind_config(request.tailwindConfigPath)
    mapped = mapper.map_manifest(manifest)

    # Step 3: Read the target file
    target_content = ""
    if request.targetFile:
        target_path = Path(request.targetFile)
        if target_path.is_file():
            target_content = target_path.read_text(encoding="utf-8")

    # Step 4: Build refactor suggestions
    suggestions = _build_visual_suggestions(manifest, mapped, target_content, request.targetFile)

    return {
        "manifest": manifest.to_dict(),
        "mapped": mapped.to_dict(),
        "suggestions": suggestions,
        "dryRun": request.dryRun,
    }


def _build_visual_suggestions(
    manifest: VisualManifest,
    mapped: MappedManifest,
    source_code: str,
    file_path: str,
) -> List[Dict]:
    """Generate actionable refactor suggestions from the visual diff."""
    suggestions = []

    for comp in mapped.components:
        if comp.class_string:
            suggestions.append({
                "component": comp.name,
                "action": "update_classes",
                "suggestedClasses": comp.class_string,
                "colorTokens": [t.to_dict() for t in comp.color_tokens],
                "layoutClasses": comp.layout_classes,
                "spacingClasses": comp.spacing_classes,
                "typographyClasses": comp.typography_classes,
            })

    if manifest.is_dark_mode and "dark:" not in source_code:
        suggestions.append({
            "component": "global",
            "action": "add_dark_mode",
            "description": "Add dark mode variant classes",
        })

    for hex_val in mapped.unmatched_colors:
        suggestions.append({
            "component": "global",
            "action": "add_custom_token",
            "hex": hex_val,
            "description": f"Color {hex_val} not found in design system — add a custom token",
        })

    return suggestions


def json_module_import_json_dumps(data):
    """Helper — serialize dict to JSON string."""
    import json
    return json.dumps(data)
