"""
IDE-specific API routes for VS Code extension and other IDEs.

These are convenience endpoints that wrap the internal services
for a better IDE experience.
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog

router = APIRouter()
logger = structlog.get_logger("api.ide")


# ============================================================================
# Request/Response Models
# ============================================================================

class GenerateRequest(BaseModel):
    """Request to generate code."""
    description: str = Field(..., description="What code to generate")
    filePath: str = Field(..., description="Current file path")
    language: str = Field("", description="Programming language")
    cursorPosition: int = Field(0, description="Current line number")


class GenerateResponse(BaseModel):
    """Code generation response."""
    success: bool = True
    code: str = ""
    explanation: str = ""


class FixBugRequest(BaseModel):
    """Request to fix a bug."""
    description: str = Field(..., description="Bug description")
    filePath: str = Field(..., description="File path")
    selectedCode: str = Field("", description="Selected code with bug")


class FixBugResponse(BaseModel):
    """Bug fix response."""
    success: bool = True
    analysis: str = ""
    fix: str = ""
    transactionId: str = ""


class ExplainRequest(BaseModel):
    """Request to explain code."""
    code: str = Field(..., description="Code to explain")
    filePath: str = Field("", description="File path for context")
    language: str = Field("", description="Programming language")


class ExplainResponse(BaseModel):
    """Code explanation response."""
    success: bool = True
    explanation: str = ""
    complexity: str = ""
    suggestions: List[str] = []


class ChatRequest(BaseModel):
    """Chat message request."""
    message: str = Field(..., description="User message")
    context: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Chat response."""
    success: bool = True
    message: str = ""
    actions: List[Dict[str, Any]] = []


class InlineCompleteRequest(BaseModel):
    """Inline completion request."""
    prefix: str = Field(..., description="Code before cursor")
    suffix: str = Field("", description="Code after cursor")
    language: str = Field("", description="Programming language")
    filePath: str = Field("", description="File path")


class InlineCompleteResponse(BaseModel):
    """Inline completion response."""
    completion: str = ""
    confidence: float = 0.0


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/generate", response_model=GenerateResponse)
async def generate_code(request: GenerateRequest):
    """
    Generate code based on a natural language description.
    
    Used by IDE extensions to create new code at cursor position.
    """
    logger.info("generate_code", description=request.description[:50])
    
    try:
        # Import LLM client
        from code4u.ai_engine.llm.client import LLMClient, LLMRequest
        
        client = LLMClient()
        
        # Build prompt
        system_prompt = f"""You are an expert code generator. 
Generate clean, well-documented {request.language or 'code'} based on the description.
Only output the code, no explanations.
Follow best practices and modern conventions."""

        user_prompt = f"""Generate code for: {request.description}

File: {request.filePath}
Language: {request.language or 'auto-detect'}

Generate only the code that should be inserted."""

        response = await client.generate(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=2048
        ))
        
        # Clean up code blocks if present
        code = response.content
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        
        return GenerateResponse(
            success=True,
            code=code,
            explanation=f"Generated {request.language or 'code'} for: {request.description[:50]}..."
        )
        
    except Exception as e:
        logger.error("generate_code_failed", error=str(e))
        return GenerateResponse(success=False, code="", explanation=str(e))


@router.post("/fix-bug", response_model=FixBugResponse)
async def fix_bug(request: FixBugRequest):
    """
    Analyze and fix a bug in the code.
    
    Provides analysis and proposed fix.
    """
    logger.info("fix_bug", description=request.description[:50])
    
    try:
        from code4u.ai_engine.llm.client import LLMClient, LLMRequest
        
        client = LLMClient()
        
        system_prompt = """You are an expert debugger. Analyze the bug and provide:
1. Root cause analysis
2. Fixed code
Output as JSON: {"analysis": "...", "fix": "..."}"""

        user_prompt = f"""Bug description: {request.description}

File: {request.filePath}

Code with bug:
```
{request.selectedCode}
```

Analyze and fix this bug."""

        response = await client.generate(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=2048
        ))
        
        import json
        try:
            result = json.loads(response.content)
            return FixBugResponse(
                success=True,
                analysis=result.get("analysis", "Bug analyzed"),
                fix=result.get("fix", ""),
                transactionId=f"tx-{hash(request.description) % 100000}"
            )
        except json.JSONDecodeError:
            return FixBugResponse(
                success=True,
                analysis=response.content[:500],
                fix="",
                transactionId=f"tx-{hash(request.description) % 100000}"
            )
        
    except Exception as e:
        logger.error("fix_bug_failed", error=str(e))
        return FixBugResponse(success=False, analysis=str(e))


@router.post("/explain", response_model=ExplainResponse)
async def explain_code(request: ExplainRequest):
    """
    Explain what code does in plain language.
    
    Useful for understanding unfamiliar code.
    """
    logger.info("explain_code", code_length=len(request.code))
    
    try:
        from code4u.ai_engine.llm.client import LLMClient, LLMRequest
        
        client = LLMClient()
        
        system_prompt = """You are an expert code explainer. 
Explain the code clearly and concisely.
Include:
1. What the code does (overview)
2. How it works (step by step)
3. Any notable patterns or techniques
4. Potential improvements (if any)"""

        user_prompt = f"""Explain this {request.language or 'code'}:

```
{request.code}
```"""

        response = await client.generate(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=1024
        ))
        
        return ExplainResponse(
            success=True,
            explanation=response.content,
            complexity="moderate",
            suggestions=[]
        )
        
    except Exception as e:
        logger.error("explain_code_failed", error=str(e))
        return ExplainResponse(success=False, explanation=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    General chat with the AI coding assistant.
    
    Can discuss code, answer questions, or help with tasks.
    """
    logger.info("chat", message_length=len(request.message))
    
    try:
        from code4u.ai_engine.llm.client import LLMClient, LLMRequest
        
        client = LLMClient()
        
        system_prompt = """You are code4u.ai, an expert AI coding assistant.
You help developers with code-related questions, debugging, architecture, and best practices.
Be concise, accurate, and helpful.
If you suggest code changes, provide clear instructions."""

        response = await client.generate(LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            temperature=0.3,
            max_tokens=2048
        ))
        
        return ChatResponse(
            success=True,
            message=response.content,
            actions=[]
        )
        
    except Exception as e:
        logger.error("chat_failed", error=str(e))
        return ChatResponse(success=False, message=str(e))


@router.post("/autocomplete/inline", response_model=InlineCompleteResponse)
async def inline_complete(request: InlineCompleteRequest):
    """
    Provide inline code completion at cursor position.
    
    Used by IDE for real-time suggestions.
    """
    try:
        # Use supercomplete engine
        from code4u.ai_engine.supercomplete.engine import SupercompleteEngine
        
        engine = SupercompleteEngine()
        
        result = await engine.complete(
            prefix=request.prefix,
            suffix=request.suffix,
            language=request.language,
            file_path=request.filePath
        )
        
        return InlineCompleteResponse(
            completion=result.get("completion", ""),
            confidence=result.get("confidence", 0.0)
        )
        
    except Exception as e:
        logger.error("inline_complete_failed", error=str(e))
        return InlineCompleteResponse(completion="", confidence=0.0)

