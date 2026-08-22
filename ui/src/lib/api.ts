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

// null means "the backend does not report this", never zero. /api/status
// (_build_status, studio_api.py:391) carries instance state, uptime and accrued
// cost — it has no VRAM, utilization, dead-man or resident-model telemetry, and
// inventing plausible numbers for those renders an idle box as a busy one.
export interface GpuStatusData {
  online: boolean;
  instance_type: string | null;
  provider: 'aws_spot' | 'shadeform' | 'local';
  vram_used_gb: number | null;
  vram_total_gb: number | null;
  gpu_utilization: number | null;
  hourly_cost: number | null;
  estimated_cost_usd: number | null;
  uptime_seconds: number | null;
  dead_man_seconds_remaining: number | null;
  resident_model: string | null;
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
      // FastAPI puts the human-readable reason in `detail`; raw JSON in a toast is noise.
      const errBody = await res.text().catch(() => '');
      let reason = errBody;
      try {
        const parsed = JSON.parse(errBody);
        reason = parsed?.detail || parsed?.message || errBody;
      } catch {
        // non-JSON body: use it as-is
      }
      throw new Error(reason || `API Error ${res.status}: ${res.statusText}`);
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

  // GPU Spot Instance Telemetry. Throws on a failed fetch: a status poll that
  // cannot reach the server is an unknown state, not an idle GPU.
  async getGpuStatus(): Promise<GpuStatusData> {
    const data = await this.fetchJson<any>('/api/status');
    return {
      online: Boolean(data.gpu_online),
      instance_type: data.instance?.type ?? null,
      provider: 'aws_spot',
      vram_used_gb: null,
      vram_total_gb: null,
      gpu_utilization: null,
      hourly_cost: null,
      estimated_cost_usd: data.estimated_cost_usd ?? null,
      uptime_seconds: typeof data.uptime_minutes === 'number' ? data.uptime_minutes * 60 : null,
      dead_man_seconds_remaining: null,
      resident_model: null,
    };
  }

  // Launch Spot GPU. GpuActionRequest (studio_api.py:467) 400s without
  // {confirm: true}; it takes no instance_type, so the size is server-side config.
  async launchGpu(confirm = true): Promise<{ status: string; message?: string }> {
    return this.fetchJson('/api/gpu/launch', {
      method: 'POST',
      body: JSON.stringify({ confirm }),
    });
  }

  // Terminate Spot GPU. Same confirm requirement as launch.
  async terminateGpu(confirm = true): Promise<{ status: string; message?: string }> {
    return this.fetchJson('/api/gpu/terminate', {
      method: 'POST',
      body: JSON.stringify({ confirm }),
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
