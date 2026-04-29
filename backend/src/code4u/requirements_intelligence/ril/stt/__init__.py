"""
Speech-to-Text Layer

Options:
1. Platform transcripts (Zoom/Teams) - Best for meetings
2. Self-hosted Whisper - Full control
3. Cloud STT (Deepgram/AssemblyAI) - Fast, accurate

Audio is NEVER recorded unless explicitly enabled (enterprise trust).
"""

from .whisper import WhisperSTT
from .transcriber import TranscriptionService

__all__ = [
    "WhisperSTT",
    "TranscriptionService",
]

