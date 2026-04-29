"""Hotspot Analysis & Predictive Risk API routes.

Endpoints:
  - POST /api/v1/analytics/hotspots        — analyze repo for churn hotspots
  - GET  /api/v1/analytics/hotspots/demo   — get demo hotspot data
  - POST /api/v1/analytics/predict         — predict risks for diffs
  - GET  /api/v1/analytics/predict/report  — get latest prediction report
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from code4u.analytics.hotspot_analyzer import Hotspot, HotspotAnalyzer
from code4u.agents.predictor_agent import PredictorAgent

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_last_hotspots: List[Dict[str, Any]] = []
_last_predictions: List[Dict[str, Any]] = []
_last_report: str = ""


class HotspotRequest(BaseModel):
    repo_path: str = Field(".", description="Path to git repository")
    days: int = Field(90, description="Days of history to analyze")
    top_n: int = Field(20, description="Number of top hotspots")


class PredictRequest(BaseModel):
    diffs: Dict[str, str] = Field(
        ..., description="filepath -> diff content"
    )
    hotspots: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Hotspot data (from /hotspots). If empty, uses demo data.",
    )
    repo_path: str = Field(".", description="Path to git repo for auto-analysis")


@router.post("/hotspots")
async def analyze_hotspots(request: HotspotRequest) -> Dict[str, Any]:
    global _last_hotspots
    analyzer = HotspotAnalyzer(repo_path=request.repo_path)
    result = await analyzer.analyze(days=request.days, top_n=request.top_n)
    _last_hotspots = result.get("hotspots", [])
    return result


@router.get("/hotspots/demo")
async def get_demo_hotspots() -> Dict[str, Any]:
    global _last_hotspots
    analyzer = HotspotAnalyzer(repo_path=".")
    churn_data = analyzer._demo_churn_data()
    hotspots = []
    for fc in churn_data:
        cx = analyzer._estimate_complexity(fc.file_path)
        rs = analyzer._calculate_risk_score(fc, cx)
        rl = (
            "critical"
            if rs > 80
            else "high"
            if rs > 50
            else "medium"
            if rs > 25
            else "low"
        )
        pred = analyzer._generate_prediction(fc, cx, rs)
        h = Hotspot(fc.file_path, round(rs, 2), fc, cx, rl, pred)
        hotspots.append(h.to_dict())
    hotspots.sort(key=lambda x: x["riskScore"], reverse=True)
    _last_hotspots = hotspots
    return {
        "hotspots": hotspots,
        "totalFilesAnalyzed": len(churn_data),
        "topRiskFiles": len(
            [h for h in hotspots if h["riskLevel"] in ("critical", "high")]
        ),
        "analyzedDays": 90,
        "repoPath": ".",
    }


@router.post("/predict")
async def predict_risks(request: PredictRequest) -> Dict[str, Any]:
    global _last_predictions, _last_report
    hotspots = request.hotspots
    if not hotspots:
        hotspots = _last_hotspots
    if not hotspots:
        demo = await get_demo_hotspots()
        hotspots = demo.get("hotspots", [])

    agent = PredictorAgent()
    warnings = agent.predict_risks(request.diffs, hotspots)
    _last_predictions = [w.to_dict() for w in warnings]
    _last_report = agent.generate_report(warnings)
    return {
        "warnings": _last_predictions,
        "totalWarnings": len(warnings),
        "critical": sum(1 for w in warnings if w.risk_level == "critical"),
        "high": sum(1 for w in warnings if w.risk_level == "high"),
    }


@router.get("/predict/report")
async def get_prediction_report() -> Dict[str, Any]:
    return {"report": _last_report, "warningCount": len(_last_predictions)}
