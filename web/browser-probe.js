/* What a browser can honestly work out about the machine it is running on.
 *
 * Order matters. The GPU renderer string names the chip outright, so it is read
 * first; navigator.deviceMemory answers memory where the browser implements it;
 * core count is the last resort and is treated as a hint, never an answer.
 *
 * Inferring a chip from core count is how llmconfigurator.com reports a 32 GB
 * M1 Max as a "~12GB M1 Pro" — ten cores fits both, and the renderer string it
 * ignored says which. Every field here carries a confidence, and nothing is
 * reported as known when it was guessed.
 */

export const APPLE_CHIPS = {
  // gpuCores is the discriminator the core count cannot provide.
  "m1":        { cores: [8],            memory: [8, 16] },
  "m1 pro":    { cores: [8, 10],        memory: [16, 32] },
  "m1 max":    { cores: [10],           memory: [32, 64] },
  "m1 ultra":  { cores: [20],           memory: [64, 128] },
  "m2":        { cores: [8],            memory: [8, 16, 24] },
  "m2 pro":    { cores: [10, 12],       memory: [16, 32] },
  "m2 max":    { cores: [12],           memory: [32, 64, 96] },
  "m2 ultra":  { cores: [24],           memory: [64, 128, 192] },
  "m3":        { cores: [8],            memory: [8, 16, 24] },
  "m3 pro":    { cores: [11, 12],       memory: [18, 36] },
  "m3 max":    { cores: [14, 16],       memory: [36, 48, 64, 96, 128] },
  "m4":        { cores: [10],           memory: [16, 24, 32] },
  "m4 pro":    { cores: [12, 14],       memory: [24, 48, 64] },
  "m4 max":    { cores: [14, 16],       memory: [36, 48, 64, 128] },
};

/* Metal hands a model less than the memory installed. Measured on an M1 Max
 * 32 GB: torch.mps.recommended_max_memory() reports 24.96 GB, 78% of RAM.
 * Applied here as a stated approximation, never as the precise figure — that
 * one only exists once the local process asks Metal directly. */
export const METAL_WORKING_SET_FRACTION = 0.78;

function renderer() {
  try {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2") || c.getContext("webgl");
    if (!gl) return null;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const s = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    const lose = gl.getExtension("WEBGL_lose_context");
    if (lose) lose.loseContext();          // a probe should not hold a GL context
    return s || null;
  } catch { return null; }
}

function chipFromRenderer(str) {
  if (!str) return null;
  // "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Max, Unspecified Version)"
  const apple = str.match(/Apple\s+(M\d+)(\s+(Pro|Max|Ultra))?/i);
  if (apple) {
    return { vendor: "apple", name: `Apple ${apple[1].toUpperCase()}${apple[3] ? " " + apple[3][0].toUpperCase() + apple[3].slice(1).toLowerCase() : ""}` };
  }
  const nvidia = str.match(/NVIDIA\s+(GeForce\s+)?(RTX|GTX)\s*(\d{4}\s*(Ti|SUPER)?)/i);
  if (nvidia) return { vendor: "nvidia", name: `NVIDIA ${nvidia[2].toUpperCase()} ${nvidia[3].trim()}` };
  const amd = str.match(/(Radeon[\w\s]*?(RX\s*\d{4}\s*\w*))/i);
  if (amd) return { vendor: "amd", name: amd[1].trim() };
  return { vendor: "unknown", name: str };
}

export function probeBrowser(nav = navigator) {
  const raw = renderer();
  const chip = chipFromRenderer(raw);
  const cores = nav.hardwareConcurrency ?? null;
  const declared = nav.deviceMemory ?? null;   // Chromium only; absent in Safari and Firefox

  const out = {
    chip: chip ? { value: chip.name, confidence: chip.vendor === "unknown" ? "low" : "high",
                   source: "webgl-renderer" }
               : { value: null, confidence: "none", source: null },
    backend: null,
    cores: cores == null ? { value: null, confidence: "none", source: null }
                         : { value: cores, confidence: "high", source: "hardwareConcurrency" },
    memoryBytes: { value: null, confidence: "none", source: null },
    workingSetBytes: { value: null, confidence: "none", source: null },
    webgpu: !!nav.gpu,
    rendererString: raw,
    limits: [],
  };

  if (chip?.vendor === "apple") out.backend = "metal";
  else if (chip?.vendor === "nvidia") out.backend = "cuda";
  else if (chip?.vendor === "amd") out.backend = "rocm";

  if (declared != null) {
    // Chromium rounds this to a power of two and historically capped it at 8.
    // A reported 8 on a machine with more than eight cores may be the cap
    // rather than the truth, so it is not promoted to high confidence.
    const capped = declared === 8 && (cores ?? 0) > 8;
    out.memoryBytes = {
      value: declared * 1024 ** 3,
      confidence: capped ? "low" : "medium",
      source: "deviceMemory",
      note: capped
        ? "8 GB may be the API's old ceiling rather than this machine's memory"
        : "rounded to a power of two by the browser",
    };
  } else if (chip?.vendor === "apple" && cores) {
    // Nothing reported it. Offer the configurations this chip ships in and say
    // that is what we are doing — never collapse them to one number.
    const key = chip.name.replace(/^Apple\s+/i, "").toLowerCase();
    const spec = APPLE_CHIPS[key];
    if (spec) {
      out.memoryBytes = {
        value: null, confidence: "none", source: null,
        candidates: spec.memory,
        note: `${chip.name} ships with ${spec.memory.join(", ")} GB — the browser cannot tell which`,
      };
    }
  }

  if (out.backend === "metal" && out.memoryBytes.value) {
    out.workingSetBytes = {
      value: Math.round(out.memoryBytes.value * METAL_WORKING_SET_FRACTION),
      confidence: "low",
      source: "estimated",
      note: `about ${Math.round(METAL_WORKING_SET_FRACTION * 100)}% of memory, the ratio Metal reported on a measured M1 Max — the exact ceiling needs the local app`,
    };
  } else if (out.memoryBytes.value) {
    out.workingSetBytes = { ...out.memoryBytes, confidence: "low", source: "estimated" };
  }

  out.limits = [
    "The exact memory a model may use — Metal reports it, the browser cannot ask",
    "How much memory is free right now",
    "Free disk space",
    "Which models are already downloaded",
    "How long anything actually takes on this machine",
  ];
  return out;
}

export default probeBrowser;
