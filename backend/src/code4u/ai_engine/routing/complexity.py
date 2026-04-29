from __future__ import annotations
"""Complexity scoring for routing decisions.

Complexity is GRAPH-DERIVED, not guessed.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import structlog

logger = structlog.get_logger("routing.complexity")


class RiskLevel(str, Enum):
    """Risk level of an operation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ComplexityScore:
    """
    Complexity score for routing decisions.
    
    All inputs are deterministic, derived from the Knowledge Graph.
    """
    # Raw metrics
    impacted_node_count: int = 0
    schema_involvement: bool = False
    cross_repo_impact: bool = False
    breaking_change: bool = False
    prompt_token_estimate: int = 0
    
    # Derived scores
    structural_complexity: float = 0.0  # 0-1
    semantic_complexity: float = 0.0    # 0-1
    risk_complexity: float = 0.0        # 0-1
    
    # Final score
    total_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    
    # Routing recommendation
    requires_premium: bool = False
    recommendation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "impacted_nodes": self.impacted_node_count,
            "schema_involvement": self.schema_involvement,
            "cross_repo": self.cross_repo_impact,
            "breaking_change": self.breaking_change,
            "token_estimate": self.prompt_token_estimate,
            "total_score": self.total_score,
            "risk_level": self.risk_level.value,
            "requires_premium": self.requires_premium,
        }


class ComplexityScorer:
    """
    Score request complexity for routing.
    
    Inputs:
    - Number of impacted nodes
    - Schema involvement
    - Cross-repo impact
    - Breaking change flag
    - Prompt token size
    """
    
    # Thresholds (configurable per tenant)
    DEFAULT_THRESHOLDS = {
        "low_complexity": 0.3,
        "medium_complexity": 0.6,
        "high_complexity": 0.8,
        "max_self_hosted_tokens": 6000,
        "max_self_hosted_nodes": 15,
    }
    
    def __init__(self, thresholds: Dict[str, Any] | None = None):
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
    
    def score(
        self,
        impacted_nodes: list[Any],
        context: Dict[str, Any]
    ) -> ComplexityScore:
        """
        Score the complexity of a request.
        
        Returns a deterministic ComplexityScore for routing.
        """
        result = ComplexityScore()
        
        # Count impacted nodes
        result.impacted_node_count = len(impacted_nodes)
        
        # Check for schema involvement
        result.schema_involvement = any(
            n.get("node_type") == "schema" or n.get("nodeType") == "schema"
            for n in impacted_nodes
            if isinstance(n, dict)
        )
        
        # Check for cross-repo impact
        repos = set()
        for node in impacted_nodes:
            if isinstance(node, dict):
                repo_id = node.get("repository_id") or node.get("repositoryId")
                if repo_id:
                    repos.add(repo_id)
        result.cross_repo_impact = len(repos) > 1
        
        # Check breaking change
        result.breaking_change = context.get("breaking_change", False)
        
        # Estimate tokens
        result.prompt_token_estimate = context.get("token_estimate", 0)
        
        # Calculate sub-scores
        result.structural_complexity = self._score_structural(result)
        result.semantic_complexity = self._score_semantic(result)
        result.risk_complexity = self._score_risk(result)
        
        # Calculate total score (weighted)
        result.total_score = (
            result.structural_complexity * 0.3 +
            result.semantic_complexity * 0.3 +
            result.risk_complexity * 0.4
        )
        
        # Determine risk level
        result.risk_level = self._determine_risk_level(result.total_score)
        
        # Determine if premium is required
        result.requires_premium = self._requires_premium(result)
        result.recommendation = self._get_recommendation(result)
        
        logger.info(
            "complexity_scored",
            total_score=result.total_score,
            risk_level=result.risk_level.value,
            requires_premium=result.requires_premium
        )
        
        return result
    
    def _score_structural(self, result: ComplexityScore) -> float:
        """Score based on structural complexity."""
        node_score = min(result.impacted_node_count / 20, 1.0)
        token_score = min(result.prompt_token_estimate / 8000, 1.0)
        return (node_score * 0.6 + token_score * 0.4)
    
    def _score_semantic(self, result: ComplexityScore) -> float:
        """Score based on semantic complexity."""
        score = 0.0
        if result.schema_involvement:
            score += 0.4
        if result.cross_repo_impact:
            score += 0.4
        # Base complexity
        score += 0.2
        return min(score, 1.0)
    
    def _score_risk(self, result: ComplexityScore) -> float:
        """Score based on risk factors."""
        if result.breaking_change:
            return 0.9
        if result.schema_involvement and result.cross_repo_impact:
            return 0.7
        if result.schema_involvement or result.cross_repo_impact:
            return 0.5
        return 0.2
    
    def _determine_risk_level(self, total_score: float) -> RiskLevel:
        """Determine risk level from score."""
        if total_score >= self.thresholds["high_complexity"]:
            return RiskLevel.HIGH
        if total_score >= self.thresholds["medium_complexity"]:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
    
    def _requires_premium(self, result: ComplexityScore) -> bool:
        """Determine if premium model is required."""
        # Hard rules
        if result.prompt_token_estimate > self.thresholds["max_self_hosted_tokens"]:
            return True
        if result.impacted_node_count > self.thresholds["max_self_hosted_nodes"]:
            return True
        
        # Risk-based rules (configurable)
        if result.breaking_change and result.schema_involvement:
            return True  # Can be made configurable
        
        return False
    
    def _get_recommendation(self, result: ComplexityScore) -> str:
        """Get human-readable recommendation."""
        if result.requires_premium:
            return "Use premium model for reliability"
        if result.risk_level == RiskLevel.HIGH:
            return "Self-hosted with careful validation"
        if result.risk_level == RiskLevel.MEDIUM:
            return "Self-hosted with standard validation"
        return "Self-hosted model"

