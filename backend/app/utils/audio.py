"""Audio utility functions."""

import asyncio
from pathlib import Path
from typing import Optional


async def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
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


async def concatenate_audio_files(
    input_files: list[Path],
    output_path: Path,
) -> bool:
    """Concatenate multiple audio files into one."""
    if not input_files:
        return False
    
    if len(input_files) == 1:
        import shutil
        shutil.copy(input_files[0], output_path)
        return True
    
    try:
        # Create concat list file
        list_file = output_path.parent / "_concat_list.txt"
        with open(list_file, "w") as f:
            for file in input_files:
                f.write(f"file '{file.absolute()}'\n")
        
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy", str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        
        list_file.unlink()
        return process.returncode == 0
        
    except Exception as e:
        print(f"Audio concatenation failed: {e}")
        return False


async def convert_to_mp3(
    input_path: Path,
    output_path: Path,
    bitrate: str = "192k",
) -> bool:
    """Convert audio file to MP3."""
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(input_path),
            "-acodec", "libmp3lame", "-b:a", bitrate,
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        return process.returncode == 0
    except Exception:
        return False

