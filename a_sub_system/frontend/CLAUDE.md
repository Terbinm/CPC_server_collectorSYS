# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CPC Server Collector System is a distributed audio recording and management platform with:
- **Flask backend** with SocketIO for real-time communication
- **MongoDB** for audio recording metadata storage
- **Edge client devices** for distributed audio capture
- Web-based dashboard for recording management and scheduling

## Architecture

### Core System Components

**Three-layer architecture:**

1. **Server Layer** (`main.py`)
   - Flask app with SocketIO server
   - MongoDB handler for recording data
   - SQLite for schedule persistence (optional)
   - Serves on port 5000

2. **Edge Client Layer** (`a_sub_system/edge_client/edge_client.py`)
   - Autonomous recording devices
   - SocketIO client connects to server
   - Records audio via sounddevice/soundfile
   - Uploads recordings with hash verification

3. **Web UI Layer** (`templates/`, `static/`)
   - Dashboard for recording management
   - Schedule management interface
   - Audio playback and download

### Data Flow

**Recording submission flow:**
- Edge devices register via SocketIO `register_device` event
- Server sends `record` command with duration
- Device captures audio, calculates hash, uploads via `/upload_recording`
- Server validates hash, stores metadata in MongoDB
- Real-time updates broadcast via SocketIO `new_recording` event

**Schedule execution flow:**
- Schedules stored in `device_schedules` (shared_state.py)
- Background task `schedule_checker()` runs every second
- Executes scheduled recordings by emitting `record` events
- Device-level locks prevent concurrent execution

### Database Structure

**MongoDB document format** (models.py:73-110):
- `AnalyzeUUID`: Primary identifier
- `files.raw`: Original file metadata
- `info_features`: Device, upload time, file hash, duration, metadata
- `analyze_features`: Empty (reserved for future analysis)
- Indexes on: AnalyzeUUID, device_id, upload_time, file_hash, filename

**Key models:**
- `AudioRecording`: ORM-like object for recordings
- `MongoDBHandler`: Connection and index management
- `RecordingRepository`: Data access layer

## Common Development Tasks

### Running the Application

**Start the server:**
```bash
python main.py
```
Server runs on http://0.0.0.0:5000 with debug mode enabled.

**Start an edge client:**
```bash
cd a_sub_system/edge_client
python edge_client.py
```
Client loads config from `device_config.json` and connects to server.

**Run with Docker:**
```bash
docker build -t cpc-server .
docker run -p 5000:5000 cpc-server
```

### Database Operations

**Check MongoDB data:**
```bash
python check_mongodb_data.py
```

**Delete all data (debug):**
```bash
python debug_tools/delete_all_data.py
```

**MongoDB connection config** in `config.py`:
- Host: localhost:27020
- Database: web_db
- Collection: recordings
- Auth: web_ui/hod2iddfsgsrl

### Installing Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies: Flask, Flask-SocketIO, Flask-SQLAlchemy, pymongo, sounddevice, soundfile, pytz

## Key Configuration

### Server Configuration (`config.py`)

- `UPLOAD_FOLDER`: 'uploads' - where audio files are stored
- `TAIPEI_TZ`: Asia/Taipei timezone for timestamps
- `MONGODB_CONFIG`: MongoDB connection parameters
- `DATASET_CONFIG`: Dataset UUID and object ID for recordings
- `AUDIO_CONFIG`: Default sample rate (44100), channels (1), format (wav)

### Edge Client Configuration

**device_config.json format:**
```json
{
  "device_id": "uuid-string",
  "device_name": "Device_name"
}
```

If missing, client requests new ID from server via `request_id` event.

## Important Implementation Details

### SocketIO Events

**Client → Server:**
- `register_device`: Register/reconnect with ID and name
- `request_id`: Request new device ID
- `update_status`: Update device status (IDLE/RECORDING/OFFLINE)

**Server → Client:**
- `record`: Command to start recording with duration
- `update_devices`: Broadcast device list changes
- `new_recording`: Broadcast new recording added
- `assign_id`: Assign new device ID

### File Upload Verification

Edge devices calculate SHA-256 hash before upload. Server validates:
1. File size matches expected
2. File hash matches expected
3. If mismatch, file is deleted and error returned

### Schedule Management

`RecordingSchedule` class (shared_state.py):
- `interval`: Minutes between recordings
- `duration`: Recording length in seconds
- `count`: Total recordings (None = infinite)
- Uses device-specific locks to prevent concurrent execution

### Shared State Management

Global dictionaries in `shared_state.py`:
- `connected_clients`: Maps socket SID to client info
- `recording_devices`: Maps device_id to device status/name
- `device_schedules`: Maps device_id to RecordingSchedule

## Routes and Endpoints

**Web pages:**
- `/`: Landing page
- `/dashboard`: Main management dashboard
- `/schedule_management`: Schedule configuration
- `/play/<id>`: Audio playback page

**API endpoints:**
- `POST /upload_recording`: Upload audio file
- `GET /recordings`: List all recordings
- `GET /download/<id>`: Download recording
- `GET /check_upload/<id>`: Check upload status
- `POST /delete/<id>`: Delete recording
- `POST /schedule`: Create schedule
- `GET /schedule/<device_id>`: Get schedule
- `DELETE /schedule/<device_id>`: Delete schedule

## Dataset Integration

System follows V3_multi_dataset structure:
- `dataset_UUID`: 'WEB_UI_Dataset'
- `obj_ID`: '99' (Web UI identifier)
- Recordings tagged with source: WEB_UPLOAD or EDGE_DEVICE
- Compatible with external analysis pipelines

## Development Notes

- Use `logging` module for all output (avoid print statements)
- All times stored in UTC, displayed in Taipei timezone
- Audio files use secure_filename() for safety
- Background schedule checker runs as SocketIO background task
- MongoDB indexes created automatically on startup
