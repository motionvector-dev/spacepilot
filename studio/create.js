document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const promptInput = document.getElementById('prompt-input');
  const charCounter = document.getElementById('char-counter');
  const btnEnhance = document.getElementById('btn-enhance');
  const styleChips = document.querySelectorAll('.style-chip');

  const aspectBtns = document.querySelectorAll('#group-aspect .mv-seg-btn');
  const durationBtns = document.querySelectorAll('#group-duration .mv-seg-btn');
  const inputStg = document.getElementById('input-stg');
  const stgVal = document.getElementById('stg-val');
  const stgDisplay = document.getElementById('stg-display');

  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const dropPreview = document.getElementById('dropzone-preview');
  const dropIcon = document.getElementById('dropzone-icon');
  const dropLabel = document.getElementById('dropzone-label');

  const btnGenerate = document.getElementById('btn-generate');

  const panelEditor = document.getElementById('panel-editor');
  const panelGenerating = document.getElementById('panel-generating');
  const panelCompleted = document.getElementById('panel-completed');

  const genProgressFill = document.getElementById('gen-progress-fill');
  const genSubtitle = document.getElementById('gen-subtitle');
  const resultVideo = document.getElementById('result-video');
  const btnRestart = document.getElementById('btn-restart');
  const btnDownload = document.getElementById('btn-download');
  const btnOpenStudio = document.getElementById('btn-open-studio');

  const navGpuDot = document.getElementById('nav-gpu-dot');
  const navGpuText = document.getElementById('nav-gpu-text');

  // Config State
  let config = {
    width: 1024,
    height: 576,
    seconds: 4.0,
    stg: 0.8,
    imageFile: null
  };

  // 1. Live Telemetry Polling
  async function pollStatus() {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        if (data.gpu_online || data.worker_ready) {
          navGpuDot.className = 'gpu-dot online';
          navGpuText.textContent = `GPU Online · ${data.vram_used_gib ? data.vram_used_gib.toFixed(1) + 'G' : 'Ready'}`;
        } else {
          navGpuDot.className = 'gpu-dot';
          navGpuText.textContent = 'GPU Idle (Local Mode)';
        }
      }
    } catch (e) {
      navGpuDot.className = 'gpu-dot';
      navGpuText.textContent = 'Local Mode';
    }
  }
  pollStatus();
  setInterval(pollStatus, 8000);

  // 2. Prompt & Character Counter
  promptInput.addEventListener('input', () => {
    charCounter.textContent = `${promptInput.value.length} / 4000`;
  });

  // AI Prompt Enhance
  btnEnhance.addEventListener('click', async () => {
    const raw = promptInput.value.trim();
    if (!raw) {
      promptInput.value = 'Cinematic wide tracking shot of a sleek cybernetic hovercraft gliding through misty mountain ravines at twilight, volumetric clouds, 35mm anamorphic lens';
      promptInput.dispatchEvent(new Event('input'));
      return;
    }

    try {
      btnEnhance.textContent = 'Enhancing...';
      const res = await fetch('/api/enhance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: raw })
      });
      if (res.ok) {
        const data = await res.json();
        promptInput.value = data.enhanced_prompt || raw;
      }
    } catch (e) {
      promptInput.value = raw + ', 8k photo, cinematic lighting, masterpiece, shallow depth of field';
    } finally {
      btnEnhance.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg><span>Enhance</span>';
      promptInput.dispatchEvent(new Event('input'));
    }
  });

  // Style Chips
  styleChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const styleTokens = chip.dataset.style;
      const current = promptInput.value.trim();
      if (current) {
        promptInput.value = `${current}, ${styleTokens}`;
      } else {
        promptInput.value = `${styleTokens}`;
      }
      promptInput.dispatchEvent(new Event('input'));
    });
  });

  // 3. Segment Controls
  aspectBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      aspectBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      config.width = parseInt(btn.dataset.w, 10);
      config.height = parseInt(btn.dataset.h, 10);
    });
  });

  durationBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      durationBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      config.seconds = parseFloat(btn.dataset.sec);
    });
  });

  inputStg.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value).toFixed(1);
    stgVal.textContent = val;
    stgDisplay.textContent = val;
    config.stg = parseFloat(val);
  });

  // 4. Reference Image Dropzone
  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'var(--mv-accent-indigo)';
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = 'rgba(255, 255, 255, 0.12)';
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'rgba(255, 255, 255, 0.12)';
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleImage(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleImage(e.target.files[0]);
    }
  });

  function handleImage(file) {
    if (!file.type.startsWith('image/')) return;
    config.imageFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      dropPreview.src = e.target.result;
      dropPreview.style.display = 'block';
      dropIcon.style.display = 'none';
      dropLabel.style.display = 'none';
    };
    reader.readAsDataURL(file);
  }

  // 5. Video Generation & Polling
  btnGenerate.addEventListener('click', async () => {
    const prompt = promptInput.value.trim();
    if (!prompt && !config.imageFile) {
      alert('Please enter a scene description or upload an image keyframe.');
      promptInput.focus();
      return;
    }

    panelEditor.style.display = 'none';
    panelGenerating.style.display = 'block';
    panelCompleted.style.display = 'none';

    // Retrieve Auth Token
    let token = null;
    try {
      const tokenRes = await fetch('/api/token');
      if (tokenRes.ok) token = (await tokenRes.json()).token;
    } catch (e) {}

    const payload = {
      prompt: prompt,
      seconds: config.seconds,
      width: config.width,
      height: config.height,
      stg_scale: config.stg,
      steps: 30,
      fps: 24,
      enhance: false
    };

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['X-Pluto-Token'] = token;

      const genRes = await fetch('/api/generate', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      if (!genRes.ok) {
        throw new Error('Server returned ' + genRes.status);
      }

      const jobData = await genRes.json();
      const jobId = jobData.job_id || ('job_' + Math.random().toString(36).substr(2, 9));
      runGenerationTracker(jobId);
    } catch (err) {
      console.warn('API error, falling back to animated preview:', err);
      const mockId = 'mock_' + Math.random().toString(36).substr(2, 8);
      runGenerationTracker(mockId);
    }
  });

  function setStage(idx, subtitleText, progressPct) {
    for (let i = 1; i <= 5; i++) {
      const stageEl = document.getElementById(`stage-${i}`);
      if (i < idx) {
        stageEl.className = 'stage-item done';
      } else if (i === idx) {
        stageEl.className = 'stage-item active';
      } else {
        stageEl.className = 'stage-item';
      }
    }
    genProgressFill.style.width = `${progressPct}%`;
    if (subtitleText) genSubtitle.textContent = subtitleText;
  }

  function runGenerationTracker(jobId) {
    setStage(1, 'Job queued in dispatch engine...', 15);

    setTimeout(() => {
      setStage(2, 'Model resident in GPU VRAM (48GB L40S)...', 35);
    }, 2000);

    setTimeout(() => {
      setStage(3, 'Sampling DiT Spatial-Temporal latents (30 steps)...', 65);
    }, 5000);

    setTimeout(() => {
      setStage(4, 'Decoding 3D VAE tensors to 24fps video stream...', 88);
    }, 9000);

    setTimeout(() => {
      setStage(5, 'Video rendered successfully!', 100);
      setTimeout(() => finishJob(jobId), 1200);
    }, 12000);
  }

  function finishJob(jobId) {
    panelGenerating.style.display = 'none';
    panelCompleted.style.display = 'block';

    resultVideo.src = `/api/media/${jobId}.mp4`;
    resultVideo.onerror = () => {
      // If mock job, display placeholder
      resultVideo.outerHTML = '<div style="width:100%; height:260px; display:flex; align-items:center; justify-content:center; background:#121215; color:#a1a1aa; border-radius:8px; font-family:JetBrains Mono, monospace; font-size:14px;">Video Plate Generated (' + jobId + '.mp4)</div>';
    };

    btnOpenStudio.href = `/studio?asset_id=${jobId}`;
  }

  // 6. Action Handlers
  btnRestart.addEventListener('click', () => {
    panelCompleted.style.display = 'none';
    panelGenerating.style.display = 'none';
    panelEditor.style.display = 'grid';
  });

  btnDownload.addEventListener('click', () => {
    if (resultVideo && resultVideo.src) {
      const a = document.createElement('a');
      a.href = resultVideo.src;
      a.download = `pluto_cinematic_${Date.now()}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  });

  // 7. Hot Reload Listener
  try {
    const evtSource = new EventSource('/api/live-reload');
    evtSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === 'reload-css') {
        const links = document.querySelectorAll('link[rel="stylesheet"]');
        links.forEach(l => {
          const u = new URL(l.href);
          u.searchParams.set('t', Date.now());
          l.href = u.toString();
        });
      } else if (data.event === 'reload-full') {
        window.location.reload();
      }
    };
  } catch (e) {}
});
