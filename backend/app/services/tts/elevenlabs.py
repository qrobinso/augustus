"""ElevenLabs TTS provider for high-quality cloud speech synthesis."""

import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult, Voice, SegmentTiming

settings = get_settings()


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs API provider for premium TTS."""
    
    BASE_URL = "https://api.elevenlabs.io/v1"
    
    # Default voices with volume boost settings
    # Some voices are naturally quieter, so we adjust stability/similarity to compensate
    VOICES = {
        "host1": Voice(
            id="21m00Tcm4TlvDq8ikWAM",
            name="Rachel",
            description="Calm female voice",
            language="en",
        ),
        "host2": Voice(
            id="AZnzlk1XvdvUeBnXmlld",
            name="Domi",
            description="Strong female voice",
            language="en",
        ),
        "adam": Voice(
            id="pNInz6obpgDQGcFmaJgB",
            name="Adam",
            description="Deep male voice",
            language="en",
        ),
        "josh": Voice(
            id="TxGEqnHWrfWFTfGW9XjX",
            name="Josh",
            description="Young male voice",
            language="en",
        ),
    }
    
    # Voice-specific settings to normalize volume output
    # style parameter (0-1) can affect perceived loudness
    VOICE_SETTINGS = {
        "21m00Tcm4TlvDq8ikWAM": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
        "AZnzlk1XvdvUeBnXmlld": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
        "pNInz6obpgDQGcFmaJgB": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
        "TxGEqnHWrfWFTfGW9XjX": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.elevenlabs_api_key
        self._client: Optional[httpx.AsyncClient] = None
        
        if not self.api_key:
            raise ValueError("ElevenLabs API key is required")
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize text using ElevenLabs."""
        # Resolve voice ID from alias
        actual_voice_id = self._resolve_voice_id(voice_id)
        
        # Clean and validate text
        text = text.strip()
        if not text:
            raise ValueError("Text cannot be empty")
        
        # Truncate very long text (ElevenLabs has limits)
        max_chars = 5000
        if len(text) > max_chars:
            print(f"[ElevenLabs] Warning: Text truncated from {len(text)} to {max_chars} chars")
            text = text[:max_chars]
        
        # Get voice-specific settings for consistent volume
        # Use simpler settings that work with all voices
        voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
        }
        
        # Get configured model from settings (refresh to get latest value)
        from app.config import get_settings
        current_settings = get_settings()
        configured_model = current_settings.elevenlabs_model or "eleven_turbo_v2_5"
        
        # Try configured model first, then fall back to alternatives
        models_to_try = [configured_model]
        # Add fallbacks if the configured model is different
        fallback_models = ["eleven_turbo_v2_5", "eleven_multilingual_v2", "eleven_monolingual_v1"]
        for fallback in fallback_models:
            if fallback not in models_to_try:
                models_to_try.append(fallback)
        
        last_error = None
        
        for model_id in models_to_try:
            print(f"[ElevenLabs] Trying model: {model_id}")
            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": voice_settings,
            }
            
            response = await self.client.post(
                f"/text-to-speech/{actual_voice_id}",
                json=payload,
            )
            
            if response.status_code == 200:
                # Success - save audio and return
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.content)
                
                duration = await self._get_audio_duration(output_path)
                
                print(f"[ElevenLabs] Success with model: {model_id}")
                return TTSResult(
                    audio_path=output_path,
                    duration_seconds=duration,
                    voice_id=actual_voice_id,
                    format="mp3",
                )
            
            # Log error details for debugging
            error_detail = response.text
            print(f"[ElevenLabs] Error with model {model_id}: {response.status_code}")
            print(f"[ElevenLabs] Error detail: {error_detail}")
            last_error = f"{response.status_code}: {error_detail}"
            
            # If it's not a model compatibility issue, don't try other models
            if response.status_code != 400 or "model" not in error_detail.lower():
                break
        
        # All attempts failed
        raise RuntimeError(f"ElevenLabs TTS failed: {last_error}")
    
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
            print(f"[ElevenLabs] Using voices - HOST1: {voice_map['HOST1']}, HOST2: {voice_map['HOST2']}")
        
        # Generate audio for each segment and track durations
        segment_paths = []
        segment_durations = []
        segment_data = []  # Store segment info for timing
        temp_files = []
        
        try:
            print(f"[ElevenLabs] Generating {len(script)} segments...")
            
            segment_index = 0
            for i, segment in enumerate(script):
                speaker = segment.get("speaker", "HOST1")
                text = segment.get("text", "")
                
                if not text.strip():
                    continue
                
                voice_id = voice_map.get(speaker, "host1")
                
                # Create temp file for segment
                temp_path = output_path.parent / f"_segment_{i}.mp3"
                temp_files.append(temp_path)
                
                print(f"[ElevenLabs] Generating segment {segment_index+1}/{len(script)} ({speaker})...")
                result = await self.synthesize(text, voice_id, temp_path)
                
                segment_paths.append(temp_path)
                segment_durations.append(result.duration_seconds)
                segment_data.append({
                    "index": segment_index,
                    "speaker": speaker,
                    "text": text,
                    "duration": result.duration_seconds,
                })
                segment_index += 1
            
            print(f"[ElevenLabs] All {len(segment_paths)} segments generated. Concatenating...")
            
            # Concatenate all segments
            if segment_paths:
                await self._concatenate_audio(segment_paths, output_path)
                
                # Verify output file was created
                if not output_path.exists():
                    raise RuntimeError(f"Concatenation failed - output file not created: {output_path}")
                
                print(f"[ElevenLabs] Audio saved to: {output_path}")
            else:
                raise RuntimeError("No audio segments were generated")
            
            duration = await self._get_audio_duration(output_path)
            print(f"[ElevenLabs] Total duration: {duration:.1f} seconds")
            
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
                print(f"[ElevenLabs] Segment {seg['index']}: {timing.start_seconds:.1f}s - {timing.end_seconds:.1f}s ({seg['speaker']})")
            
            return TTSResult(
                audio_path=output_path,
                duration_seconds=duration,
                voice_id="conversation",
                format="mp3",
                segment_timings=segment_timings,
            )
            
        except Exception as e:
            print(f"[ElevenLabs] Error during conversation synthesis: {e}")
            raise
            
        finally:
            # Cleanup temp files
            for temp_file in temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception:
                    pass  # Ignore cleanup errors
    
    def list_voices(self) -> list[Voice]:
        """List available ElevenLabs voices."""
        return list(self.VOICES.values())
    
    def _resolve_voice_id(self, voice_id: str) -> str:
        """Resolve voice alias to actual voice ID."""
        if voice_id in self.VOICES:
            return self.VOICES[voice_id].id
        return voice_id
    
    async def _concatenate_audio(self, segments: list[Path], output_path: Path):
        """Concatenate audio segments using ffmpeg with volume normalization."""
        list_file = output_path.parent / "_concat_list.txt"
        temp_output = output_path.parent / "_temp_concat.mp3"
        
        try:
            # Try ffmpeg with loudnorm filter for volume normalization
            with open(list_file, "w") as f:
                for seg in segments:
                    # Use forward slashes for ffmpeg compatibility
                    f.write(f"file '{str(seg.absolute()).replace(chr(92), '/')}'\n")
            
            print(f"[ElevenLabs] Running ffmpeg to concatenate {len(segments)} segments with normalization...")
            
            # First concatenate, then normalize
            # Step 1: Concatenate
            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy", str(temp_output),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"[ElevenLabs] ffmpeg concat error: {stderr.decode()}")
                raise RuntimeError(f"ffmpeg concat failed with code {process.returncode}")
            
            # Step 2: Normalize volume using loudnorm filter
            # Target: -16 LUFS (standard for podcasts), true peak -1.5 dB
            print(f"[ElevenLabs] Normalizing audio volume...")
            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y",
                "-i", str(temp_output),
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "44100",
                "-b:a", "192k",
                str(output_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"[ElevenLabs] ffmpeg normalize error: {stderr.decode()}")
                # If normalization fails, just use the concatenated file
                import shutil
                shutil.move(str(temp_output), str(output_path))
                print(f"[ElevenLabs] Using non-normalized concatenated file")
            else:
                print(f"[ElevenLabs] ffmpeg concatenation and normalization successful")
            
            # Clean up temp files
            if temp_output.exists():
                temp_output.unlink()
            if list_file.exists():
                list_file.unlink()
            
        except FileNotFoundError:
            print("[ElevenLabs] ffmpeg not found, using pydub fallback...")
            await self._concatenate_with_pydub(segments, output_path)
            
        except Exception as e:
            print(f"[ElevenLabs] ffmpeg failed ({e}), trying pydub fallback...")
            await self._concatenate_with_pydub(segments, output_path)
        
        finally:
            # Clean up temp files if they exist
            for f in [list_file, temp_output]:
                if f.exists():
                    try:
                        f.unlink()
                    except Exception:
                        pass
    
    async def _concatenate_with_pydub(self, segments: list[Path], output_path: Path):
        """Fallback concatenation using pydub with volume normalization."""
        # First try pydub
        try:
            from pydub import AudioSegment
            
            print(f"[ElevenLabs] Concatenating {len(segments)} segments with pydub (with normalization)...")
            
            # Target loudness in dBFS (decibels relative to full scale)
            # -20 dBFS is a good target for spoken audio
            TARGET_DBFS = -20.0
            
            # Load all segments first
            loaded_segments = []
            for i, seg_path in enumerate(segments):
                if seg_path.exists():
                    try:
                        segment = AudioSegment.from_file(str(seg_path), format="mp3")
                        loaded_segments.append((i, segment))
                    except Exception as seg_error:
                        print(f"[ElevenLabs] Error loading segment {i+1}: {seg_error}")
                else:
                    print(f"[ElevenLabs] Segment {i+1} not found: {seg_path}")
            
            if not loaded_segments:
                raise RuntimeError("No segments could be loaded")
            
            # Normalize and concatenate
            combined = None
            for i, segment in loaded_segments:
                # Normalize volume to target dBFS
                current_dbfs = segment.dBFS
                if current_dbfs != float('-inf'):  # Check for silence
                    gain_adjustment = TARGET_DBFS - current_dbfs
                    # Limit gain adjustment to prevent clipping or extreme changes
                    gain_adjustment = max(-12, min(12, gain_adjustment))
                    normalized_segment = segment.apply_gain(gain_adjustment)
                    segment_duration = len(normalized_segment) / 1000
                    print(f"[ElevenLabs] Segment {i+1}: {segment_duration:.1f}s, adjusted {gain_adjustment:+.1f}dB")
                else:
                    normalized_segment = segment
                    print(f"[ElevenLabs] Segment {i+1}: silent segment, no adjustment")
                
                if combined is None:
                    combined = normalized_segment
                else:
                    combined = combined + normalized_segment
            
            total_duration = len(combined) / 1000
            print(f"[ElevenLabs] Combined audio duration: {total_duration:.1f}s")
            
            # Export combined audio
            combined.export(str(output_path), format="mp3", bitrate="192k")
            
            # Verify the file was created and has content
            if output_path.exists():
                file_size = output_path.stat().st_size
                print(f"[ElevenLabs] pydub concatenation successful: {output_path} ({file_size} bytes)")
            else:
                raise RuntimeError("Output file was not created")
            
        except ImportError as e:
            print(f"[ElevenLabs] pydub import failed: {e}, trying binary concatenation...")
            await self._concatenate_binary(segments, output_path)
        except Exception as e:
            print(f"[ElevenLabs] pydub failed: {e}, trying binary concatenation...")
            await self._concatenate_binary(segments, output_path)
    
    async def _concatenate_binary(self, segments: list[Path], output_path: Path):
        """Simple binary concatenation of MP3 files.
        
        This works because MP3 is a streaming format - you can concatenate
        MP3 files directly and they'll play back correctly.
        """
        print(f"[ElevenLabs] Binary concatenating {len(segments)} MP3 segments...")
        
        try:
            total_size = 0
            with open(output_path, 'wb') as outfile:
                for i, seg_path in enumerate(segments):
                    if seg_path.exists():
                        with open(seg_path, 'rb') as infile:
                            data = infile.read()
                            outfile.write(data)
                            total_size += len(data)
                            print(f"[ElevenLabs] Added segment {i+1}/{len(segments)} ({len(data)} bytes)")
                    else:
                        print(f"[ElevenLabs] Segment {i+1} not found: {seg_path}")
            
            if output_path.exists():
                file_size = output_path.stat().st_size
                print(f"[ElevenLabs] Binary concatenation successful: {output_path} ({file_size} bytes)")
            else:
                raise RuntimeError("Output file was not created")
                
        except Exception as e:
            print(f"[ElevenLabs] Binary concatenation failed: {e}")
            # Last resort: copy first segment
            if segments and segments[0].exists():
                import shutil
                shutil.copy(segments[0], output_path)
                print(f"[ElevenLabs] Copied first segment as fallback")
    
    async def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds using ffprobe or mutagen."""
        # Try ffprobe first
        try:
            process = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0 and stdout:
                duration = float(stdout.decode().strip())
                return duration
        except FileNotFoundError:
            # ffprobe not installed - silently fall back to mutagen
            pass
        except Exception:
            # Other ffprobe errors - silently fall back to mutagen
            pass
        
        # Try mutagen as fallback
        try:
            from mutagen.mp3 import MP3
            audio = MP3(str(audio_path))
            duration = audio.info.length
            return duration
        except ImportError:
            # mutagen not installed - fall back to estimation
            pass
        except Exception:
            # mutagen error - fall back to estimation
            pass
        
        # Last resort: estimate based on file size
        # ElevenLabs outputs ~128kbps MP3, so ~16KB per second
        try:
            size = audio_path.stat().st_size
            duration = size / 16000  # 128kbps = 16KB/s
            return duration
        except Exception:
            return 0.0
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

