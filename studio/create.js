document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const promptInput = document.getElementById('prompt-input');
  const charCount = document.getElementById('char-count');
  const btnEnhance = document.getElementById('btn-enhance');
  const presetChips = document.querySelectorAll('.preset-chip');
  
  const aspectBtns = document.querySelectorAll('#aspect-ratio-group .toggle-btn');
  const durationBtns = document.querySelectorAll('#duration-group .toggle-btn');
  const stgSlider = document.getElementById('stg-slider');
  const stgVal = document.getElementById('stg-val');
  
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const dropPreview = document.getElementById('dropzone-preview');
  
  const btnGenerate = document.getElementById('btn-generate');
  
  const panelEditor = document.getElementById('panel-editor');
  const panelGenerating = document.getElementById('panel-generating');
  const panelCompleted = document.getElementById('panel-completed');
  
  const jobIdEl = document.getElementById('job-id');
  const jobEtaEl = document.getElementById('job-eta');
  const progressFill = document.getElementById('progress-fill');
  const resultVideo = document.getElementById('result-video');
  const btnDownload = document.getElementById('btn-download');
  const btnRestart = document.getElementById('btn-restart');
  const btnStudio = document.getElementById('btn-studio');

  let currentMode = new URLSearchParams(window.location.search).get('mode') || 't2v';

  // State
  let config = {
    aspect: '16:9',
    duration: '6s',
    stg: 0.8,
    image: null
  };

  // Init
  if (currentMode === 'i2v') {
    // Optionally highlight the dropzone to encourage upload
    dropzone.style.borderColor = 'var(--accent-cyan)';
  }

  // --- Prompt Logic ---
  promptInput.addEventListener('input', () => {
    charCount.textContent = `${promptInput.value.length}/500`;
  });

  btnEnhance.addEventListener('click', () => {
    const current = promptInput.value.trim();
    if (current) {
      promptInput.value = current + ', 8k resolution, cinematic lighting, highly detailed, photorealistic, masterpiece';
    } else {
      promptInput.value = 'Cinematic wide shot of a futuristic city, neon lights reflecting on wet streets, 8k resolution, masterpiece';
    }
    promptInput.dispatchEvent(new Event('input'));
  });

  presetChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const style = chip.textContent;
      const current = promptInput.value.trim();
      if (current) {
        promptInput.value = `${style} style: ${current}`;
      } else {
        promptInput.value = `${style} style: `;
      }
      promptInput.dispatchEvent(new Event('input'));
    });
  });

  // --- Controls Logic ---
  const handleToggle = (btns, key) => {
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        btns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        config[key] = btn.dataset.val;
      });
    });
  };

  handleToggle(aspectBtns, 'aspect');
  handleToggle(durationBtns, 'duration');

  stgSlider.addEventListener('input', (e) => {
    stgVal.textContent = parseFloat(e.target.value).toFixed(1);
    config.stg = parseFloat(e.target.value);
  });

  // --- Dropzone Logic ---
  dropzone.addEventListener('click', () => fileInput.click());
  
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-active');
  });
  
  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('drag-active');
  });
  
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-active');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  });
  
  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  });

  function handleFile(file) {
    if (!file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      dropPreview.src = e.target.result;
      dropPreview.style.display = 'block';
      config.image = file;
    };
    reader.readAsDataURL(file);
  }

  // --- Generation Logic ---
  btnGenerate.addEventListener('click', async () => {
    if (!promptInput.value.trim() && !config.image) {
      alert('Please enter a prompt or attach an image.');
      return;
    }

    panelEditor.style.display = 'none';
    panelGenerating.style.display = 'block';
    
    const jobId = 'job_' + Math.random().toString(36).substr(2, 9);
    jobIdEl.textContent = jobId;
    
    try {
      // Mock /api/token request
      const tokenRes = await fetch('/api/token', { headers: { 'X-Pluto-Token': 'true' } }).catch(() => null);
      
      // Simulate polling /api/status/{job_id}
      simulateGeneration(jobId);
    } catch (err) {
      console.error(err);
      simulateGeneration(jobId); // Fallback to simulation
    }
  });

  function updateStage(stageIndex) {
    for (let i = 1; i <= 5; i++) {
      const stageEl = document.getElementById(`stage-${i}`);
      if (i < stageIndex) {
        stageEl.classList.remove('active');
        stageEl.classList.add('done');
      } else if (i === stageIndex) {
        stageEl.classList.add('active');
        stageEl.classList.remove('done');
      } else {
        stageEl.classList.remove('active', 'done');
      }
    }
    
    // Fill width mapping: 1->0%, 2->25%, 3->50%, 4->75%, 5->100%
    const progressPct = (stageIndex - 1) * 25;
    progressFill.style.width = `${progressPct}%`;
  }

  function simulateGeneration(jobId) {
    let currentStage = 1;
    let eta = 45;
    
    updateStage(currentStage);
    
    const interval = setInterval(() => {
      eta -= 2;
      if (eta < 0) eta = 0;
      jobEtaEl.textContent = `${eta}s`;
      
      if (eta === 35) { currentStage = 2; updateStage(currentStage); }
      if (eta === 25) { currentStage = 3; updateStage(currentStage); }
      if (eta === 10) { currentStage = 4; updateStage(currentStage); }
      if (eta === 0) {
        currentStage = 5; 
        updateStage(currentStage);
        clearInterval(interval);
        setTimeout(() => showCompletion(jobId), 1000);
      }
    }, 1000);
  }

  function showCompletion(jobId) {
    panelGenerating.style.display = 'none';
    panelCompleted.style.display = 'block';
    
    // Auto-play mock or real video
    resultVideo.src = `/api/media/${jobId}.mp4`;
    // Fallback if no backend
    resultVideo.onerror = () => {
      resultVideo.outerHTML = '<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; background:#141720; color:#94a3b8;">[Mock Video Rendered Successfully]</div>';
    };
    
    btnStudio.href = `/studio?asset_id=${jobId}`;
  }

  btnRestart.addEventListener('click', () => {
    panelCompleted.style.display = 'none';
    panelEditor.style.display = 'grid'; // restoring grid
    
    // reset UI
    progressFill.style.width = '0%';
    for (let i=1; i<=5; i++) {
      document.getElementById(`stage-${i}`).className = 'stage';
    }
  });

  btnDownload.addEventListener('click', () => {
    if (resultVideo && resultVideo.src) {
      const a = document.createElement('a');
      a.href = resultVideo.src;
      a.download = `pluto_video_${Date.now()}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  });

  // Hot Reload Listener
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
