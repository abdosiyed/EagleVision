"""
Computer Vision Service - Main Entry Point

Real-time construction equipment detection, tracking, and activity classification.
Processes video frames, detects equipment, analyzes motion, and publishes events to Kafka.
"""

import os
import sys
import cv2
import logging
import signal
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from confluent_kafka.admin import AdminClient, NewTopic

from detector import EquipmentDetector
from motion_analyzer import MotionAnalyzer
from activity_classifier import ActivityClassifier
from kafka_producer import KafkaProducer
from frame_publisher import FramePublisher

# Load environment variables
load_dotenv()

# Logging setup
LOG_LEVEL = logging.DEBUG if os.getenv("DEBUG", "0") == "1" else logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "equipment-events")
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "data/input.mp4")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.45))
MOTION_THRESHOLD = float(os.getenv("MOTION_THRESHOLD", 2.5))
FRAME_SKIP = int(os.getenv("FRAME_SKIP", 2))
TARGET_FPS = int(os.getenv("TARGET_FPS", 15))
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_FRAME_CHANNEL = os.getenv("REDIS_FRAME_CHANNEL", "frames")

# Global state
shutdown_requested = False
frame_count = 0


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def ensure_kafka_topic() -> None:
    """Ensure Kafka topic exists, create if necessary."""
    try:
        admin_client = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
        
        # Check existing topics
        metadata = admin_client.list_topics(timeout=10)
        topics = metadata.topics.keys()
        
        if KAFKA_TOPIC not in topics:
            logger.info(f"Creating Kafka topic: {KAFKA_TOPIC}")
            topic = NewTopic(KAFKA_TOPIC, num_partitions=3, replication_factor=1)
            admin_client.create_topics([topic], validate_only=False)
            logger.info(f"Topic {KAFKA_TOPIC} created successfully")
        else:
            logger.info(f"Topic {KAFKA_TOPIC} already exists")
    
    except Exception as e:
        logger.error(f"Error ensuring Kafka topic: {e}")
        raise


def wait_for_kafka(max_attempts: int = 30, retry_delay: int = 2) -> None:
    """Wait for Kafka to be available."""
    logger.info("Waiting for Kafka to be available...")
    
    for attempt in range(max_attempts):
        try:
            admin_client = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
            admin_client.list_topics(timeout=5)
            logger.info("Kafka is ready")
            return
        except Exception as e:
            logger.warning(f"Kafka not ready (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(retry_delay)
    
    raise RuntimeError("Kafka failed to become available")


def draw_detections(
    frame,
    detections: List[dict],
    equipment_times: Dict[str, dict]
) -> None:
    """
    Draw bounding boxes and labels on frame.
    
    Args:
        frame: Image frame to draw on
        detections: List of detection dictionaries
        equipment_times: Time tracking dictionary
    """
    for det in detections:
        bbox = det["bbox"]
        equipment_id = det["equipment_id"]
        state = det.get("current_state", "INACTIVE")
        activity = det.get("current_activity", "WAITING")
        util_pct = det.get("utilization_percent", 0.0)
        
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        
        # Color based on state
        if state == "ACTIVE":
            color = (0, 255, 0)  # Green
        else:
            color = (0, 0, 255)  # Red
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Draw label
        label = f"{equipment_id} | {activity} | {util_pct:.0f}%"
        cv2.putText(
            frame,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2
        )


def build_kafka_payload(
    frame_id: int,
    detection: dict,
    motion_source: str,
    flow,
    equipment_times: Dict[str, dict],
    fps: float
) -> dict:
    """
    Build Kafka event payload.
    
    Args:
        frame_id: Frame number
        detection: Detection dictionary
        motion_source: Motion source string
        flow: Optical flow array
        equipment_times: Time tracking dictionary
        fps: Frames per second
    
    Returns:
        Payload dictionary matching Kafka schema
    """
    equipment_id = detection["equipment_id"]
    equipment_class = detection["class_name"]
    
    # Get time tracking
    if equipment_id not in equipment_times:
        equipment_times[equipment_id] = {
            "tracked_s": 0.0,
            "active_s": 0.0,
            "idle_s": 0.0,
            "last_ts": time.time(),
            "state": "INACTIVE"
        }
    
    times = equipment_times[equipment_id]
    current_time = time.time()
    delta_t = (current_time - times["last_ts"]) / fps if fps > 0 else 0
    times["last_ts"] = current_time
    
    current_state = "ACTIVE" if motion_source != "none" else "INACTIVE"
    times["tracked_s"] += delta_t
    
    if current_state == "ACTIVE":
        times["active_s"] += delta_t
    else:
        times["idle_s"] += delta_t
    
    times["state"] = current_state
    
    # Calculate utilization
    util_pct = 0.0
    if times["tracked_s"] > 0:
        util_pct = round((times["active_s"] / times["tracked_s"]) * 100, 1)
    else:
        util_pct = 0.0
    
    # Get activity from detector (this will be filled by main loop)
    current_activity = detection.get("current_activity", "WAITING")
    
    # Calculate video timestamp
    video_seconds = frame_id / fps if fps > 0 else 0
    timestamp_delta = timedelta(seconds=video_seconds)
    timestamp_str = str(timestamp_delta)[:-3]  # Remove last 3 digits for milliseconds
    
    payload = {
        "frame_id": frame_id,
        "equipment_id": equipment_id,
        "equipment_class": equipment_class,
        "timestamp": timestamp_str,
        "utilization": {
            "current_state": current_state,
            "current_activity": current_activity,
            "motion_source": motion_source
        },
        "time_analytics": {
            "total_tracked_seconds": round(times["tracked_s"], 1),
            "total_active_seconds": round(times["active_s"], 1),
            "total_idle_seconds": round(times["idle_s"], 1),
            "utilization_percent": util_pct
        }
    }
    
    return payload


def main():
    """Main processing loop."""
    global shutdown_requested, frame_count
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting EagleVision CV Service")
    
    try:
        # Wait for dependencies
        wait_for_kafka()
        
        # Ensure Kafka topic exists
        ensure_kafka_topic()
        
        # Check video source
        video_path = Path(VIDEO_SOURCE)
        if not video_path.exists():
            logger.error(f"Video source not found: {VIDEO_SOURCE}")
            sys.exit(1)
        
        # Initialize components
        logger.info("Initializing CV components...")
        detector = EquipmentDetector(YOLO_MODEL, CONFIDENCE_THRESHOLD)
        motion_analyzer = MotionAnalyzer(MOTION_THRESHOLD)
        activity_classifier = ActivityClassifier()
        kafka_producer = KafkaProducer(KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC)
        frame_publisher = FramePublisher(REDIS_HOST, REDIS_PORT, REDIS_FRAME_CHANNEL)
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Failed to open video: {VIDEO_SOURCE}")
            sys.exit(1)
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = TARGET_FPS
        logger.info(f"Video FPS: {fps}")
        
        # Time tracking
        equipment_times = {}
        frame_count = 0
        skip_counter = 0
        
        logger.info("Starting frame processing loop...")
        
        # Main loop
        while not shutdown_requested:
            ret, frame = cap.read()
            
            if not ret:
                logger.info("End of video reached, restarting...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                motion_analyzer.prev_frame = None
                continue
            
            skip_counter += 1
            if skip_counter < FRAME_SKIP:
                continue
            skip_counter = 0
            
            frame_count += 1
            
            # Detect equipment
            detections = detector.detect(frame)
            
            # Process each detection
            for detection in detections:
                bbox = detection["bbox"]
                track_id = detection["track_id"]
                equipment_id = detection["equipment_id"]
                
                # Analyze motion
                state, motion_source, upper_mag, lower_mag = motion_analyzer.analyze(
                    frame, bbox, motion_analyzer.prev_frame
                )
                
                # Get optical flow for activity classification
                x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                h, w = frame.shape[:2]
                x1 = max(0, min(x1, w - 1))
                x2 = max(0, min(x2, w - 1))
                y1 = max(0, min(y1, h - 1))
                y2 = max(0, min(y2, h - 1))
                
                if motion_analyzer.prev_frame is not None and x1 < x2 and y1 < y2:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    curr_crop = gray[y1:y2, x1:x2]
                    prev_crop = motion_analyzer.prev_frame[y1:y2, x1:x2]
                    
                    if curr_crop.shape == prev_crop.shape and curr_crop.shape[0] >= 3 and curr_crop.shape[1] >= 3:
                        flow = cv2.calcOpticalFlowFarneback(
                            prev_crop, curr_crop, None,
                            pyr_scale=0.5, levels=3, winsize=15,
                            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                        )
                    else:
                        flow = None
                else:
                    flow = None
                
                # Classify activity
                if flow is not None:
                    current_activity = activity_classifier.classify(
                        track_id, motion_source, flow, bbox
                    )
                else:
                    current_activity = "WAITING"
                
                detection["current_state"] = state
                detection["current_activity"] = current_activity
                
                # Build and send payload
                payload = build_kafka_payload(
                    frame_count, detection, motion_source, flow, equipment_times, fps
                )
                detection["utilization_percent"] = payload["time_analytics"]["utilization_percent"]
                
                kafka_producer.send(payload)
            
            # Update prev frame
            motion_analyzer.update_prev_frame(frame)
            
            # Draw annotated frame
            draw_detections(frame, detections, equipment_times)
            
            # Publish frame
            frame_publisher.publish(frame)
            
            if frame_count % 30 == 0:
                logger.info(f"Processed {frame_count} frames, detected {len(detections)} equipment")
    
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        shutdown_requested = True
    finally:
        logger.info("Performing cleanup...")
        try:
            kafka_producer.flush()
            frame_publisher.close()
            if 'cap' in locals():
                cap.release()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        logger.info("CV Service shutdown complete")


if __name__ == "__main__":
    main()
