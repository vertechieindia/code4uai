from __future__ import annotations
"""Golden dataset management for code4u.ai evaluation."""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
import json
import structlog

logger = structlog.get_logger("evaluation.dataset")


class EvaluationCategory(str, Enum):
    """Categories of evaluation cases."""
    REFACTOR = "refactor"
    API_EVOLUTION = "api_evolution"
    FRONTEND_BACKEND_SYNC = "frontend_backend_sync"
    REJECTION_CASES = "rejection_cases"
    SCHEMA_MIGRATION = "schema_migration"
    RENAME = "rename"
    EXTRACT = "extract"


@dataclass
class ExpectedOutput:
    """Expected output for evaluation."""
    diff: str
    allowed_variations: List[str] = field(default_factory=list)
    breaking_change: bool = False
    affected_files: List[str] = field(default_factory=list)
    
    def matches(self, actual_diff: str, strict: bool = False) -> tuple[bool, float]:
        """
        Check if actual diff matches expected.
        
        Returns (matches, similarity_score)
        """
        # Normalize diffs for comparison
        expected_normalized = self._normalize(self.diff)
        actual_normalized = self._normalize(actual_diff)
        
        # Exact match
        if expected_normalized == actual_normalized:
            return True, 1.0
        
        # Check allowed variations
        for variation in self.allowed_variations:
            if self._normalize(variation) == actual_normalized:
                return True, 0.95
        
        if strict:
            return False, 0.0
        
        # Fuzzy match - check key changes are present
        similarity = self._calculate_similarity(expected_normalized, actual_normalized)
        return similarity > 0.8, similarity
    
    def _normalize(self, diff: str) -> str:
        """Normalize diff for comparison."""
        lines = diff.strip().split("\n")
        # Remove line numbers and whitespace variations
        normalized = []
        for line in lines:
            line = line.rstrip()
            if line.startswith("@@"):
                # Normalize hunk headers
                normalized.append("@@")
            elif line and not line.startswith("\\"):
                normalized.append(line)
        return "\n".join(normalized)
    
    def _calculate_similarity(self, expected: str, actual: str) -> float:
        """Calculate similarity score between diffs."""
        expected_lines = set(expected.split("\n"))
        actual_lines = set(actual.split("\n"))
        
        if not expected_lines:
            return 0.0
        
        intersection = expected_lines & actual_lines
        return len(intersection) / len(expected_lines)


@dataclass
class EvaluationCase:
    """A single evaluation case."""
    case_id: str
    category: EvaluationCategory
    name: str
    description: str
    
    # Input
    input_files: Dict[str, str]  # path -> content
    instruction: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Expected output
    expected: ExpectedOutput = field(default_factory=lambda: ExpectedOutput(diff=""))
    
    # Metadata
    difficulty: str = "medium"  # easy, medium, hard
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "input_files": self.input_files,
            "instruction": self.instruction,
            "context": self.context,
            "expected": {
                "diff": self.expected.diff,
                "breaking_change": self.expected.breaking_change,
                "affected_files": self.expected.affected_files,
            },
            "difficulty": self.difficulty,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationCase":
        return cls(
            case_id=data["case_id"],
            category=EvaluationCategory(data["category"]),
            name=data["name"],
            description=data["description"],
            input_files=data["input_files"],
            instruction=data["instruction"],
            context=data.get("context", {}),
            expected=ExpectedOutput(
                diff=data.get("expected", {}).get("diff", ""),
                breaking_change=data.get("expected", {}).get("breaking_change", False),
                affected_files=data.get("expected", {}).get("affected_files", []),
            ),
            difficulty=data.get("difficulty", "medium"),
            tags=data.get("tags", []),
        )


class GoldenDataset:
    """
    Golden dataset for evaluation.
    
    Structure:
    /eval
      ├── refactor/
      ├── api-evolution/
      ├── frontend-backend-sync/
      ├── rejection-cases/
    """
    
    def __init__(self, dataset_path: str = "./eval"):
        self.dataset_path = Path(dataset_path)
        self.cases: dict[str, EvaluationCase] = {}
        self._load_cases()
    
    def _load_cases(self):
        """Load all evaluation cases from disk."""
        if not self.dataset_path.exists():
            logger.warning("dataset_path_not_found", path=str(self.dataset_path))
            return
        
        for category_dir in self.dataset_path.iterdir():
            if category_dir.is_dir():
                for case_file in category_dir.glob("*.json"):
                    try:
                        data = json.loads(case_file.read_text())
                        case = EvaluationCase.from_dict(data)
                        self.cases[case.case_id] = case
                    except Exception as e:
                        logger.error("case_load_failed", file=str(case_file), error=str(e))
        
        logger.info("dataset_loaded", case_count=len(self.cases))
    
    def get_case(self, case_id: str) -> EvaluationCase | None:
        """Get a specific case by ID."""
        return self.cases.get(case_id)
    
    def get_cases_by_category(self, category: EvaluationCategory) -> list[EvaluationCase]:
        """Get all cases in a category."""
        return [c for c in self.cases.values() if c.category == category]
    
    def get_all_cases(self) -> list[EvaluationCase]:
        """Get all cases."""
        return list(self.cases.values())
    
    def add_case(self, case: EvaluationCase):
        """Add a new case to the dataset."""
        self.cases[case.case_id] = case
        self._save_case(case)
    
    def _save_case(self, case: EvaluationCase):
        """Save case to disk."""
        category_dir = self.dataset_path / case.category.value
        category_dir.mkdir(parents=True, exist_ok=True)
        
        case_file = category_dir / f"{case.case_id}.json"
        case_file.write_text(json.dumps(case.to_dict(), indent=2))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        by_category = {}
        by_difficulty = {}
        
        for case in self.cases.values():
            cat = case.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            
            diff = case.difficulty
            by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
        
        return {
            "total_cases": len(self.cases),
            "by_category": by_category,
            "by_difficulty": by_difficulty,
        }


def create_sample_golden_dataset(output_path: str = "./eval") -> GoldenDataset:
    """Create a sample golden dataset for testing."""
    dataset = GoldenDataset(output_path)
    
    # Sample case 1: Python rename
    dataset.add_case(EvaluationCase(
        case_id="refactor-001",
        category=EvaluationCategory.RENAME,
        name="Rename Pydantic field",
        description="Rename email field to primaryEmail in a Pydantic model",
        input_files={
            "schemas/user.py": """from pydantic import BaseModel

class User(BaseModel):
    id: int
    email: str
    name: str
"""
        },
        instruction="Rename the field 'email' to 'primaryEmail'",
        context={"language": "python", "frameworks": ["pydantic"]},
        expected=ExpectedOutput(
            diff="""--- a/schemas/user.py
+++ b/schemas/user.py
@@ -3,5 +3,5 @@
 class User(BaseModel):
     id: int
-    email: str
+    primaryEmail: str
     name: str""",
            breaking_change=True,
            affected_files=["schemas/user.py"]
        ),
        difficulty="easy",
        tags=["rename", "pydantic", "breaking"]
    ))
    
    # Sample case 2: React component extraction
    dataset.add_case(EvaluationCase(
        case_id="refactor-002",
        category=EvaluationCategory.EXTRACT,
        name="Extract React button component",
        description="Extract button into a reusable component",
        input_files={
            "components/UserProfile.tsx": """export function UserProfile({ user }) {
  return (
    <div className="profile">
      <h1>{user.name}</h1>
      <button onClick={() => alert('clicked')}>
        Click me
      </button>
    </div>
  );
}"""
        },
        instruction="Extract the button into a separate Button component in the same file",
        context={"language": "typescript", "frameworks": ["react"]},
        expected=ExpectedOutput(
            diff="""--- a/components/UserProfile.tsx
+++ b/components/UserProfile.tsx
@@ -1,9 +1,14 @@
+function Button({ onClick, children }) {
+  return <button onClick={onClick}>{children}</button>;
+}
+
 export function UserProfile({ user }) {
   return (
     <div className="profile">
       <h1>{user.name}</h1>
-      <button onClick={() => alert('clicked')}>
+      <Button onClick={() => alert('clicked')}>
         Click me
-      </button>
+      </Button>
     </div>
   );
 }""",
            breaking_change=False,
            affected_files=["components/UserProfile.tsx"]
        ),
        difficulty="medium",
        tags=["extract", "react", "component"]
    ))
    
    # Sample case 3: Rejection case
    dataset.add_case(EvaluationCase(
        case_id="rejection-001",
        category=EvaluationCategory.REJECTION_CASES,
        name="Reject vague instruction",
        description="Should reject when instruction is too vague",
        input_files={
            "utils/helper.py": "def process(data): return data"
        },
        instruction="Make it better",
        context={"language": "python"},
        expected=ExpectedOutput(
            diff="INSUFFICIENT_CONTEXT",
            breaking_change=False
        ),
        difficulty="easy",
        tags=["rejection", "vague"]
    ))
    
    logger.info("sample_dataset_created", case_count=len(dataset.cases))
    return dataset

