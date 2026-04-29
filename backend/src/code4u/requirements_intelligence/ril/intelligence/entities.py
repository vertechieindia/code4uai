"""Entity extraction from conversation segments."""

from __future__ import annotations
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExtractedEntities:
    """Extracted entities from text."""
    systems: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    dates: List[Dict[str, Any]] = field(default_factory=list)
    deadlines: List[Dict[str, Any]] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    metrics: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "systems": self.systems,
            "services": self.services,
            "people": self.people,
            "roles": self.roles,
            "dates": self.dates,
            "deadlines": self.deadlines,
            "technologies": self.technologies,
            "constraints": self.constraints,
            "metrics": self.metrics,
        }


class EntityExtractor:
    """
    Extracts entities from conversation text.
    
    Combines:
    - Rule-based extraction (fast, deterministic)
    - LLM extraction (accurate, contextual)
    """
    
    # Common technology keywords
    TECHNOLOGIES = {
        # Languages
        "python", "javascript", "typescript", "java", "go", "rust", "kotlin",
        "swift", "c#", "ruby", "php",
        # Frameworks
        "react", "vue", "angular", "next.js", "nuxt", "django", "flask",
        "fastapi", "spring", "express", "nest.js",
        # Databases
        "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch",
        "dynamodb", "cassandra", "neo4j",
        # Infrastructure
        "kubernetes", "docker", "aws", "gcp", "azure", "terraform",
        "helm", "istio", "envoy",
        # Services
        "kafka", "rabbitmq", "sqs", "sns", "s3", "lambda",
        "cloudflare", "datadog", "sentry", "grafana",
        # Auth
        "oauth", "oidc", "saml", "okta", "auth0", "keycloak",
    }
    
    # Compliance/constraint keywords
    CONSTRAINTS = {
        "soc2", "soc 2", "iso 27001", "gdpr", "hipaa", "pci",
        "pci-dss", "ccpa", "fedramp", "fips",
    }
    
    # Role patterns
    ROLES = {
        "pm", "product manager", "engineer", "developer", "designer",
        "qa", "tester", "devops", "sre", "architect", "tech lead",
        "cto", "vp", "director", "manager", "frontend", "backend",
        "fullstack", "mobile", "data scientist", "ml engineer",
    }
    
    def __init__(self, llm_client=None):
        """Initialize extractor.
        
        Args:
            llm_client: Optional LLM client for enhanced extraction
        """
        self.llm_client = llm_client
    
    def extract(self, text: str) -> ExtractedEntities:
        """Extract entities from text.
        
        Args:
            text: Text to extract from
            
        Returns:
            Extracted entities
        """
        entities = ExtractedEntities()
        text_lower = text.lower()
        
        # Extract technologies
        entities.technologies = self._extract_technologies(text_lower)
        
        # Extract constraints
        entities.constraints = self._extract_constraints(text_lower)
        
        # Extract dates/deadlines
        entities.dates, entities.deadlines = self._extract_dates(text)
        
        # Extract metrics
        entities.metrics = self._extract_metrics(text)
        
        # Extract roles
        entities.roles = self._extract_roles(text_lower)
        
        return entities
    
    def _extract_technologies(self, text: str) -> List[str]:
        """Extract technology mentions."""
        found = []
        for tech in self.TECHNOLOGIES:
            # Word boundary matching
            pattern = r'\b' + re.escape(tech) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found.append(tech)
        return list(set(found))
    
    def _extract_constraints(self, text: str) -> List[str]:
        """Extract compliance/constraint mentions."""
        found = []
        for constraint in self.CONSTRAINTS:
            if constraint in text:
                found.append(constraint.upper())
        return list(set(found))
    
    def _extract_dates(self, text: str) -> tuple[List[Dict], List[Dict]]:
        """Extract date and deadline mentions."""
        dates = []
        deadlines = []
        
        # Quarter patterns
        quarter_pattern = r'\b(q[1-4])\s*(?:of\s*)?(\d{4})?\b'
        for match in re.finditer(quarter_pattern, text, re.IGNORECASE):
            quarter = match.group(1).upper()
            year = match.group(2) or str(datetime.now().year)
            
            entry = {
                "type": "quarter",
                "quarter": quarter,
                "year": int(year),
                "raw": match.group(0),
            }
            
            # Check if it's a deadline
            context_start = max(0, match.start() - 20)
            context = text[context_start:match.start()].lower()
            if any(word in context for word in ["by", "before", "deadline", "due", "until"]):
                deadlines.append(entry)
            else:
                dates.append(entry)
        
        # Month patterns
        months = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ]
        month_pattern = r'\b(' + '|'.join(months) + r')\s+(\d{4})?\b'
        for match in re.finditer(month_pattern, text, re.IGNORECASE):
            month = match.group(1).capitalize()
            year = match.group(2) or str(datetime.now().year)
            
            entry = {
                "type": "month",
                "month": month,
                "year": int(year),
                "raw": match.group(0),
            }
            dates.append(entry)
        
        # Relative dates
        relative_patterns = [
            (r'\bnext\s+week\b', "next_week"),
            (r'\bnext\s+month\b', "next_month"),
            (r'\bend\s+of\s+(month|year|quarter)\b', "end_of"),
            (r'\b(\d+)\s+days?\b', "days"),
            (r'\b(\d+)\s+weeks?\b', "weeks"),
            (r'\basap\b', "asap"),
        ]
        
        for pattern, date_type in relative_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entry = {
                    "type": "relative",
                    "value": date_type,
                    "raw": match.group(0),
                }
                
                # Check context for deadline indicators
                context_start = max(0, match.start() - 20)
                context = text[context_start:match.start()].lower()
                if any(word in context for word in ["by", "within", "deadline", "due", "need"]):
                    deadlines.append(entry)
                else:
                    dates.append(entry)
        
        return dates, deadlines
    
    def _extract_metrics(self, text: str) -> List[Dict[str, Any]]:
        """Extract performance metrics."""
        metrics = []
        
        # Latency patterns
        latency_pattern = r'(\d+)\s*(ms|milliseconds?|seconds?|s)\s*(latency|response\s*time)?'
        for match in re.finditer(latency_pattern, text, re.IGNORECASE):
            metrics.append({
                "type": "latency",
                "value": int(match.group(1)),
                "unit": match.group(2),
                "raw": match.group(0),
            })
        
        # Percentage patterns
        percent_pattern = r'(\d+(?:\.\d+)?)\s*%\s*(uptime|availability|success|error)?'
        for match in re.finditer(percent_pattern, text, re.IGNORECASE):
            metric_type = match.group(2) or "percentage"
            metrics.append({
                "type": metric_type,
                "value": float(match.group(1)),
                "unit": "%",
                "raw": match.group(0),
            })
        
        # SLA patterns
        sla_pattern = r'(\d+(?:\.\d+)?)\s*(?:nines?|9s)\s*(uptime|availability)?'
        for match in re.finditer(sla_pattern, text, re.IGNORECASE):
            nines = float(match.group(1))
            uptime = 100 - (10 ** -nines) * 100
            metrics.append({
                "type": "sla",
                "nines": nines,
                "uptime": uptime,
                "raw": match.group(0),
            })
        
        # User count patterns
        user_pattern = r'(\d+(?:,\d+)*(?:k|m|b)?)\s*(users?|customers?|requests?(?:/s)?)'
        for match in re.finditer(user_pattern, text, re.IGNORECASE):
            value_str = match.group(1).replace(',', '')
            multiplier = 1
            if value_str.endswith('k'):
                multiplier = 1000
                value_str = value_str[:-1]
            elif value_str.endswith('m'):
                multiplier = 1000000
                value_str = value_str[:-1]
            elif value_str.endswith('b'):
                multiplier = 1000000000
                value_str = value_str[:-1]
            
            metrics.append({
                "type": match.group(2).lower().rstrip('s'),
                "value": int(float(value_str) * multiplier),
                "raw": match.group(0),
            })
        
        return metrics
    
    def _extract_roles(self, text: str) -> List[str]:
        """Extract role mentions."""
        found = []
        for role in self.ROLES:
            pattern = r'\b' + re.escape(role) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found.append(role)
        return list(set(found))
    
    async def extract_with_llm(
        self,
        text: str,
        context: Optional[str] = None,
    ) -> ExtractedEntities:
        """Extract entities using LLM for better accuracy.
        
        Args:
            text: Text to extract from
            context: Optional context
            
        Returns:
            Extracted entities
        """
        # Start with rule-based
        entities = self.extract(text)
        
        if not self.llm_client:
            return entities
        
        # Enhance with LLM
        prompt = f"""Extract structured entities from this conversation segment.

TEXT: {text}

Extract:
1. systems: Software systems, services, components (e.g., "Auth Service", "User API")
2. services: Microservices or service names
3. people: Names of people mentioned (only actual names, not roles)
4. technologies: Technologies, frameworks, tools
5. constraints: Compliance requirements, limitations
6. deadlines: Any mentioned deadlines with context

Respond in JSON only:
{{
  "systems": [],
  "services": [],
  "people": [],
  "technologies": [],
  "constraints": [],
  "deadlines": []
}}"""
        
        try:
            import json
            response = await self.llm_client.complete(
                prompt=prompt,
                temperature=0.0,
                max_tokens=500,
            )
            
            data = json.loads(response)
            
            # Merge with rule-based results
            entities.systems.extend(data.get("systems", []))
            entities.services.extend(data.get("services", []))
            entities.people.extend(data.get("people", []))
            entities.technologies.extend(data.get("technologies", []))
            entities.constraints.extend(data.get("constraints", []))
            
            for deadline in data.get("deadlines", []):
                if isinstance(deadline, str):
                    entities.deadlines.append({"type": "llm", "value": deadline})
                else:
                    entities.deadlines.append(deadline)
            
            # Deduplicate
            entities.systems = list(set(entities.systems))
            entities.services = list(set(entities.services))
            entities.people = list(set(entities.people))
            entities.technologies = list(set(entities.technologies))
            entities.constraints = list(set(entities.constraints))
            
        except Exception:
            pass  # Fall back to rule-based only
        
        return entities

