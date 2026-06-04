import os
os.environ["OMP_NUM_THREADS"] = "4"
import uvicorn
import yaml
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import websocket as ws_module
from app.streaming.streamer import Streamer

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

config = load_config()

app = FastAPI(title="Pharma Tracker Live Dashboard API")

# Allow CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Streamer
streamer = Streamer(config)

# Inject streamer into websocket router
ws_module.streamer = streamer

# Include routers
app.include_router(ws_module.router)

# Mount the dashboard static files at the root
dashboard_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")

if __name__ == "__main__":
    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 8000)
    print(f"Starting server on {host}:{port}...", flush=True)
    uvicorn.run(app, host=host, port=port, reload=False)
