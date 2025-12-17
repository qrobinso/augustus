"""Piper TTS provider for self-hosted speech synthesis."""

import asyncio
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional
import struct

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult, Voice, SegmentTiming

settings = get_settings()


class PiperProvider(TTSProvider):
    """Piper TTS provider for local speech synthesis.
    
    Note: Requires piper-tts to be installed separately.
    Install with: pip install piper-tts
    Download models from: https://github.com/rhasspy/piper/releases
    """
    
    # Default voices (model files)
    VOICES = {
        "host1": Voice(
            id="en_US-lessac-medium",
            name="Lessac",
            description="US English male voice",
            language="en-US",
        ),
        "host2": Voice(
            id="en_US-amy-medium", 
            name="Amy",
            description="US English female voice",
            language="en-US",
        ),
        "en_US-lessac-medium": Voice(
            id="en_US-lessac-medium",
            name="Lessac",
            description="US English male voice",
            language="en-US",
        ),
    }
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.piper_model_path
        self._piper_available: Optional[bool] = None
    
    async def _check_piper_available(self) -> bool:
        """Check if piper is available."""
        if self._piper_available is not None:
            return self._piper_available
        
        try:
            result = await asyncio.create_subprocess_exec(
                "piper", "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            self._piper_available = result.returncode == 0
            if not self._piper_available:
                print("[TTS] Piper command found but returned non-zero exit code")
        except FileNotFoundError:
            self._piper_available = False
            print("[TTS] Piper not found in PATH - will use placeholder audio or fallback to ElevenLabs")
        except Exception as e:
            self._piper_available = False
            print(f"[TTS] Error checking Piper availability: {e}")
        
        return self._piper_available
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize text using Piper."""
        if not await self._check_piper_available():
            # Raise an error so fallback provider can be used
            raise RuntimeError("Piper TTS is not available. Install piper-tts or ensure it's in PATH.")
        
        # Determine model path based on voice_id
        model_path = self._get_model_path(voice_id)
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # Run piper
            process = await asyncio.create_subprocess_exec(
                "piper",
                "--model", str(model_path),
                "--output_file", str(tmp_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate(input=text.encode())
            
            if process.returncode != 0:
                raise RuntimeError(f"Piper failed: {stderr.decode()}")
            
            # Convert WAV to MP3 if needed (requires ffmpeg)
            if output_path.suffix.lower() == ".mp3":
                await self._convert_to_mp3(tmp_path, output_path)
            else:
                tmp_path.rename(output_path)
            
            # Get duration
            duration = await self._get_audio_duration(output_path)
            
            return TTSResult(
                audio_path=output_path,
                duration_seconds=duration,
                voice_id=voice_id,
                format=output_path.suffix[1:],
            )
            
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    
    async def synthesize_conversation(
        self,
        script: list[dict],
        output_path: Path,
        voice_map: Optional[dict[str, str]] = None,
    ) -> TTSResult:
        """Synthesize a multi-speaker conversation."""
        # Get voice settings from config
        from app.config import get_settings
        current_settings = get_settings()
        
        if voice_map is None:
            # Use configured voices from settings
            voice_map = {
                "HOST1": current_settings.tts_voice_host1,
                "HOST2": current_settings.tts_voice_host2,
            }
            print(f"[Piper] Using voices - HOST1: {voice_map['HOST1']}, HOST2: {voice_map['HOST2']}")
        
        # Generate audio for each segment and track durations
        segment_paths = []
        segment_data = []
        temp_files = []
        
        try:
            segment_index = 0
            for i, segment in enumerate(script):
                speaker = segment.get("speaker", "HOST1")
                text = segment.get("text", "")
                
                if not text.strip():
                    continue
                
                voice_id = voice_map.get(speaker, "host1")
                
                # Create temp file for segment
                temp_path = output_path.parent / f"_segment_{i}.wav"
                temp_files.append(temp_path)
                
                result = await self.synthesize(text, voice_id, temp_path)
                segment_paths.append(temp_path)
                segment_data.append({
                    "index": segment_index,
                    "speaker": speaker,
                    "text": text,
                    "duration": result.duration_seconds,
                })
                segment_index += 1
            
            # Concatenate all segments
            if segment_paths:
                await self._concatenate_audio(segment_paths, output_path)
            else:
                # Create empty audio if no segments
                await self._create_placeholder_audio("", "host1", output_path)
            
            duration = await self._get_audio_duration(output_path)
            
            # Calculate segment timings
            segment_timings = []
            current_time = 0.0
            for seg in segment_data:
                timing = SegmentTiming(
                    index=seg["index"],
                    speaker=seg["speaker"],
                    text=seg["text"],
                    start_seconds=current_time,
                    end_seconds=current_time + seg["duration"],
                    duration_seconds=seg["duration"],
                )
                segment_timings.append(timing)
                current_time += seg["duration"]
            
            return TTSResult(
                audio_path=output_path,
                duration_seconds=duration,
                voice_id="conversation",
                format=output_path.suffix[1:],
                segment_timings=segment_timings,
            )
            
        finally:
            # Cleanup temp files
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()
    
    def list_voices(self) -> list[Voice]:
        """List available Piper voices."""
        return list(self.VOICES.values())
    
    def _get_model_path(self, voice_id: str) -> Path:
        """Get model path for voice ID."""
        # Map voice aliases to model names
        model_name = {
            "host1": "en_US-lessac-medium",
            "host2": "en_US-amy-medium",
        }.get(voice_id, voice_id)
        
        return Path(f"./models/{model_name}.onnx")
    
    async def _convert_to_mp3(self, wav_path: Path, mp3_path: Path):
        """Convert WAV to MP3 using ffmpeg."""
        try:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", str(wav_path),
                "-acodec", "libmp3lame", "-q:a", "2",
                str(mp3_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        except FileNotFoundError:
            # ffmpeg not available, just copy the wav
            import shutil
            mp3_path = mp3_path.with_suffix(".wav")
            shutil.copy(wav_path, mp3_path)
    
    async def _concatenate_audio(self, segments: list[Path], output_path: Path):
        """Concatenate audio segments."""
        try:
            # Try using ffmpeg
            list_file = output_path.parent / "_concat_list.txt"
            with open(list_file, "w") as f:
                for seg in segments:
                    f.write(f"file '{seg.absolute()}'\n")
            
            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy", str(output_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            list_file.unlink()
            
        except FileNotFoundError:
            # Fallback: just use the first segment
            if segments:
                import shutil
                shutil.copy(segments[0], output_path)
    
    async def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        try:
            if audio_path.suffix.lower() == ".wav":
                with wave.open(str(audio_path), 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    return frames / float(rate)
            else:
                # Try ffprobe
                process = await asyncio.create_subprocess_exec(
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                return float(stdout.decode().strip())
        except Exception:
            return 0.0
    
    async def _create_placeholder_audio(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Create a placeholder silent audio file for testing."""
        # Create a simple WAV file with silence
        duration = max(1.0, len(text) / 15)  # Rough estimate: 15 chars/second
        sample_rate = 22050
        num_samples = int(sample_rate * duration)
        
        wav_path = output_path.with_suffix(".wav")
        
        with wave.open(str(wav_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            # Write silence
            wf.writeframes(b'\x00\x00' * num_samples)
        
        if output_path.suffix.lower() != ".wav":
            await self._convert_to_mp3(wav_path, output_path)
            wav_path.unlink()
        else:
            output_path = wav_path
        
        return TTSResult(
            audio_path=output_path,
            duration_seconds=duration,
            voice_id=voice_id,
            format=output_path.suffix[1:],
        )
    
    async def close(self):
        """No cleanup needed for Piper."""
        pass

