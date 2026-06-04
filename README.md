# Intervention Management System (IMS)

The Intervention Management System is a real-time, AI-driven video analytics pipeline designed to monitor and track operator interactions (interventions) within pharmaceutical isolator glove ports. The system leverages state-of-the-art computer vision to track glove movements, calculate intervention durations, classify activity states (Active vs. Idle), and present telemetry via a unified live dashboard.

## 🏗️ Architecture Overview

The application utilizes a **Unified Monolith Architecture**, where a single Python backend serves both the heavy AI processing pipeline and the compiled React frontend application.

### 1. AI Inference Pipeline (`tracker_app/app/pipeline/`)
- **Engine**: Powered by **YOLOv11** running on PyTorch for high-fidelity segmentation and object tracking.
- **Logic**: The `PipelineProcessor` tracks bounding boxes of operator gloves against predefined polygonal Regions of Interest (ROIs) representing isolator ports.
- **Metrics**: Computes real-time telemetry, including active intervention duration, idle time, and port-specific usage statistics.

### 2. FastAPI Backend (`tracker_app/main.py`)
- **REST API**: Provides endpoints (`/api/events`, `/api/summary`) to supply historical session data and aggregated telemetry.
- **WebSocket Streaming**: A background asynchronous worker (`Streamer`) processes video frames natively via OpenCV, encodes them to Base64, and pushes them directly to the client at `ws://localhost:8000/ws/video` alongside live JSON metrics.
- **Static Hosting**: Serves the compiled production build of the React frontend from `frontend/dist` directly at the root path (`/`).

### 3. React Frontend (`frontend/`)
- **Stack**: Built with React, TypeScript, Vite, and TailwindCSS.
- **Dashboard**: Features a responsive, glassmorphic UI that seamlessly parses the WebSocket stream to render live video frames at zero-latency without React state collisions.
- **HITL Review**: Includes a Human-in-the-Loop classification table to review completed and in-progress interventions.

---

## 🚀 How to Run the Application

Since the frontend is already pre-compiled into the `frontend/dist` directory, you do **not** need to run a separate Node.js server to use the application. The entire stack is launched via a single command.

### Prerequisites
Ensure you have Python 3.10+ installed. Install the backend dependencies:
```bash
pip install -r requirements.txt
```

*(Note: The system requires the heavy YOLO weights file `best.pt` and the video source `test_video.avi` to be present in the working directory as defined by `tracker_app/config/config.yaml`.)*

### Starting the Server
Run the FastAPI application directly:
```bash
python3 tracker_app/main.py
```

### Initialization Sequence
1. The server will begin booting and immediately load the PyTorch weights into memory.
2. **Please wait ~2 to 3 minutes** for the PyTorch memory cache to fully initialize on the CPU. During this time, the server will not accept HTTP requests.
3. Once you see `Uvicorn running on http://0.0.0.0:8000` in your terminal, the server is ready.

### Accessing the Dashboard
1. Open your web browser and navigate to: **[http://localhost:8000](http://localhost:8000)**
2. Click the blue **START STREAM** button.
3. The WebSocket connection will instantly establish, and the live PyTorch video feed will render alongside the real-time intervention tracking table.

---

## 🛠️ Development & Building

If you make modifications to the React frontend (`frontend/src/`), you must rebuild the static assets so the Python backend can serve them.

Navigate to the root directory and run the automated build script:
```bash
bash build_frontend.sh
```
This script will automatically install Node dependencies, compile the Vite production build into `frontend/dist`, and prepare the application for the FastAPI server.
