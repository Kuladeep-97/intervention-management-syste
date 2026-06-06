# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Copy frontend configuration and install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the Python backend
FROM python:3.10-slim
WORKDIR /app

# Install system dependencies required for OpenCV and YOLO
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend code and model files
COPY . .

# Copy built frontend from Stage 1 into the location expected by FastAPI
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose the API and Dashboard port
EXPOSE 8000

# Set environment variables for better Python performance
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=4

# Command to run the application
CMD ["python", "tracker_app/main.py"]
