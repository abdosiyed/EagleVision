"""
Database module for Dashboard (shared with analytics service).

Simple interface for querying equipment statistics from TimescaleDB.
"""

import logging
import psycopg2
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    """Database interface for querying equipment statistics."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "eaglevision",
        user: str = "postgres",
        password: str = "password"
    ):
        """Initialize database configuration."""
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
            logger.info(f"Connected to database: {self.database}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def get_latest_stats(self) -> List[Dict[str, Any]]:
        """Get latest statistics for each equipment."""
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
                
                stats = []
                for row in results:
                    stats.append({
                        "equipment_id": row[0],
                        "equipment_class": row[1],
                        "current_state": row[2],
                        "current_activity": row[3],
                        "motion_source": row[4],
                        "util_percent": float(row[5]) if row[5] else 0.0,
                        "active_seconds": float(row[6]) if row[6] else 0.0,
                        "idle_seconds": float(row[7]) if row[7] else 0.0,
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
