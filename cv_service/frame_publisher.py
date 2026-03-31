"""
Redis frame publisher module for real-time frame streaming.

Publishes annotated frames to Redis pub/sub channel for dashboard consumption.
"""

import logging
import cv2
from typing import Optional

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)


class FramePublisher:
    """
    Publishes video frames to Redis pub/sub channel.
    
    Encodes frames as JPEG and publishes to Redis for real-time consumption
    by dashboard and other subscribers.
    """
    
    def __init__(self, host: str = "localhost", port: int = 6379, channel: str = "frames"):
        """
        Initialize the frame publisher.
        
        Args:
            host: Redis host address
            port: Redis port
            channel: Redis channel name for frame publishing
        """
        self.host = host
        self.port = port
        self.channel = channel
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            if redis is None:
                logger.warning("redis module not available, frame publishing disabled")
                return
            
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=False
            )
            self.redis_client.ping()
            logger.info(f"Redis connected: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def publish(self, frame) -> None:
        """
        Publish a frame to Redis.
        
        Args:
            frame: Image frame (BGR format, numpy array)
        """
        if self.redis_client is None:
            return
        
        try:
            # Encode frame as JPEG
            success, buffer = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 70]
            )
            
            if success:
                self.redis_client.publish(self.channel, buffer.tobytes())
        
        except Exception as e:
            logger.error(f"Error publishing frame to Redis: {e}")
    
    def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
