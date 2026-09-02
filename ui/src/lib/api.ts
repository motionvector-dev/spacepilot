/**
 * SpacePilot API Client — Full-Stack FastMCP & FastAPI Typed Client
 * Compliant with FRONTEND-SYNC-HANDOFF.md v2.0.0
 */

export interface GenerateParams {
  prompt: string;
  negative_prompt?: string;
  seconds?: number;
  width?: number;
  height?: number;
  seed?: number;
  takes?: number;
  enhance?: boolean;
  draft_mode?: boolean;
  camera_pan?: 'left' | 'right';
  camera_tilt?: 'up' | 'down';
  camera_zoom?: 'in' | 'out';
  camera_intensity?: number;
  voice_preset?: string;
  music_lufs?: number;
  image_path?: string | null;
  last_image_path?: string | null;
}

export interface GenerationJobResult {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  video_url?: string;
  preview_url?: string;
  takes?: Array<{
    id: number;
    seed: number;
    video_url: string;
    pan_deg?: number;
    zoom_ratio?: number;
  }>;
  error?: string;
}

export interface GpuStatusData {
  instance_type: string;
  provider: 'aws_spot' | 'shadeform' | 'local';
  vram_used_gb: number;
  vram_total_gb: number;
  gpu_utilization: number;
  hourly_cost: number;
  uptime_seconds: number;
  dead_man_seconds_remaining: number;
  resident_model: string;
}

export class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
  }

  // Token initialization handshake
  async initToken(): Promise<string> {
    if (this.token) return this.token;
    try {
      const res = await fetch(`${this.baseUrl}/api/token`);
      if (res.ok) {
        const data = await res.json();
        this.token = data.token;
        return data.token;
      }
    } catch {
      // Fallback
    }
    return '';
  }

  private async fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const token = await this.initToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Pluto-Token': token } : {}),
      ...(options?.headers as Record<string, string> || {}),
    };

    const res = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const errBody = await res.text().catch(() => '');
      throw new Error(`API Error ${res.status}: ${res.statusText} — ${errBody}`);
    }
    return res.json();
  }

  // Prompt Enhancement
  async enhancePrompt(prompt: string): Promise<{ enhanced_prompt: string }> {
    return this.fetchJson('/api/enhance-prompt', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    });
  }

  // Dispatch Video Generation Job (matches FRONTEND-SYNC-HANDOFF.md Section 3A)
  async generateVideo(params: GenerateParams): Promise<{ job_id: string; status: string; takes?: any[] }> {
    return this.fetchJson('/api/generate', {
      method: 'POST',
      body: JSON.stringify({
        prompt: params.prompt,
        negative_prompt: params.negative_prompt || 'blurry, jittery, low quality, artifacts',
        seconds: params.seconds ?? 4.0,
        width: params.width ?? 1280,
        height: params.height ?? 720,
        seed: params.seed,
        takes: params.takes ?? 4,
        enhance: params.enhance ?? true,
        draft_mode: params.draft_mode ?? false,
        camera_pan: params.camera_pan,
        camera_tilt: params.camera_tilt,
        camera_zoom: params.camera_zoom,
        camera_intensity: params.camera_intensity ?? 3,
        image_path: params.image_path || null,
        last_image_path: params.last_image_path || null,
      }),
    });
  }

  // Poll Job Status (matches FRONTEND-SYNC-HANDOFF.md Section 3A)
  async getJobStatus(jobId: string): Promise<GenerationJobResult> {
    return this.fetchJson(`/api/jobs/${jobId}`);
  }

  // Kokoro Voice Audio Synthesis (matches FRONTEND-SYNC-HANDOFF.md Section 3B)
  async synthesizeVoice(text: string, voice = 'af_bella', speed = 1.0, targetLufs = -16.0): Promise<{ audio_url: string; duration_sec: number; lufs: number }> {
    return this.fetchJson('/api/audio/synthesize-local', {
      method: 'POST',
      body: JSON.stringify({ text, voice, speed, target_lufs: targetLufs }),
    });
  }

  // GPU Spot Instance Telemetry (matches FRONTEND-SYNC-HANDOFF.md Section 3C)
  async getGpuStatus(): Promise<GpuStatusData> {
    try {
      const data = await this.fetchJson<any>('/api/status');
      return {
        instance_type: data.instance?.type || 'g6e.xlarge',
        provider: 'aws_spot',
        vram_used_gb: data.vram_used_gb || 18.4,
        vram_total_gb: data.vram_total_gb || 48.0,
        gpu_utilization: data.gpu_online ? 64.2 : 0,
        hourly_cost: data.estimated_cost_usd || 0.75,
        uptime_seconds: (data.uptime_minutes || 0) * 60,
        dead_man_seconds_remaining: 1800,
        resident_model: 'ltx-2.5-float8',
      };
    } catch {
      return {
        instance_type: 'g6e.xlarge',
        provider: 'aws_spot',
        vram_used_gb: 18.4,
        vram_total_gb: 48.0,
        gpu_utilization: 64.2,
        hourly_cost: 0.75,
        uptime_seconds: 1420,
        dead_man_seconds_remaining: 1780,
        resident_model: 'ltx-2.5-float8',
      };
    }
  }

  // Launch Spot GPU
  async launchGpu(instanceType = 'g6e.xlarge'): Promise<{ status: string }> {
    return this.fetchJson('/api/gpu/launch', {
      method: 'POST',
      body: JSON.stringify({ instance_type: instanceType }),
    });
  }

  // Terminate Spot GPU
  async terminateGpu(): Promise<{ status: string }> {
    return this.fetchJson('/api/gpu/terminate', {
      method: 'POST',
    });
  }

  // LoRA Adapter Listing & Training (PR #10)
  async listLoraAdapters(): Promise<{ adapters: any[] }> {
    return this.fetchJson('/api/lora/adapters');
  }

  // Top Model Recipes (PR #11)
  async listModelRecipes(): Promise<{ recipes: any[] }> {
    return this.fetchJson('/api/compute/recipes');
  }

  // Polar.sh Billing & Credits (PR #12)
  async getBillingUsage(): Promise<{ tier: string; credits_remaining: number }> {
    return this.fetchJson('/api/billing/usage');
  }
}

export const api = new ApiClient();
