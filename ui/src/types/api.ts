/**
 * Master SpacePilot API Type Definitions
 * Derived from FastAPI Pydantic Models
 */

export interface StatusResponse {
  gpu_online: boolean;
  worker_ready: boolean;
  version?: string;
  uptime_seconds?: number;
}

export interface CockpitStatus {
  instance?: {
    id: string;
    type: string;
    ip: string;
    state: string;
  };
  gpu_online: boolean;
  worker_ready: boolean;
  vram_used_gb: number;
  vram_total_gb: number;
  uptime_minutes: number;
  estimated_cost_usd: number;
  watchdog?: {
    elapsed_mins: number;
  };
}

export interface GpuMetrics {
  gpu_utilization_pct: number;
  vram_used_mb: number;
  vram_total_mb: number;
  temperature_c: number;
  power_draw_w: number;
  driver_version?: string;
  cuda_version?: string;
  device_name?: string;
}

export interface ComputeProfile {
  device: string;
  device_name: string;
  total_vram_gb: number;
  free_vram_gb: number;
  instruction_set: string;
  is_cuda: boolean;
  is_mps: boolean;
}

export interface RecommendedModel {
  id: string;
  name: string;
  category: string;
  precision: string;
  size_gb: number;
  is_local_runnable: boolean;
  fit?: 'Optimal' | 'Degraded' | 'OOM Warning';
  status: 'cached' | 'downloading' | 'remote';
  download_progress?: number;
}

export interface EngineItem {
  id: string;
  name: string;
  architecture: string;
  vram_requirement_gb: number;
  cold_start_seconds: number;
  supported: boolean;
}

export interface GenerateRequest {
  prompt: string;
  negative_prompt?: string;
  engine?: string;
  seconds?: number;
  width?: number;
  height?: number;
  seed?: number;
  num_takes?: number;
  camera_pan?: string;
  camera_tilt?: string;
  camera_zoom?: string;
  camera_intensity?: number;
  image_path?: string | null;
  last_image_path?: string | null;
  enhance?: boolean;
  draft_mode?: boolean;
}

export interface JobResult {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress?: number;
  takes?: Array<{
    id: number;
    seed: number;
    video_url: string;
    pan_deg?: number;
    zoom_ratio?: number;
  }>;
  video_url?: string;
  error?: string;
}

export interface AudioSynthRequest {
  text: string;
  voice?: string;
  speed?: number;
  target_lufs?: number;
}

export interface AudioSynthResponse {
  audio_url: string;
  duration_sec: number;
  lufs: number;
  status?: string;
}

export interface AssetRecord {
  id: string;
  filename: string;
  file_url: string;
  thumbnail_url?: string;
  created_at: string;
  size_bytes: number;
  duration_sec?: number;
  prompt?: string;
  engine?: string;
}
