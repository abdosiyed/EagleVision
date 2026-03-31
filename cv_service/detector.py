"""
Computer vision detector module for equipment tracking using YOLOv8 and ByteTrack.

This module provides real-time object detection and tracking of construction equipment
using the YOLOv8 model with ByteTrack for persistent tracking across frames.
"""

import logging
from typing import List, Tuple, Optional
from ultralytics import YOLO
import os

logger = logging.getLogger(__name__)

# COCO class mapping
COCO_CLASSES = {
    5: "bus",
    7: "truck",
}

# Equipment ID prefixes
EQUIPMENT_ID_PREFIX_EXCAVATOR = "EX"
EQUIPMENT_ID_PREFIX_TRUCK = "DT"


class EquipmentDetector:
    """
    Detects and tracks construction equipment in video frames.
    
    Uses YOLOv8 model with ByteTrack for persistent object tracking across frames.
    Filters detections to construction equipment classes (trucks as proxy for dump trucks,
    and class 7 mapped to excavator).
    """
    
    def __init__(self, model_name: str = "yolov8n.pt", confidence_threshold: float = 0.45):
        """
        Initialize the detector with a YOLOv8 model.
        
        Args:
            model_name: Name of YOLOv8 model to load (e.g., 'yolov8n.pt')
            confidence_threshold: Confidence threshold for detections
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the YOLOv8 model from ultralytics."""
        try:
            logger.info(f"Loading YOLOv8 model: {self.model_name}")
            self.model = YOLO(self.model_name)
            logger.info("YOLOv8 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {e}")
            raise
    
    def detect(self, frame) -> List[dict]:
        """
        Detect and track equipment in a frame.
        
        Args:
            frame: Input image frame (numpy array, BGR format)
        
        Returns:
            List of detections, each containing:
                - bbox: (x1, y1, x2, y2)
                - track_id: Integer track ID
                - class_name: Equipment class name
                - confidence: Detection confidence score
                - equipment_id: Unique equipment identifier
        """
        detections = []
        
        try:
            # Run YOLOv8 tracking with ByteTrack
            results = self.model.track(
                frame,
                conf=self.confidence_threshold,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False
            )
            
            if results and len(results) > 0:
                result = results[0]
                
                # Process detections
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls.item())
                        track_id = int(box.id.item()) if box.id is not None else -1
                        confidence = float(box.conf.item())
                        bbox = box.xyxy[0].cpu().numpy()
                        
                        # Filter to equipment classes: truck (7) or bus (5)
                        if class_id not in [5, 7]:
                            continue
                        
                        # Map class_id to equipment type
                        if class_id == 7 or class_id == 5:
                            class_name = "excavator" if class_id == 7 else "dump_truck"
                            prefix = EQUIPMENT_ID_PREFIX_EXCAVATOR if class_id == 7 else EQUIPMENT_ID_PREFIX_TRUCK
                        else:
                            continue
                        
                        # Generate equipment ID
                        equipment_id = f"{prefix}-{track_id:03d}"
                        
                        detection = {
                            "bbox": tuple(bbox),
                            "track_id": track_id,
                            "class_name": class_name,
                            "confidence": confidence,
                            "equipment_id": equipment_id
                        }
                        detections.append(detection)
        
        except Exception as e:
            logger.error(f"Error during detection: {e}")
            return []
        
        return detections
