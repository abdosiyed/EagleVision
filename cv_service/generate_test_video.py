"""
Generate synthetic test video for EagleVision pipeline.

Creates a simple 30-second synthetic video with moving rectangles simulating
construction equipment motion for testing without real video footage.

Usage:
    python generate_test_video.py [output_path]
    
Default output: cv_service/data/input.mp4
"""

import cv2
import numpy as np
import argparse
from pathlib import Path


def generate_test_video(output_path: str = "cv_service/data/input.mp4", duration_s: int = 30, fps: int = 15):
    """
    Generate a synthetic test video with simulated equipment motion.
    
    Args:
        output_path: Path to save the video file
        duration_s: Video duration in seconds
        fps: Frames per second
    """
    # Create output directory if needed
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Video parameters
    width, height = 640, 480
    total_frames = duration_s * fps
    
    # Define codec and create VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    print(f"Generating {duration_s}s test video at {fps}fps...")
    print(f"Output: {output_path}")
    
    # Equipment positions and parameters
    equipment = [
        {
            "name": "Excavator",
            "x": 100,
            "y": 200,
            "width": 120,
            "height": 100,
            "color": (50, 150, 200),  # BGR
            "motion": "digging"
        },
        {
            "name": "Dump Truck",
            "x": 400,
            "y": 250,
            "width": 150,
            "height": 80,
            "color": (0, 100, 200),  # BGR
            "motion": "stationary"
        }
    ]
    
    # Generate frames
    for frame_idx in range(total_frames):
        # Create black frame (simulates site background)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add some texture/noise for realism
        noise = np.random.randint(0, 5, (height, width, 3), dtype=np.uint8)
        frame = cv2.add(frame, noise)
        
        # Add grid pattern for visual reference
        for x in range(0, width, 80):
            cv2.line(frame, (x, 0), (x, height), (30, 30, 30), 1)
        for y in range(0, height, 60):
            cv2.line(frame, (0, y), (width, y), (30, 30, 30), 1)
        
        # Draw equipment
        for equip in equipment:
            x = equip["x"]
            y = equip["y"]
            w = equip["width"]
            h = equip["height"]
            color = equip["color"]
            
            # Simulate motion based on frame
            if equip["motion"] == "digging":
                # Oscillate up and down (simulates arm digging)
                amplitude = 30
                y_offset = int(amplitude * np.sin(2 * np.pi * frame_idx / (fps * 3)))
                y += y_offset
            elif equip["motion"] == "moving":
                # Move left to right
                x_offset = int((frame_idx / total_frames) * (width - w - 100)) + 100
                x = x_offset
            
            # Draw equipment bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
            # Draw equipment label
            cv2.putText(
                frame,
                equip["name"],
                (x + 5, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )
            
            # Draw activity indicator
            if equip["motion"] == "digging":
                activity = "ACTIVE" if abs(np.sin(2 * np.pi * frame_idx / (fps * 3))) > 0.3 else "IDLE"
                cv2.putText(
                    frame,
                    activity,
                    (x + 5, y + h - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 255, 0) if activity == "ACTIVE" else (0, 0, 255),
                    1
                )
        
        # Add frame counter and timestamp
        timestamp = frame_idx / fps
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        millis = int((timestamp % 1) * 100)
        
        cv2.putText(
            frame,
            f"Frame: {frame_idx} | Time: {minutes:02d}:{seconds:02d}.{millis:02d}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1
        )
        
        # Write frame
        out.write(frame)
        
        if (frame_idx + 1) % (fps * 5) == 0:
            progress = ((frame_idx + 1) / total_frames) * 100
            print(f"  {progress:.0f}% complete ({frame_idx + 1}/{total_frames} frames)")
    
    # Release the video writer
    out.release()
    
    print(f"✓ Test video generated successfully!")
    print(f"  Location: {output_path}")
    print(f"  Size: {width}x{height}")
    print(f"  Duration: {duration_s}s at {fps}fps")
    print(f"  Total frames: {total_frames}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic test video for EagleVision"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="cv_service/data/input.mp4",
        help="Output file path (default: cv_service/data/input.mp4)"
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=30,
        help="Video duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--fps",
        "-f",
        type=int,
        default=15,
        help="Frames per second (default: 15)"
    )
    
    args = parser.parse_args()
    
    generate_test_video(args.output, args.duration, args.fps)
