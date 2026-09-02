/**
 * Master SpacePilot API Type Definitions
 * Derived from FastAPI Pydantic Models
 */

export interface StatusResponse {
  gpu_online: boolean;
  worker_ready: boolean;
  version?: string;
  uptime_seconds?: number;
  vram_used_gb?: number;
  vram_used_gib?: number;
  vram_total_gb?: number;
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
  /** false when no instance is running — a state, not an error. */
  running?: boolean;
  reason?: string;
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
  fps?: number;
  stg_scale?: number;
  steps?: number;
  seed?: number;
  num_takes?: number;
  takes?: number;
  camera_pan?: string;
  camera_tilt?: string;
  camera_zoom?: string;
  camera_roll?: string;
  camera_intensity?: number;
  image_path?: string | null;
  last_image_path?: string | null;
  enhance?: boolean;
  draft_mode?: boolean;
  bgm_preset?: string;
  voice?: string;
  target_lufs?: number;
  asset_id?: string;
}

export interface JobResult {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress?: number;
  phase?: string;
  phase_text?: string;
  take_group_id?: string;
  jobs?: Array<{
    job_id: string;
    video_url?: string;
    seed?: number;
    prompt?: string;
  }>;
  takes?: Array<{
    id: number;
    seed: number;
    video_url: string;
    pan_deg?: number;
    zoom_ratio?: number;
    prompt?: string;
    duration_sec?: number;
    fps?: number;
    width?: number;
    height?: number;
    created_at?: string;
  }>;
  video_url?: string;
  preview_url?: string;
  error?: string;
  patch?: Record<string, unknown>;
}

export interface StoryboardScene {
  scene_idx: number;
  title: string;
  prompt: string;
  duration_sec: number;
  camera_motion: string;
  shot_type: string;
  lighting: string;
  character_seed: number;
}

export interface StoryboardDecomposeRequest {
  script: string;
  target_duration_sec?: number;
  scene_count?: number;
  style?: string;
}

export interface StoryboardDecomposeResponse {
  scenes: StoryboardScene[];
  total_duration_sec: number;
  character_seed: number;
}

export interface AudioSynthRequest {
  text: string;
  voice?: string;
  speed?: number;
  target_lufs?: number;
  bgm_preset?: string;
}

export interface AudioSynthResponse {
  audio_url: string;
  duration_sec: number;
  lufs: number;
  status?: string;
  job_id?: string;
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

export interface CockpitConfig {
  provider?: 'aws' | 'shadeform' | 'runpod' | 'local';
  shadeform_api_key?: string;
  runpod_api_key?: string;
  aws_profile?: string;
  local_host?: string;
  region?: string;
  instance_type?: string;
  spot_hourly_rate?: number;
  key_file?: string;
  default_duration?: number;
  default_stg?: number;
  default_modality?: number;
  idle_shutdown_minutes?: number;
}

export interface SkyCloudArbitrageItem {
  name: string;
  provider: string;
  accelerator: string;
  vram_gb: number;
  spot_price_usd: number;
  ondemand_price_usd: number;
  preemption_risk: 'very-low' | 'low' | 'medium' | 'high';
  preemption_rate_pct: number;
  is_cheapest?: boolean;
}

export interface SkyStatus {
  active: boolean;
  cluster_name?: string;
  provider?: string;
  accelerator?: string;
  spot_hourly_rate_usd?: number;
  checkpoint_synced?: boolean;
  preemption_failover_count?: number;
  last_failover_timestamp?: string;
}

export interface SkyYamlResponse {
  status: string;
  yaml: string;
}

export interface InspectMetricsResponse {
  /** false when no instance is running — a state, not an error. */
  running?: boolean;
  reason?: string;
  gpu?: {
    utilization?: string;
    memory_used?: string;
    memory_total?: string;
    temperature?: string;
  };
  disk?: string;
  memory?: string;
  raw?: string;
}

export interface DiskStorageInfo {
  root_used_gb: number;
  root_total_gb: number;
  root_percent: number;
  cache_used_gb: number;
  cache_total_gb: number;
  cache_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  io_throughput_mb_s?: number;
}

