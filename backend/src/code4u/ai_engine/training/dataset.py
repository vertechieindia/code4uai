from __future__ import annotations
"""Training dataset schema and builder for code4u.ai.

Training examples follow a strict schema to ensure:
- Deterministic output behavior
- Constraint awareness
- Rejection of invalid requests
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import json


class ExampleType(str, Enum):
    """Types of training examples."""
    REFACTOR_DIFF = "refactor_diff"
    SCHEMA_EVOLUTION = "schema_evolution"
    FRONTEND_BACKEND_SYNC = "frontend_backend_sync"
    FAILING_TO_PASSING = "failing_to_passing"
    REJECT_CHANGE = "reject_change"  # Negative examples
    OWNERSHIP_VIOLATION = "ownership_violation"


@dataclass
class CodeContext:
    """Context for a training example."""
    language: str
    frameworks: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)


@dataclass
class InputCode:
    """Input code for training."""
    file_path: str
    content: str
    line_range: Tuple[int, int] | None = None


@dataclass
class ExpectedOutput:
    """Expected output for training."""
    diff: str
    explanation: Optional[str] = None


@dataclass
class TrainingExample:
    """
    Single training example for code4u.ai fine-tuning.
    
    Schema matches the fine-tuning dataset specification:
    - instruction: What to do
    - context: Language, frameworks, constraints
    - input_code: Source code
    - expected_output: Unified diff
    - metadata: Quality signals
    """
    instruction: str
    context: CodeContext
    input_code: InputCode
    expected_output: ExpectedOutput
    
    # Metadata for quality/filtering
    example_type: ExampleType = ExampleType.REFACTOR_DIFF
    breaking_change: bool = False
    confidence: str = "high"  # high, medium, low
    source: str = "synthetic"  # synthetic, real_commit, human_reviewed
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_jsonl(self) -> str:
        """Convert to JSONL format for training."""
        return json.dumps({
            "instruction": self.instruction,
            "context": {
                "language": self.context.language,
                "frameworks": self.context.frameworks,
                "constraints": self.context.constraints,
                "affected_components": self.context.affected_components,
            },
            "input_code": {
                "file_path": self.input_code.file_path,
                "content": self.input_code.content,
            },
            "expected_output": {
                "diff": self.expected_output.diff,
            },
            "metadata": {
                "example_type": self.example_type.value,
                "breaking_change": self.breaking_change,
                "confidence": self.confidence,
                "source": self.source,
            }
        })
    
    def to_prompt(self) -> str:
        """Convert to prompt format for training."""
        constraints_str = "\n".join(f"- {c}" for c in self.context.constraints) or "- None"
        components_str = "\n".join(f"- {c}" for c in self.context.affected_components) or "- None"
        
        return f"""SYSTEM:
You are a deterministic code refactoring engine for code4u.ai.
Output ONLY unified diff format. No explanations.

INSTRUCTION:
{self.instruction}

CONTEXT:
- Language: {self.context.language}
- Frameworks: {', '.join(self.context.frameworks)}

CONSTRAINTS:
{constraints_str}

AFFECTED COMPONENTS:
{components_str}

INPUT CODE:
```{self.context.language}
{self.input_code.content}
```

OUTPUT:
```diff
{self.expected_output.diff}
```
---END---"""


class DatasetBuilder:
    """Build training datasets from various sources."""
    
    def __init__(self, output_dir: str = "./training_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.examples: list[TrainingExample] = []
    
    def add_example(self, example: TrainingExample) -> None:
        """Add a training example."""
        self.examples.append(example)
    
    def add_from_git_commit(
        self,
        repo_path: str,
        commit_sha: str,
        instruction: str,
        language: str,
        frameworks: List[str] | None = None
    ) -> None:
        """
        Create training example from a git commit.
        
        This extracts real-world refactoring patterns.
        """
        import subprocess
        
        # Get diff from commit
        result = subprocess.run(
            ["git", "-C", repo_path, "show", commit_sha, "--format="],
            capture_output=True, text=True
        )
        diff = result.stdout
        
        # Get files changed
        files_result = subprocess.run(
            ["git", "-C", repo_path, "show", "--name-only", commit_sha, "--format="],
            capture_output=True, text=True
        )
        files = files_result.stdout.strip().split("\n")
        
        # Get content before change
        if files:
            before_result = subprocess.run(
                ["git", "-C", repo_path, "show", f"{commit_sha}^:{files[0]}"],
                capture_output=True, text=True
            )
            content = before_result.stdout
            
            self.add_example(TrainingExample(
                instruction=instruction,
                context=CodeContext(
                    language=language,
                    frameworks=frameworks or [],
                    constraints=["Preserve functionality"],
                    affected_components=files,
                ),
                input_code=InputCode(
                    file_path=files[0],
                    content=content,
                ),
                expected_output=ExpectedOutput(diff=diff),
                source="real_commit",
                example_type=ExampleType.REFACTOR_DIFF,
            ))
    
    def add_reject_example(
        self,
        instruction: str,
        reason: str,
        input_code: str,
        language: str
    ) -> None:
        """
        Add a negative example where change should be rejected.
        
        This teaches the model when NOT to generate code.
        """
        self.add_example(TrainingExample(
            instruction=instruction,
            context=CodeContext(
                language=language,
                constraints=["Must have sufficient context"],
            ),
            input_code=InputCode(
                file_path="unknown.py",
                content=input_code,
            ),
            expected_output=ExpectedOutput(
                diff="INSUFFICIENT_CONTEXT",
                explanation=reason,
            ),
            example_type=ExampleType.REJECT_CHANGE,
            confidence="high",
        ))
    
    def save_jsonl(self, filename: str = "dataset.jsonl") -> Path:
        """Save all examples to JSONL file."""
        output_path = self.output_dir / filename
        with open(output_path, "w") as f:
            for example in self.examples:
                f.write(example.to_jsonl() + "\n")
        return output_path
    
    def save_prompts(self, filename: str = "prompts.txt") -> Path:
        """Save all examples as formatted prompts."""
        output_path = self.output_dir / filename
        with open(output_path, "w") as f:
            for example in self.examples:
                f.write(example.to_prompt())
                f.write("\n\n" + "=" * 80 + "\n\n")
        return output_path
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        type_counts = {}
        source_counts = {}
        confidence_counts = {}
        
        for ex in self.examples:
            type_counts[ex.example_type.value] = type_counts.get(ex.example_type.value, 0) + 1
            source_counts[ex.source] = source_counts.get(ex.source, 0) + 1
            confidence_counts[ex.confidence] = confidence_counts.get(ex.confidence, 0) + 1
        
        return {
            "total_examples": len(self.examples),
            "by_type": type_counts,
            "by_source": source_counts,
            "by_confidence": confidence_counts,
            "breaking_changes": sum(1 for ex in self.examples if ex.breaking_change),
        }

