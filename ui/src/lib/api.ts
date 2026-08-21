export interface GenerationRequest {
  prompt: string;
  takes?: number;
  camera_pan?: number;
  camera_zoom?: number;
  camera_tilt?: number;
  camera_roll?: number;
  voice_preset?: string;
  music_lufs?: number;
  seed?: number;
}

export interface GenerationResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  video_url?: string;
  takes?: Array<{
    id: number;
    seed: number;
    video_url: string;
    pan_deg: number;
    zoom_ratio: number;
  }>;
}

export interface GpuStatusResponse {
  instance_type: string;
  provider: string;
  vram_used_gb: number;
  vram_total_gb: number;
  gpu_utilization: number;
  hourly_cost: number;
  uptime_seconds: number;
  dead_man_seconds_remaining: number;
}

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
  }

  async generate(req: GenerationRequest): Promise<GenerationResponse> {
    const res = await fetch(`${this.baseUrl}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      throw new Error(`Generation failed: ${res.statusText}`);
    }
    return res.json();
  }

  async getGpuStatus(): Promise<GpuStatusResponse> {
    const res = await fetch(`${this.baseUrl}/api/gpu/status`);
    if (!res.ok) {
      throw new Error(`GPU status check failed: ${res.statusText}`);
    }
    return res.json();
  }

  async launchGpu(instanceType = 'g6e.xlarge'): Promise<{ status: string }> {
    const res = await fetch(`${this.baseUrl}/api/gpu/launch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instance_type: instanceType }),
    });
    if (!res.ok) {
      throw new Error(`GPU launch failed: ${res.statusText}`);
    }
    return res.json();
  }

  async terminateGpu(): Promise<{ status: string }> {
    const res = await fetch(`${this.baseUrl}/api/gpu/terminate`, {
      method: 'POST',
    });
    if (!res.ok) {
      throw new Error(`GPU termination failed: ${res.statusText}`);
    }
    return res.json();
  }
}

export const api = new ApiClient();
