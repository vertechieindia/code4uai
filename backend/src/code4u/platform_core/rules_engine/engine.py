"""Rules engine for applying rules and workflows."""

from __future__ import annotations
import os
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid

from .models import (
    Rule,
    RuleType,
    RuleScope,
    Workflow,
    WorkflowStep,
    Memory,
    RulesContext,
    RuleFile,
)
from .parser import RuleParser, WorkflowParser


class RulesEngine:
    """
    Engine for managing and applying rules and workflows.
    
    Features:
    - Load rules from .mdc files
    - Apply rules based on context
    - Execute workflows
    - Manage memories
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize rules engine.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        
        self._rules: Dict[str, Rule] = {}
        self._workflows: Dict[str, Workflow] = {}
        self._memories: Dict[str, Memory] = {}
        self._rule_files: Dict[str, RuleFile] = {}
        
        self._parser = RuleParser()
        self._workflow_parser = WorkflowParser()
        self._lock = threading.RLock()
        
        # Built-in workflows
        self._register_builtin_workflows()
    
    def _register_builtin_workflows(self) -> None:
        """Register built-in workflows."""
        # Code review workflow
        self.add_workflow(Workflow(
            id="builtin-code-review",
            name="Code Review",
            command="code-review",
            description="Review code for issues and improvements",
            steps=[
                WorkflowStep(
                    id="1",
                    name="Analyze code",
                    action="prompt",
                    prompt="Review the following code for:\n"
                           "1. Bugs and potential issues\n"
                           "2. Security vulnerabilities\n"
                           "3. Performance problems\n"
                           "4. Code style and best practices\n\n"
                           "Provide specific, actionable feedback.",
                ),
            ],
            tags=["review", "quality"],
        ))
        
        # PR description workflow
        self.add_workflow(Workflow(
            id="builtin-pr",
            name="PR Description",
            command="pr",
            description="Generate PR description from changes",
            steps=[
                WorkflowStep(
                    id="1",
                    name="Generate description",
                    action="prompt",
                    prompt="Generate a pull request description for the following changes.\n"
                           "Include:\n"
                           "- Summary of changes\n"
                           "- Motivation\n"
                           "- Testing done\n"
                           "- Breaking changes (if any)",
                ),
            ],
            tags=["git", "pr"],
        ))
        
        # Commit message workflow
        self.add_workflow(Workflow(
            id="builtin-commit",
            name="Commit Message",
            command="commit",
            description="Generate commit message from staged changes",
            steps=[
                WorkflowStep(
                    id="1",
                    name="Generate message",
                    action="prompt",
                    prompt="Generate a conventional commit message for these changes.\n"
                           "Use format: type(scope): description\n"
                           "Types: feat, fix, docs, style, refactor, test, chore",
                ),
            ],
            tags=["git", "commit"],
        ))
        
        # Fix tests workflow
        self.add_workflow(Workflow(
            id="builtin-fix-tests",
            name="Fix Tests",
            command="fix-tests",
            description="Fix failing tests",
            steps=[
                WorkflowStep(
                    id="1",
                    name="Analyze failures",
                    action="prompt",
                    prompt="Analyze the failing tests and identify the root causes.",
                    output_variable="analysis",
                ),
                WorkflowStep(
                    id="2",
                    name="Generate fixes",
                    action="refactor",
                    parameters={"intent": "Fix the failing tests based on analysis"},
                ),
            ],
            tags=["testing", "fix"],
        ))
    
    # ============= Rules =============
    
    def add_rule(self, rule: Rule) -> str:
        """Add a rule."""
        with self._lock:
            self._rules[rule.id] = rule
            return rule.id
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule."""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)
    
    def list_rules(self) -> List[Rule]:
        """List all rules."""
        return list(self._rules.values())
    
    def get_applicable_rules(self, context: RulesContext) -> List[Rule]:
        """Get rules applicable to a context.
        
        Args:
            context: Context for rule matching
            
        Returns:
            List of applicable rules, sorted by priority
        """
        applicable = []
        
        for rule in self._rules.values():
            if rule.matches(
                file_path=context.file_path,
                language=context.language,
                directory=context.directory,
            ):
                applicable.append(rule)
        
        # Sort by priority (higher first)
        applicable.sort(key=lambda r: r.priority, reverse=True)
        return applicable
    
    def load_rules_from_directory(
        self, 
        directory: str,
        pattern: str = "**/*.mdc",
    ) -> int:
        """Load rules from .mdc files in a directory.
        
        Args:
            directory: Directory to scan
            pattern: Glob pattern for rule files
            
        Returns:
            Number of rules loaded
        """
        count = 0
        path = Path(directory)
        
        for file_path in path.glob(pattern):
            try:
                rule_file = self._parser.parse_file(str(file_path))
                self._rule_files[str(file_path)] = rule_file
                
                for rule in rule_file.rules:
                    self.add_rule(rule)
                    count += 1
            except Exception as e:
                # Log error but continue
                pass
        
        return count
    
    def build_prompt_additions(self, context: RulesContext) -> str:
        """Build additional prompt content from rules.
        
        Args:
            context: Context for rule matching
            
        Returns:
            Additional prompt content
        """
        rules = self.get_applicable_rules(context)
        
        if not rules:
            return ""
        
        sections = {
            RuleType.INSTRUCTION: [],
            RuleType.CONSTRAINT: [],
            RuleType.STYLE: [],
            RuleType.CONTEXT: [],
        }
        
        for rule in rules:
            if rule.type in sections:
                sections[rule.type].append(rule.instruction)
        
        parts = []
        
        if sections[RuleType.CONTEXT]:
            parts.append("## Context\n" + "\n".join(sections[RuleType.CONTEXT]))
        
        if sections[RuleType.INSTRUCTION]:
            parts.append("## Instructions\n" + "\n".join(f"- {i}" for i in sections[RuleType.INSTRUCTION]))
        
        if sections[RuleType.CONSTRAINT]:
            parts.append("## Constraints\n" + "\n".join(f"- {c}" for c in sections[RuleType.CONSTRAINT]))
        
        if sections[RuleType.STYLE]:
            parts.append("## Style Guidelines\n" + "\n".join(f"- {s}" for s in sections[RuleType.STYLE]))
        
        return "\n\n".join(parts)
    
    # ============= Workflows =============
    
    def add_workflow(self, workflow: Workflow) -> str:
        """Add a workflow."""
        with self._lock:
            self._workflows[workflow.id] = workflow
            return workflow.id
    
    def remove_workflow(self, workflow_id: str) -> bool:
        """Remove a workflow."""
        with self._lock:
            if workflow_id in self._workflows:
                del self._workflows[workflow_id]
                return True
            return False
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)
    
    def get_workflow_by_command(self, command: str) -> Optional[Workflow]:
        """Get a workflow by command name."""
        for workflow in self._workflows.values():
            if workflow.command == command:
                return workflow
        return None
    
    def list_workflows(self) -> List[Workflow]:
        """List all workflows."""
        return list(self._workflows.values())
    
    async def execute_workflow(
        self,
        workflow_id: str,
        context: RulesContext,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a workflow.
        
        Args:
            workflow_id: Workflow to execute
            context: Execution context
            variables: Input variables
            
        Returns:
            Execution results
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Merge variables
        vars = {**workflow.default_values, **(variables or {})}
        results = {"steps": [], "success": True}
        
        for step in workflow.steps:
            # Check condition
            if step.condition and not self._eval_condition(step.condition, vars):
                continue
            
            # Execute step
            try:
                step_result = await self._execute_step(step, context, vars)
                results["steps"].append({
                    "step_id": step.id,
                    "name": step.name,
                    "success": True,
                    "result": step_result,
                })
                
                # Store output variable
                if step.output_variable:
                    vars[step.output_variable] = step_result
                    
            except Exception as e:
                results["steps"].append({
                    "step_id": step.id,
                    "name": step.name,
                    "success": False,
                    "error": str(e),
                })
                
                if step.on_error == "fail":
                    results["success"] = False
                    break
        
        return results
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        context: RulesContext,
        variables: Dict[str, Any],
    ) -> Any:
        """Execute a single workflow step."""
        if step.action == "prompt":
            # Return prompt with variables substituted
            prompt = step.prompt or ""
            for key, value in variables.items():
                prompt = prompt.replace(f"{{{key}}}", str(value))
            return {"prompt": prompt}
        
        elif step.action == "refactor":
            # Would call refactor API
            return {"action": "refactor", "parameters": step.parameters}
        
        elif step.action == "validate":
            # Would call validation
            return {"action": "validate"}
        
        elif step.action == "wait_for_approval":
            return {"action": "waiting", "status": "pending_approval"}
        
        return {"action": step.action}
    
    def _eval_condition(self, condition: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a condition expression."""
        # Simple evaluation - in production would use safe parser
        try:
            return eval(condition, {"__builtins__": {}}, variables)
        except:
            return True
    
    # ============= Memories =============
    
    def add_memory(self, memory: Memory) -> str:
        """Add a memory."""
        with self._lock:
            self._memories[memory.id] = memory
            return memory.id
    
    def remove_memory(self, memory_id: str) -> bool:
        """Remove a memory."""
        with self._lock:
            if memory_id in self._memories:
                del self._memories[memory_id]
                return True
            return False
    
    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        return self._memories.get(memory_id)
    
    def list_memories(self) -> List[Memory]:
        """List all memories."""
        return list(self._memories.values())
    
    def get_relevant_memories(
        self,
        context: RulesContext,
        limit: int = 10,
    ) -> List[Memory]:
        """Get memories relevant to context.
        
        Args:
            context: Context for matching
            limit: Maximum memories to return
            
        Returns:
            List of relevant memories
        """
        memories = [m for m in self._memories.values() if m.enabled]
        
        # Sort by confidence and use count
        memories.sort(
            key=lambda m: (m.confidence, m.use_count),
            reverse=True,
        )
        
        return memories[:limit]
    
    def create_memory_from_interaction(
        self,
        content: str,
        source: str = "inferred",
        confidence: float = 0.8,
    ) -> Memory:
        """Create a memory from an interaction.
        
        Args:
            content: Memory content
            source: Memory source
            confidence: Confidence score
            
        Returns:
            Created memory
        """
        memory = Memory(
            id=str(uuid.uuid4()),
            content=content,
            source=source,
            confidence=confidence,
        )
        self.add_memory(memory)
        return memory

