"""Piper TTS provider for self-hosted speech synthesis."""

import asyncio
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional
import struct
import httpx

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult, Voice, SegmentTiming


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
        # Get fresh settings each time to ensure we have the latest values
        settings = get_settings()
        self.model_path = model_path or settings.piper_model_path
        # Strip whitespace and check if URL is actually set
        self.piper_url = (settings.piper_url or "").strip() or None
        self._piper_available: Optional[bool] = None
        # Only use HTTP if URL is non-empty after stripping
        self._use_http = bool(self.piper_url)
        
        # Log configuration for debugging
        if self._use_http:
            print(f"[Piper] Configured for HTTP API: {self.piper_url}")
        else:
            print(f"[Piper] Configured for CLI, model path: {self.model_path}")
    
    async def _check_piper_available(self) -> bool:
        """Check if piper is available."""
        if self._piper_available is not None:
            return self._piper_available
        
        # If using HTTP API, assume it's available (will fail gracefully during actual synthesis if not)
        if self._use_http:
            # Don't block on health check - let actual API calls handle errors
            # This allows users to configure URL even if service is temporarily down
            self._piper_available = True
            return True
        
        # Otherwise check CLI availability using synchronous subprocess
        try:
            result = subprocess.run(
                ["piper", "--help"],
                capture_output=True,
                text=True
            )
            self._piper_available = result.returncode == 0
            if not self._piper_available:
                print("[TTS] Piper command found but returned non-zero exit code")
        except FileNotFoundError:
            self._piper_available = False
            print("[TTS] Piper not found in PATH - will use placeholder audio or fallback to ElevenLabs")
        except Exception as e:
            self._piper_available = False
            error_msg = str(e) if e else "Unknown error"
            print(f"[TTS] Error checking Piper availability: {error_msg}")
        
        return self._piper_available
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        briefing_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize text using Piper."""
        if not await self._check_piper_available():
            # Raise an error so fallback provider can be used
            raise RuntimeError("Piper TTS is not available. Install piper-tts or ensure it's in PATH, or configure a Piper URL.")
        
        # Use HTTP API if URL is configured
        if self._use_http:
            return await self._synthesize_http(text, voice_id, output_path)
        
        # Otherwise use CLI
        return await self._synthesize_cli(text, voice_id, output_path)
    
    async def _synthesize_http(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize text using Piper HTTP API."""
        if not self.piper_url:
            raise RuntimeError("Piper URL is not configured")
        
        # Resolve internal aliases to Piper model names
        voice_aliases = {
            "host1": "en_US-lessac-medium",
            "host2": "en_US-amy-medium",
        }

        if voice_id in voice_aliases:
            voice = voice_aliases[voice_id]
        elif voice_id:
            # Use the voice_id directly — cast voices are passed through as Piper voice names
            voice = voice_id
        else:
            raise RuntimeError("No voice specified. Configure voice/model in the cast settings.")
        
        # Prepare request - Piper uses POST with query parameters
        api_url = f"{self.piper_url.rstrip('/')}/tts"
        params = {"text": text, "voice": voice}
        
        print(f"[Piper] Making HTTP POST request to {api_url} with voice: {voice}, text length: {len(text)}")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    api_url,
                    params=params,
                )
                response.raise_for_status()
                
                # Save audio data to file
                audio_data = response.content
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # If response is WAV, save directly; if MP3, save as MP3
                content_type = response.headers.get("content-type", "")
                if "audio/wav" in content_type or output_path.suffix.lower() == ".wav":
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                else:
                    # Assume WAV from API, convert if needed
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp_path = Path(tmp.name)
                        tmp.write(audio_data)
                    
                    if output_path.suffix.lower() == ".mp3":
                        await self._convert_to_mp3(tmp_path, output_path)
                        tmp_path.unlink()
                    else:
                        tmp_path.rename(output_path)
                
                # Get duration
                duration = await self._get_audio_duration(output_path)
                print(f"[Piper] Successfully synthesized segment, duration: {duration:.2f}s, size: {len(audio_data)} bytes")
                
                return TTSResult(
                    audio_path=output_path,
                    duration_seconds=duration,
                    voice_id=voice_id,
                    format=output_path.suffix[1:],
                )
        except httpx.HTTPStatusError as e:
            error_detail = f"Status {e.response.status_code}"
            try:
                error_body = e.response.text
                error_detail += f": {error_body}"
            except:
                pass
            print(f"[Piper] HTTP API error: {error_detail}")
            raise RuntimeError(f"Piper HTTP API failed: {error_detail}")
        except httpx.RequestError as e:
            print(f"[Piper] Request error: {str(e)}")
            raise RuntimeError(f"Piper HTTP API request failed: {str(e)}")
        except Exception as e:
            print(f"[Piper] Unexpected error: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"Piper HTTP API failed: {str(e)}")
    
    async def _synthesize_cli(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize text using Piper CLI."""
        # Run synchronously in thread pool to avoid Windows asyncio subprocess issues
        return await asyncio.to_thread(
            self._synthesize_cli_sync, text, voice_id, output_path
        )
    
    def _synthesize_cli_sync(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Synchronous Piper CLI synthesis."""
        import shutil
        
        # Determine model path based on voice_id
        model_path = self._get_model_path(voice_id)
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # Run piper synchronously
            result = subprocess.run(
                [
                    "piper",
                    "--model", str(model_path),
                    "--output_file", str(tmp_path)
                ],
                input=text.encode(),
                capture_output=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Piper failed: {result.stderr.decode()}")
            
            # Convert WAV to MP3 if needed (requires ffmpeg)
            if output_path.suffix.lower() == ".mp3":
                self._convert_to_mp3_sync(tmp_path, output_path)
            else:
                shutil.move(str(tmp_path), str(output_path))
            
            # Get duration
            duration = self._get_audio_duration_sync(output_path)
            
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
        briefing_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize a multi-speaker conversation."""
        if voice_map is None:
            voice_map = {
                "HOST1": "en_US-lessac-medium",
                "HOST2": "en_US-amy-medium",
            }
            print(f"[Piper] WARNING: No voice_map provided, using defaults")

        # Log distinct cast voices being used
        distinct_voices = set(voice_map.values())
        if len(distinct_voices) > 1:
            print(f"[Piper] Multiple cast voices detected: {voice_map}")
        else:
            print(f"[Piper] Single voice in use: {distinct_voices}")
        
        # Generate audio for each segment and track durations
        segment_paths = []
        segment_data = []
        temp_files = []
        
        try:
            print(f"[Piper] Starting conversation synthesis, output: {output_path}")
            segment_index = 0
            total_segments = len([s for s in script if s.get("text", "").strip()])
            print(f"[Piper] Synthesizing conversation with {total_segments} segments")
            
            for i, segment in enumerate(script):
                speaker = segment.get("speaker", "HOST1")
                text = segment.get("text", "")
                
                if not text.strip():
                    continue
                
                voice_id = voice_map.get(speaker, "host1")
                
                # Create temp file for segment
                temp_path = output_path.parent / f"_segment_{i}.wav"
                temp_files.append(temp_path)
                
                print(f"[Piper] Processing segment {segment_index + 1}/{total_segments} (speaker: {speaker}, voice_id: {voice_id})")
                result = await self.synthesize(text, voice_id, temp_path)
                print(f"[Piper] Segment {segment_index + 1} complete: {result.duration_seconds:.2f}s")
                
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
                print(f"[Piper] Concatenating {len(segment_paths)} segments into final audio...")
                await self._concatenate_audio(segment_paths, output_path)
                print(f"[Piper] Concatenation complete, output: {output_path}")
            else:
                # Create empty audio if no segments
                print("[Piper] No segments to concatenate, creating placeholder audio")
                await self._create_placeholder_audio("", "host1", output_path)
            
            # Verify output file exists
            if not output_path.exists():
                raise RuntimeError(f"Output audio file was not created: {output_path}")
            
            # Calculate segment timings and total duration from segments
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
            
            # Use sum of segment durations as the total duration (most reliable)
            total_duration_from_segments = current_time
            
            # Also try to get duration from the output file
            print(f"[Piper] Getting duration for final audio file...")
            file_duration = await self._get_audio_duration(output_path)
            print(f"[Piper] File duration: {file_duration:.2f}s, Segment sum: {total_duration_from_segments:.2f}s")
            
            # Use segment sum as it's more reliable (file-based detection may fail on Windows without ffprobe)
            duration = total_duration_from_segments if total_duration_from_segments > 0 else file_duration
            
            result = TTSResult(
                audio_path=output_path,
                duration_seconds=duration,
                voice_id="conversation",
                format=output_path.suffix[1:],
                segment_timings=segment_timings,
            )
            print(f"[Piper] Conversation synthesis complete: {duration:.2f}s total, {len(segment_timings)} segments")
            return result
            
        except Exception as e:
            print(f"[Piper] Error during conversation synthesis: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"[Piper] Traceback:\n{traceback.format_exc()}")
            raise
        finally:
            # Cleanup temp files
            print(f"[Piper] Cleaning up {len(temp_files)} temporary segment files")
            for temp_file in temp_files:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception as cleanup_error:
                        print(f"[Piper] Warning: Failed to delete temp file {temp_file}: {cleanup_error}")
    
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
        await asyncio.to_thread(self._convert_to_mp3_sync, wav_path, mp3_path)
    
    def _convert_to_mp3_sync(self, wav_path: Path, mp3_path: Path):
        """Synchronous WAV to MP3 conversion using ffmpeg."""
        import shutil
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(wav_path),
                    "-acodec", "libmp3lame", "-q:a", "2",
                    str(mp3_path)
                ],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"[Piper] ffmpeg MP3 conversion warning: {result.stderr}")
        except FileNotFoundError:
            # ffmpeg not available, just copy the wav
            mp3_path = mp3_path.with_suffix(".wav")
            shutil.copy(wav_path, mp3_path)
    
    async def _concatenate_audio(self, segments: list[Path], output_path: Path):
        """Concatenate audio segments."""
        if not segments:
            raise ValueError("No segments to concatenate")
        
        # Verify all segment files exist
        for seg in segments:
            if not seg.exists():
                raise FileNotFoundError(f"Segment file not found: {seg}")
        
        # Run concatenation in thread pool to avoid blocking and Windows asyncio issues
        await asyncio.to_thread(self._concatenate_audio_sync, segments, output_path)
    
    def _concatenate_audio_sync(self, segments: list[Path], output_path: Path):
        """Synchronous audio concatenation using ffmpeg."""
        import shutil
        
        list_file = output_path.parent / "_concat_list.txt"
        
        try:
            # Create concat list file for ffmpeg
            with open(list_file, "w", encoding="utf-8") as f:
                for seg in segments:
                    # Use absolute path and escape single quotes for ffmpeg
                    seg_path = str(seg.absolute()).replace("'", "'\\''")
                    f.write(f"file '{seg_path}'\n")
            
            print(f"[Piper] Created concat list file with {len(segments)} segments")
            
            # Run ffmpeg synchronously
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(list_file),
                    "-c", "copy", str(output_path)
                ],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown ffmpeg error"
                print(f"[Piper] ffmpeg concatenation failed: {error_msg}")
                raise RuntimeError(f"ffmpeg failed to concatenate audio: {error_msg}")
            
            print(f"[Piper] ffmpeg concatenation successful")
            
        except FileNotFoundError:
            # ffmpeg not available, try alternative method
            print("[Piper] ffmpeg not found, trying alternative concatenation method")
            if len(segments) == 1:
                shutil.copy(segments[0], output_path)
                print("[Piper] Copied single segment as output")
            else:
                # For multiple WAV files, concatenate manually
                self._concatenate_wav_files(segments, output_path)
        finally:
            # Clean up concat list file
            if list_file.exists():
                try:
                    list_file.unlink()
                except:
                    pass
    
    def _concatenate_wav_files(self, segments: list[Path], output_path: Path):
        """Manually concatenate WAV files without ffmpeg."""
        import shutil
        
        print(f"[Piper] Concatenating {len(segments)} WAV files manually")
        
        # Read all WAV files and concatenate their data
        all_frames = []
        params = None
        
        for seg in segments:
            with wave.open(str(seg), 'rb') as wf:
                if params is None:
                    params = wf.getparams()
                all_frames.append(wf.readframes(wf.getnframes()))
        
        if params is None:
            raise RuntimeError("No valid WAV files to concatenate")
        
        # Write concatenated WAV
        wav_output = output_path.with_suffix('.wav')
        with wave.open(str(wav_output), 'wb') as wf:
            wf.setparams(params)
            for frames in all_frames:
                wf.writeframes(frames)
        
        # If output should be MP3, the caller will handle conversion
        # For now, just rename if needed
        if output_path.suffix.lower() == '.wav':
            if wav_output != output_path:
                shutil.move(wav_output, output_path)
        else:
            # Just use WAV for now, rename to expected path
            shutil.move(wav_output, output_path)
        
        print(f"[Piper] Manual WAV concatenation complete")
    
    async def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        return await asyncio.to_thread(self._get_audio_duration_sync, audio_path)
    
    def _get_audio_duration_sync(self, audio_path: Path) -> float:
        """Synchronous audio duration detection."""
        try:
            # First try reading as WAV (works for both .wav and mis-labeled WAV files)
            try:
                with wave.open(str(audio_path), 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration = frames / float(rate)
                    if duration > 0:
                        return duration
            except Exception:
                pass  # Not a valid WAV file, try other methods
            
            # Try ffprobe for other formats
            try:
                result = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        str(audio_path)
                    ],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
                    if duration > 0:
                        return duration
            except FileNotFoundError:
                print("[Piper] ffprobe not found, cannot determine duration for non-WAV files")
            except Exception as e:
                print(f"[Piper] ffprobe error: {e}")
            
            # Fallback: estimate from file size (rough approximation for WAV: ~176KB per second at 22050Hz 16-bit mono)
            try:
                file_size = audio_path.stat().st_size
                # Assume WAV format: sample_rate=22050, bits=16, channels=1
                # bytes per second = 22050 * 2 * 1 = 44100
                estimated_duration = file_size / 44100
                if estimated_duration > 0:
                    print(f"[Piper] Estimated duration from file size: {estimated_duration:.2f}s")
                    return estimated_duration
            except Exception:
                pass
            
            return 0.0
        except Exception as e:
            print(f"[Piper] Error getting audio duration: {e}")
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

