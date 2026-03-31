"""
Database module for TimescaleDB operations.

Handles connection management, schema initialization, and event inserts/queries
for construction equipment events.
"""

import logging
import psycopg2
from psycopg2.extras import execute_values
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class Database:
    """
    Database interface for TimescaleDB equipment events.
    
    Manages connections and provides methods for inserting equipment events
    and querying the latest statistics.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "eaglevision",
        user: str = "postgres",
        password: str = "password"
    ):
        """
        Initialize database configuration.
        
        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None
    
    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"Connected to database: {self.database} at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def init_db(self) -> None:
        """Initialize database extensions and verify schema."""
        try:
            if self.conn is None:
                raise RuntimeError("Database not connected")
            
            with self.conn.cursor() as cur:
                # Create TimescaleDB extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
                self.conn.commit()
                logger.info("TimescaleDB extension verified")
        
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def insert_event(self, payload: Dict[str, Any]) -> None:
        """
        Insert equipment event into database.
        
        Args:
            payload: Event payload dictionary
        """
        try:
            if self.conn is None:
                raise RuntimeError("Database not connected")
            
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO equipment_events
                    (frame_id, equipment_id, equipment_class,
                     current_state, current_activity, motion_source,
                     util_percent, active_seconds, idle_seconds)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payload.get("frame_id"),
                        payload.get("equipment_id"),
                        payload.get("equipment_class"),
                        payload.get("utilization", {}).get("current_state"),
                        payload.get("utilization", {}).get("current_activity"),
                        payload.get("utilization", {}).get("motion_source"),
                        payload.get("time_analytics", {}).get("utilization_percent"),
                        payload.get("time_analytics", {}).get("total_active_seconds"),
                        payload.get("time_analytics", {}).get("total_idle_seconds")
                    )
                )
                self.conn.commit()
        
        except Exception as e:
            logger.error(f"Error inserting event: {e}")
            self.conn.rollback()
    
    def get_latest_stats(self) -> List[Dict[str, Any]]:
        """
        Get latest statistics for each equipment.
        
        Returns:
            List of dictionaries containing latest equipment stats
        """
        try:
            if self.conn is None:
                raise RuntimeError("Database not connected")
            
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (equipment_id)
                        equipment_id, equipment_class, current_state, current_activity,
                        motion_source, util_percent, active_seconds, idle_seconds, time
                    FROM equipment_events
                    ORDER BY equipment_id, time DESC
                    """
                )
                
                results = cur.fetchall()
                
                # Convert to list of dictionaries
                stats = []
                for row in results:
                    stats.append({
                        "equipment_id": row[0],
                        "equipment_class": row[1],
                        "current_state": row[2],
                        "current_activity": row[3],
                        "motion_source": row[4],
                        "util_percent": row[5],
                        "active_seconds": row[6],
                        "idle_seconds": row[7],
                        "time": row[8]
                    })
                
                return stats
        
        except Exception as e:
            logger.error(f"Error querying latest stats: {e}")
            return []
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")
