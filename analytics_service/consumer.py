"""
Kafka consumer module for equipment events.

Consumes equipment utilization events from Kafka and processes them for storage.
"""

import logging
import json
from typing import Callable, Optional
from confluent_kafka import Consumer, KafkaError

logger = logging.getLogger(__name__)


class EquipmentConsumer:
    """
    Consumes equipment events from Kafka.
    
    Reads messages from the equipment-events topic and calls a callback function
    for processing each event.
    """
    
    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str
    ):
        """
        Initialize the Kafka consumer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
            topic: Topic to consume from
            group_id: Consumer group ID
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.consumer = None
        self._init_consumer()
    
    def _init_consumer(self) -> None:
        """Initialize the Kafka consumer."""
        try:
            config = {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True
            }
            self.consumer = Consumer(config)
            self.consumer.subscribe([self.topic])
            logger.info(f"Kafka consumer initialized for topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise
    
    def consume_loop(self, callback: Callable, timeout_ms: float = 1000) -> None:
        """
        Main consume loop.
        
        Args:
            callback: Function to call with each message payload
            timeout_ms: Message poll timeout in milliseconds
        """
        try:
            while True:
                msg = self.consumer.poll(timeout_ms)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug("Reached end of partition")
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                    continue
                
                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    callback(payload)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue
        
        except KeyboardInterrupt:
            logger.info("Consumer interrupted")
        finally:
            self.close()
    
    def close(self) -> None:
        """Close the consumer."""
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.error(f"Error closing consumer: {e}")
