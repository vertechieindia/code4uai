"""Unified transcription service."""

from __future__ import annotations
import os
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field

from .whisper import WhisperSTT, TranscriptionResult


class TranscriptionProvider(str, Enum):
    """Available transcription providers."""
    PLATFORM = "platform"  # Use platform's native transcript
    WHISPER = "whisper"    # Self-hosted Whisper
    DEEPGRAM = "deepgram"  # Deepgram API
    ASSEMBLY = "assembly"  # AssemblyAI


@dataclass
class SpeakerTurn:
    """A speaker turn with text."""
    speaker: str
    text: str
    start: float
    end: float


class TranscriptionService:
    """
    Unified transcription service.
    
    Supports multiple providers:
    1. Platform transcripts (best for Zoom/Teams)
    2. Self-hosted Whisper (full control)
    3. Cloud APIs (fast, accurate)
    """
    
    def __init__(
        self,
        provider: TranscriptionProvider = TranscriptionProvider.PLATFORM,
        whisper_model: str = "large-v3",
    ):
        """Initialize transcription service.
        
        Args:
            provider: Transcription provider to use
            whisper_model: Whisper model size if using Whisper
        """
        self.provider = provider
        self._whisper: Optional[WhisperSTT] = None
        
        if provider == TranscriptionProvider.WHISPER:
            self._whisper = WhisperSTT(model_size=whisper_model)
    
    async def transcribe(
        self,
        audio_source: str,
        platform_transcript: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio.
        
        Args:
            audio_source: Path or URL to audio
            platform_transcript: Pre-existing platform transcript
            
        Returns:
            Transcription result
        """
        # Prefer platform transcript if available
        if platform_transcript and self.provider == TranscriptionProvider.PLATFORM:
            return self._parse_platform_transcript(platform_transcript)
        
        if self.provider == TranscriptionProvider.WHISPER:
            if audio_source.startswith("http"):
                return self._whisper.transcribe_url(audio_source)
            return await self._whisper.transcribe_async(audio_source)
        
        if self.provider == TranscriptionProvider.DEEPGRAM:
            return await self._transcribe_deepgram(audio_source)
        
        if self.provider == TranscriptionProvider.ASSEMBLY:
            return await self._transcribe_assembly(audio_source)
        
        raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _parse_platform_transcript(
        self,
        transcript: str,
    ) -> TranscriptionResult:
        """Parse a platform transcript.
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            Parsed result
        """
        from .whisper import TranscriptSegment
        
        segments = []
        lines = transcript.strip().split('\n')
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Try to parse speaker format: [Speaker]: Text
            speaker = None
            text = line
            
            if line.startswith('[') and ']: ' in line:
                parts = line.split(']: ', 1)
                speaker = parts[0][1:]  # Remove leading [
                text = parts[1] if len(parts) > 1 else ""
            
            segments.append(TranscriptSegment(
                id=i,
                start=0.0,  # No timing from platform transcript
                end=0.0,
                text=text,
                speaker=speaker,
            ))
        
        return TranscriptionResult(
            text=transcript,
            segments=segments,
        )
    
    async def _transcribe_deepgram(
        self,
        audio_source: str,
    ) -> TranscriptionResult:
        """Transcribe using Deepgram API."""
        import httpx
        from .whisper import TranscriptSegment
        
        api_key = os.getenv("DEEPGRAM_API_KEY", "")
        
        async with httpx.AsyncClient() as client:
            if audio_source.startswith("http"):
                # URL-based transcription
                response = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers={
                        "Authorization": f"Token {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"url": audio_source},
                    params={
                        "model": "nova-2",
                        "smart_format": "true",
                        "diarize": "true",
                        "punctuate": "true",
                    },
                )
            else:
                # File-based transcription
                with open(audio_source, "rb") as f:
                    audio_data = f.read()
                
                response = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers={
                        "Authorization": f"Token {api_key}",
                        "Content-Type": "audio/mpeg",
                    },
                    content=audio_data,
                    params={
                        "model": "nova-2",
                        "smart_format": "true",
                        "diarize": "true",
                        "punctuate": "true",
                    },
                )
            
            response.raise_for_status()
            data = response.json()
        
        # Parse Deepgram response
        channel = data.get("results", {}).get("channels", [{}])[0]
        alternatives = channel.get("alternatives", [{}])
        best = alternatives[0] if alternatives else {}
        
        segments = []
        for i, word in enumerate(best.get("words", [])):
            # Group by speaker
            segments.append(TranscriptSegment(
                id=i,
                start=word.get("start", 0.0),
                end=word.get("end", 0.0),
                text=word.get("punctuated_word", word.get("word", "")),
                speaker=f"Speaker {word.get('speaker', 0)}",
                confidence=word.get("confidence", 0.0),
            ))
        
        return TranscriptionResult(
            text=best.get("transcript", ""),
            segments=self._merge_speaker_segments(segments),
            duration=data.get("metadata", {}).get("duration", 0.0),
        )
    
    async def _transcribe_assembly(
        self,
        audio_source: str,
    ) -> TranscriptionResult:
        """Transcribe using AssemblyAI."""
        import httpx
        from .whisper import TranscriptSegment
        
        api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
        
        async with httpx.AsyncClient() as client:
            # Upload if file
            if not audio_source.startswith("http"):
                with open(audio_source, "rb") as f:
                    upload_resp = await client.post(
                        "https://api.assemblyai.com/v2/upload",
                        headers={"Authorization": api_key},
                        content=f.read(),
                    )
                    upload_resp.raise_for_status()
                    audio_source = upload_resp.json()["upload_url"]
            
            # Start transcription
            transcript_resp = await client.post(
                "https://api.assemblyai.com/v2/transcript",
                headers={"Authorization": api_key},
                json={
                    "audio_url": audio_source,
                    "speaker_labels": True,
                    "auto_chapters": True,
                },
            )
            transcript_resp.raise_for_status()
            transcript_id = transcript_resp.json()["id"]
            
            # Poll for completion
            import asyncio
            while True:
                status_resp = await client.get(
                    f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                    headers={"Authorization": api_key},
                )
                status_resp.raise_for_status()
                data = status_resp.json()
                
                if data["status"] == "completed":
                    break
                elif data["status"] == "error":
                    raise Exception(data.get("error", "Transcription failed"))
                
                await asyncio.sleep(3)
        
        # Parse response
        segments = []
        for i, utt in enumerate(data.get("utterances", [])):
            segments.append(TranscriptSegment(
                id=i,
                start=utt["start"] / 1000.0,
                end=utt["end"] / 1000.0,
                text=utt["text"],
                speaker=f"Speaker {utt['speaker']}",
                confidence=utt.get("confidence", 0.0),
            ))
        
        return TranscriptionResult(
            text=data.get("text", ""),
            segments=segments,
            duration=data.get("audio_duration", 0.0),
        )
    
    def _merge_speaker_segments(
        self,
        word_segments: List["TranscriptSegment"],
    ) -> List["TranscriptSegment"]:
        """Merge word-level segments into speaker turns."""
        from .whisper import TranscriptSegment
        
        if not word_segments:
            return []
        
        merged = []
        current_speaker = word_segments[0].speaker
        current_words = []
        start = word_segments[0].start
        end = word_segments[0].end
        
        for seg in word_segments:
            if seg.speaker != current_speaker:
                # Save current segment
                merged.append(TranscriptSegment(
                    id=len(merged),
                    start=start,
                    end=end,
                    text=" ".join(current_words),
                    speaker=current_speaker,
                ))
                
                # Start new segment
                current_speaker = seg.speaker
                current_words = [seg.text]
                start = seg.start
                end = seg.end
            else:
                current_words.append(seg.text)
                end = seg.end
        
        # Don't forget last segment
        if current_words:
            merged.append(TranscriptSegment(
                id=len(merged),
                start=start,
                end=end,
                text=" ".join(current_words),
                speaker=current_speaker,
            ))
        
        return merged

