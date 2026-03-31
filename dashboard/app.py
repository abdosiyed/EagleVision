"""
Dashboard - Streamlit Web Application

Real-time visualization of construction equipment utilization with live video feed
and equipment statistics.
"""

import os
import logging
import time
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
from PIL import Image
import io

try:
    import redis
except ImportError:
    redis = None

from db import Database

# Load environment variables
load_dotenv()

# Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "eaglevision")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_FRAME_CHANNEL = os.getenv("REDIS_FRAME_CHANNEL", "frames")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(page_title="EagleVision", layout="wide")
st.title("🦅 EagleVision - Equipment Utilization Monitor")

# Initialize session state
if "db" not in st.session_state:
    try:
        st.session_state.db = Database(
            POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
        )
        st.session_state.db.connect()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        st.session_state.db = None

if "redis_client" not in st.session_state:
    if redis:
        try:
            st.session_state.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=False
            )
            st.session_state.redis_client.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            st.session_state.redis_client = None
    else:
        st.session_state.redis_client = None

if "pubsub" not in st.session_state:
    if st.session_state.redis_client:
        try:
            st.session_state.pubsub = st.session_state.redis_client.pubsub()
            st.session_state.pubsub.subscribe(REDIS_FRAME_CHANNEL)
        except Exception as e:
            logger.error(f"Failed to subscribe to Redis channel: {e}")
            st.session_state.pubsub = None
    else:
        st.session_state.pubsub = None


def get_latest_frame():
    """Get the latest frame from Redis."""
    if st.session_state.pubsub is None:
        return None
    
    try:
        message = st.session_state.pubsub.get_message(timeout=1.0)
        if message and message["type"] == "message":
            return message["data"]
    except Exception as e:
        logger.error(f"Error getting frame: {e}")
    
    return None


def get_equipment_stats():
    """Get latest equipment statistics from database."""
    if st.session_state.db is None:
        return []
    
    try:
        return st.session_state.db.get_latest_stats()
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return []


# Create columns for layout
col_video, col_stats = st.columns([2, 1])

# Video column
with col_video:
    st.subheader("📹 Live Video Feed")
    
    video_placeholder = st.empty()
    status_placeholder = st.empty()
    
    if st.session_state.pubsub is None:
        status_placeholder.warning("⚠️ Video feed unavailable (Redis not connected)")
    else:
        status_placeholder.info("🟢 Video feed active - waiting for frames...")

# Stats column
with col_stats:
    st.subheader("📊 Equipment Status")
    stats_placeholder = st.empty()

# Auto-refresh setup
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=1000, key="refresh")
except ImportError:
    logger.warning("streamlit-autorefresh not installed, manual refresh only")

# Main display loop
while True:
    # Update video frame
    frame_data = get_latest_frame()
    if frame_data:
        try:
            image = Image.open(io.BytesIO(frame_data))
            video_placeholder.image(image, use_column_width=True, channels="BGR")
        except Exception as e:
            logger.error(f"Error displaying frame: {e}")
    
    # Update equipment statistics
    stats = get_equipment_stats()
    
    with stats_placeholder.container():
        if not stats:
            st.info("⏳ Waiting for first detections...")
        else:
            for stat in stats:
                st.markdown(f"### {stat['equipment_id']} — {stat['equipment_class']}")
                
                # State badge
                if stat["current_state"] == "ACTIVE":
                    st.markdown("🟢 **ACTIVE**")
                else:
                    st.markdown("🔴 **INACTIVE**")
                
                # Metrics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Utilization", f"{stat['util_percent']:.1f}%")
                with col2:
                    st.metric("Active Time", f"{stat['active_seconds']:.0f}s")
                
                st.metric("Idle Time", f"{stat['idle_seconds']:.0f}s")
                
                # Activity info
                st.caption(
                    f"Activity: **{stat['current_activity']}** | Motion: **{stat['motion_source']}**"
                )
                st.divider()
    
    time.sleep(1)
