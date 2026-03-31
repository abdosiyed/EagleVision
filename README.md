# EagleVision: Construction Equipment Utilization Pipeline

Real-time microservices pipeline for tracking construction equipment utilization from video feeds using computer vision, Apache Kafka, and TimescaleDB.

## Table of Contents
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Setup Instructions](#setup-instructions)
- [Test Video](#test-video)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Custom YOLO Model](#custom-yolo-model)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      EagleVision System                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Input Video (mp4/avi)                                             │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────┐                                              │
│  │   cv_service     │  ◄─── YOLOv8 Detection + ByteTrack          │
│  │  ◄─────────────┤ ├──────────┐                                   │
│  │                │          │                                      │
│  │ • Detect Object│ │         ▼                                     │
│  │ • Track Motion │ │    ┌─────────────────┐                       │
│  │ • Classify Act │ │    │  Optical Flow   │                       │
│  │   └────────────┘ │    │  & Activity ML  │                       │
│  │                │ │    └─────────────────┘                       │
│  └────────┬───────┘                                                 │
│           │                     ┌──────────────┐                    │
│           ├────────────────────►│ Redis Channel│─ ► Dashboard      │
│           │  (frames via JPEG)  │ (frame video)│    (Streamlit)    │
│           │                     └──────────────┘                    │
│           ▼                                                          │
│      Kafka Broker                                                    │
│    (equipment-events)                                                │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                               │
│  │analytics_service│  ◄─── Consumer (confluent-kafka)             │
│  │ • Process Events│                                               │
│  │ • Store in DB   │                                               │
│  └────────┬────────┘                                               │
│           │                                                          │
│           ▼                                                          │
│    TimescaleDB                                                       │
│  (PostgreSQL)                                                        │
│  equipment_events                                                    │
│  hypertable                                                          │
│           ▲                                                          │
│           │                                                          │
│           └─────────────────────────────────────────┐              │
│                                                     │              │
│                            ┌─────────────────────┐  │              │
│                            │   Dashboard (web)   │  │              │
│                            │ • Display video feed│──┘              │
│                            │ • Show equipment    │                 │
│                            │   utilization stats │                 │
│                            └─────────────────────┘                 │
│                                (Streamlit)                         │
│                               Port 8501                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Video Input** → cv_service reads video frames
2. **Detection** → YOLOv8 + ByteTrack detects and tracks equipment
3. **Motion Analysis** → Optical flow analysis determines equipment state
4. **Activity Classification** → Temporal patterns identify equipment activity
5. **Kafka Publishing** → Equipment events published to Kafka topic
6. **Frame Streaming** → Annotated frames published to Redis pub/sub
7. **Analytics** → analytics_service consumes Kafka events
8. **Storage** → Events stored in TimescaleDB hypertable
9. **Dashboard** → Web UI displays live video and equipment statistics

## Prerequisites

- **Docker & Docker Compose** (v20.10+)
- **Git** (optional, for cloning)
- **Test video file** (see [Test Video](#test-video) section)
- Minimum **4GB RAM** (6GB+ recommended)
- **2+ CPU cores** recommended

## Quick Start

```bash
# 1. Clone or navigate to the project directory
cd eaglevision

# 2. Copy environment template
cp .env.example .env

# 3. Get a test video (see Test Video section below)
# Place it at: cv_service/data/input.mp4

# 4. Start all services
docker compose up --build

# 5. Open dashboard in browser
# Navigate to: http://localhost:8501
```

Expected startup time: **30-60 seconds** for all services to initialize.

## Setup Instructions

### 1. Clone or Create Directory

```bash
mkdir -p eaglevision && cd eaglevision
# If cloning from git:
# git clone <repo> eaglevision && cd eaglevision
```

### 2. Copy Environment Configuration

```bash
cp .env.example .env
```

The `.env` file contains:
- Kafka bootstrap servers
- PostgreSQL credentials
- Redis connection details
- CV model and processing parameters

**Default credentials are suitable for development.** For production, change:
- `POSTGRES_PASSWORD`
- Update the same value in `docker-compose.yml`

### 3. Obtain Test Video

Choose one of these options:

#### Option A: Use Roberts & Golparvar-Fard Benchmark Dataset (Recommended)

Download from: https://data.mendeley.com/datasets/fyw6ps2d2j/1

Extract any `.mp4` file from the dataset:
```bash
mkdir -p cv_service/data
cp /path/to/benchmark/video.mp4 cv_service/data/input.mp4
```

#### Option B: YouTube Video

Search for "excavator digging loading dump truck site camera" or similar construction site videos.

Install yt-dlp:
```bash
pip install yt-dlp
```

Download video:
```bash
mkdir -p cv_service/data
yt-dlp -o cv_service/data/input.mp4 "https://www.youtube.com/watch?v=VIDEO_ID"
```

#### Option C: Generate Synthetic Test Video

Run the test video generator:
```bash
python cv_service/generate_test_video.py
```

This creates a 30-second synthetic video with simulated equipment motion.

### 4. Build and Start Services

```bash
docker compose up --build
```

This command:
1. Builds Docker images for cv_service, analytics_service, dashboard
2. Starts all services (Zookeeper, Kafka, TimescaleDB, Redis)
3. Initializes databases and topics
4. Begins video processing

### 5. Monitor Logs

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f cv_service
docker compose logs -f analytics_service
docker compose logs -f dashboard
```

### 6. Access Dashboard

Open http://localhost:8501 in your browser.

**Expected dashboard features:**
- Left: Live video feed with equipment bounding boxes (green=active, red=idle)
- Right: Equipment cards showing:
  - Equipment ID (e.g., EX-001, DT-002)
  - Equipment class (excavator, dump_truck)
  - Current state (🟢 ACTIVE or 🔴 INACTIVE)
  - Utilization percentage
  - Active/idle time accumulation
  - Current activity (DIGGING, SWINGING, DUMPING, WAITING)
  - Motion source (full_body, arm_only, tracks_only, none)

### 7. Stop Services

```bash
docker compose down
```

To also remove databases:
```bash
docker compose down -v
```

## Test Video

The system requires a video file at `cv_service/data/input.mp4`.

**Recommended video characteristics:**
- Format: MP4, AVI, MOV
- Duration: 30s - 5m (longer = more processing time)
- Resolution: 640x480 - 1920x1080
- FPS: 15 - 30 fps
- Contains: Excavators, dump trucks, or other equipment with visible motion

**If no video is available:**

Generate a synthetic test video:
```bash
python cv_service/generate_test_video.py
```

This creates `input.mp4` with:
- Black background (simulating site)
- Moving rectangle (simulates machine)
- Oscillating Y position (simulates digging)
- 30 seconds duration, 15 fps

## Configuration

Edit `.env` to customize:

```env
# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC=equipment-events
KAFKA_GROUP_ID=analytics-group

# TimescaleDB
POSTGRES_HOST=timescaledb
POSTGRES_PORT=5432
POSTGRES_DB=eaglevision
POSTGRES_USER=ev_user
POSTGRES_PASSWORD=ev_pass

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_FRAME_CHANNEL=frames

# CV Service
VIDEO_SOURCE=data/input.mp4           # Path to input video
CONFIDENCE_THRESHOLD=0.45              # YOLOv8 confidence (0.0-1.0)
MOTION_THRESHOLD=2.5                   # Optical flow magnitude threshold
FRAME_SKIP=2                           # Process every Nth frame (1=all frames)
TARGET_FPS=15                          # Output FPS for processing

# Model
YOLO_MODEL=yolov8n.pt                 # YOLOv8 model variant

# Logging
DEBUG=0                                # Set to 1 for debug logs
```

### Parameter Tuning

**CONFIDENCE_THRESHOLD (0.0-1.0)**
- Lower = More detections (more false positives)
- Higher = Fewer, higher-confidence detections
- Recommended: 0.4-0.5

**MOTION_THRESHOLD (float)**
- Lower = More motion sensitivity (lower threshold for "ACTIVE")
- Higher = Requires more visible motion
- Recommended: 2.0-3.5

**FRAME_SKIP (integer)**
- 1 = Process every frame (slower, more accurate)
- 2+ = Skip N-1 frames (faster, may miss short movements)
- Recommended: 1-2 for real-time, 2-4 for analysis

## How It Works

### Zone-Based Optical Flow Analysis

The motion analyzer splits each equipment bounding box into two zones:

```
┌─────────────────────┐
│      UPPER ZONE     │
│   (arm/bucket)      │
├─────────────────────┤
│                     │
│      LOWER ZONE     │
│   (tracks/base)     │
└─────────────────────┘
```

**Optical Flow Computation:**

1. Extract previous and current grayscale frame patches within bounding box
2. Compute dense optical flow using Farneback algorithm:
   - Pyramid levels: 3
   - Window size: 15x15 pixels
   - Iterations: 3
3. Calculate flow magnitude: `√(vx² + vy²)`
4. Compute mean magnitude for each zone

**State Determination:**

| Upper Motion | Lower Motion | State    | Motion Source |
|--------------|--------------|----------|---------------|
| High         | High         | ACTIVE   | full_body     |
| High         | Low          | ACTIVE   | arm_only      |
| Low          | High         | ACTIVE   | tracks_only   |
| Low          | Low          | INACTIVE | none          |

### Activity Classification

The activity classifier uses flow vector analysis to distinguish equipment activities:

**Rule-Based State Machine:**

1. No motion → **WAITING**
2. Vertical downward motion (arm moves down) → **DIGGING**
3. Primarily horizontal motion → **SWINGING**
4. Vertical upward motion (arm moves up, bucket tilts) → **DUMPING**
5. Complex motion → **DIGGING** (default active)

**Debouncing:**

- Requires 3 consecutive frames with same signal before reporting state change
- Prevents flickering from optical noise
- Ensures temporal stability

### Time Tracking

Per equipment instance:
- **Total Tracked Time**: Cumulative time equipment visible
- **Active Time**: Time in ACTIVE state
- **Idle Time**: Time in INACTIVE state
- **Utilization %**: (Active Time / Total Time) × 100

Updates every frame with delta-t based on actual frame rate.

## Custom YOLO Model

The system defaults to `yolov8n.pt` (nano model, ~3.2M parameters).

### Using a Different YOLOv8 Variant

Edit `.env`:

```env
YOLO_MODEL=yolov8m.pt  # Medium: Better accuracy, slower
YOLO_MODEL=yolov8l.pt  # Large: Best accuracy, slowest
```

Available models:
- `yolov8n.pt` - Nano (fastest, least accurate)
- `yolov8s.pt` - Small
- `yolov8m.pt` - Medium (recommended)
- `yolov8l.pt` - Large
- `yolov8x.pt` - Extra Large (most accurate, slowest)

### Using a Custom Fine-Tuned Model

1. Train a YOLOv8 model on construction equipment images:

```python
from ultralytics import YOLO

model = YOLO('yolov8n.pt')
results = model.train(
    data='path/to/dataset.yaml',
    epochs=100,
    imgsz=640
)
```

2. Export trained model:

```bash
yolo detect export model=runs/detect/train/weights/best.pt format=pt
```

3. Place model in cv_service directory:

```bash
cp runs/detect/train/weights/best.pt cv_service/custom_model.pt
```

4. Update `.env`:

```env
YOLO_MODEL=custom_model.pt
```

### Fine-Tuning Dataset Recommendations

For best results with construction equipment:

- **Excavators**: 200-500 images with various angles, lighting
- **Dump Trucks**: 200-500 images
- **Angles**: Top-down, side, 45° perspectives
- **Lighting**: Day, night, overcast, shadows
- **Scales**: Close-up, mid-range, distant shots

Annotation format: YOLO txt format (one `.txt` per image)

See [Roboflow](https://roboflow.com) for annotation tools and dataset management.

## Known Limitations

### Detection Limitations

1. **COCO Class Ambiguity**
   - COCO YOLOv8 doesn't have dedicated "excavator" class
   - We map class 7 (truck) to excavator; fine-tuned model recommended for better accuracy
   - Occlusion/partial visibility may reduce confidence

2. **Single Model**
   - Assumes similar equipment types across site
   - Different equipment requires model retraining

3. **Lighting Conditions**
   - Poor lighting (night, shadows) degrades detection
   - Reflective surfaces may cause false positives

### Motion Analysis Limitations

1. **Optical Flow Noise**
   - Small camera movements can create spurious motion
   - Lighting changes interpreted as motion
   - Recommended: Fixed camera stabilization

2. **Zone Thresholds**
   - Motion thresholds tuned for mid-range distances
   - Very close or very distant equipment may need re-tuning

3. **Partial Frame**
   - Equipment partially outside frame boundaries may misclassify

### Activity Classification Limitations

1. **No Deep Learning Fallback**
   - Rule-based system may misclassify novel motion patterns
   - Requires manual rule updates for new equipment types

2. **Temporal Debouncing**
   - 3-frame debounce may miss very short activities
   - Fast equipment movement might be smoothed out

3. **No Context**
   - System doesn't know equipment constraints or capabilities
   - May misclassify transitional states

### Infrastructure Limitations

1. **Single Broker**
   - Kafka runs with replication factor 1
   - Not suitable for production without replication

2. **No Persistence**
   - Redis frame buffer not persistent (frames lost on restart)

3. **Synchronous Processing**
   - No frame batching or async processing
   - Slower videos preferred (1-2x playback speed)

### Video Requirements

- Requires fixed camera (moving camera = detection jitter)
- Single equipment type per frame recommended
- Minimum 15 fps video recommended
- Best results: 640x480 - 1280x720 resolution

## Troubleshooting

### Services fail to start

**Error**: `docker: command not found`
- Docker not installed. Install from https://www.docker.com/products/docker-desktop

**Error**: `Bind for 0.0.0.0:8501 failed: port is already in use`
- Port 8501 occupied. Change in docker-compose.yml: `"8502:8501"`

### Video not detected

**Error**: `Video source not found: data/input.mp4`
- Place video file at `cv_service/data/input.mp4`
- Use absolute path in `.env` if in different location

### Kafka consumer not reading messages

**Error**: Consumer group lag increasing, no messages processed

```bash
# Check Kafka is healthy
docker compose logs kafka | grep "INFO"

# List topics
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Verify messages are being produced
docker compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic equipment-events --from-beginning
```

### TimescaleDB errors

**Error**: `FATAL: remaining connection slots are reserved`
- Too many connections. Increase in docker-compose.yml

**Error**: `relation "equipment_events" does not exist`
- Database initialization failed. Check init.sql execution:

```bash
docker compose exec timescaledb psql -U ev_user -d eaglevision -f /docker-entrypoint-initdb.d/init.sql
```

### Dashboard not updating

**Error**: Stats always show "Waiting for first detections..."

1. Check cv_service is running:
   ```bash
   docker compose logs cv_service | tail -20
   ```

2. Check analytics_service is consuming:
   ```bash
   docker compose logs analytics_service | tail -20
   ```

3. Verify video processing:
   ```bash
   docker compose logs cv_service | grep "Processed"
   ```

### Performance Issues

**Slow frame rate:**

1. Reduce resolution: `cv2.resize(frame, (640, 480))`
2. Increase `FRAME_SKIP`: Process fewer frames
3. Use smaller model: `YOLO_MODEL=yolov8n.pt`
4. Lower `CONFIDENCE_THRESHOLD` to 0.3

**High memory usage:**

1. Reduce video resolution
2. Close other applications
3. Use lighter model
4. Restart services: `docker compose restart`

### Clean Rebuild

To start fresh:

```bash
# Stop and remove all containers/volumes
docker compose down -v

# Clear models (download fresh)
rm -rf ~/.cache/yolo

# Rebuild
docker compose up --build
```

## Performance Tips

### For Real-Time Processing

- Use `yolov8n.pt` model
- Set `FRAME_SKIP=2` (process every 2nd frame)
- Use video resolution ≤ 1280x720
- Dedicated GPU: Add `runtime: nvidia` to cv_service in docker-compose.yml

### For Accuracy

- Use `yolov8m.pt` model
- Set `FRAME_SKIP=1` (process all frames)
- Use high-resolution video (1920x1080+)
- Use fine-tuned model on construction equipment

## Example Output

### Console Logs

```
2024-03-15 10:30:45 [cv_service] INFO: Loaded YOLOv8 model
2024-03-15 10:30:46 [cv_service] INFO: Kafka topic ready
2024-03-15 10:30:48 [cv_service] INFO: Processed 30 frames, detected 2 equipment
2024-03-15 10:30:49 [analytics_service] INFO: Consumed message: EX-001
2024-03-15 10:30:49 [analytics_service] INFO: Stored event for EX-001
```

### Kafka Events

```json
{
  "frame_id": 450,
  "equipment_id": "EX-001",
  "equipment_class": "excavator",
  "timestamp": "00:00:15.000",
  "utilization": {
    "current_state": "ACTIVE",
    "current_activity": "DIGGING",
    "motion_source": "arm_only"
  },
  "time_analytics": {
    "total_tracked_seconds": 15.0,
    "total_active_seconds": 12.5,
    "total_idle_seconds": 2.5,
    "utilization_percent": 83.3
  }
}
```

### Dashboard Display

```
🦅 EagleVision - Equipment Utilization Monitor

📹 Live Video Feed          📊 Equipment Status
[Live video stream]         ### EX-001 — excavator
[Annotated boxes]           🟢 ACTIVE
                           Utilization: 83.3%
                           Active Time: 12.5s
                           Idle Time: 2.5s
                           Activity: DIGGING | Motion: arm_only
```

## Contributing

To modify or extend EagleVision:

1. Make changes to source files
2. Rebuild: `docker compose up --build`
3. Test: Verify logs and dashboard output
4. Commit: Push changes to repository

## License

This project is provided as-is for demonstration and educational purposes.

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting)
2. Review service logs: `docker compose logs -f [service]`
3. Verify configuration in `.env`

---

**Built with:** Python, OpenCV, YOLOv8, Apache Kafka, TimescaleDB (PostgreSQL), Redis, Streamlit, Docker

**Version:** 1.0.0  
**Last Updated:** March 2024
