"""Google Gemini TTS provider."""

import asyncio
import tempfile
import wave
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult, Voice, SegmentTiming


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
        
        if not response.candidates or not response.candidates[0].content.parts:
            raise RuntimeError("Gemini TTS failed to generate audio")

        audio_part = response.candidates[0].content.parts[0]
        if not hasattr(audio_part, 'inline_data') or not audio_part.inline_data:
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
        # Get fresh settings each time
        settings = get_settings()
        
        if voice_map is None:
            voice_map = {
                "HOST1": settings.tts_voice_host1,
                "HOST2": settings.tts_voice_host2,
            }

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
        # Get fresh settings each time
        settings = get_settings()
        
        if voice_id == "host1":
            return self._resolve_voice_id(settings.tts_voice_host1)
        if voice_id == "host2":
            return self._resolve_voice_id(settings.tts_voice_host2)
            
        # If it's a known Gemini voice, return it
        if voice_id in self.VOICES:
            return voice_id
            
        # Default to Kore if unknown
        return "Kore"

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
        except Exception as e:
            print(f"[Gemini] Conversion to MP3 failed: {e}")
            # If ffmpeg fails, just copy the wav (though it won't be mp3)
            import shutil
            shutil.copy(wav_path, mp3_path)

    async def _concatenate_audio(self, segments: list[Path], output_path: Path):
        """Concatenate audio segments using ffmpeg."""
        try:
            list_file = output_path.parent / "_gemini_concat_list.txt"
            with open(list_file, "w") as f:
                for seg in segments:
                    # Use forward slashes for ffmpeg compatibility on Windows
                    f.write(f"file '{str(seg.absolute()).replace(chr(92), '/')}'\n")
            
            # For Gemini, segments are WAV, so we concatenate them into the final output path
            # If output_path is .mp3, we convert during concatenation or after
            is_mp3 = output_path.suffix.lower() == ".mp3"
            
            if is_mp3:
                # Concatenate and convert to mp3
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(list_file),
                    "-acodec", "libmp3lame", "-q:a", "2",
                    str(output_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                # Just concatenate
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(list_file),
                    "-c", "copy",
                    str(output_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
            await process.communicate()
            if list_file.exists():
                list_file.unlink()
                
        except Exception as e:
            print(f"[Gemini] Concatenation failed: {e}")
            # Fallback: copy first segment
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
                if stdout:
                    return float(stdout.decode().strip())
                return 0.0
        except Exception:
            return 0.0
