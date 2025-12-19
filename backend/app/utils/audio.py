"""Audio utility functions."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional


async def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
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


async def concatenate_audio_files(
    input_files: list[Path],
    output_path: Path,
    reencode: bool = False,
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
) -> bool:
    """Concatenate multiple audio files into one.
    
    Args:
        input_files: List of input audio file paths
        output_path: Output audio file path
        reencode: If True, re-encode audio (more reliable, slower). If False, use stream copy (faster, requires identical formats)
        sample_rate: Target sample rate (only used if reencode=True)
        channels: Target number of channels (only used if reencode=True)
    
    Returns:
        True if successful, False otherwise
    """
    if not input_files:
        return False
    
    if len(input_files) == 1:
        import shutil
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(input_files[0], output_path)
        return True
    
    list_file = None
    try:
        # Verify all input files exist
        missing_files = [f for f in input_files if not f.exists()]
        if missing_files:
            print(f"[Audio] Missing input files: {missing_files}")
            return False
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create concat list file
        list_file = output_path.parent / "_concat_list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for file in input_files:
                # Use forward slashes for ffmpeg compatibility on Windows
                file_path = str(file.resolve()).replace('\\', '/')
                # Escape single quotes
                file_path_escaped = file_path.replace("'", "'\\''")
                f.write(f"file '{file_path_escaped}'\n")
        
        # Build ffmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
        ]
        
        if reencode:
            # Re-encode to ensure format consistency
            if sample_rate:
                cmd.extend(["-ar", str(sample_rate)])
            if channels:
                cmd.extend(["-ac", str(channels)])
            cmd.extend(["-acodec", "pcm_s16le"])
        else:
            # Stream copy (faster but requires identical formats)
            cmd.extend(["-c", "copy"])
        
        cmd.append(str(output_path))
        
        # Use subprocess.run wrapped in asyncio.to_thread for Windows compatibility
        def run_ffmpeg():
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        
        result = await asyncio.to_thread(run_ffmpeg)
        
        if result.returncode != 0:
            print(f"[Audio] ffmpeg concatenation failed: {result.stderr}")
            return False
        
        if not output_path.exists():
            print(f"[Audio] Output file was not created: {output_path}")
            return False
        
        return True
        
    except Exception as e:
        print(f"[Audio] Concatenation failed: {e}")
        return False
    finally:
        # Clean up list file
        if list_file and list_file.exists():
            try:
                list_file.unlink()
            except Exception:
                pass


async def convert_to_mp3(
    input_path: Path,
    output_path: Path,
    bitrate: str = "192k",
) -> bool:
    """Convert audio file to MP3."""
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-acodec", "libmp3lame", "-b:a", bitrate,
            str(output_path),
        ]
        
        # Use subprocess.run wrapped in asyncio.to_thread for Windows compatibility
        def run_ffmpeg():
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        
        result = await asyncio.to_thread(run_ffmpeg)
        return result.returncode == 0
    except Exception:
        return False

