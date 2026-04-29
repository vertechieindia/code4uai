"""Self-hosted Whisper STT."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import tempfile


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio."""
    id: int
    start: float  # Start time in seconds
    end: float    # End time in seconds
    text: str
    speaker: Optional[str] = None
    confidence: float = 0.0


@dataclass
class TranscriptionResult:
    """Complete transcription result."""
    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)
    language: str = "en"
    duration: float = 0.0
    
    def with_speaker_diarization(self, speakers: Dict[int, str]) -> "TranscriptionResult":
        """Add speaker labels to segments.
        
        Args:
            speakers: Mapping of segment index to speaker name
            
        Returns:
            Updated result
        """
        for i, seg in enumerate(self.segments):
            if i in speakers:
                seg.speaker = speakers[i]
        return self


class WhisperSTT:
    """
    Self-hosted Whisper Speech-to-Text.
    
    Uses OpenAI Whisper (large-v3) for transcription.
    GPU-accelerated for fast processing.
    """
    
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        language: Optional[str] = None,
    ):
        """Initialize Whisper.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large, large-v3)
            device: Device to use (cuda, cpu)
            language: Force language (None for auto-detect)
        """
        self.model_size = model_size
        self.device = device
        self.language = language
        self._model = None
    
    def load_model(self) -> None:
        """Load the Whisper model."""
        try:
            import whisper
            self._model = whisper.load_model(self.model_size, device=self.device)
        except ImportError:
            # Use faster-whisper if available
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type="float16" if self.device == "cuda" else "int8",
                )
            except ImportError:
                raise ImportError("Install whisper or faster-whisper")
    
    def transcribe(
        self,
        audio_path: str,
        word_timestamps: bool = True,
    ) -> TranscriptionResult:
        """Transcribe audio file.
        
        Args:
            audio_path: Path to audio file
            word_timestamps: Include word-level timestamps
            
        Returns:
            Transcription result
        """
        if not self._model:
            self.load_model()
        
        # Check if using faster-whisper
        if hasattr(self._model, 'transcribe') and 'WhisperModel' in str(type(self._model)):
            return self._transcribe_faster_whisper(audio_path)
        else:
            return self._transcribe_whisper(audio_path, word_timestamps)
    
    def _transcribe_whisper(
        self,
        audio_path: str,
        word_timestamps: bool,
    ) -> TranscriptionResult:
        """Transcribe using openai-whisper."""
        result = self._model.transcribe(
            audio_path,
            language=self.language,
            word_timestamps=word_timestamps,
            fp16=(self.device == "cuda"),
        )
        
        segments = []
        for i, seg in enumerate(result.get("segments", [])):
            segments.append(TranscriptSegment(
                id=i,
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip(),
                confidence=seg.get("avg_logprob", 0.0),
            ))
        
        return TranscriptionResult(
            text=result["text"],
            segments=segments,
            language=result.get("language", "en"),
        )
    
    def _transcribe_faster_whisper(self, audio_path: str) -> TranscriptionResult:
        """Transcribe using faster-whisper."""
        segments_gen, info = self._model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            word_timestamps=True,
        )
        
        segments = []
        full_text = []
        
        for i, seg in enumerate(segments_gen):
            segments.append(TranscriptSegment(
                id=i,
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                confidence=seg.avg_logprob if hasattr(seg, 'avg_logprob') else 0.0,
            ))
            full_text.append(seg.text.strip())
        
        return TranscriptionResult(
            text=" ".join(full_text),
            segments=segments,
            language=info.language if hasattr(info, 'language') else "en",
            duration=info.duration if hasattr(info, 'duration') else 0.0,
        )
    
    async def transcribe_async(
        self,
        audio_path: str,
        word_timestamps: bool = True,
    ) -> TranscriptionResult:
        """Async wrapper for transcription.
        
        Args:
            audio_path: Path to audio file
            word_timestamps: Include word-level timestamps
            
        Returns:
            Transcription result
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.transcribe(audio_path, word_timestamps),
        )
    
    def transcribe_url(
        self,
        audio_url: str,
        word_timestamps: bool = True,
    ) -> TranscriptionResult:
        """Transcribe from URL.
        
        Args:
            audio_url: URL to audio file
            word_timestamps: Include word-level timestamps
            
        Returns:
            Transcription result
        """
        import httpx
        
        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            with httpx.stream("GET", audio_url) as response:
                for chunk in response.iter_bytes():
                    f.write(chunk)
            temp_path = f.name
        
        try:
            return self.transcribe(temp_path, word_timestamps)
        finally:
            os.unlink(temp_path)

