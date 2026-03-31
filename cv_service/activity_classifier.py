"""
Activity classification module for construction equipment state detection.

Uses motion flow patterns and debouncing to classify equipment activities
(DIGGING, SWINGING, DUMPING, WAITING) with temporal stability.
"""

import logging
import numpy as np
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Activity states
ACTIVITY_WAITING = "WAITING"
ACTIVITY_DIGGING = "DIGGING"
ACTIVITY_SWINGING = "SWINGING"
ACTIVITY_DUMPING = "DUMPING"

# Debounce configuration
DEBOUNCE_FRAMES = 3


class ActivityClassifier:
    """
    Classifies construction equipment activities based on motion patterns.
    
    Uses optical flow analysis to distinguish between different equipment activities
    (digging, swinging, dumping, waiting) with debouncing for temporal stability.
    """
    
    def __init__(self, debounce_frames: int = DEBOUNCE_FRAMES):
        """
        Initialize the activity classifier.
        
        Args:
            debounce_frames: Number of consecutive frames required to confirm state change
        """
        self.debounce_frames = debounce_frames
        # Track state per equipment_id: {track_id: {"state": str, "count": int, "activity": str}}
        self.state_tracker = defaultdict(lambda: {
            "pending_state": None,
            "frame_count": 0,
            "last_activity": ACTIVITY_WAITING
        })
    
    def classify(
        self,
        track_id: int,
        motion_source: str,
        flow: np.ndarray,
        bbox
    ) -> str:
        """
        Classify equipment activity based on motion patterns.
        
        Args:
            track_id: Unique track identifier
            motion_source: Motion source ("full_body", "arm_only", "tracks_only", "none")
            flow: Optical flow array (height, width, 2)
            bbox: Bounding box (x1, y1, x2, y2)
        
        Returns:
            Activity string: "DIGGING", "SWINGING", "DUMPING", or "WAITING"
        """
        try:
            # Get or initialize state tracker for this track
            state = self.state_tracker[track_id]
            
            # Determine candidate activity
            candidate = ACTIVITY_WAITING
            
            if motion_source == "none":
                candidate = ACTIVITY_WAITING
            else:
                # Compute flow statistics in upper zone
                if flow.shape[0] > 0 and flow.shape[1] > 0:
                    h = flow.shape[0]
                    upper_zone = flow[:h // 2, :]
                    
                    if upper_zone.size > 0:
                        vx_mean = float(np.mean(upper_zone[..., 0]))
                        vy_mean = float(np.mean(upper_zone[..., 1]))
                        abs_vx = abs(vx_mean)
                        abs_vy = abs(vy_mean)
                        
                        # Activity rules
                        if abs_vy > abs_vx * 1.5 and vy_mean > 0:
                            candidate = ACTIVITY_DIGGING
                        elif abs_vx > abs_vy * 1.2:
                            candidate = ACTIVITY_SWINGING
                        elif abs_vy > abs_vx * 1.5 and vy_mean < 0:
                            candidate = ACTIVITY_DUMPING
                        else:
                            candidate = ACTIVITY_DIGGING
                    else:
                        candidate = ACTIVITY_DIGGING
                else:
                    candidate = ACTIVITY_DIGGING
            
            # Debounce: only update if candidate persists
            if candidate == state["pending_state"]:
                state["frame_count"] += 1
                if state["frame_count"] >= self.debounce_frames:
                    state["last_activity"] = candidate
                    state["pending_state"] = None
                    state["frame_count"] = 0
            else:
                state["pending_state"] = candidate
                state["frame_count"] = 1
            
            return state["last_activity"]
        
        except Exception as e:
            logger.error(f"Error in activity classification: {e}")
            return ACTIVITY_WAITING
    
    def reset_track(self, track_id: int) -> None:
        """
        Reset tracking state for a lost track.
        
        Args:
            track_id: Track ID to reset
        """
        if track_id in self.state_tracker:
            del self.state_tracker[track_id]
