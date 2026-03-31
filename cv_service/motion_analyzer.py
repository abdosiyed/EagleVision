"""
Motion analysis module using optical flow for construction equipment state detection.

Analyzes motion within equipment bounding boxes using Farneback optical flow to
determine equipment state (ACTIVE/INACTIVE) and motion source (arm, tracks, full body).
"""

import logging
import cv2
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


class MotionAnalyzer:
    """
    Analyzes equipment motion using optical flow to determine activity state.
    
    Computes dense optical flow within equipment bounding boxes and divides
    the region into upper (arm) and lower (tracks) zones to classify motion patterns.
    """
    
    def __init__(self, motion_threshold: float = 2.5):
        """
        Initialize the motion analyzer.
        
        Args:
            motion_threshold: Magnitude threshold for motion detection
        """
        self.motion_threshold = motion_threshold
        self.prev_frame = None
    
    def analyze(
        self,
        frame,
        bbox: Tuple[float, float, float, float],
        prev_frame
    ) -> Tuple[str, str, float, float]:
        """
        Analyze motion within a bounding box.
        
        Args:
            frame: Current frame (BGR)
            bbox: Bounding box (x1, y1, x2, y2)
            prev_frame: Previous grayscale frame
        
        Returns:
            Tuple of (state, motion_source, upper_mag, lower_mag)
                - state: "ACTIVE" or "INACTIVE"
                - motion_source: "full_body", "arm_only", "tracks_only", or "none"
                - upper_mag: Mean motion magnitude in upper region
                - lower_mag: Mean motion magnitude in lower region
        """
        try:
            # Convert current frame to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Extract box coordinates
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            
            # Clip to frame bounds
            h, w = gray.shape
            x1 = max(0, min(x1, w - 1))
            x2 = max(0, min(x2, w - 1))
            y1 = max(0, min(y1, h - 1))
            y2 = max(0, min(y2, h - 1))
            
            if x1 >= x2 or y1 >= y2:
                return "INACTIVE", "none", 0.0, 0.0
            
            # Crop regions
            curr_crop = gray[y1:y2, x1:x2]
            
            if prev_frame is None:
                return "INACTIVE", "none", 0.0, 0.0
            
            prev_crop = prev_frame[y1:y2, x1:x2]
            
            # Ensure crops are the same size
            if curr_crop.shape != prev_crop.shape:
                min_h = min(curr_crop.shape[0], prev_crop.shape[0])
                min_w = min(curr_crop.shape[1], prev_crop.shape[1])
                curr_crop = curr_crop[:min_h, :min_w]
                prev_crop = prev_crop[:min_h, :min_w]
            
            if curr_crop.shape[0] < 3 or curr_crop.shape[1] < 3:
                return "INACTIVE", "none", 0.0, 0.0
            
            # Compute optical flow using Farneback method
            flow = cv2.calcOpticalFlowFarneback(
                prev_crop, curr_crop, None,
                pyr_scale=0.5,
                levels=3,
                winsize=15,
                iterations=3,
                poly_n=5,
                poly_sigma=1.2,
                flags=0
            )
            
            # Compute magnitude
            mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            
            # Split vertically
            h_split = mag.shape[0] // 2
            upper_mag = float(np.mean(mag[:h_split, :]))
            lower_mag = float(np.mean(mag[h_split:, :]))
            
            # Determine state and motion source
            if upper_mag > self.motion_threshold and lower_mag > self.motion_threshold:
                state = "ACTIVE"
                motion_source = "full_body"
            elif upper_mag > self.motion_threshold:
                state = "ACTIVE"
                motion_source = "arm_only"
            elif lower_mag > self.motion_threshold:
                state = "ACTIVE"
                motion_source = "tracks_only"
            else:
                state = "INACTIVE"
                motion_source = "none"
            
            return state, motion_source, upper_mag, lower_mag
        
        except Exception as e:
            logger.error(f"Error in motion analysis: {e}")
            return "INACTIVE", "none", 0.0, 0.0
    
    def update_prev_frame(self, frame) -> None:
        """
        Update the previous frame for next iteration.
        
        Args:
            frame: Current frame (BGR)
        """
        self.prev_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
