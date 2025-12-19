"""Google Gemini TTS provider."""

import asyncio
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult, Voice, SegmentTiming
from app.utils.audio import concatenate_audio_files, convert_to_mp3 as audio_convert_to_mp3


class GeminiProvider(TTSProvider):
    """Google Gemini TTS provider using native speech generation."""

    # Default voices supported by Gemini TTS
    # Reference: https://ai.google.dev/gemini-api/docs/speech-generation#voice_options
    VOICES = {
        "Kore": Voice(id="Kore", name="Kore", description="Firm", language="en-US"),
        "Puck": Voice(id="Puck", name="Puck", description="Upbeat", language="en-US"),
        "Charon": Voice(id="Charon", name="Charon", description="Informative", language="en-US"),
        "Zephyr": Voice(id="Zephyr", name="Zephyr", description="Bright", language="en-US"),
        "Fenrir": Voice(id="Fenrir", name="Fenrir", description="Excitable", language="en-US"),
        "Leda": Voice(id="Leda", name="Leda", description="Youthful", language="en-US"),
        "Orus": Voice(id="Orus", name="Orus", description="Firm", language="en-US"),
        "Aoede": Voice(id="Aoede", name="Aoede", description="Breezy", language="en-US"),
        "Callirrhoe": Voice(id="Callirrhoe", name="Callirrhoe", description="Easy-going", language="en-US"),
        "Autonoe": Voice(id="Autonoe", name="Autonoe", description="Bright", language="en-US"),
        "Enceladus": Voice(id="Enceladus", name="Enceladus", description="Breathy", language="en-US"),
        "Iapetus": Voice(id="Iapetus", name="Iapetus", description="Clear", language="en-US"),
        "Umbriel": Voice(id="Umbriel", name="Umbriel", description="Easy-going", language="en-US"),
        "Algieba": Voice(id="Algieba", name="Algieba", description="Smooth", language="en-US"),
        "Despina": Voice(id="Despina", name="Despina", description="Smooth", language="en-US"),
        "Erinome": Voice(id="Erinome", name="Erinome", description="Clear", language="en-US"),
        "Algenib": Voice(id="Algenib", name="Algenib", description="Gravelly", language="en-US"),
        "Rasalgethi": Voice(id="Rasalgethi", name="Rasalgethi", description="Informative", language="en-US"),
        "Laomedeia": Voice(id="Laomedeia", name="Laomedeia", description="Upbeat", language="en-US"),
        "Achernar": Voice(id="Achernar", name="Achernar", description="Soft", language="en-US"),
        "Alnilam": Voice(id="Alnilam", name="Alnilam", description="Firm", language="en-US"),
        "Schedar": Voice(id="Schedar", name="Schedar", description="Even", language="en-US"),
        "Gacrux": Voice(id="Gacrux", name="Gacrux", description="Mature", language="en-US"),
        "Pulcherrima": Voice(id="Pulcherrima", name="Pulcherrima", description="Forward", language="en-US"),
        "Achird": Voice(id="Achird", name="Achird", description="Friendly", language="en-US"),
        "Zubenelgenubi": Voice(id="Zubenelgenubi", name="Zubenelgenubi", description="Casual", language="en-US"),
        "Vindemiatrix": Voice(id="Vindemiatrix", name="Vindemiatrix", description="Gentle", language="en-US"),
        "Sadachbia": Voice(id="Sadachbia", name="Sadachbia", description="Lively", language="en-US"),
        "Sadaltager": Voice(id="Sadaltager", name="Sadaltager", description="Knowledgeable", language="en-US"),
        "Sulafat": Voice(id="Sulafat", name="Sulafat", description="Warm", language="en-US"),
    }

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        # Get fresh settings each time to avoid stale cache issues
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model
        
        if not self.api_key:
            raise ValueError("Gemini API key is required")
            
        self._client = genai.Client(api_key=self.api_key)

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
    ) -> TTSResult:
        """Synthesize text using Gemini."""
        # Resolve voice ID from alias (host1, host2) if provided
        actual_voice_id = self._resolve_voice_id(voice_id)
        
        # Clean text
        text = text.strip()
        if not text:
            raise ValueError("Text cannot be empty")

        print(f"[Gemini] Synthesizing text with voice {actual_voice_id}...")
        
        # Call Gemini API
        # Since the google-genai library might be blocking or use its own async, 
        # we'll wrap the call if necessary, but according to docs it's synchronous in the example.
        # However, we are in an async context, so we should run it in a thread if it's blocking.
        
        def _call_gemini():
            return self._client.models.generate_content(
                model=self.model_name,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=actual_voice_id,
                            )
                        )
                    ),
                )
            )

        response = await asyncio.to_thread(_call_gemini)
        
        if not response or not hasattr(response, 'candidates') or not response.candidates:
            raise RuntimeError("Gemini TTS failed: No response or candidates")
        
        candidate = response.candidates[0]
        if not candidate or not hasattr(candidate, 'content') or not candidate.content:
            raise RuntimeError("Gemini TTS failed: No content in response candidate")
        
        if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
            raise RuntimeError("Gemini TTS failed: No parts in response content")

        audio_part = candidate.content.parts[0]
        if not audio_part or not hasattr(audio_part, 'inline_data') or not audio_part.inline_data:
            raise RuntimeError("Gemini TTS response did not contain audio data")
            
        data = audio_part.inline_data.data

        # Save as WAV first (Gemini outputs raw PCM 16-bit 24kHz mono)
        # We use a temporary wav file if the final requested format is different
        is_mp3 = output_path.suffix.lower() == ".mp3"
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(24000)
                wf.writeframes(data)
            
            if is_mp3:
                await self._convert_to_mp3(tmp_path, output_path)
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy(tmp_path, output_path)
            
            duration = await self._get_audio_duration(output_path)
            
            return TTSResult(
                audio_path=output_path,
                duration_seconds=duration,
                voice_id=actual_voice_id,
                format="mp3" if is_mp3 else "wav",
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
        """Synthesize a multi-speaker conversation by segments to maintain timings."""
        if voice_map is None:
            # Use default voices (should always be passed from cast, but fallback just in case)
            voice_map = {
                "HOST1": "Kore",
                "HOST2": "Puck",
            }
            print(f"[Gemini] WARNING: No voice_map provided, using defaults")

        segment_paths = []
        segment_data = []
        temp_files = []
        
        try:
            print(f"[Gemini] Generating {len(script)} segments...")
            
            segment_index = 0
            for i, segment in enumerate(script):
                speaker = segment.get("speaker", "HOST1")
                text = segment.get("text", "")
                
                if not text.strip():
                    continue
                
                voice_id = voice_map.get(speaker, speaker) # fallback to speaker name as voice id
                
                temp_path = output_path.parent / f"_gemini_seg_{i}.wav"
                temp_files.append(temp_path)
                
                print(f"[Gemini] Generating segment {segment_index+1}/{len(script)} ({speaker})...")
                result = await self.synthesize(text, voice_id, temp_path)
                
                # Verify the file was created and is readable
                if not temp_path.exists():
                    raise RuntimeError(f"Segment file was not created: {temp_path}")
                if temp_path.stat().st_size == 0:
                    raise RuntimeError(f"Segment file is empty: {temp_path}")
                
                segment_paths.append(temp_path)
                segment_data.append({
                    "index": segment_index,
                    "speaker": speaker,
                    "text": text,
                    "duration": result.duration_seconds,
                })
                segment_index += 1
            
            # Verify all segment files are valid WAV files before concatenation
            print(f"[Gemini] Verifying {len(segment_paths)} segment files...")
            for i, seg_path in enumerate(segment_paths):
                try:
                    with wave.open(str(seg_path), 'rb') as wf:
                        channels = wf.getnchannels()
                        sampwidth = wf.getsampwidth()
                        framerate = wf.getframerate()
                        frames = wf.getnframes()
                        print(f"[Gemini]   Segment {i}: {channels}ch, {sampwidth*8}bit, {framerate}Hz, {frames} frames")
                        # Verify format matches expected (1 channel, 16-bit, 24kHz)
                        if channels != 1 or sampwidth != 2 or framerate != 24000:
                            print(f"[Gemini]   WARNING: Segment {i} format mismatch - expected 1ch 16bit 24kHz, got {channels}ch {sampwidth*8}bit {framerate}Hz")
                except Exception as e:
                    print(f"[Gemini]   ERROR: Could not verify segment {i}: {e}")
                    raise RuntimeError(f"Invalid WAV file for segment {i}: {seg_path} - {e}")
            
            # Concatenate all segments
            if segment_paths:
                await self._concatenate_audio(segment_paths, output_path)
            else:
                raise RuntimeError("No audio segments were generated")
            
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
            for temp_file in temp_files:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass

    def list_voices(self) -> list[Voice]:
        """List available Gemini voices."""
        return list(self.VOICES.values())

    async def close(self):
        """No explicit close needed for Gemini Client."""
        pass

    def _resolve_voice_id(self, voice_id: str) -> str:
        """Resolve voice alias to actual voice ID."""
        # If it's a known Gemini voice, return it
        if voice_id in self.VOICES:
            return voice_id
            
        # Default to Kore if unknown
        return "Kore"

    async def _convert_to_mp3(self, wav_path: Path, mp3_path: Path):
        """Convert WAV to MP3 using common audio utility."""
        # Use VBR quality 2 (equivalent to high quality)
        # Note: audio_convert_to_mp3 uses bitrate, but we can use it as fallback
        # For better quality, we could enhance the utility function, but this works
        success = await audio_convert_to_mp3(wav_path, mp3_path, bitrate="192k")
        if not success:
            # Fallback: try with a custom command for VBR
            try:
                cmd = [
                    "ffmpeg", "-y", "-i", str(wav_path),
                    "-acodec", "libmp3lame", "-q:a", "2",
                    str(mp3_path),
                ]
                
                def run_ffmpeg():
                    return subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                
                result = await asyncio.to_thread(run_ffmpeg)
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
            except Exception as e:
                print(f"[Gemini] Conversion to MP3 failed: {e}")
                # If ffmpeg fails, just copy the wav (though it won't be mp3)
                import shutil
                shutil.copy(wav_path, mp3_path)

    async def _concatenate_audio(self, segments: list[Path], output_path: Path):
        """Concatenate audio segments using common audio utility."""
        is_mp3 = output_path.suffix.lower() == ".mp3"
        
        if is_mp3:
            # Two-step process: concatenate to WAV first, then convert to MP3
            # This is more reliable than trying to do both in one step
            temp_wav_output = output_path.with_suffix(".wav")
            
            print(f"[Gemini] Step 1: Concatenating {len(segments)} WAV segments...")
            # Re-encode to ensure format consistency (all segments are PCM 16-bit 24kHz mono)
            success = await concatenate_audio_files(
                segments,
                temp_wav_output,
                reencode=True,
                sample_rate=24000,
                channels=1,
            )
            
            if not success:
                raise RuntimeError("Failed to concatenate WAV segments")
            
            if not temp_wav_output.exists():
                raise RuntimeError(f"Concatenated WAV file was not created: {temp_wav_output}")
            
            # Step 2: Convert WAV to MP3
            print(f"[Gemini] Step 2: Converting WAV to MP3...")
            success = await audio_convert_to_mp3(temp_wav_output, output_path, bitrate="192k")
            
            # Clean up temp WAV file
            if temp_wav_output.exists():
                try:
                    temp_wav_output.unlink()
                except Exception:
                    pass
            
            if not success:
                raise RuntimeError("Failed to convert concatenated WAV to MP3")
        else:
            # Single step: concatenate WAV files
            print(f"[Gemini] Concatenating {len(segments)} WAV segments...")
            # Re-encode to ensure format consistency
            success = await concatenate_audio_files(
                segments,
                output_path,
                reencode=True,
                sample_rate=24000,
                channels=1,
            )
            
            if not success:
                raise RuntimeError("Failed to concatenate WAV segments")
        
        output_size = output_path.stat().st_size
        print(f"[Gemini] Successfully concatenated {len(segments)} segments into {output_path.name} ({output_size} bytes)")

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
                cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ]
                
                # Use subprocess.run wrapped in asyncio.to_thread for Windows compatibility
                def run_ffprobe():
                    return subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                
                result = await asyncio.to_thread(run_ffprobe)
                if result.returncode == 0 and result.stdout:
                    return float(result.stdout.strip())
                return 0.0
        except Exception:
            return 0.0
