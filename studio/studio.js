/**
 * Pluto Studio UI Controller & State Manager
 */

let state = {
  activeAsset: null,
  assets: [],
  gpuStatus: null,
  isPlaying: false,
  duration: 4.0,
  width: 1024,
  height: 576,
  isGenerating: false,
};

const elements = {
  gpuStatusDot: document.getElementById('gpuStatusDot'),
  gpuStatusText: document.getElementById('gpuStatusText'),
  vramText: document.getElementById('vramText'),
  costText: document.getElementById('costText'),
  btnLaunchGpu: document.getElementById('btnLaunchGpu'),
  gpuActionLabel: document.getElementById('gpuActionLabel'),
  btnRefresh: document.getElementById('btnRefresh'),
  assetGrid: document.getElementById('assetGrid'),
  assetCount: document.getElementById('assetCount'),
  mainVideoPlayer: document.getElementById('mainVideoPlayer'),
  resolutionTag: document.getElementById('resolutionTag'),
  loadingOverlay: document.getElementById('loadingOverlay'),
  loadingText: document.getElementById('loadingText'),
  progressBarFill: document.getElementById('progressBarFill'),
  btnPlayPause: document.getElementById('btnPlayPause'),
  playIcon: document.getElementById('playIcon'),
  timecodeDisplay: document.getElementById('timecodeDisplay'),
  btnQuickUpscale: document.getElementById('btnQuickUpscale'),
  btnDownloadCurrent: document.getElementById('btnDownloadCurrent'),
  promptInput: document.getElementById('promptInput'),
  btnEnhance: document.getElementById('btnEnhance'),
  btnGenerate: document.getElementById('btnGenerate'),
  seedInput: document.getElementById('seedInput'),
  durationSelector: document.getElementById('durationSelector'),
  aspectSelector: document.getElementById('aspectSelector'),
  inspResolution: document.getElementById('inspResolution'),
  inspDuration: document.getElementById('inspDuration'),
  inspSeed: document.getElementById('inspSeed'),
  inspSize: document.getElementById('inspSize'),
  btnRun4kUpscale: document.getElementById('btnRun4kUpscale'),
  upscaleStatus: document.getElementById('upscaleStatus'),
  timelineTrackContainer: document.getElementById('timelineTrackContainer'),
  timelinePlayhead: document.getElementById('timelinePlayhead'),
  timelineClipName: document.getElementById('timelineClipName'),
  timelineClipDur: document.getElementById('timelineClipDur'),
  timelineScrubTime: document.getElementById('timelineScrubTime'),
};

// ── Initialization ──────────────────────────────────────────
async function init() {
  setupEventListeners();
  await refreshStatus();
  await refreshAssets();
  setInterval(refreshStatus, 4000);
}

function setupEventListeners() {
  // Play / Pause
  elements.btnPlayPause.addEventListener('click', togglePlayPause);
  elements.mainVideoPlayer.addEventListener('timeupdate', updatePlaybackProgress);
  elements.mainVideoPlayer.addEventListener('ended', () => setPlaying(false));

  // Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && document.activeElement !== elements.promptInput) {
      e.preventDefault();
      togglePlayPause();
    } else if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      triggerGenerate();
    }
  });

  // Prompt Enhance
  elements.btnEnhance.addEventListener('click', async () => {
    const p = elements.promptInput.value.trim();
    if (!p) return;
    try {
      const res = await fetch('/api/enhance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: p })
      });
      const data = await res.json();
      if (data.enhanced_prompt) {
        elements.promptInput.value = data.enhanced_prompt;
      }
    } catch (e) {
      console.error('Enhance failed', e);
    }
  });

  // Preset Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const token = chip.getAttribute('data-token');
      const cur = elements.promptInput.value.trim();
      elements.promptInput.value = cur ? `${cur}, ${token}` : token;
    });
  });

  // Duration Selector
  elements.durationSelector.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      elements.durationSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.duration = parseFloat(btn.getAttribute('data-val'));
    });
  });

  // Aspect Selector
  elements.aspectSelector.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      elements.aspectSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.width = parseInt(btn.getAttribute('data-w'));
      state.height = parseInt(btn.getAttribute('data-h'));
      elements.resolutionTag.textContent = `${state.width} × ${state.height}`;
    });
  });

  // Generate Button
  elements.btnGenerate.addEventListener('click', triggerGenerate);

  // 4K Upscale Buttons
  elements.btnRun4kUpscale.addEventListener('click', trigger4kUpscale);
  elements.btnQuickUpscale.addEventListener('click', trigger4kUpscale);

  // Download Current
  elements.btnDownloadCurrent.addEventListener('click', () => {
    if (state.activeAsset) {
      const a = document.createElement('a');
      a.href = `/api/media/${state.activeAsset.id}.mp4`;
      a.download = `${state.activeAsset.id}.mp4`;
      a.click();
    }
  });

  // GPU Launch Button
  elements.btnLaunchGpu.addEventListener('click', toggleGpuLaunch);
  elements.btnRefresh.addEventListener('click', () => { refreshStatus(); refreshAssets(); });

  // Timeline Scrubbing
  elements.timelineTrackContainer.addEventListener('click', (e) => {
    const rect = elements.timelineTrackContainer.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    if (elements.mainVideoPlayer.duration) {
      elements.mainVideoPlayer.currentTime = pos * elements.mainVideoPlayer.duration;
    }
  });
}

// ── Telemetry & Status ──────────────────────────────────────
async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state.gpuStatus = data;

    if (data.gpu_online && data.worker_ready) {
      elements.gpuStatusDot.className = 'status-dot online';
      elements.gpuStatusText.textContent = `Spot GPU Online (L40S)`;
      elements.vramText.textContent = `${data.worker?.vram_allocated_gib || '43.3'} / 44 GiB`;
      elements.costText.textContent = `$${data.estimated_cost_usd?.toFixed(2) || '0.00'}`;
      elements.gpuActionLabel.textContent = 'Terminate GPU';
    } else if (data.gpu_online && !data.worker_ready) {
      elements.gpuStatusDot.className = 'status-dot warming';
      elements.gpuStatusText.textContent = `Warming VRAM (~170s)...`;
      elements.gpuActionLabel.textContent = 'Terminate GPU';
    } else {
      elements.gpuStatusDot.className = 'status-dot offline';
      elements.gpuStatusText.textContent = `GPU Offline (Mock Mode)`;
      elements.vramText.textContent = `-- / 44 GiB`;
      elements.costText.textContent = `$0.00`;
      elements.gpuActionLabel.textContent = 'Launch Spot GPU';
    }
  } catch (e) {
    console.error('Status fetch failed', e);
  }
}

async function toggleGpuLaunch() {
  if (state.gpuStatus?.gpu_online) {
    if (confirm('Terminate GPU instance to stop billing?')) {
      await fetch('/api/gpu/terminate', { method: 'POST' });
      await refreshStatus();
    }
  } else {
    elements.gpuActionLabel.textContent = 'Launching...';
    await fetch('/api/gpu/launch', { method: 'POST' });
    setTimeout(refreshStatus, 2000);
  }
}

// ── Asset Management ────────────────────────────────────────
async function refreshAssets() {
  try {
    const res = await fetch('/api/assets');
    const data = await res.json();
    state.assets = data.assets || [];
    elements.assetCount.textContent = state.assets.length;

    renderAssetGrid();

    // Select first asset if none active
    if (!state.activeAsset && state.assets.length > 0) {
      selectAsset(state.assets[0]);
    }
  } catch (e) {
    console.error('Asset fetch error', e);
  }
}

function renderAssetGrid() {
  if (state.assets.length === 0) {
    elements.assetGrid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎬</div>
        <p>No video clips yet.<br>Type a prompt below to generate!</p>
      </div>`;
    return;
  }

  elements.assetGrid.innerHTML = state.assets.map(a => `
    <div class="asset-card ${state.activeAsset?.id === a.id ? 'active' : ''}" onclick="selectAssetById('${a.id}')">
      <img class="asset-thumb" src="/api/media/${a.id}.png" onerror="this.src=''" alt="thumb">
      <div class="asset-details">
        <div class="asset-name">${a.prompt ? a.prompt.substring(0, 32) + '...' : a.id}</div>
        <div class="asset-sub">${a.width}×${a.height} · ${a.duration_sec || 4}s</div>
        ${a.is_upscaled ? '<span class="tag-4k">4K MASTER</span>' : ''}
      </div>
    </div>
  `).join('');
}

window.selectAssetById = function(id) {
  const target = state.assets.find(a => a.id === id);
  if (target) selectAsset(target);
};

function selectAsset(asset) {
  state.activeAsset = asset;
  renderAssetGrid();

  // Load into video player
  elements.mainVideoPlayer.src = `/api/media/${asset.id}.mp4`;
  elements.mainVideoPlayer.load();
  elements.resolutionTag.textContent = `${asset.width} × ${asset.height}`;

  // Update Inspector
  elements.inspResolution.textContent = `${asset.width} × ${asset.height} ${asset.is_upscaled ? '(4K UHD)' : ''}`;
  elements.inspDuration.textContent = `${asset.duration_sec || 4}s`;
  elements.inspSeed.textContent = asset.seed || '--';
  elements.inspSize.textContent = asset.size_mb ? `${asset.size_mb} MB` : '--';

  // Update Timeline
  elements.timelineClipName.textContent = asset.prompt ? asset.prompt.substring(0, 24) + '...' : asset.id;
  elements.timelineClipDur.textContent = `${asset.duration_sec || 4}s`;
}

// ── Playback Controls ───────────────────────────────────────
function togglePlayPause() {
  if (elements.mainVideoPlayer.paused) {
    elements.mainVideoPlayer.play();
    setPlaying(true);
  } else {
    elements.mainVideoPlayer.pause();
    setPlaying(false);
  }
}

function setPlaying(isPlaying) {
  state.isPlaying = isPlaying;
  elements.playIcon.innerHTML = isPlaying 
    ? `<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>`
    : `<polygon points="5 3 19 12 5 21 5 3"></polygon>`;
}

function updatePlaybackProgress() {
  const cur = elements.mainVideoPlayer.currentTime || 0;
  const dur = elements.mainVideoPlayer.duration || state.duration || 4.0;
  const pct = (cur / dur) * 100;
  elements.timelinePlayhead.style.left = `${pct}%`;

  const curFormatted = `00:${String(Math.floor(cur)).padStart(2, '0')}.${Math.floor((cur % 1) * 10)}`;
  const durFormatted = `00:${String(Math.floor(dur)).padStart(2, '0')}.0`;
  elements.timecodeDisplay.textContent = `${curFormatted} / ${durFormatted}`;
  elements.timelineScrubTime.textContent = `${curFormatted} / ${durFormatted}`;
}

// ── Generation Workflow ─────────────────────────────────────
async function triggerGenerate() {
  const prompt = elements.promptInput.value.trim();
  if (!prompt) return;

  state.isGenerating = true;
  elements.loadingOverlay.style.display = 'flex';
  elements.loadingText.textContent = state.gpuStatus?.gpu_online 
    ? 'Dispatching inference to L40S Spot GPU (12s)...' 
    : 'Simulating video generation in Mock mode...';

  try {
    const seedVal = elements.seedInput.value ? parseInt(elements.seedInput.value) : null;
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        seconds: state.duration,
        width: state.width,
        height: state.height,
        seed: seedVal,
      })
    });

    const data = await res.json();
    const jobId = data.job_id;

    // Poll until completed
    const pollInterval = setInterval(async () => {
      await refreshAssets();
      const ready = state.assets.find(a => a.id === jobId && a.status === 'completed');
      if (ready) {
        clearInterval(pollInterval);
        state.isGenerating = false;
        elements.loadingOverlay.style.display = 'none';
        selectAsset(ready);
      }
    }, 2000);

  } catch (e) {
    console.error('Generation error', e);
    state.isGenerating = false;
    elements.loadingOverlay.style.display = 'none';
  }
}

// ── 4K Super-Resolution Export ──────────────────────────────
async function trigger4kUpscale() {
  if (!state.activeAsset) return;
  elements.upscaleStatus.textContent = '⚡ Running CoreML 4K upscale on Apple Silicon...';
  
  try {
    const res = await fetch('/api/upscale-4k', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        asset_id: state.activeAsset.id,
        scale: 4,
      })
    });
    const data = await res.json();
    const target4kId = data.output_id;

    const poll4k = setInterval(async () => {
      await refreshAssets();
      const ready4k = state.assets.find(a => a.id === target4kId);
      if (ready4k) {
        clearInterval(poll4k);
        elements.upscaleStatus.textContent = '✓ 4K UHD Master Ready!';
        selectAsset(ready4k);
      }
    }, 2000);
  } catch (e) {
    elements.upscaleStatus.textContent = `Error: ${e.message}`;
  }
}

window.addEventListener('DOMContentLoaded', init);
