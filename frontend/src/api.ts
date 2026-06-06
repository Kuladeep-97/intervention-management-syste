/**
 * Dheera AI — API client
 * Typed fetch wrappers for the FastAPI backend.
 */

const API_BASE = '/api';  // proxied to localhost:5000 by Vite

// ---- Types -----------------------------------------------------------

export interface InterventionEvent {
  event_id: number;
  roi_index: number;
  roi_label: string;
  start_frame: number;
  end_frame: number;
  start_sec: number;
  end_sec: number;
  duration_sec: number;
  start_time: string;
  end_time: string;
  recorded_at: string;
  snapshot_path: string;
  clip_path?: string;
  intervention_type: string;
}

export interface Deviation {
  type: string;
  message: string;
  current_value: number;
  limit: number;
  severity: string;
  detected_at: string;
  trigger_event: number;
  trigger_time: string;
}

export interface PortStat {
  count: number;
  total_duration_sec: number;
}

export interface Summary {
  total_events: number;
  total_duration_sec: number;
  avg_duration_sec: number;
  frequency_per_min: number;
  count_usage_pct: number;
  duration_usage_pct: number;
  max_count: number;
  max_duration_sec: number;
  port_stats: Record<string, PortStat>;
  has_deviations: boolean;
  deviation_count: number;
  video_duration_sec: number;
}

export interface ClipInfo {
  filename: string;
  size_bytes: number;
  url: string;
}

export interface AppConfig {
  detection?: Record<string, number>;
  events?: Record<string, number>;
  limits?: Record<string, number>;
  rois?: Array<Record<string, unknown>>;
  output?: Record<string, unknown>;
}

// ---- Fetch helpers ---------------------------------------------------

export async function fetchEvents(): Promise<InterventionEvent[]> {
  const res = await fetch(`${API_BASE}/events`);
  return res.json();
}

export async function fetchDeviations(): Promise<Deviation[]> {
  const res = await fetch(`${API_BASE}/deviations`);
  return res.json();
}

export async function fetchSummary(): Promise<Summary> {
  const res = await fetch(`${API_BASE}/summary`);
  return res.json();
}

export async function fetchConfig(): Promise<AppConfig> {
  const res = await fetch(`${API_BASE}/config`);
  return res.json();
}

export async function saveConfig(config: AppConfig): Promise<void> {
  await fetch(`${API_BASE}/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
}

export async function fetchClips(): Promise<ClipInfo[]> {
  const res = await fetch(`${API_BASE}/clips`);
  return res.json();
}

export async function saveClassifications(
  classifications: Record<string, string>,
): Promise<void> {
  await fetch(`${API_BASE}/classifications`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ classifications }),
  });
}

// ---- Streaming -------------------------------------------------------

export interface StreamStatus {
  is_running: boolean;
  frame_idx: number;
  total_frames: number;
  progress_pct: number;
  fps: number;
  elapsed_sec: number;
  events: InterventionEvent[];
  deviations: Deviation[];
  summary: Summary;
}

export async function startStream(videoPath?: string): Promise<void> {
  await fetch(`${API_BASE}/stream/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_path: videoPath }),
  });
}

export async function stopStream(): Promise<void> {
  await fetch(`${API_BASE}/stream/stop`, {
    method: 'POST',
  });
}

export async function resetStream(): Promise<void> {
  await fetch(`${API_BASE}/stream/reset`, {
    method: 'POST',
  });
}

export async function fetchStreamStatus(): Promise<StreamStatus> {
  const res = await fetch(`${API_BASE}/stream/status`);
  return res.json();
}

// ---- URL builders ----------------------------------------------------

export function clipUrl(filename: string): string {
  return `${API_BASE}/clips/${filename}`;
}

export function snapshotUrl(snapshotPath: string): string {
  // snapshot_path in events.json is like "output\\snapshots\\event_1_port1_f5.jpg"
  const filename = snapshotPath.split(/[/\\]/).pop() || '';
  return `${API_BASE}/snapshots/${filename}`;
}

export const VIDEO_FEED_URL = '/video_feed';
