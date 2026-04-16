"""Google Gemini TTS provider."""

import asyncio
import mimetypes
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.tts.base import TTSProvider, TTSResult, Voice, SegmentTiming
from app.utils.audio import convert_to_mp3 as audio_convert_to_mp3


def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    """Parses bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys.
    """
    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                pass  # Keep rate as default
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass  # Keep bits_per_sample as default if conversion fails

    return {"bits_per_sample": bits_per_sample, "rate": rate}


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file from raw audio data.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the complete WAV file.
    """
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

    # http://soundfile.sapp.org/doc/WaveFormat/
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize (total file size - 8 bytes)
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size (size of audio data)
    )
    return header + audio_data


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
        briefing_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize text using Gemini."""
        # Resolve voice ID from alias (host1, host2) if provided
        actual_voice_id = self._resolve_voice_id(voice_id)
        
        # Clean text
        text = text.strip()
        if not text:
            raise ValueError("Text cannot be empty")

        print(f"[Gemini] Synthesizing text with voice {actual_voice_id}, model {self.model_name}...")
        
        # Call Gemini API using the proper content structure
        def _call_gemini():
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=text),
                    ],
                ),
            ]
            
            config = types.GenerateContentConfig(
                temperature=1,
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=actual_voice_id,
                        )
                    )
                ),
            )
            
            # Use streaming to handle potentially large responses
            all_audio_data = b""
            mime_type = None
            
            for chunk in self._client.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue
                    
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    all_audio_data += part.inline_data.data
                    if mime_type is None:
                        mime_type = part.inline_data.mime_type
            
            return all_audio_data, mime_type

        if briefing_id:
            from app.services.cancellation import cancellable_await
            audio_data, mime_type = await cancellable_await(
                asyncio.to_thread(_call_gemini), briefing_id,
            )
        else:
            audio_data, mime_type = await asyncio.to_thread(_call_gemini)

        if not audio_data:
            raise RuntimeError("Gemini TTS failed: No audio data received")
        
        print(f"[Gemini] Received {len(audio_data)} bytes of audio data, mime_type: {mime_type}")

        # Convert raw audio to WAV using proper header generation
        wav_data = convert_to_wav(audio_data, mime_type or "audio/L16;rate=24000")
        
        # Save as WAV first
        is_mp3 = output_path.suffix.lower() == ".mp3"
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # Write WAV data
            with open(tmp_path, "wb") as f:
                f.write(wav_data)
            
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
        briefing_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize a multi-speaker conversation using Gemini's native multi-speaker support."""
        if voice_map is None:
            voice_map = {
                "HOST1": "Kore",
                "HOST2": "Sadachbia",
            }
            print(f"[Gemini] WARNING: No voice_map provided, using defaults")
        
        # Build the conversation text with speaker labels
        # Format: "Speaker Name: dialogue text"
        conversation_parts = []
        segment_data = []
        unique_speakers = set()
        
        segment_index = 0
        for segment in script:
            speaker = segment.get("speaker", "HOST1")
            text = segment.get("text", "").strip()
            
            if not text:
                continue
            
            unique_speakers.add(speaker)
            conversation_parts.append(f"{speaker}: {text}")
            segment_data.append({
                "index": segment_index,
                "speaker": speaker,
                "text": text,
            })
            segment_index += 1
        
        if not conversation_parts:
            raise RuntimeError("No valid conversation segments provided")
        
        # Join with newlines for clear speaker separation
        full_conversation = "\n".join(conversation_parts)
        
        # Build speaker voice configs for each unique speaker
        speaker_voice_configs = []
        for speaker in unique_speakers:
            # Get voice ID from map, resolve to valid Gemini voice
            voice_id = voice_map.get(speaker, "Kore")
            actual_voice = self._resolve_voice_id(voice_id)
            
            speaker_voice_configs.append(
                types.SpeakerVoiceConfig(
                    speaker=speaker,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=actual_voice
                        )
                    ),
                )
            )
        
        print(f"[Gemini] Generating multi-speaker conversation with {len(unique_speakers)} speakers, {len(segment_data)} segments...")
        speaker_info = ', '.join(f'{s}={self._resolve_voice_id(voice_map.get(s, "Kore"))}' for s in unique_speakers)
        print(f"[Gemini] Speakers: {speaker_info}")
        
        # Call Gemini API with multi-speaker config
        def _call_gemini_multispeaker():
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=full_conversation),
                    ],
                ),
            ]
            
            config = types.GenerateContentConfig(
                temperature=1,
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=speaker_voice_configs
                    ),
                ),
            )
            
            # Use streaming to handle potentially large responses
            all_audio_data = b""
            mime_type = None
            
            for chunk in self._client.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue
                    
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    all_audio_data += part.inline_data.data
                    if mime_type is None:
                        mime_type = part.inline_data.mime_type
            
            return all_audio_data, mime_type
        
        if briefing_id:
            from app.services.cancellation import cancellable_await
            audio_data, mime_type = await cancellable_await(
                asyncio.to_thread(_call_gemini_multispeaker), briefing_id,
            )
        else:
            audio_data, mime_type = await asyncio.to_thread(_call_gemini_multispeaker)
        
        if not audio_data:
            raise RuntimeError("Gemini multi-speaker TTS failed: No audio data received")
        
        print(f"[Gemini] Received {len(audio_data)} bytes of audio data, mime_type: {mime_type}")
        
        # Convert raw audio to WAV
        wav_data = convert_to_wav(audio_data, mime_type or "audio/L16;rate=24000")
        
        # Save as WAV first, then convert if needed
        is_mp3 = output_path.suffix.lower() == ".mp3"
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # Write WAV data
            with open(tmp_path, "wb") as f:
                f.write(wav_data)
            
            if is_mp3:
                await self._convert_to_mp3(tmp_path, output_path)
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy(tmp_path, output_path)
            
            # Get actual duration from the audio file
            duration = await self._get_audio_duration(output_path if not is_mp3 else tmp_path)
            
            # Estimate segment timings based on text length
            # Since we can't get exact timings from multi-speaker audio, we estimate proportionally
            total_chars = sum(len(seg["text"]) for seg in segment_data)
            segment_timings = []
            current_time = 0.0
            
            for seg in segment_data:
                # Estimate segment duration proportional to text length
                seg_proportion = len(seg["text"]) / total_chars if total_chars > 0 else 0
                seg_duration = duration * seg_proportion
                
                timing = SegmentTiming(
                    index=seg["index"],
                    speaker=seg["speaker"],
                    text=seg["text"],
                    start_seconds=current_time,
                    end_seconds=current_time + seg_duration,
                    duration_seconds=seg_duration,
                )
                segment_timings.append(timing)
                current_time += seg_duration
            
            print(f"[Gemini] Multi-speaker conversation complete: {duration:.2f}s total, {len(segment_timings)} segments")
            
            return TTSResult(
                audio_path=output_path,
                duration_seconds=duration,
                voice_id="conversation",
                format=output_path.suffix[1:],
                segment_timings=segment_timings,
            )
            
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

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
