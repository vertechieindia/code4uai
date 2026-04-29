"""Parser for rule files (.mdc format)."""

from __future__ import annotations
import re
import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .models import (
    Rule,
    RuleType,
    RuleScope,
    Workflow,
    WorkflowStep,
    RuleFile,
)


class RuleParser:
    """
    Parser for .mdc rule files.
    
    Format (similar to Cursor):
    ```
    ---
    Description: Rules for the dashboard application
    Globs: apps/dashboard/**/*
    ---
    
    # Dashboard Application Rules
    
    ## Instructions:
    - Follow Next.js App Router best practices
    - Use React Server Components by default
    
    ## Constraints:
    - Never use var, always const or let
    - Always use TypeScript
    
    @file apps/dashboard/tsconfig.json
    @file apps/dashboard/.env
    ```
    """
    
    def parse_file(self, file_path: str) -> RuleFile:
        """Parse a .mdc rule file.
        
        Args:
            file_path: Path to rule file
            
        Returns:
            Parsed RuleFile
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        rule_file = RuleFile(
            path=file_path,
            last_modified=datetime.fromtimestamp(os.path.getmtime(file_path)),
        )
        
        # Parse frontmatter
        frontmatter, body = self._parse_frontmatter(content)
        rule_file.description = frontmatter.get("description")
        rule_file.globs = self._parse_globs(frontmatter.get("globs", ""))
        rule_file.content = body
        
        # Parse rules from body
        rule_file.rules = self._parse_rules(body, rule_file.globs)
        
        return rule_file
    
    def parse_string(self, content: str) -> List[Rule]:
        """Parse rules from a string.
        
        Args:
            content: Rule content
            
        Returns:
            List of parsed rules
        """
        frontmatter, body = self._parse_frontmatter(content)
        globs = self._parse_globs(frontmatter.get("globs", ""))
        return self._parse_rules(body, globs)
    
    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML-like frontmatter."""
        frontmatter = {}
        body = content
        
        # Check for frontmatter block
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm_content = parts[1].strip()
                body = parts[2].strip()
                
                # Parse key-value pairs
                for line in fm_content.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        frontmatter[key.strip().lower()] = value.strip()
        
        return frontmatter, body
    
    def _parse_globs(self, globs_str: str) -> List[str]:
        """Parse glob patterns."""
        if not globs_str:
            return []
        return [g.strip() for g in globs_str.split(",") if g.strip()]
    
    def _parse_rules(self, content: str, globs: List[str]) -> List[Rule]:
        """Parse rules from content."""
        rules = []
        
        # Find sections
        sections = self._find_sections(content)
        
        for section_name, section_content in sections.items():
            rule_type = self._infer_rule_type(section_name)
            
            # Parse bullet points as individual rules
            bullet_pattern = r"^\s*[-*]\s+(.+)$"
            for match in re.finditer(bullet_pattern, section_content, re.MULTILINE):
                instruction = match.group(1).strip()
                
                rule = Rule(
                    id=str(uuid.uuid4()),
                    name=f"{section_name}: {instruction[:30]}...",
                    type=rule_type,
                    instruction=instruction,
                    scope=RuleScope.FILE_PATTERN if globs else RuleScope.GLOBAL,
                    globs=globs,
                )
                rules.append(rule)
        
        # Parse standalone paragraphs as context rules
        if not sections:
            for para in content.split("\n\n"):
                para = para.strip()
                if para and not para.startswith("#") and not para.startswith("@"):
                    rule = Rule(
                        id=str(uuid.uuid4()),
                        name=f"Context: {para[:30]}...",
                        type=RuleType.CONTEXT,
                        instruction=para,
                        scope=RuleScope.FILE_PATTERN if globs else RuleScope.GLOBAL,
                        globs=globs,
                    )
                    rules.append(rule)
        
        return rules
    
    def _find_sections(self, content: str) -> Dict[str, str]:
        """Find markdown sections."""
        sections = {}
        current_section = None
        current_content = []
        
        for line in content.split("\n"):
            # Check for section header
            match = re.match(r"^#+\s+(.+)$", line)
            if match:
                # Save previous section
                if current_section:
                    sections[current_section] = "\n".join(current_content)
                
                current_section = match.group(1).strip().rstrip(":")
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_content)
        
        return sections
    
    def _infer_rule_type(self, section_name: str) -> RuleType:
        """Infer rule type from section name."""
        name_lower = section_name.lower()
        
        if "instruction" in name_lower:
            return RuleType.INSTRUCTION
        elif "constraint" in name_lower or "forbidden" in name_lower:
            return RuleType.CONSTRAINT
        elif "style" in name_lower or "format" in name_lower:
            return RuleType.STYLE
        elif "template" in name_lower:
            return RuleType.TEMPLATE
        else:
            return RuleType.INSTRUCTION


class WorkflowParser:
    """Parser for workflow definitions."""
    
    def parse_yaml(self, content: str) -> Workflow:
        """Parse workflow from YAML content.
        
        Args:
            content: YAML content
            
        Returns:
            Parsed Workflow
        """
        import yaml
        
        data = yaml.safe_load(content)
        
        steps = []
        for step_data in data.get("steps", []):
            step = WorkflowStep(
                id=step_data.get("id", str(uuid.uuid4())),
                name=step_data.get("name", "Unnamed step"),
                action=step_data.get("action", "prompt"),
                parameters=step_data.get("parameters", {}),
                prompt=step_data.get("prompt"),
                condition=step_data.get("condition"),
                on_error=step_data.get("on_error", "fail"),
                output_variable=step_data.get("output"),
            )
            steps.append(step)
        
        return Workflow(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Unnamed workflow"),
            command=data.get("command", "custom"),
            description=data.get("description", ""),
            steps=steps,
            input_variables=data.get("inputs", []),
            default_values=data.get("defaults", {}),
            tags=data.get("tags", []),
        )

