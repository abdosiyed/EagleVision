"""
Kafka producer module for publishing equipment events.

Sends equipment utilization events to Kafka topic using confluent-kafka library
with JSON serialization and error handling.
"""

import logging
import json
import os
from typing import Dict, Any
from confluent_kafka import Producer

logger = logging.getLogger(__name__)


class KafkaProducer:
    """
    Produces equipment events to Kafka topic.
    
    Handles serialization and publishing of equipment utilization data to Kafka
    with fault tolerance and proper cleanup on shutdown.
    """
    
    def __init__(self, bootstrap_servers: str, topic: str):
        """
        Initialize the Kafka producer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers (e.g., "kafka:9092")
            topic: Topic name for publishing events
        """
        self.topic = topic
        self.producer = None
        self._init_producer(bootstrap_servers)
    
    def _init_producer(self, bootstrap_servers: str) -> None:
        """
        Initialize the Kafka producer client.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
        """
        try:
            config = {
                "bootstrap.servers": bootstrap_servers,
            }
            self.producer = Producer(config)
            logger.info(f"Kafka producer initialized for topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise
    
    def send(self, payload: Dict[str, Any]) -> None:
        """
        Send an equipment event to Kafka.
        
        Args:
            payload: Event payload dictionary
        """
        try:
            equipment_id = payload.get("equipment_id", "UNKNOWN")
            key = equipment_id.encode("utf-8")
            value = json.dumps(payload).encode("utf-8")
            
            self.producer.produce(
                self.topic,
                key=key,
                value=value
            )
            self.producer.poll(0)
        
        except Exception as e:
            logger.error(f"Error sending Kafka message: {e}")
    
    def flush(self, timeout_ms: int = 10000) -> None:
        """
        Flush pending messages and close producer.
        
        Args:
            timeout_ms: Timeout for flushing in milliseconds
        """
        try:
            if self.producer:
                self.producer.flush(timeout_ms // 1000)
                logger.info("Kafka producer flushed and closed")
        except Exception as e:
            logger.error(f"Error flushing Kafka producer: {e}")
