"""
Analytics Service - Main Entry Point

Consumes equipment events from Kafka and stores them in TimescaleDB.
"""

import os
import sys
import logging
import signal
import time
from dotenv import load_dotenv

from db import Database
from consumer import EquipmentConsumer

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
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "analytics-group")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "eaglevision")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

# Global state
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def wait_for_postgres(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    max_attempts: int = 30,
    retry_delay: int = 2
) -> None:
    """
    Wait for PostgreSQL to be available.
    
    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        user: PostgreSQL user
        password: PostgreSQL password
        database: PostgreSQL database
        max_attempts: Maximum attempts
        retry_delay: Delay between attempts in seconds
    """
    logger.info("Waiting for PostgreSQL to be available...")
    
    for attempt in range(max_attempts):
        try:
            db = Database(host, port, database, user, password)
            db.connect()
            db.close()
            logger.info("PostgreSQL is ready")
            return
        except Exception as e:
            logger.warning(f"PostgreSQL not ready (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(retry_delay)
    
    raise RuntimeError("PostgreSQL failed to become available")


def wait_for_kafka(
    bootstrap_servers: str,
    max_attempts: int = 30,
    retry_delay: int = 2
) -> None:
    """
    Wait for Kafka to be available.
    
    Args:
        bootstrap_servers: Kafka bootstrap servers
        max_attempts: Maximum attempts
        retry_delay: Delay between attempts in seconds
    """
    logger.info("Waiting for Kafka to be available...")
    
    for attempt in range(max_attempts):
        try:
            from confluent_kafka.admin import AdminClient
            admin_client = AdminClient({"bootstrap.servers": bootstrap_servers})
            admin_client.list_topics(timeout=5)
            logger.info("Kafka is ready")
            return
        except Exception as e:
            logger.warning(f"Kafka not ready (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(retry_delay)
    
    raise RuntimeError("Kafka failed to become available")


def main():
    """Main processing loop."""
    global shutdown_requested
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting EagleVision Analytics Service")
    
    try:
        # Wait for dependencies
        wait_for_postgres(POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
        wait_for_kafka(KAFKA_BOOTSTRAP_SERVERS)
        
        # Initialize database
        logger.info("Initializing database...")
        db = Database(POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
        db.connect()
        db.init_db()
        
        # Initialize Kafka consumer
        logger.info("Starting Kafka consumer...")
        consumer = EquipmentConsumer(KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, KAFKA_GROUP_ID)
        
        # Define callback for processing messages
        def on_message(payload):
            """Process incoming equipment event."""
            try:
                db.insert_event(payload)
                equipment_id = payload.get("equipment_id", "UNKNOWN")
                logger.debug(f"Stored event for {equipment_id}")
            except Exception as e:
                logger.error(f"Error storing event: {e}")
        
        # Start consuming
        logger.info("Analytics Service ready, consuming messages...")
        consumer.consume_loop(on_message)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Performing cleanup...")
        try:
            if 'db' in locals():
                db.close()
            if 'consumer' in locals():
                consumer.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        logger.info("Analytics Service shutdown complete")


if __name__ == "__main__":
    main()
