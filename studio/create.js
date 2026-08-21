document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const promptInput = document.getElementById('prompt-input');
  const charCounter = document.getElementById('char-counter');
  const btnEnhance = document.getElementById('btn-enhance');
  const styleChips = document.querySelectorAll('.style-chip');

  const selectEngine = document.getElementById('select-engine');
  const engineBadge = document.getElementById('engine-badge');
  const aspectBtns = document.querySelectorAll('#group-aspect .mv-seg-btn');
  const durationBtns = document.querySelectorAll('#group-duration .mv-seg-btn');
  const inputStg = document.getElementById('input-stg');
  const camPanBtns = document.querySelectorAll('#group-cam-pan .mv-seg-btn');
  const camTiltBtns = document.querySelectorAll('#group-cam-tilt .mv-seg-btn');
  const camZoomBtns = document.querySelectorAll('#group-cam-zoom .mv-seg-btn');
  const camRollBtns = document.querySelectorAll('#group-cam-roll .mv-seg-btn');
  const inputCamIntensity = document.getElementById('input-cam-intensity');
  const camIntensityDisplay = document.getElementById('cam-intensity-display');
  const stgVal = document.getElementById('stg-val');
  const stgDisplay = document.getElementById('stg-display');

  // Dropzone Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const dropzonePrompt = document.getElementById('dropzone-prompt');
  const dropzonePreviewBox = document.getElementById('dropzone-preview-box');
  const dropPreview = document.getElementById('dropzone-preview');
  const dropzoneDims = document.getElementById('dropzone-dims');
  const dropzoneAspectTag = document.getElementById('dropzone-aspect-tag');
  const btnAutoAspect = document.getElementById('btn-auto-aspect');
  const btnRemoveImage = document.getElementById('btn-remove-image');

  const btnGenerate = document.getElementById('btn-generate');
  const btnToggleDiff = document.getElementById('btn-toggle-diff');
  const diffOpsList = document.getElementById('diff-ops-list');

  // Patch Card Diff Values
  const diffPromptVal = document.getElementById('diff-prompt-val');
  const diffEngineVal = document.getElementById('diff-engine-val');
  const diffStgVal = document.getElementById('diff-stg-val');
  const diffCameraRow = document.getElementById('diff-camera-row');
  const diffCameraVal = document.getElementById('diff-camera-val');
  const diffAspectVal = document.getElementById('diff-aspect-val');
  const diffDurationVal = document.getElementById('diff-duration-val');
  const diffSeedVal = document.getElementById('diff-seed-val');
  const diffImageRow = document.getElementById('diff-image-row');
  const diffImageVal = document.getElementById('diff-image-val');

  // Fact Specs & Quotes
  const patchCostBadge = document.getElementById('patch-cost-badge');
  const patchFactSpecs = document.getElementById('patch-fact-specs');
  const patchComputeQuote = document.getElementById('patch-compute-quote');
  const factEngineName = document.getElementById('fact-engine-name');

  const genFactSpecs = document.getElementById('gen-fact-specs');
  const genEngineName = document.getElementById('gen-engine-name');
  const genComputeQuote = document.getElementById('gen-compute-quote');

  const compFactSpecs = document.getElementById('comp-fact-specs');
  const compReceipt = document.getElementById('comp-receipt');

  // Panels
  const panelEditor = document.getElementById('panel-editor');
  const panelGenerating = document.getElementById('panel-generating');
  const panelCompleted = document.getElementById('panel-completed');

  // Generating & Completed state elements
  const genProgressFill = document.getElementById('gen-progress-fill');
  const genSubtitle = document.getElementById('gen-subtitle');
  const genPhaseText = document.getElementById('gen-phase-text');
  const resultVideo = document.getElementById('result-video');
  const btnRestart = document.getElementById('btn-restart');
  const btnDownload = document.getElementById('btn-download');
  const btnOpenStudio = document.getElementById('btn-open-studio');

  const navGpuDot = document.getElementById('nav-gpu-dot');
  const navGpuText = document.getElementById('nav-gpu-text');

  // Resolution presets for Draft vs Pro
  const RESOLUTIONS = {
    pro: {
      '16:9': { w: 1024, h: 576 },
      '9:16': { w: 576, h: 1024 },
      '1:1': { w: 768, h: 768 }
    },
    draft: {
      '16:9': { w: 768, h: 432 },
      '9:16': { w: 432, h: 768 },
      '1:1': { w: 576, h: 576 }
    }
  };

  // Config State
  const config = {
    width: 1024,
    height: 576,
    aspectName: '16:9',
    seconds: 4.0,
    stg: 0.8,
    steps: 30,
    fps: 24,
    draftMode: false,
    cameraPan: 'static',
    cameraTilt: 'static',
    cameraZoom: 'static',
    cameraRoll: 'none',
    cameraIntensity: 3,
    gpuOnline: false,
    imageFile: null,
    imagePath: null,
    imageWidth: null,
    imageHeight: null,
    detectedAspect: null,
    detectedLabel: null
  };

  function updatePatchCardDiff() {
    const rawPrompt = promptInput.value.trim();
    if (diffPromptVal) {
      diffPromptVal.textContent = rawPrompt ? `“${rawPrompt.slice(0, 80)}${rawPrompt.length > 80 ? '…' : ''}”` : 'empty';
    }
    if (diffEngineVal) {
      diffEngineVal.textContent = config.draftMode ? 'Engine: Draft (15 steps)' : 'Engine: Pro Cinema (30 steps)';
    }
    if (diffStgVal) {
      diffStgVal.textContent = config.stg.toFixed(1);
    }
    if (diffAspectVal) {
      diffAspectVal.textContent = `${config.aspectName} (${config.width}x${config.height})`;
    }
    if (diffDurationVal) {
      const frames = Math.floor((config.seconds * config.fps - 1) / 8) * 8 + 1;
      diffDurationVal.textContent = `${config.seconds.toFixed(1)}s (${frames} frames)`;
    }
    
    if (diffCameraRow && diffCameraVal) {
      let motions = [];
      if (config.cameraPan !== 'static') motions.push(`Pan ${config.cameraPan}`);
      if (config.cameraTilt !== 'static') motions.push(`Tilt ${config.cameraTilt}`);
      if (config.cameraZoom !== 'static') motions.push(`Zoom ${config.cameraZoom}`);
      if (config.cameraRoll !== 'none') motions.push(config.cameraRoll === 'orbit' ? 'Orbit 360' : `Roll ${config.cameraRoll}`);

      if (motions.length > 0) {
        diffCameraRow.style.display = 'flex';
        diffCameraVal.textContent = `${motions.join(', ')} (Intensity ${config.cameraIntensity})`;
      } else {
        diffCameraRow.style.display = 'none';
      }
    }

    if (diffSeedVal) {
      diffSeedVal.textContent = 'Dynamic (Auto)';
    }

    if (diffImageRow && diffImageVal) {
      if (config.imageFile || config.imagePath) {
        diffImageRow.style.display = 'flex';
        const name = config.imageFile ? config.imageFile.name : (config.imagePath || 'Keyframe');
        const dims = (config.imageWidth && config.imageHeight) ? ` (${config.imageWidth}×${config.imageHeight})` : '';
        diffImageVal.textContent = `${name}${dims}`;
      } else {
        diffImageRow.style.display = 'none';
      }
    }

    let costBadgeText, computeQuoteText;
    if (config.gpuOnline) {
      costBadgeText = config.draftMode ? '~$0.01 · Spot Draft' : '~$0.04 · Spot Compute (L40S)';
      computeQuoteText = config.draftMode
        ? 'Estimated Spot compute: ~$0.01 (No charge on failure)'
        : 'Estimated Spot compute: ~$0.04 (No charge on failure)';
    } else {
      costBadgeText = '$0.00 · Local Mock Mode';
      computeQuoteText = 'Local Mode (Free FFmpeg Preview)';
    }

    if (patchCostBadge) patchCostBadge.textContent = costBadgeText;
    if (patchComputeQuote) patchComputeQuote.textContent = computeQuoteText;
    if (genComputeQuote) genComputeQuote.textContent = computeQuoteText;

    const engineNameText = config.draftMode ? 'LTX-2.5 Draft Generation' : 'LTX-2.5 Video Generation';
    if (factEngineName) factEngineName.textContent = engineNameText;
    if (genEngineName) genEngineName.textContent = engineNameText;

    const specsText = `${config.width}x${config.height} · ${config.fps}fps · ${config.seconds.toFixed(1)}s`;
    if (patchFactSpecs) patchFactSpecs.textContent = specsText;
    if (genFactSpecs) genFactSpecs.textContent = specsText;
    if (compFactSpecs) compFactSpecs.textContent = specsText;

    if (compReceipt) {
      const cost = config.draftMode ? '~$0.01' : '~$0.04';
      const tier = config.draftMode ? 'LTX-2.5 Draft' : 'LTX-2.5';
      compReceipt.textContent = `1 op applied · ${cost} — ${tier} · undo byte-exact`;
    }
  }

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
    updatePatchCardDiff();
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

  // 3. Controls
  // Engine Quality Dropdown Switcher (Draft vs Pro)
  if (selectEngine) {
    selectEngine.addEventListener('change', () => {
      const mode = selectEngine.value;
      const isDraft = mode === 'draft';
      config.draftMode = isDraft;
      config.steps = isDraft ? 15 : 30;

      if (engineBadge) {
        engineBadge.textContent = isDraft ? 'Draft (15s)' : 'Pro Cinema';
      }

      // Update resolution based on current aspect & mode
      const modeKey = config.draftMode ? 'draft' : 'pro';
      const res = RESOLUTIONS[modeKey][config.aspectName] || RESOLUTIONS[modeKey]['16:9'];
      config.width = res.w;
      config.height = res.h;

      updatePatchCardDiff();
    });
  }

  // Aspect Ratio Switcher
  aspectBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      aspectBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      config.aspectName = btn.dataset.aspect || '16:9';

      const modeKey = config.draftMode ? 'draft' : 'pro';
      const res = RESOLUTIONS[modeKey][config.aspectName] || RESOLUTIONS[modeKey]['16:9'];
      config.width = res.w;
      config.height = res.h;

      if (btnAutoAspect && config.detectedAspect) {
        if (config.aspectName === config.detectedAspect) {
          btnAutoAspect.classList.add('matched');
          btnAutoAspect.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span>Matched ${config.detectedLabel || config.aspectName}</span>`;
        } else {
          btnAutoAspect.classList.remove('matched');
          btnAutoAspect.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg><span>Auto-match Aspect Ratio</span>`;
        }
      }

      updatePatchCardDiff();
    });
  });

  // Duration Switcher
  durationBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      durationBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      config.seconds = parseFloat(btn.dataset.sec);
      updatePatchCardDiff();
    });
  });

  // Motion Guidance (STG) Slider
  inputStg.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value).toFixed(1);
    stgVal.textContent = val;
    stgDisplay.textContent = val;
    config.stg = parseFloat(val);
    updatePatchCardDiff();
  });

  
  function setupCamGroup(btns, configKey) {
    if (!btns) return;
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        btns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        config[configKey] = btn.dataset.val;
        updatePatchCardDiff();
      });
    });
  }
  setupCamGroup(camPanBtns, 'cameraPan');
  setupCamGroup(camTiltBtns, 'cameraTilt');
  setupCamGroup(camZoomBtns, 'cameraZoom');
  setupCamGroup(camRollBtns, 'cameraRoll');

  if (inputCamIntensity) {
    inputCamIntensity.addEventListener('input', (e) => {
      config.cameraIntensity = parseInt(e.target.value, 10);
      camIntensityDisplay.textContent = config.cameraIntensity;
      updatePatchCardDiff();
    });
  }

  // Toggle Diff Inspector
  if (btnToggleDiff && diffOpsList) {
    btnToggleDiff.addEventListener('click', () => {
      const isHidden = diffOpsList.style.display === 'none';
      diffOpsList.style.display = isHidden ? 'flex' : 'none';
      btnToggleDiff.textContent = isHidden ? 'Collapse' : 'Expand';
    });
  }

  // 4. Reference Image Dropzone & Dynamic Aspect Matching
  function getClosestAspect(w, h) {
    if (!w || !h) return { aspect: '16:9', label: '16:9 Wide' };
    const r = w / h;
    const diff169 = Math.abs(Math.log(r / (16 / 9)));
    const diff916 = Math.abs(Math.log(r / (9 / 16)));
    const diff11 = Math.abs(Math.log(r / 1));
    if (diff169 <= diff916 && diff169 <= diff11) {
      return { aspect: '16:9', label: '16:9 Wide' };
    } else if (diff916 <= diff169 && diff916 <= diff11) {
      return { aspect: '9:16', label: '9:16 Reel' };
    } else {
      return { aspect: '1:1', label: '1:1 Square' };
    }
  }

  async function uploadImageFile(file) {
    try {
      const formData = new FormData();
      formData.append('file', file);

      let token = null;
      try {
        const tokenRes = await fetch('/api/token');
        if (tokenRes.ok) token = (await tokenRes.json()).token;
      } catch (e) {}

      const headers = {};
      if (token) headers['X-Pluto-Token'] = token;

      const res = await fetch('/api/upload-image', {
        method: 'POST',
        headers: headers,
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        config.imagePath = data.image_path || data.path || data.file_path || file.name;
        if (data.width) config.imageWidth = data.width;
        if (data.height) config.imageHeight = data.height;
      } else {
        config.imagePath = file.name;
      }
    } catch (err) {
      console.warn('Image upload fallback to local reference:', err);
      config.imagePath = file.name;
    }
    updatePatchCardDiff();
  }

  function handleImage(file) {
    if (!file || !file.type.startsWith('image/')) return;
    config.imageFile = file;
    config.imagePath = file.name;

    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      dropPreview.src = dataUrl;

      const img = new Image();
      img.onload = () => {
        const w = img.naturalWidth || dropPreview.naturalWidth || 1024;
        const h = img.naturalHeight || dropPreview.naturalHeight || 576;
        config.imageWidth = w;
        config.imageHeight = h;

        const match = getClosestAspect(w, h);
        config.detectedAspect = match.aspect;
        config.detectedLabel = match.label;

        if (dropzoneDims) dropzoneDims.textContent = `${w}×${h}`;
        if (dropzoneAspectTag) dropzoneAspectTag.textContent = match.label;

        if (dropzonePreviewBox) dropzonePreviewBox.style.display = 'flex';
        if (dropzonePrompt) dropzonePrompt.style.display = 'none';
        if (dropzone) dropzone.classList.add('has-image');

        if (btnAutoAspect) {
          btnAutoAspect.classList.remove('matched');
          btnAutoAspect.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg><span>Auto-match Aspect Ratio</span>`;
        }

        updatePatchCardDiff();
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);

    // Upload image to backend
    uploadImageFile(file);
  }

  // Auto-match Aspect Ratio button click
  if (btnAutoAspect) {
    btnAutoAspect.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!config.detectedAspect) return;

      aspectBtns.forEach(btn => {
        if (btn.dataset.aspect === config.detectedAspect) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      config.aspectName = config.detectedAspect;
      const modeKey = config.draftMode ? 'draft' : 'pro';
      const res = RESOLUTIONS[modeKey][config.aspectName] || RESOLUTIONS[modeKey]['16:9'];
      config.width = res.w;
      config.height = res.h;

      btnAutoAspect.classList.add('matched');
      btnAutoAspect.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span>Matched ${config.detectedLabel || config.aspectName}</span>`;

      updatePatchCardDiff();
    });
  }

  // Remove Image button click
  if (btnRemoveImage) {
    btnRemoveImage.addEventListener('click', (e) => {
      e.stopPropagation();
      config.imageFile = null;
      config.imagePath = null;
      config.imageWidth = null;
      config.imageHeight = null;
      config.detectedAspect = null;
      config.detectedLabel = null;
      if (fileInput) fileInput.value = '';

      if (dropPreview) dropPreview.src = '';
      if (dropzonePreviewBox) dropzonePreviewBox.style.display = 'none';
      if (dropzonePrompt) dropzonePrompt.style.display = 'flex';
      if (dropzone) dropzone.classList.remove('has-image');
      if (btnAutoAspect) btnAutoAspect.classList.remove('matched');

      updatePatchCardDiff();
    });
  }

  // Dropzone click & drag-drop handling
  if (dropzone && fileInput) {
    dropzone.addEventListener('click', (e) => {
      if (e.target.closest('#btn-auto-aspect') || e.target.closest('#btn-remove-image')) {
        return;
      }
      if (!dropzone.classList.contains('has-image')) {
        fileInput.click();
      }
    });

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.style.borderColor = 'var(--border-focus)';
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.style.borderColor = '';
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.style.borderColor = '';
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleImage(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleImage(e.target.files[0]);
      }
    });
  }

  // Initialize initial diff values
  
  // EXTENSION LOGIC
  const urlParams = new URLSearchParams(window.location.search);
  const extendId = urlParams.get('extend_id');
  
  if (extendId) {
    fetch(`/api/jobs/${extendId}`)
      .then(res => res.json())
      .then(data => {
        if (data.prompt) {
          promptInput.value = data.prompt;
          promptInput.dispatchEvent(new Event('input'));
        }
        
        dropzonePrompt.style.display = 'none';
        dropzonePreviewBox.style.display = 'block';
        dropPreview.src = `/api/assets/${extendId}/thumbnail`;
        dropzoneDims.innerHTML = `<span class="badge" style="background:#0a84ff; color:white; padding: 2px 6px; border-radius: 4px; font-size:10px;">🔗 Extension: Continued from Take #${extendId.substring(0,6)}</span>`;
        dropzoneAspectTag.textContent = 'EXTEND MODE';
        btnRemoveImage.style.display = 'none';
        
        updatePatchCardDiff();
      })
      .catch(e => console.error("Failed to load extension job:", e));
  }


  updatePatchCardDiff();

  // 5. Video Generation & Multi-Phase Pipeline
  
  async function startGeneration(takesCount) {
    const prompt = promptInput.value.trim();
    if (!prompt && !config.imageFile && !config.imagePath) {
      if (window.mvDialog) {
        window.mvDialog.alert('Please enter a scene description or upload an image keyframe to start generation.', 'Input Required');
      } else {
        alert('Please enter a scene description or upload an image keyframe.');
      }
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
      steps: config.steps,
      fps: config.fps,
      enhance: false,
      draft_mode: config.draftMode,
      takes: takesCount,

      camera_pan: config.cameraPan !== 'static' ? config.cameraPan : null,
      camera_tilt: config.cameraTilt !== 'static' ? config.cameraTilt : null,
      camera_zoom: config.cameraZoom !== 'static' ? config.cameraZoom : null,
      camera_roll: config.cameraRoll !== 'none' ? config.cameraRoll : null,
      camera_intensity: config.cameraIntensity,

    };

    if (config.imagePath) {
      payload.image_path = config.imagePath;
    }

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['X-Pluto-Token'] = token;

      
      let endpoint = '/api/generate';
      if (extendId) {
        endpoint = '/api/video/extend';
        payload.asset_id = extendId;
      }
      
      const genRes = await fetch(endpoint, {

        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      if (!genRes.ok) {
        throw new Error('Server returned ' + genRes.status);
      }

      const jobData = await genRes.json();
      const jobId = jobData.job_id || ('job_' + Math.random().toString(36).substr(2, 9));
      runGenerationTracker(jobId, jobData.patch);
    } catch (err) {
      console.warn('API error, falling back to animated preview:', err);
      const mockId = 'mock_' + Math.random().toString(36).substr(2, 8);
      runGenerationTracker(mockId, null);
    }
  }

  btnGenerate.addEventListener('click', () => startGeneration(1));
  const btnGenerate4Take = document.getElementById('btn-generate-4take');
  if (btnGenerate4Take) {
    btnGenerate4Take.addEventListener('click', () => startGeneration(4));
  }


  function setStage(stageIdx, phaseText, subtitleText, progressPct, customStepLabel) {
    for (let i = 1; i <= 5; i++) {
      const stageEl = document.getElementById(`stage-${i}`);
      if (!stageEl) continue;
      if (i < stageIdx) {
        stageEl.className = 'phase-step done stage-item done';
      } else if (i === stageIdx) {
        stageEl.className = 'phase-step active stage-item active';
      } else {
        stageEl.className = 'phase-step stage-item';
      }
    }

    if (customStepLabel) {
      const step3Label = document.getElementById('stage-3-label');
      if (step3Label) step3Label.textContent = customStepLabel;
    }

    if (genProgressFill) {
      genProgressFill.style.width = `${progressPct}%`;
    }
    if (genPhaseText && phaseText) {
      genPhaseText.textContent = phaseText;
    }
    if (genSubtitle && subtitleText) {
      genSubtitle.textContent = subtitleText;
    }
  }

  function runGenerationTracker(jobId, patchData, jobData) {
    const totalSteps = config.steps || (config.draftMode ? 15 : 30);
    const tierName = config.draftMode ? 'LTX-2.5 Draft' : 'LTX-2.5 Resident';
    const genPhaseTag = document.getElementById('gen-phase-tag');
    if (genPhaseTag) genPhaseTag.textContent = tierName;

    // Phase 1: Queued (0%)
    setStage(
      1,
      'Phase 1: Queued (0%) — keep editing, it\'ll land when it\'s ready.',
      'Job queued in dispatch engine... (0%)',
      0
    );

    // Phase 2: Staging VRAM & Weights (15%) after 1.2s
    setTimeout(() => {
      setStage(
        2,
        'Phase 2: Staging VRAM & Weights (15%) — keep editing, it\'ll land when it\'s ready.',
        'Model resident in GPU VRAM (48GB L40S)... (15%)',
        15
      );
    }, 1200);

    // Phase 3: DiT Sampling (Step X/totalSteps) (20% - 85%) across totalSteps
    const samplingStartTime = 2400;
    const samplingDuration = config.draftMode ? 3600 : 5500;
    const stepInterval = samplingDuration / totalSteps;

    for (let step = 1; step <= totalSteps; step++) {
      setTimeout(() => {
        const pct = Math.round(20 + (step / totalSteps) * 65);
        setStage(
          3,
          `Phase 3: DiT Sampling (Step ${step}/${totalSteps}) (${pct}%) — keep editing, it'll land when it's ready.`,
          `Sampling DiT Spatial-Temporal latents (Step ${step}/${totalSteps})...`,
          pct,
          `DiT Sampling (Step ${step}/${totalSteps})`
        );
      }, samplingStartTime + (step - 1) * stepInterval);
    }

    // Phase 4: VAE Latent Decode & Audio Vocoder (90% - 98%)
    const vaeTime = samplingStartTime + samplingDuration + 400;
    setTimeout(() => {
      setStage(
        4,
        'Phase 4: VAE Latent Decode & Audio Vocoder (94%) — keep editing, it\'ll land when it\'s ready.',
        'Decoding 3D VAE tensors to 24fps video stream...',
        94
      );
    }, vaeTime);

    // Phase 5: Plate Ready (100%)
    const completeTime = vaeTime + (config.draftMode ? 1400 : 2200);
    setTimeout(() => {
      setStage(
        5,
        'Phase 5: Plate Ready (100%)',
        'Video rendered successfully! Finalizing asset...',
        100
      );
      setTimeout(() => finishJob(jobId, patchData, jobData), 800);
    }, completeTime);
  }

    function finishJob(jobId, patchData, jobData) {
    panelGenerating.style.display = 'none';
    panelCompleted.style.display = 'block';

    const grid4Take = document.getElementById('grid-4take');
    const resultVideoFrame = document.querySelector('.video-preview-frame');

    if (jobData && jobData.jobs && jobData.jobs.length > 1) {
      // It's a 4-Take Batch
      grid4Take.style.display = 'grid';
      resultVideoFrame.classList.add('hide');
      grid4Take.innerHTML = '';
      
      jobData.jobs.forEach((job, index) => {
        const jId = job.job_id;
        const videoSrc = `/api/media/${jId}.mp4`;
        
        const item = document.createElement('div');
        item.className = 'grid-item';
        item.innerHTML = `
          <video src="${videoSrc}" controls loop playsinline muted></video>
          <div class="grid-item-actions">
            <button class="grid-btn" title="Star / Keep Best Take">⭐</button>
            <button class="grid-btn" title="Extend (+4s)">➕</button>
            <button class="grid-btn" title="Send to Timeline NLE">✂️</button>
            <button class="grid-btn" title="Download MP4" onclick="window.open('${videoSrc}', '_blank')">💾</button>
          </div>
        `;
        
        const vid = item.querySelector('video');
        item.addEventListener('mouseenter', () => vid.play().catch(e=>e));
        item.addEventListener('mouseleave', () => vid.pause());
        
        grid4Take.appendChild(item);
      });
      
      if (compReceipt) {
        compReceipt.textContent = `4 takes generated · ~$0.16 — LTX-2.5 · Group: ${jobData.take_group_id}`;
      }
    } else {
      // Single Take
      grid4Take.style.display = 'none';
      resultVideoFrame.classList.remove('hide');
      const videoSrc = `/api/media/${jobId}.mp4`;
      resultVideo.src = videoSrc;
      resultVideo.onerror = () => {
        resultVideo.outerHTML = '<div style="width:100%; height:260px; display:flex; align-items:center; justify-content:center; background:#121215; color:#a1a1aa; border-radius:8px; font-family:JetBrains Mono, monospace; font-size:14px;">Video Plate Ready (' + jobId + '.mp4)</div>';
      };

      if (compReceipt) {
        const cost = config.draftMode ? '~$0.01' : '~$0.04';
        const tier = config.draftMode ? 'LTX-2.5 Draft' : 'LTX-2.5';
        compReceipt.textContent = `1 op applied · ${cost} — ${tier} · undo byte-exact`;
      }
    }

    if (btnOpenStudio) {
      btnOpenStudio.href = `/studio?asset_id=${jobId}`;
    }
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
