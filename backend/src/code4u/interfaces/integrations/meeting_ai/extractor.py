"""Requirement extractor using LLM to analyze meeting transcripts."""

from __future__ import annotations
import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..base import Requirement, MeetingMinutes


class RequirementExtractor:
    """
    Extracts requirements from meeting transcripts using LLM.
    
    Features:
    - Identify feature requests, bugs, enhancements
    - Determine priority from discussion context
    - Extract acceptance criteria
    - Identify assignees from mentions
    - Estimate effort from complexity discussed
    """
    
    # Prompt for requirement extraction
    EXTRACTION_PROMPT = """Analyze this meeting transcript and extract all software requirements discussed.

For each requirement, identify:
1. Title: A concise title
2. Description: Detailed description with context
3. Type: feature, bug, enhancement, or task
4. Priority: critical, high, medium, or low (based on urgency expressed)
5. Acceptance Criteria: What defines "done"
6. Assignee: Person mentioned as responsible (if any)
7. Dependencies: Other requirements this depends on

Return as JSON array:
[
  {
    "title": "...",
    "description": "...",
    "type": "feature|bug|enhancement|task",
    "priority": "critical|high|medium|low",
    "acceptance_criteria": ["..."],
    "assignee": "name or null",
    "dependencies": []
  }
]

TRANSCRIPT:
{transcript}

REQUIREMENTS JSON:"""

    MINUTES_PROMPT = """Generate meeting minutes from this transcript.

Include:
1. Summary: 2-3 sentence overview
2. Key Points: Main topics discussed
3. Decisions: Any decisions made
4. Action Items: Tasks assigned with owners

Return as JSON:
{
  "summary": "...",
  "key_points": ["..."],
  "decisions": ["..."],
  "action_items": [
    {"task": "...", "owner": "...", "due_date": "..."}
  ]
}

TRANSCRIPT:
{transcript}

MEETING MINUTES JSON:"""

    def __init__(self):
        """Initialize extractor."""
        self._llm_client = None
    
    async def extract_requirements(
        self,
        transcript: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Requirement]:
        """Extract requirements from meeting transcript.
        
        Args:
            transcript: Meeting transcript text
            context: Additional context (meeting info, participants)
            
        Returns:
            List of extracted requirements
        """
        # Build prompt
        prompt = self.EXTRACTION_PROMPT.format(transcript=transcript[:10000])
        
        # Call LLM
        response = await self._call_llm(prompt)
        
        # Parse response
        try:
            requirements_data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                requirements_data = json.loads(match.group())
            else:
                requirements_data = []
        
        # Convert to Requirement objects
        requirements = []
        for data in requirements_data:
            req = Requirement(
                id=str(uuid.uuid4()),
                title=data.get("title", "Untitled Requirement"),
                description=data.get("description", ""),
                source_type="meeting",
                source_id=context.get("meeting_id", "") if context else "",
                type=data.get("type", "feature"),
                priority=data.get("priority", "medium"),
                assignee=data.get("assignee"),
                status="draft",
            )
            
            # Store acceptance criteria
            req.dependencies = data.get("dependencies", [])
            
            requirements.append(req)
        
        return requirements
    
    async def generate_minutes(
        self,
        transcript: str,
        meeting_id: str,
        participants: Optional[List[str]] = None,
        meeting_title: Optional[str] = None,
    ) -> MeetingMinutes:
        """Generate meeting minutes from transcript.
        
        Args:
            transcript: Meeting transcript
            meeting_id: Meeting identifier
            participants: List of participants
            meeting_title: Meeting title
            
        Returns:
            MeetingMinutes object
        """
        # Build prompt
        prompt = self.MINUTES_PROMPT.format(transcript=transcript[:10000])
        
        # Call LLM
        response = await self._call_llm(prompt)
        
        # Parse response
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                data = {
                    "summary": "Meeting minutes could not be generated.",
                    "key_points": [],
                    "decisions": [],
                    "action_items": [],
                }
        
        minutes = MeetingMinutes(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            meeting_title=meeting_title or f"Meeting {meeting_id[:8]}",
            participants=participants or [],
            summary=data.get("summary", ""),
            key_points=data.get("key_points", []),
            decisions=data.get("decisions", []),
            action_items=data.get("action_items", []),
            status="draft",
        )
        
        return minutes
    
    async def refine_requirements(
        self,
        requirements: List[Requirement],
        feedback: str,
    ) -> List[Requirement]:
        """Refine requirements based on feedback.
        
        Args:
            requirements: Current requirements
            feedback: User feedback for refinement
            
        Returns:
            Refined requirements
        """
        prompt = f"""Refine these requirements based on the feedback.

CURRENT REQUIREMENTS:
{json.dumps([{"title": r.title, "description": r.description, "type": r.type, "priority": r.priority} for r in requirements], indent=2)}

FEEDBACK:
{feedback}

Return updated requirements as JSON array with the same structure.

REFINED REQUIREMENTS JSON:"""
        
        response = await self._call_llm(prompt)
        
        try:
            refined_data = json.loads(response)
        except json.JSONDecodeError:
            return requirements
        
        # Update requirements
        for i, data in enumerate(refined_data):
            if i < len(requirements):
                requirements[i].title = data.get("title", requirements[i].title)
                requirements[i].description = data.get("description", requirements[i].description)
                requirements[i].type = data.get("type", requirements[i].type)
                requirements[i].priority = data.get("priority", requirements[i].priority)
                requirements[i].updated_at = datetime.utcnow()
        
        return requirements
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for analysis.
        
        Args:
            prompt: Prompt to send
            
        Returns:
            LLM response
        """
        # In production, this would use the code4u.ai LLM infrastructure
        # For now, return a mock response for demonstration
        
        # This would integrate with:
        # from code4u.ai_engine.llm import LLMClient
        # client = LLMClient()
        # return await client.generate(prompt)
        
        # Mock response for demonstration
        if "REQUIREMENTS JSON" in prompt:
            return json.dumps([
                {
                    "title": "User Authentication Enhancement",
                    "description": "Add OAuth2 support for third-party login providers including Google, GitHub, and Microsoft.",
                    "type": "feature",
                    "priority": "high",
                    "acceptance_criteria": [
                        "Users can login with Google",
                        "Users can login with GitHub",
                        "Users can login with Microsoft"
                    ],
                    "assignee": None,
                    "dependencies": []
                },
                {
                    "title": "Dashboard Performance Optimization",
                    "description": "Improve dashboard loading time by implementing lazy loading and caching.",
                    "type": "enhancement",
                    "priority": "medium",
                    "acceptance_criteria": [
                        "Dashboard loads in under 2 seconds",
                        "Implement component lazy loading"
                    ],
                    "assignee": None,
                    "dependencies": []
                }
            ])
        
        elif "MEETING MINUTES JSON" in prompt:
            return json.dumps({
                "summary": "Team discussed upcoming feature priorities and technical debt items. Focus on authentication improvements and performance optimization for Q1.",
                "key_points": [
                    "OAuth2 integration is top priority",
                    "Dashboard performance needs improvement",
                    "Mobile app development postponed to Q2"
                ],
                "decisions": [
                    "Proceed with OAuth2 implementation using Auth0",
                    "Allocate 20% of sprint capacity to performance work"
                ],
                "action_items": [
                    {"task": "Create OAuth2 technical design", "owner": "Engineering Lead", "due_date": "Next Monday"},
                    {"task": "Profile dashboard performance", "owner": "Frontend Team", "due_date": "This Friday"}
                ]
            })
        
        return "{}"

