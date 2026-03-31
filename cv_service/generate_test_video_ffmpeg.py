"""
Generate simple test MP4 video using ffmpeg (cross-platform).

This script creates a simple black video with a moving white rectangle
without requiring OpenCV on the host machine.

Usage:
    python generate_test_video_ffmpeg.py
"""

import subprocess
import sys
import os
from pathlib import Path


def generate_test_video_ffmpeg(
    output_path: str = "cv_service/data/input.mp4",
    duration: int = 30,
    fps: int = 15,
    width: int = 640,
    height: int = 480
) -> bool:
    """
    Generate test video using ffmpeg.
    
    Args:
        output_path: Output video file path
        duration: Duration in seconds
        fps: Frames per second
        width: Video width
        height: Video height
    
    Returns:
        True if successful, False otherwise
    """
    # Create output directory
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: ffmpeg not found. Install ffmpeg to generate test video.")
        print("\nInstallation:")
        print("  Windows: choco install ffmpeg  (or download from https://ffmpeg.org/download.html)")
        print("  macOS:   brew install ffmpeg")
        print("  Ubuntu:  sudo apt-get install ffmpeg")
        return False
    
    print(f"Generating {duration}s test video at {fps}fps using ffmpeg...")
    print(f"Output: {output_path}")
    
    # Create a simple black video with color filter
    # Pattern: black background with moving white rectangles (simulating equipment)
    filter_complex = f"""
    color=c=black:s={width}x{height}:d={duration} [bg];
    [bg] drawbox=x='if(lt(t\\,10)\\,100+sin(t)*50\\,200))':y=200:w=120:h=100:c=white:t=2 [v1];
    [v1] fps={fps} [out]
    """
    
    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", f"color=c=black:s={width}x{height}:d={duration}",
        "-filter_complex",
        f"drawbox=x='100+sin(t*3.14)*30':y=200:w=120:h=100:c=white:t=2[out1];\
[out1]drawbox=x=400:y='250+sin(t*1.5)*20':w=150:h=80:c=gray:t=2[out]",
        "-map", "[out]",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "fast",
        "-y",
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✓ Test video generated successfully!")
        print(f"  Location: {output_path}")
        print(f"  Size: {width}x{height}")
        print(f"  Duration: {duration}s at {fps}fps")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: ffmpeg failed: {e.stderr.decode() if e.stderr else e}")
        return False


if __name__ == "__main__":
    success = generate_test_video_ffmpeg()
    sys.exit(0 if success else 1)
