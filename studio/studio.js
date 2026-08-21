/**
 * Pluto Studio 2.5 Pro · UI Controller & State Manager
 * Integrated AI Director, DaVinci Multi-Track Timeline & MotionVector Compositor
 */

// Server-supplied strings (prompts, titles, narration, filenames) are untrusted:
// run them through this before they reach an innerHTML template.
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Every endpoint that spends compute or money needs the session token.
let plutoToken = null;
async function authHeaders(extra) {
  if (!plutoToken) {
    const r = await fetch('/api/token');
    plutoToken = (await r.json()).token;
  }
  return { 'X-Pluto-Token': plutoToken, ...(extra || {}) };
}

let state = {
  activeAsset: null,
  assets: [],
  gpuStatus: null,
  isPlaying: false,
  duration: 4.0,
  width: 1024,
  height: 576,
  takesCount: 1,
  engineMode: 'pro', // 'draft' | 'pro'
  draftMode: false,
  imageKeyframePath: null,
  imageKeyframeUrl: null,
  imageKeyframeName: null,
  isGenerating: false,
  activeMode: 'director', // 'director' | 'vibe'
  storyboard: null,
  timelineZoom: 1.0,
  safeGridVisible: false,
  shuttleRate: 0, // 0 = paused, 1, 2, 4, 8, -2, -4, -8
  shuttleInterval: null,
  inPoint: null,
  outPoint: null,
  exportConfig: {
    preset: 'prores', // 'prores' | 'h264' | 'upscale'
    range: 'full',    // 'full' | 'inout'
    resolution: '4k', // '4k' | '1080p'
    includeOverlay: true,
    isExporting: false,
  },
  overlayConfig: {
    visible: true,
    title: 'Diffusion Velocity Field',
    formula: 'dx_t = f(x_t)dt + g(t)dw_t',
    accentColor: '#fafafa',
    position: 'bottom_left',
  }
};

const elements = {
  // Navigation & Tabs
  tabDirector: document.getElementById('tabDirector'),
  tabVibeEditor: document.getElementById('tabVibeEditor'),
  directorView: document.getElementById('directorView'),
  vibeView: document.getElementById('vibeView'),

  // Header & Telemetry
  gpuTelemetryCapsule: document.getElementById('gpuTelemetryCapsule'),
  gpuStatusDot: document.getElementById('gpuStatusDot'),
  gpuStatusText: document.getElementById('gpuStatusText'),
  vramText: document.getElementById('vramText'),
  costText: document.getElementById('costText'),
  btnLaunchGpu: document.getElementById('btnLaunchGpu'),
  gpuActionLabel: document.getElementById('gpuActionLabel'),
  btnHeaderExport: document.getElementById('btnHeaderExport'),

  // AI Director Storyboard
  directorTopicInput: document.getElementById('directorTopicInput'),
  btnGenerateStoryboard: document.getElementById('btnGenerateStoryboard'),
  storyboardCardsGrid: document.getElementById('storyboardCardsGrid'),
  reelSceneCount: document.getElementById('reelSceneCount'),
  btnRenderAllTakes: document.getElementById('btnRenderAllTakes'),
  btnExportFullDoc: document.getElementById('btnExportFullDoc'),

  // Asset Bin & Library
  assetGrid: document.getElementById('assetGrid'),
  assetCount: document.getElementById('assetCount'),
  btnSyncAssets: document.getElementById('btnSyncAssets'),

  // Takes Filmstrip Shelf
  takesFilmstripShelf: document.getElementById('takesFilmstripShelf'),
  takesFilmstripTrack: document.getElementById('takesFilmstripTrack'),
  takesShelfCount: document.getElementById('takesShelfCount'),
  btnTakesPrev: document.getElementById('btnTakesPrev'),
  btnTakesNext: document.getElementById('btnTakesNext'),

  // Viewport & Player
  mainVideoPlayer: document.getElementById('mainVideoPlayer'),
  playerWrapper: document.querySelector('.player-wrapper'),
  viewportCanvasContainer: document.querySelector('.viewport-canvas-container'),
  resolutionTag: document.getElementById('resolutionTag'),
  loadingOverlay: document.getElementById('loadingOverlay'),
  loadingText: document.getElementById('loadingText'),
  progressBarFill: document.getElementById('progressBarFill'),
  safeMarginsOverlay: document.getElementById('safeMarginsOverlay'),

  // Canvas Math Overlay
  canvasMathOverlay: document.getElementById('canvasMathOverlay'),
  overlayGlassCard: document.getElementById('overlayGlassCard'),
  cardAccentBar: document.getElementById('cardAccentBar'),
  cardTitleText: document.getElementById('cardTitleText'),
  cardFormulaKaTeX: document.getElementById('cardFormulaKaTeX'),

  // Transport Bar
  btnPlayPause: document.getElementById('btnPlayPause'),
  playIcon: document.getElementById('playIcon'),
  btnSkipBack: document.getElementById('btnSkipBack'),
  btnSkipFwd: document.getElementById('btnSkipFwd'),
  timecodeSMPTE: document.getElementById('timecodeSMPTE'),
  timecodeDuration: document.getElementById('timecodeDuration'),
  btnToggleOverlay: document.getElementById('btnToggleOverlay'),
  btnToggleGrid: document.getElementById('btnToggleGrid'),
  btnQuickUpscale: document.getElementById('btnQuickUpscale'),
  btnDownloadCurrent: document.getElementById('btnDownloadCurrent'),
  btnMuteToggle: document.getElementById('btnMuteToggle'),
  volumeIcon: document.getElementById('volumeIcon'),
  volumeSlider: document.getElementById('volumeSlider'),
  btnSpeedToggle: document.getElementById('btnSpeedToggle'),
  speedLabel: document.getElementById('speedLabel'),
  btnFullscreen: document.getElementById('btnFullscreen'),

  // Prompt Bar
  promptBarContainer: document.getElementById('promptBarContainer') || document.querySelector('.prompt-bar-container'),
  promptInput: document.getElementById('promptInput'),
  btnAttachImage: document.getElementById('btnAttachImage'),
  imageKeyframeInput: document.getElementById('imageKeyframeInput'),
  imageKeyframeChip: document.getElementById('imageKeyframeChip'),
  imageKeyframeThumb: document.getElementById('imageKeyframeThumb'),
  imageKeyframeName: document.getElementById('imageKeyframeName'),
  btnRemoveKeyframe: document.getElementById('btnRemoveKeyframe'),
  engineModeSelector: document.getElementById('engineModeSelector'),
  btnEnhance: document.getElementById('btnEnhance'),
  btnGenerate: document.getElementById('btnGenerate'),
  durationSelector: document.getElementById('durationSelector'),
  aspectSelector: document.getElementById('aspectSelector'),
  takesSelector: document.getElementById('takesSelector'),

  // Inspector Panel
  inpCardTitle: document.getElementById('inpCardTitle'),
  inpCardFormula: document.getElementById('inpCardFormula'),
  inspectorKaTeXPreview: document.getElementById('inspectorKaTeXPreview'),
  posSelector: document.getElementById('posSelector'),
  btnRun4kUpscale: document.getElementById('btnRun4kUpscale'),
  upscaleStatus: document.getElementById('upscaleStatus'),

  // Timeline
  timelineZoomRange: document.getElementById('timelineZoomRange'),
  timelineRuler: document.getElementById('timelineRuler'),
  timelineScrollArea: document.getElementById('timelineScrollArea'),
  trackLanesContainer: document.getElementById('trackLanesContainer'),
  timelinePlayhead: document.getElementById('timelinePlayhead'),
  timelineClipName: document.getElementById('timelineClipName'),
  timelineClipDur: document.getElementById('timelineClipDur'),
  audioWaveformCanvas: document.getElementById('audioWaveformCanvas'),

  // NLE Timeline Marker & Shuttle Elements
  btnSetInPoint: document.getElementById('btnSetInPoint'),
  btnSetOutPoint: document.getElementById('btnSetOutPoint'),
  btnClearInOut: document.getElementById('btnClearInOut'),
  timelineInOutBadge: document.getElementById('timelineInOutBadge'),
  shuttleStatusPill: document.getElementById('shuttleStatusPill'),
  markerInHandle: document.getElementById('markerInHandle'),
  markerOutHandle: document.getElementById('markerOutHandle'),
  timelineInOutRegion: document.getElementById('timelineInOutRegion'),

  // Track V1 & V2 Elements
  trackV1Lane: document.getElementById('trackV1Lane'),
  v1ClipBlock: document.getElementById('v1ClipBlock'),
  v1ClipTitle: document.getElementById('v1ClipTitle'),
  v1ThumbsContainer: document.getElementById('v1ThumbsContainer'),
  v2ClipBlock: document.getElementById('v2ClipBlock'),
  v2ClipTitle: document.getElementById('v2ClipTitle'),

  // Command Palette (⌘K)
  btnOpenCommandPalette: document.getElementById('btnOpenCommandPalette'),
  commandPaletteModal: document.getElementById('commandPaletteModal'),
  cmdSearchInput: document.getElementById('cmdSearchInput'),
  cmdResultsList: document.getElementById('cmdResultsList'),

  // Export Master Drawer & Modal
  exportMasterModal: document.getElementById('exportMasterModal'),
  btnCloseExportModal: document.getElementById('btnCloseExportModal'),
  btnCancelExport: document.getElementById('btnCancelExport'),
  btnStartExport: document.getElementById('btnStartExport'),
  btnStartExportLabel: document.getElementById('btnStartExportLabel'),
  exportSourceThumb: document.getElementById('exportSourceThumb'),
  exportSourceTitle: document.getElementById('exportSourceTitle'),
  exportSourceRes: document.getElementById('exportSourceRes'),
  exportSourceDur: document.getElementById('exportSourceDur'),
  exportFullDurText: document.getElementById('exportFullDurText'),
  exportInOutRangeText: document.getElementById('exportInOutRangeText'),
  exportPresetsGrid: document.getElementById('exportPresetsGrid'),
  exportRangeSelector: document.getElementById('exportRangeSelector'),
  exportResSelector: document.getElementById('exportResSelector'),
  chkIncludeOverlay: document.getElementById('chkIncludeOverlay'),
  exportOverlayControls: document.getElementById('exportOverlayControls'),
  exportOverlayFields: document.getElementById('exportOverlayFields'),
  inpExportTitle: document.getElementById('inpExportTitle'),
  inpExportFormula: document.getElementById('inpExportFormula'),
  exportStatusBox: document.getElementById('exportStatusBox'),
  exportSpinner: document.getElementById('exportSpinner'),
  exportStatusText: document.getElementById('exportStatusText'),
  exportProgressBar: document.getElementById('exportProgressBar'),
  exportSuccessActions: document.getElementById('exportSuccessActions'),
  btnDownloadExported: document.getElementById('btnDownloadExported'),
  btnLoadExportedToCanvas: document.getElementById('btnLoadExportedToCanvas'),
};

// ── Initialization ──────────────────────────────────────────
async function init() {
  setupEventListeners();
  initPointerScrubbing();
  buildTimelineRuler();
  renderAudioWaveform();
  updateKaTeXMath();
  initHotReload();
  
  await refreshStatus();
  await refreshAssets();

  // Check URL query for mode or deep-linked asset
  const urlParams = new URLSearchParams(window.location.search);
  const deepLinkId = urlParams.get('asset_id') || urlParams.get('job_id');
  
  if (deepLinkId) {
    const cleanId = deepLinkId.replace(/\.mp4$/i, '');
    let clip = state.assets.find(a => a.id === cleanId);
    
    if (!clip) {
      try {
        const res = await fetch(`/api/jobs/${encodeURIComponent(cleanId)}`);
        if (res.ok) clip = await res.json();
      } catch (e) {
        console.warn('Could not fetch deep-linked asset', e);
      }
    }
    
    // Fallback if not found in API but ID is provided
    if (!clip) {
      clip = { id: cleanId, prompt: cleanId, width: 1024, height: 576, seconds: 4.0 };
    }
    
    selectAsset(clip);
    setMode('vibe');
    
    // Highlight in Asset Bin if it exists there
    setTimeout(() => {
      const cards = document.querySelectorAll('.asset-card');
      const targetCard = Array.from(cards).find(c => c.innerHTML.includes(cleanId));
      if (targetCard) targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);

    showToast('🎬 Loaded video into Studio Workspace');
  } else if (urlParams.get('mode') === 'vibe') {
    setMode('vibe');
  } else {
    await triggerAutoStoryboard();
  }

  setInterval(refreshStatus, 4000);
}

function showToast(message) {
  const toast = document.createElement('div');
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: rgba(15, 15, 20, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #fff;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    z-index: 9999;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    backdrop-filter: blur(10px);
  `;
  document.body.appendChild(toast);
  
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ── Live Hot Reload (CSS HMR & Graceful Live Update) ─────────
function initHotReload() {
  try {
    const evtSource = new EventSource('/api/live-reload');
    evtSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === 'reload-css') {
        // CSS HMR: swap stylesheet without touching JS state
        const links = document.querySelectorAll('link[rel="stylesheet"]');
        links.forEach(link => {
          if (link.href.includes('studio.css')) {
            const url = new URL(link.href);
            url.searchParams.set('t', Date.now());
            link.href = url.toString();
          }
        });
        // Re-render waveform after CSS change (canvas may resize)
        requestAnimationFrame(() => renderAudioWaveform());
      } else if (data.event === 'reload-full') {
        // Snapshot playback state before full reload
        const video = elements.mainVideoPlayer;
        const snapshot = {
          currentTime: video.currentTime || 0,
          wasPlaying: !video.paused,
          activeAssetId: state.activeAsset ? state.activeAsset.id : null,
          activeMode: state.activeMode,
          overlayConfig: { ...state.overlayConfig },
          timelineZoom: state.timelineZoom,
          safeGridVisible: state.safeGridVisible,
        };
        try {
          sessionStorage.setItem('pluto_hot_reload_snapshot', JSON.stringify(snapshot));
        } catch (err) {
          // sessionStorage may be unavailable in some contexts
        }
        window.location.reload();
      }
    };
    evtSource.onerror = () => {
      // SSE connection lost — silently reconnect on next server restart
    };
  } catch (err) {
    // Hot reload unavailable in this environment
  }
}

// ── Event Listeners Setup ───────────────────────────────────
function setupEventListeners() {
  // Mode Switcher Tabs
  elements.tabDirector.addEventListener('click', () => setMode('director'));
  elements.tabVibeEditor.addEventListener('click', () => setMode('vibe'));

  // Director Storyboard
  elements.btnGenerateStoryboard.addEventListener('click', triggerAutoStoryboard);
  elements.directorTopicInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') triggerAutoStoryboard();
  });

  document.querySelectorAll('.topic-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.topic-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      elements.directorTopicInput.value = chip.dataset.topic;
      triggerAutoStoryboard();
    });
  });

  elements.btnRenderAllTakes.addEventListener('click', renderAllStoryboardTakes);
  elements.btnExportFullDoc.addEventListener('click', exportFullDocumentaryMaster);
  elements.btnHeaderExport.addEventListener('click', openExportMasterDrawer);

  // Play / Pause & Transport Controls
  elements.btnPlayPause.addEventListener('click', togglePlayPause);
  elements.btnSkipBack.addEventListener('click', () => stepTime(-1.0));
  elements.btnSkipFwd.addEventListener('click', () => stepTime(1.0));
  elements.mainVideoPlayer.addEventListener('timeupdate', updatePlaybackProgress);
  elements.mainVideoPlayer.addEventListener('ended', () => shuttleStop());

  // Volume & Mute Controls
  if (elements.volumeSlider) {
    elements.volumeSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      elements.mainVideoPlayer.volume = val;
      elements.mainVideoPlayer.muted = (val === 0);
      updateVolumeIcon(val === 0);
    });
  }

  if (elements.btnMuteToggle) {
    elements.btnMuteToggle.addEventListener('click', () => {
      elements.mainVideoPlayer.muted = !elements.mainVideoPlayer.muted;
      if (!elements.mainVideoPlayer.muted && elements.mainVideoPlayer.volume === 0) {
        elements.mainVideoPlayer.volume = 0.8;
        if (elements.volumeSlider) elements.volumeSlider.value = '0.8';
      }
      updateVolumeIcon(elements.mainVideoPlayer.muted);
    });
  }

  // Playback Speed Toggle (0.5x, 1x, 1.25x, 1.5x, 2x)
  const playbackSpeeds = [0.5, 1.0, 1.25, 1.5, 2.0];
  let currentSpeedIdx = 1; // 1.0x
  if (elements.btnSpeedToggle) {
    elements.btnSpeedToggle.addEventListener('click', () => {
      currentSpeedIdx = (currentSpeedIdx + 1) % playbackSpeeds.length;
      const speed = playbackSpeeds[currentSpeedIdx];
      elements.mainVideoPlayer.playbackRate = speed;
      if (elements.speedLabel) elements.speedLabel.textContent = `${speed}×`;
    });
  }

  // Fullscreen Button
  if (elements.btnFullscreen) {
    elements.btnFullscreen.addEventListener('click', () => {
      const wrapper = document.querySelector('.player-wrapper');
      if (!document.fullscreenElement) {
        if (wrapper && wrapper.requestFullscreen) {
          wrapper.requestFullscreen();
        } else if (elements.mainVideoPlayer.requestFullscreen) {
          elements.mainVideoPlayer.requestFullscreen();
        }
      } else {
        if (document.exitFullscreen) document.exitFullscreen();
      }
    });
  }

  function updateVolumeIcon(isMuted) {
    if (!elements.volumeIcon) return;
    if (isMuted || elements.mainVideoPlayer.volume === 0) {
      elements.volumeIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>`;
    } else if (elements.mainVideoPlayer.volume < 0.5) {
      elements.volumeIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
    } else {
      elements.volumeIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>`;
    }
  }

  // Toggle Overlays
  elements.btnToggleOverlay.addEventListener('click', () => {
    state.overlayConfig.visible = !state.overlayConfig.visible;
    elements.canvasMathOverlay.style.display = state.overlayConfig.visible ? 'block' : 'none';
    elements.btnToggleOverlay.classList.toggle('active', state.overlayConfig.visible);
  });

  elements.btnToggleGrid.addEventListener('click', () => {
    state.safeGridVisible = !state.safeGridVisible;
    elements.safeMarginsOverlay.style.display = state.safeGridVisible ? 'block' : 'none';
    elements.btnToggleGrid.classList.toggle('active', state.safeGridVisible);
  });

  // Math Overlay Real-time Inputs
  elements.inpCardTitle.addEventListener('input', (e) => {
    state.overlayConfig.title = e.target.value;
    elements.cardTitleText.textContent = e.target.value;
  });

  elements.inpCardFormula.addEventListener('input', (e) => {
    state.overlayConfig.formula = e.target.value;
    updateKaTeXMath();
  });

  // Color Picker Dots
  document.querySelectorAll('.color-dot').forEach(dot => {
    dot.addEventListener('click', () => {
      document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
      dot.classList.add('active');
      const color = dot.dataset.color;
      state.overlayConfig.accentColor = color;
      elements.cardAccentBar.style.backgroundColor = color;
      elements.overlayGlassCard.style.borderColor = color;
    });
  });

  // Overlay Position Selector
  elements.posSelector.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      elements.posSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const pos = btn.dataset.pos;
      state.overlayConfig.position = pos;
      elements.canvasMathOverlay.className = `canvas-math-overlay pos-${pos.replace('_', '-')}`;
    });
  });

  // Asset Filter Tabs
  document.querySelectorAll('.filter-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      filterAssets(tab.dataset.filter);
    });
  });

  // Takes Filmstrip Scroll Buttons
  if (elements.btnTakesPrev && elements.takesFilmstripTrack) {
    elements.btnTakesPrev.addEventListener('click', () => {
      elements.takesFilmstripTrack.scrollBy({ left: -240, behavior: 'smooth' });
    });
  }
  if (elements.btnTakesNext && elements.takesFilmstripTrack) {
    elements.btnTakesNext.addEventListener('click', () => {
      elements.takesFilmstripTrack.scrollBy({ left: 240, behavior: 'smooth' });
    });
  }

  // NLE Timeline In / Out Buttons
  if (elements.btnSetInPoint) {
    elements.btnSetInPoint.addEventListener('click', setInPoint);
  }
  if (elements.btnSetOutPoint) {
    elements.btnSetOutPoint.addEventListener('click', setOutPoint);
  }
  if (elements.btnClearInOut) {
    elements.btnClearInOut.addEventListener('click', clearInOutPoints);
  }

  // Keyboard Shortcuts (J / K / L Shuttle + ⌘K + In / Out + Arrows)
  window.addEventListener('keydown', (e) => {
    const isTyping = ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName);
    
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      toggleCommandPalette(true);
    } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'e') {
      e.preventDefault();
      openExportMasterDrawer();
    } else if (e.key === 'Escape') {
      if (elements.commandPaletteModal && elements.commandPaletteModal.style.display !== 'none') {
        toggleCommandPalette(false);
      }
      if (elements.exportMasterModal && elements.exportMasterModal.style.display !== 'none') {
        closeExportMasterDrawer();
      }
    } else if (!isTyping) {
      if (e.code === 'Space') {
        e.preventDefault();
        togglePlayPause();
      } else if (e.key.toLowerCase() === 'k') {
        e.preventDefault();
        shuttleStop();
      } else if (e.key.toLowerCase() === 'j') {
        e.preventDefault();
        shuttleRewind();
      } else if (e.key.toLowerCase() === 'l') {
        e.preventDefault();
        shuttleForward();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (e.shiftKey) {
          stepTime(-1.0);
        } else {
          stepFrame(-1);
        }
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (e.shiftKey) {
          stepTime(1.0);
        } else {
          stepFrame(1);
        }
      } else if (e.key.toLowerCase() === 'i') {
        e.preventDefault();
        setInPoint();
      } else if (e.key.toLowerCase() === 'o') {
        e.preventDefault();
        setOutPoint();
      } else if ((e.altKey || e.metaKey) && e.key.toLowerCase() === 'x') {
        e.preventDefault();
        clearInOutPoints();
      }
    }
  });

  // Prompt Enhance
  elements.btnEnhance.addEventListener('click', async () => {
    const p = elements.promptInput.value.trim();
    if (!p) return;
    try {
      elements.btnEnhance.innerHTML = '<span>Enhancing...</span>';
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
    } finally {
      elements.btnEnhance.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
        <span>Enhance</span>
      `;
    }
  });

  // Preset Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const token = chip.dataset.token;
      if (elements.promptInput.value.trim()) {
        elements.promptInput.value += `, ${token}`;
      } else {
        elements.promptInput.value = token;
      }
    });
  });

  // Duration Selector
  elements.durationSelector.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      elements.durationSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.duration = parseFloat(btn.dataset.val);
    });
  });

  // Aspect Selector
  elements.aspectSelector.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      elements.aspectSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.width = parseInt(btn.dataset.w);
      state.height = parseInt(btn.dataset.h);
    });
  });

  // Engine Mode Selector (Draft / Pro)
  if (elements.engineModeSelector) {
    elements.engineModeSelector.querySelectorAll('.pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        elements.engineModeSelector.querySelectorAll('.pill-btn').forEach(b => {
          b.classList.remove('active');
          b.setAttribute('aria-checked', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-checked', 'true');
        state.engineMode = btn.dataset.mode || 'pro';
        state.draftMode = (state.engineMode === 'draft');
        showToast(state.draftMode ? '⚡ Switched to Draft Mode (15s fast preview)' : '🎬 Switched to Pro Mode (30s high quality)');
      });
    });
  }

  // Image Keyframe Attachment (I2V)
  if (elements.btnAttachImage && elements.imageKeyframeInput) {
    elements.btnAttachImage.addEventListener('click', () => elements.imageKeyframeInput.click());
    elements.imageKeyframeInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        attachImageKeyframe(e.target.files[0]);
      }
    });
  }
  if (elements.btnRemoveKeyframe) {
    elements.btnRemoveKeyframe.addEventListener('click', removeImageKeyframe);
  }

  // Drag and Drop Image Keyframe onto Prompt Bar, Canvas, or Player
  const dropTargets = [elements.promptBarContainer, elements.viewportCanvasContainer, elements.playerWrapper];
  dropTargets.forEach(target => {
    if (!target) return;
    target.addEventListener('dragover', (e) => {
      e.preventDefault();
      target.classList.add('drag-over');
    });
    target.addEventListener('dragleave', (e) => {
      if (!target.contains(e.relatedTarget)) {
        target.classList.remove('drag-over');
      }
    });
    target.addEventListener('drop', (e) => {
      e.preventDefault();
      target.classList.remove('drag-over');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        if (file.type.startsWith('image/')) {
          attachImageKeyframe(file);
        }
      }
    });
  });

  // Takes Selector
  if (elements.takesSelector) {
    elements.takesSelector.querySelectorAll('.pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        elements.takesSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.takesCount = parseInt(btn.dataset.takes);
      });
    });
  }

  // Generate Plate
  elements.btnGenerate.addEventListener('click', triggerGenerate);

  // 4K Compositor (P0 Composite Order Enforced)
  elements.btnQuickUpscale.addEventListener('click', openExportMasterDrawer);
  elements.btnRun4kUpscale.addEventListener('click', openExportMasterDrawer);

  // Download File
  elements.btnDownloadCurrent.addEventListener('click', () => {
    if (state.activeAsset) {
      window.open(`/api/assets/${encodeURIComponent(state.activeAsset.id)}/file`, '_blank');
    }
  });

  // GPU Action (Launch / Terminate)
  elements.btnLaunchGpu.addEventListener('click', () => {
    const isStopped = !state.gpuStatus || !state.gpuStatus.instance || state.gpuStatus.instance.state === 'stopped' || state.gpuStatus.instance.state === 'offline';
    if (isStopped) {
      const doLaunch = async () => {
        try {
          elements.gpuActionLabel.textContent = 'Launching Spot GPU...';
          elements.btnLaunchGpu.disabled = true;
          const headers = await authHeaders();
          await fetch('/api/gpu/launch', {
            method: 'POST',
            headers,
            body: JSON.stringify({ confirm: true })
          });
          await refreshStatus();
        } catch (e) {
          console.error('Launch failed', e);
        } finally {
          elements.btnLaunchGpu.disabled = false;
        }
      };

      if (window.mvDialog) {
        window.mvDialog.confirm({
          title: 'Authorize AWS GPU Launch',
          subtitle: 'Start Spot GPU compute & warm VRAM',
          message: 'Provision Spot GPU instance. Billing starts immediately upon boot (~$0.75/hr).',
          type: 'launch',
          confirmText: 'Authorize & Launch Box',
          onConfirm: doLaunch
        });
      } else {
        doLaunch();
      }
    } else {
      const doTerminate = async () => {
        try {
          elements.gpuActionLabel.textContent = 'Terminating...';
          elements.btnLaunchGpu.disabled = true;
          const headers = await authHeaders();
          await fetch('/api/gpu/terminate', {
            method: 'POST',
            headers,
            body: JSON.stringify({ confirm: true })
          });
          await refreshStatus();
        } catch (e) {
          console.error('Terminate failed', e);
        } finally {
          elements.btnLaunchGpu.disabled = false;
        }
      };

      if (window.mvDialog) {
        window.mvDialog.confirm({
          title: 'Terminate GPU Box',
          subtitle: 'Halt cloud billing and destroy instance',
          message: '<span style="color:#f43f5e;font-weight:600;">⚠️ Warning:</span> Terminating destroys the temporary NVMe scratch volume. Any unsynced video renders will be permanently lost.',
          type: 'danger',
          requireTypedText: 'TERMINATE',
          confirmText: 'Destroy & Stop Billing',
          onConfirm: doTerminate
        });
      } else {
        doTerminate();
      }
    }
  });

  elements.btnSyncAssets.addEventListener('click', refreshAssets);

  // Timeline Zoom Slider
  elements.timelineZoomRange.addEventListener('input', (e) => {
    state.timelineZoom = parseInt(e.target.value) / 100;
    elements.trackLanesContainer.style.width = `${100 * state.timelineZoom}%`;
    elements.timelineRuler.style.width = `${100 * state.timelineZoom}%`;
  });

  // Command Palette
  elements.btnOpenCommandPalette.addEventListener('click', () => toggleCommandPalette(true));
  elements.commandPaletteModal.addEventListener('click', (e) => {
    if (e.target === elements.commandPaletteModal) toggleCommandPalette(false);
  });

  document.querySelectorAll('.cmd-item').forEach(item => {
    item.addEventListener('click', () => {
      executeCommandAction(item.dataset.action);
      toggleCommandPalette(false);
    });
  });

  // Export Master Drawer Listeners
  if (elements.btnCloseExportModal) {
    elements.btnCloseExportModal.addEventListener('click', closeExportMasterDrawer);
  }
  if (elements.btnCancelExport) {
    elements.btnCancelExport.addEventListener('click', closeExportMasterDrawer);
  }
  if (elements.exportMasterModal) {
    elements.exportMasterModal.addEventListener('click', (e) => {
      if (e.target === elements.exportMasterModal) closeExportMasterDrawer();
    });
  }
  if (elements.btnStartExport) {
    elements.btnStartExport.addEventListener('click', triggerMasterExport);
  }

  // Export Presets Selection
  if (elements.exportPresetsGrid) {
    elements.exportPresetsGrid.querySelectorAll('.export-preset-card').forEach(card => {
      card.addEventListener('click', () => {
        elements.exportPresetsGrid.querySelectorAll('.export-preset-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        state.exportConfig.preset = card.dataset.preset;
        
        // Toggle overlay fields based on preset
        if (card.dataset.preset === 'upscale') {
          if (elements.exportOverlayControls) elements.exportOverlayControls.style.opacity = '0.4';
          if (elements.exportOverlayFields) elements.exportOverlayFields.style.opacity = '0.4';
        } else {
          if (elements.exportOverlayControls) elements.exportOverlayControls.style.opacity = '1';
          if (elements.exportOverlayFields) elements.exportOverlayFields.style.opacity = '1';
        }
      });
    });
  }

  // Export Range Selection
  if (elements.exportRangeSelector) {
    elements.exportRangeSelector.querySelectorAll('.pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        elements.exportRangeSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.exportConfig.range = btn.dataset.range;
      });
    });
  }

  // Export Resolution Selection
  if (elements.exportResSelector) {
    elements.exportResSelector.querySelectorAll('.pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        elements.exportResSelector.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.exportConfig.resolution = btn.dataset.res;
      });
    });
  }

  // Include Overlay Checkbox
  if (elements.chkIncludeOverlay) {
    elements.chkIncludeOverlay.addEventListener('change', (e) => {
      state.exportConfig.includeOverlay = e.target.checked;
      if (elements.exportOverlayFields) {
        elements.exportOverlayFields.style.display = e.target.checked ? 'grid' : 'none';
      }
    });
  }
}

// ── "No Modes, Ever" Pointer Scrubbing Engine ────────────────
let isPointerScrubbing = false;

function scrubToClientX(clientX, containerElement) {
  const v = elements.mainVideoPlayer;
  if (!v || !v.duration || !containerElement) return;

  const rect = containerElement.getBoundingClientRect();
  const clickX = clientX - rect.left;
  const totalWidth = rect.width;
  const ratio = Math.max(0, Math.min(1, clickX / totalWidth));

  v.currentTime = ratio * v.duration;
  updatePlaybackProgress();
}

function initPointerScrubbing() {
  let activeScrubTarget = null;

  function onPointerDown(e) {
    if (e.button !== 0) return;
    if (e.target.closest('button') || e.target.closest('input') || e.target.closest('.take-audition-btn')) return;

    shuttleStop();
    isPointerScrubbing = true;
    activeScrubTarget = e.currentTarget;
    scrubToClientX(e.clientX, activeScrubTarget);
  }

  function onPointerMove(e) {
    if (!isPointerScrubbing || !activeScrubTarget) return;
    scrubToClientX(e.clientX, activeScrubTarget);
  }

  function onPointerUp() {
    isPointerScrubbing = false;
    activeScrubTarget = null;
  }

  if (elements.timelineRuler) {
    elements.timelineRuler.addEventListener('pointerdown', onPointerDown);
  }
  if (elements.trackLanesContainer) {
    elements.trackLanesContainer.addEventListener('pointerdown', onPointerDown);
  }
  if (elements.timelineScrollArea) {
    elements.timelineScrollArea.addEventListener('pointerdown', onPointerDown);
  }
  const vpTrack = document.getElementById('viewportScrubberTrack');
  if (vpTrack) {
    vpTrack.addEventListener('pointerdown', onPointerDown);
  }

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// ── Mode Switching ──────────────────────────────────────────
function setMode(mode) {
  state.activeMode = mode;
  if (mode === 'director') {
    elements.tabDirector.classList.add('active');
    elements.tabDirector.setAttribute('aria-selected', 'true');
    elements.tabVibeEditor.classList.remove('active');
    elements.tabVibeEditor.setAttribute('aria-selected', 'false');
    elements.directorView.style.display = 'flex';
    elements.vibeView.style.display = 'none';
  } else {
    elements.tabDirector.classList.remove('active');
    elements.tabDirector.setAttribute('aria-selected', 'false');
    elements.tabVibeEditor.classList.add('active');
    elements.tabVibeEditor.setAttribute('aria-selected', 'true');
    elements.directorView.style.display = 'none';
    elements.vibeView.style.display = 'flex';
  }
}

// ── Live KaTeX Math Rendering ────────────────────────────────
function updateKaTeXMath() {
  const formula = state.overlayConfig.formula;
  if (typeof katex !== 'undefined') {
    try {
      katex.render(formula, elements.cardFormulaKaTeX, { throwOnError: false, displayMode: true });
      katex.render(formula, elements.inspectorKaTeXPreview, { throwOnError: false, displayMode: true });
    } catch (e) {
      elements.cardFormulaKaTeX.textContent = formula;
      elements.inspectorKaTeXPreview.textContent = formula;
    }
  } else {
    elements.cardFormulaKaTeX.textContent = formula;
    elements.inspectorKaTeXPreview.textContent = formula;
  }
}

// ── AI Director Auto-Storyboard Generator ────────────────────
async function triggerAutoStoryboard() {
  const topic = elements.directorTopicInput.value.trim();
  if (!topic) return;

  try {
    elements.btnGenerateStoryboard.disabled = true;
    elements.btnGenerateStoryboard.innerHTML = '<span>Crafting Storyboard...</span>';

    const res = await fetch('/api/director/auto-script', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic, style: '3blue1brown' })
    });
    const data = await res.json();
    state.storyboard = data;
    renderStoryboardScenes(data.scenes);
  } catch (e) {
    console.error('Storyboard error', e);
  } finally {
    elements.btnGenerateStoryboard.disabled = false;
    elements.btnGenerateStoryboard.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      <span>Generate Storyboard Reel</span>
    `;
  }
}

function renderStoryboardScenes(scenes) {
  elements.storyboardCardsGrid.innerHTML = '';
  elements.reelSceneCount.textContent = `${scenes.length} Scenes · ${scenes.reduce((acc, s) => acc + s.duration_sec, 0)}s Total`;

  scenes.forEach((scene, i) => {
    const card = document.createElement('div');
    card.className = 'storyboard-card';
    card.innerHTML = `
      <div class="scene-card-header">
        <span class="scene-idx-tag">SCENE ${esc(scene.scene_idx)} · ${esc(String(scene.title || '').split(':')[0])}</span>
        <span class="scene-dur-tag">${esc(scene.duration_sec)}s</span>
      </div>
      <div class="scene-card-body">
        <h4 class="scene-card-title">${esc(scene.title)}</h4>
        <div class="scene-prompt-box">🎬 <strong>Prompt:</strong> ${esc(scene.prompt)}</div>
        <div class="scene-math-preview katex-scene-slot" id="katexScene_${i}"></div>
        <div class="scene-narration-box">🎙️ "${esc(scene.narration)}"</div>
      </div>
      <div class="scene-card-footer">
        <div class="scene-take-auditions">
          <button class="take-audition-btn active">Take A</button>
          <button class="take-audition-btn">Take B</button>
          <button class="take-audition-btn">Take C</button>
        </div>
        <button class="btn-scene-render" data-idx="${i}">
          <span>Render Take</span>
        </button>
      </div>
    `;

    // Render KaTeX for scene card
    setTimeout(() => {
      const slot = card.querySelector(`#katexScene_${i}`);
      if (slot && typeof katex !== 'undefined') {
        try {
          katex.render(scene.math_formula, slot, { throwOnError: false });
        } catch (e) {
          slot.textContent = scene.math_formula;
        }
      }
    }, 10);

    // Click on card opens in Vibe Canvas
    card.addEventListener('click', (e) => {
      if (e.target.closest('.take-audition-btn') || e.target.closest('.btn-scene-render')) return;
      loadSceneIntoVibeCanvas(scene);
    });

    // Render button
    card.querySelector('.btn-scene-render').addEventListener('click', async (e) => {
      e.stopPropagation();
      const btn = e.currentTarget;
      btn.innerHTML = '<span>Rendering...</span>';
      try {
        await generateSingleSceneTake(scene);
        btn.innerHTML = '<span>✓ Ready</span>';
      } catch (err) {
        btn.innerHTML = '<span>Failed</span>';
      }
    });

    elements.storyboardCardsGrid.appendChild(card);
  });
}

function loadSceneIntoVibeCanvas(scene) {
  setMode('vibe');
  elements.promptInput.value = scene.prompt;
  elements.inpCardTitle.value = scene.title;
  elements.inpCardFormula.value = scene.math_formula;
  state.overlayConfig.title = scene.title;
  state.overlayConfig.formula = scene.math_formula;
  elements.cardTitleText.textContent = scene.title;
  updateKaTeXMath();
}

async function generateSingleSceneTake(scene) {
  const res = await fetch('/api/generate', {
    method: 'POST',
    headers: await authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      prompt: scene.prompt,
      seconds: scene.duration_sec,
      width: 1024,
      height: 576,
    })
  });
  const data = await res.json();
  await refreshAssets();
  return data;
}

async function renderAllStoryboardTakes() {
  if (!state.storyboard || !state.storyboard.scenes) return;
  elements.btnRenderAllTakes.disabled = true;
  elements.btnRenderAllTakes.innerHTML = '<span>Rendering All Takes...</span>';

  for (const scene of state.storyboard.scenes) {
    try {
      await generateSingleSceneTake(scene);
    } catch (e) {
      console.error('Scene render error', e);
    }
  }

  elements.btnRenderAllTakes.disabled = false;
  elements.btnRenderAllTakes.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
    <span>Render All Scenes (L40S)</span>
  `;
}

async function exportFullDocumentaryMaster() {
  openExportMasterDrawer();
}

// ── Takes Filmstrip Shelf Controller ─────────────────────────
function renderTakesFilmstrip(assets) {
  if (!elements.takesFilmstripTrack) return;
  elements.takesFilmstripTrack.innerHTML = '';

  if (!assets || assets.length === 0) {
    elements.takesFilmstripTrack.innerHTML = `
      <div class="takes-empty-hint">No rendered video takes found. Generate a clip to populate filmstrip.</div>
    `;
    if (elements.takesShelfCount) elements.takesShelfCount.textContent = '0 TAKES';
    return;
  }

  if (elements.takesShelfCount) {
    elements.takesShelfCount.textContent = `${assets.length} TAKE${assets.length > 1 ? 'S' : ''}`;
  }

  assets.forEach((asset, idx) => {
    const card = document.createElement('div');
    const isSelected = state.activeAsset && state.activeAsset.id === asset.id;
    const isMaster = Boolean(asset.is_motionvector_master);
    const isUhd = Boolean(asset.is_upscaled);
    const badgeLabel = isMaster ? '4K MASTER' : isUhd ? '4K UHD' : `TAKE ${String(idx + 1).padStart(2, '0')}`;
    const badgeClass = isMaster ? 'master' : isUhd ? 'uhd' : '';
    
    card.className = `take-strip-card ${isSelected ? 'active' : ''}`;
    card.setAttribute('role', 'option');
    card.setAttribute('aria-selected', isSelected ? 'true' : 'false');
    card.setAttribute('data-asset-id', asset.id);

    card.innerHTML = `
      <div class="take-thumb-wrap">
        <img class="take-thumb-img" src="/api/assets/${encodeURIComponent(asset.id)}/thumbnail" alt="" loading="lazy" onerror="this.style.opacity='0'" />
        <span class="take-badge-tag ${badgeClass}">${esc(badgeLabel)}</span>
        <span class="take-dur-pill">${esc(asset.seconds || 4.0)}s</span>
      </div>
      <div class="take-card-info">
        <div class="take-card-title" title="${esc(asset.overlay_title || asset.prompt || asset.id)}">${esc(asset.overlay_title || asset.prompt || asset.id)}</div>
        <div class="take-card-meta">
          <span>${esc(asset.width)}×${esc(asset.height)}</span>
          <span>24fps</span>
        </div>
      </div>
    `;

    card.addEventListener('click', () => {
      selectAsset(asset);
      showToast(`🎬 Deep-loaded take into Track V1: ${asset.overlay_title || asset.prompt || asset.id}`);
    });

    elements.takesFilmstripTrack.appendChild(card);
  });
}

// ── Image Keyframe Attachment (I2V) ───────────────────────────
function attachImageKeyframe(file) {
  if (!file || !file.type.startsWith('image/')) {
    showToast('⚠️ Please drop or select a valid image file (PNG, JPG, WebP)');
    return;
  }

  const reader = new FileReader();
  reader.onload = async (e) => {
    const dataUrl = e.target.result;
    state.imageKeyframeUrl = dataUrl;
    state.imageKeyframeName = file.name || 'keyframe.png';

    if (elements.imageKeyframeThumb) elements.imageKeyframeThumb.src = dataUrl;
    if (elements.imageKeyframeName) elements.imageKeyframeName.textContent = esc(file.name || 'keyframe.png');
    if (elements.imageKeyframeChip) elements.imageKeyframeChip.style.display = 'inline-flex';
    if (elements.btnAttachImage) elements.btnAttachImage.classList.add('has-image');

    showToast(`🖼️ Attached keyframe: ${file.name} (I2V active)`);

    // Upload to server for permanent path if available
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/upload-image', {
        method: 'POST',
        headers: await authHeaders(),
        body: formData,
      });
      if (res.ok) {
        const upData = await res.json();
        if (upData.image_path) {
          state.imageKeyframePath = upData.image_path;
        }
      }
    } catch (err) {
      console.warn('Upload image to /api/upload-image failed, using dataUrl fallback', err);
    }
  };
  reader.readAsDataURL(file);
}

function removeImageKeyframe() {
  state.imageKeyframePath = null;
  state.imageKeyframeUrl = null;
  state.imageKeyframeName = null;
  if (elements.imageKeyframeChip) elements.imageKeyframeChip.style.display = 'none';
  if (elements.imageKeyframeInput) elements.imageKeyframeInput.value = '';
  if (elements.btnAttachImage) elements.btnAttachImage.classList.remove('has-image');
  showToast('Keyframe removed');
}

// ── Vibe Editor Generation & Compositor ────────────────────────
async function triggerGenerate() {
  const prompt = elements.promptInput.value.trim();
  if ((!prompt && !state.imageKeyframePath && !state.imageKeyframeUrl) || state.isGenerating) return;

  const isDraft = Boolean(state.draftMode || state.engineMode === 'draft');
  const statusMsg = isDraft
    ? '⚡ Generating draft plate (15s preview)...'
    : '🎬 Generating pro plate on Spot GPU (30s)...';

  setGenerating(true, statusMsg);

  try {
    const payload = {
      prompt: prompt || 'Cinematic video animation from keyframe',
      seconds: state.duration,
      width: state.width,
      height: state.height,
      takes: state.takesCount,
      draft_mode: isDraft,
    };
    if (state.imageKeyframePath) {
      payload.image_path = state.imageKeyframePath;
    } else if (state.imageKeyframeUrl) {
      payload.image_path = state.imageKeyframeUrl;
    }

    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: await authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    
    // Poll until completed
    await pollJob(data.job_id);
    await refreshAssets();
  } catch (e) {
    console.error('Generation failed', e);
  } finally {
    setGenerating(false);
  }
}

function showRenderError(message) {
  console.error('Render failed:', message);
  if (elements.upscaleStatus) elements.upscaleStatus.textContent = `Failed: ${message}`;
}

async function fetchJob(jobId) {
  const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
  return res.ok ? res.json() : null;
}

async function pollJob(jobId) {
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try {
      const job = await fetchJob(jobId);
      if (job && job.status === 'failed') {
        showRenderError(job.error || 'render failed');
        return;
      }
      if (job && job.status === 'completed') {
        const data = await (await fetch('/api/assets')).json();
        const match = data.assets.find(a => a.id === jobId);
        if (match) selectAsset(match);
        return;
      }
    } catch (e) {}
  }
  showRenderError('timed out waiting for the render');
}

// ── Status & Asset Telemetry ─────────────────────────────────
async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state.gpuStatus = data;

    if (data.gpu_online && data.instance) {
      elements.gpuStatusDot.className = 'status-dot online';
      elements.gpuStatusText.textContent = `Spot GPU Active (${data.instance.instance_type})`;
      elements.vramText.textContent = `${data.vram_used_gb || 0} / 44 GiB`;
      elements.costText.textContent = `$${(data.estimated_cost_usd || 0).toFixed(2)}`;
      elements.gpuActionLabel.textContent = 'Terminate GPU';
    } else {
      elements.gpuStatusDot.className = 'status-dot offline';
      elements.gpuStatusText.textContent = 'GPU Offline (Mock Mode)';
      elements.vramText.textContent = '-- / 44 GiB';
      elements.costText.textContent = '$0.00';
      elements.gpuActionLabel.textContent = 'Launch Spot GPU';
    }
  } catch (e) {
    console.error('Telemetry error', e);
  }
}

async function refreshAssets() {
  try {
    const res = await fetch('/api/assets');
    const data = await res.json();
    state.assets = data.assets || [];
    elements.assetCount.textContent = state.assets.length;
    renderAssetGrid(state.assets);
    renderTakesFilmstrip(state.assets);

    if (!state.activeAsset && state.assets.length > 0) {
      selectAsset(state.assets[0]);
    }
  } catch (e) {
    console.error('Asset refresh error', e);
  }
}

function filterAssets(filter) {
  if (filter === 'masters') {
    renderAssetGrid(state.assets.filter(a => a.is_motionvector_master || a.is_upscaled));
  } else if (filter === 'takes') {
    renderAssetGrid(state.assets.filter(a => !a.is_motionvector_master && !a.is_upscaled));
  } else {
    renderAssetGrid(state.assets);
  }
}

function renderAssetGrid(assets) {
  elements.assetGrid.innerHTML = '';
  if (assets.length === 0) {
    elements.assetGrid.innerHTML = `
      <div class="empty-state" style="padding: 24px; text-align: center; color: var(--text-faint); font-size: 11px;">
        <p>No video clips found.</p>
      </div>
    `;
    return;
  }

  assets.forEach(asset => {
    const card = document.createElement('div');
    card.className = `asset-card ${state.activeAsset && state.activeAsset.id === asset.id ? 'active' : ''}`;
    card.setAttribute('data-asset-id', asset.id);
    
    const isMaster = asset.is_motionvector_master;
    const is4k = asset.is_upscaled || isMaster;
    
    card.innerHTML = `
      <div class="asset-thumb-wrapper">
        <img class="asset-thumb" src="/api/assets/${encodeURIComponent(asset.id)}/thumbnail" alt="" loading="lazy" onerror="this.style.opacity='0'" />
        <span class="asset-badge ${isMaster ? 'master' : is4k ? 'uhd' : ''}">${isMaster ? '4K MASTER' : is4k ? '4K UHD' : 'SD'}</span>
      </div>
      <div class="asset-card-meta">
        <div class="asset-prompt-text">${esc(asset.overlay_title || asset.prompt || asset.id)}</div>
        <div class="asset-dims">${esc(asset.width)}×${esc(asset.height)} · ${esc(asset.seconds || 4)}s</div>
      </div>
    `;
    card.addEventListener('click', () => selectAsset(asset));
    elements.assetGrid.appendChild(card);
  });
}

function selectAsset(asset) {
  state.activeAsset = asset;
  
  // Highlight in Project Bin
  document.querySelectorAll('.asset-card').forEach(c => {
    const isMatch = c.getAttribute('data-asset-id') === asset.id || c.innerHTML.includes(asset.id);
    c.classList.toggle('active', isMatch);
  });

  // Highlight in Takes Filmstrip Shelf
  if (elements.takesFilmstripTrack) {
    elements.takesFilmstripTrack.querySelectorAll('.take-strip-card').forEach(c => {
      const isMatch = c.getAttribute('data-asset-id') === asset.id;
      c.classList.toggle('active', isMatch);
      c.setAttribute('aria-selected', isMatch ? 'true' : 'false');
    });
  }

  // Load Video source
  elements.mainVideoPlayer.src = `/api/assets/${encodeURIComponent(asset.id)}/file`;
  elements.mainVideoPlayer.load();
  elements.mainVideoPlayer.play().catch(() => {});
  setPlaying(true);

  if (asset.is_motionvector_master) {
    elements.resolutionTag.textContent = '4K MASTER · 3840×2160 UHD';
    elements.resolutionTag.className = 'bound-tag master-tag';
  } else if (asset.is_upscaled) {
    elements.resolutionTag.textContent = '4K UPSCALE · 3840×2160 UHD';
    elements.resolutionTag.className = 'bound-tag uhd-tag';
  } else {
    elements.resolutionTag.textContent = 'PREVIEW · SD (1024×576)';
    elements.resolutionTag.className = 'bound-tag preview-tag';
  }

  // Deep-load into Track V1
  const displayTitle = asset.overlay_title || asset.prompt || asset.id;
  elements.timelineClipName.textContent = displayTitle;
  elements.timelineClipDur.textContent = `${asset.seconds || 4.0}s`;
  
  if (elements.v1ClipTitle) {
    elements.v1ClipTitle.textContent = `V1: ${displayTitle} · ${asset.width || 1024}×${asset.height || 576} @ 24fps`;
  }

  if (elements.v1ThumbsContainer) {
    const thumbUrl = `/api/assets/${encodeURIComponent(asset.id)}/thumbnail`;
    elements.v1ThumbsContainer.innerHTML = `
      <div class="thumb-frame"><img src="${thumbUrl}" alt="" loading="lazy" onerror="this.style.opacity='0'" /></div>
      <div class="thumb-frame"><img src="${thumbUrl}" alt="" loading="lazy" onerror="this.style.opacity='0'" /></div>
      <div class="thumb-frame"><img src="${thumbUrl}" alt="" loading="lazy" onerror="this.style.opacity='0'" /></div>
      <div class="thumb-frame"><img src="${thumbUrl}" alt="" loading="lazy" onerror="this.style.opacity='0'" /></div>
    `;
  }

  // Bounds check In/Out markers
  const dur = asset.seconds || 4.0;
  if (state.inPoint !== null && state.inPoint > dur) state.inPoint = 0;
  if (state.outPoint !== null && state.outPoint > dur) state.outPoint = dur;
  updateInOutVisuals();

  buildTimelineRuler(dur);
  
  elements.mainVideoPlayer.addEventListener('loadedmetadata', () => {
    buildTimelineRuler(elements.mainVideoPlayer.duration);
    updatePlaybackProgress();
    updateInOutVisuals();
  }, { once: true });

  updateExportDrawerSource();
}

// ── NLE J-K-L Shuttle & Transport Controls ────────────────────
function togglePlayPause() {
  if (elements.mainVideoPlayer.paused) {
    shuttleStop();
    elements.mainVideoPlayer.play();
    setPlaying(true);
    if (elements.shuttleStatusPill) {
      elements.shuttleStatusPill.textContent = '▶ 1.0×';
      elements.shuttleStatusPill.className = 'shuttle-status-pill playing';
    }
  } else {
    shuttleStop();
  }
}

function shuttleStop() {
  if (state.shuttleInterval) {
    clearInterval(state.shuttleInterval);
    state.shuttleInterval = null;
  }
  state.shuttleRate = 0;
  elements.mainVideoPlayer.pause();
  elements.mainVideoPlayer.playbackRate = 1.0;
  setPlaying(false);

  if (elements.shuttleStatusPill) {
    elements.shuttleStatusPill.textContent = '❚❚ Paused';
    elements.shuttleStatusPill.className = 'shuttle-status-pill';
  }
  if (elements.speedLabel) elements.speedLabel.textContent = '1.0×';
}

function shuttleForward() {
  if (state.shuttleInterval) {
    clearInterval(state.shuttleInterval);
    state.shuttleInterval = null;
  }

  if (state.shuttleRate <= 0) {
    state.shuttleRate = 2; // 2x forward shuttle
  } else if (state.shuttleRate === 1) {
    state.shuttleRate = 2;
  } else if (state.shuttleRate === 2) {
    state.shuttleRate = 4;
  } else if (state.shuttleRate === 4) {
    state.shuttleRate = 8;
  } else {
    state.shuttleRate = 2;
  }

  elements.mainVideoPlayer.playbackRate = state.shuttleRate;
  elements.mainVideoPlayer.play().catch(() => {});
  setPlaying(true);

  if (elements.shuttleStatusPill) {
    elements.shuttleStatusPill.textContent = `▶▶ ${state.shuttleRate}.0×`;
    elements.shuttleStatusPill.className = 'shuttle-status-pill forward';
  }
  if (elements.speedLabel) elements.speedLabel.textContent = `${state.shuttleRate}.0×`;
}

function shuttleRewind() {
  elements.mainVideoPlayer.pause();
  if (state.shuttleInterval) {
    clearInterval(state.shuttleInterval);
    state.shuttleInterval = null;
  }

  if (state.shuttleRate >= 0) {
    state.shuttleRate = -2; // 2x rewind
  } else if (state.shuttleRate === -2) {
    state.shuttleRate = -4;
  } else if (state.shuttleRate === -4) {
    state.shuttleRate = -8;
  } else {
    state.shuttleRate = -2;
  }

  if (elements.shuttleStatusPill) {
    elements.shuttleStatusPill.textContent = `◀◀ ${Math.abs(state.shuttleRate)}.0×`;
    elements.shuttleStatusPill.className = 'shuttle-status-pill rewind';
  }

  // Smooth seek-safe reverse playback interval at 24fps
  const fps = 24;
  const stepSec = (Math.abs(state.shuttleRate) * (1 / fps));
  const intervalMs = Math.round(1000 / fps);

  setPlaying(true);
  state.shuttleInterval = setInterval(() => {
    const v = elements.mainVideoPlayer;
    if (!v.duration || v.currentTime <= 0) {
      shuttleStop();
      return;
    }
    v.currentTime = Math.max(0, v.currentTime - stepSec);
    updatePlaybackProgress();
  }, intervalMs);
}

function stepFrame(deltaFrames) {
  shuttleStop();
  const v = elements.mainVideoPlayer;
  const fps = 24;
  const deltaSec = deltaFrames / fps;
  v.currentTime = Math.max(0, Math.min(v.duration || 0, v.currentTime + deltaSec));
  updatePlaybackProgress();
}

function stepTime(delta) {
  shuttleStop();
  const v = elements.mainVideoPlayer;
  v.currentTime = Math.max(0, Math.min(v.duration || 0, v.currentTime + delta));
  updatePlaybackProgress();
}

function setInPoint() {
  const v = elements.mainVideoPlayer;
  state.inPoint = v.currentTime || 0;
  if (state.outPoint !== null && state.outPoint < state.inPoint) {
    state.outPoint = null;
  }
  updateInOutVisuals();
  showToast(`📍 In Point set: ${formatSMPTE(state.inPoint)}`);
}

function setOutPoint() {
  const v = elements.mainVideoPlayer;
  state.outPoint = v.currentTime || (v.duration || 4.0);
  if (state.inPoint !== null && state.inPoint > state.outPoint) {
    state.inPoint = 0;
  }
  updateInOutVisuals();
  showToast(`🏁 Out Point set: ${formatSMPTE(state.outPoint)}`);
}

function clearInOutPoints() {
  state.inPoint = null;
  state.outPoint = null;
  updateInOutVisuals();
  showToast('Cleared In/Out selection range');
}

function updateInOutVisuals() {
  const totalDur = (elements.mainVideoPlayer && elements.mainVideoPlayer.duration) || state.duration || 4.0;
  
  if (elements.markerInHandle) {
    if (state.inPoint !== null) {
      const inPct = Math.max(0, Math.min(100, (state.inPoint / totalDur) * 100));
      elements.markerInHandle.style.left = `${inPct}%`;
      elements.markerInHandle.style.display = 'flex';
    } else {
      elements.markerInHandle.style.display = 'none';
    }
  }

  if (elements.markerOutHandle) {
    if (state.outPoint !== null) {
      const outPct = Math.max(0, Math.min(100, (state.outPoint / totalDur) * 100));
      elements.markerOutHandle.style.left = `${outPct}%`;
      elements.markerOutHandle.style.display = 'flex';
    } else {
      elements.markerOutHandle.style.display = 'none';
    }
  }

  if (elements.timelineInOutRegion) {
    if (state.inPoint !== null || state.outPoint !== null) {
      const inVal = state.inPoint !== null ? state.inPoint : 0;
      const outVal = state.outPoint !== null ? state.outPoint : totalDur;
      const inPct = Math.max(0, Math.min(100, (inVal / totalDur) * 100));
      const outPct = Math.max(0, Math.min(100, (outVal / totalDur) * 100));
      const widthPct = Math.max(0, outPct - inPct);

      elements.timelineInOutRegion.style.left = `${inPct}%`;
      elements.timelineInOutRegion.style.width = `${widthPct}%`;
      elements.timelineInOutRegion.style.display = 'block';
    } else {
      elements.timelineInOutRegion.style.display = 'none';
    }
  }

  if (elements.timelineInOutBadge) {
    if (state.inPoint !== null || state.outPoint !== null) {
      const inStr = state.inPoint !== null ? formatSMPTE(state.inPoint) : '00:00:00:00';
      const outStr = state.outPoint !== null ? formatSMPTE(state.outPoint) : formatSMPTE(totalDur);
      const rangeSec = Math.max(0, (state.outPoint !== null ? state.outPoint : totalDur) - (state.inPoint !== null ? state.inPoint : 0));
      elements.timelineInOutBadge.textContent = `IN: ${inStr} · OUT: ${outStr} (${rangeSec.toFixed(1)}s)`;
      elements.timelineInOutBadge.className = 'inout-badge active-range';
    } else {
      elements.timelineInOutBadge.textContent = 'IN: --:-- · OUT: --:--';
      elements.timelineInOutBadge.className = 'inout-badge';
    }
  }

  if (elements.exportInOutRangeText) {
    const inVal = state.inPoint !== null ? state.inPoint : 0;
    const outVal = state.outPoint !== null ? state.outPoint : totalDur;
    elements.exportInOutRangeText.textContent = `${inVal.toFixed(1)}s - ${outVal.toFixed(1)}s`;
  }
}

function setPlaying(playing) {
  state.isPlaying = playing;
  if (playing) {
    elements.playIcon.innerHTML = '<rect x="6" y="4" width="4" height="16" fill="currentColor"></rect><rect x="14" y="4" width="4" height="16" fill="currentColor"></rect>';
  } else {
    elements.playIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3" fill="currentColor"></polygon>';
  }
}

function updatePlaybackProgress() {
  const v = elements.mainVideoPlayer;
  if (!v.duration) return;
  const pct = (v.currentTime / v.duration) * 100;
  elements.timelinePlayhead.style.left = `${pct}%`;
  
  // Update in-viewport scrubber
  const fill = document.getElementById('viewportProgressFill');
  const handle = document.getElementById('viewportProgressHandle');
  const buffered = document.getElementById('viewportProgressBuffered');
  if (fill) fill.style.width = `${pct}%`;
  if (handle) handle.style.left = `${pct}%`;
  
  if (buffered && v.buffered.length > 0) {
    const bufEnd = v.buffered.end(v.buffered.length - 1);
    buffered.style.width = `${(bufEnd / v.duration) * 100}%`;
  }
  
  elements.timecodeSMPTE.textContent = formatSMPTE(v.currentTime);
  elements.timecodeDuration.textContent = formatSMPTE(v.duration);
}

function formatSMPTE(sec) {
  const fps = 24;
  const totalFrames = Math.floor(sec * fps);
  const frames = totalFrames % fps;
  const totalSeconds = Math.floor(sec);
  const seconds = totalSeconds % 60;
  const minutes = Math.floor(totalSeconds / 60) % 60;
  const hours = Math.floor(totalSeconds / 3600);

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}:${String(frames).padStart(2, '0')}`;
}

function setGenerating(generating, text = '') {
  state.isGenerating = generating;
  elements.loadingOverlay.style.display = generating ? 'flex' : 'none';
  elements.loadingText.textContent = text;
  elements.btnGenerate.disabled = generating;
}

// ── Master 4K / ProRes 422 Export Drawer Controller ──────────
function openExportMasterDrawer() {
  if (!elements.exportMasterModal) return;
  elements.exportMasterModal.style.display = 'flex';
  updateExportDrawerSource();
}

function closeExportMasterDrawer() {
  if (!elements.exportMasterModal) return;
  elements.exportMasterModal.style.display = 'none';
  if (elements.exportStatusBox) elements.exportStatusBox.style.display = 'none';
  if (elements.btnStartExport) {
    elements.btnStartExport.disabled = false;
    elements.btnStartExportLabel.textContent = 'Export & Render Master';
  }
}

function updateExportDrawerSource() {
  const asset = state.activeAsset;
  if (!asset) return;

  if (elements.exportSourceThumb) {
    elements.exportSourceThumb.src = `/api/assets/${encodeURIComponent(asset.id)}/thumbnail`;
  }
  if (elements.exportSourceTitle) {
    elements.exportSourceTitle.textContent = asset.overlay_title || asset.prompt || asset.id;
  }
  if (elements.exportSourceRes) {
    elements.exportSourceRes.textContent = `${asset.width || 1024}×${asset.height || 576}`;
  }
  if (elements.exportSourceDur) {
    elements.exportSourceDur.textContent = `${asset.seconds || 4.0}s`;
  }
  if (elements.exportFullDurText) {
    elements.exportFullDurText.textContent = `${asset.seconds || 4.0}s`;
  }
  if (elements.inpExportTitle) {
    elements.inpExportTitle.value = state.overlayConfig.title;
  }
  if (elements.inpExportFormula) {
    elements.inpExportFormula.value = state.overlayConfig.formula;
  }
  updateInOutVisuals();
}

async function triggerMasterExport() {
  if (!state.activeAsset || state.exportConfig.isExporting) return;

  const preset = state.exportConfig.preset;
  const isProRes = preset === 'prores';
  const isUpscaleOnly = preset === 'upscale';
  const asset = state.activeAsset;

  state.exportConfig.isExporting = true;
  elements.btnStartExport.disabled = true;
  elements.btnStartExportLabel.textContent = 'Exporting Master...';
  elements.exportStatusBox.style.display = 'flex';
  elements.exportSuccessActions.style.display = 'none';
  elements.exportProgressBar.style.width = '15%';
  elements.exportStatusText.textContent = isProRes 
    ? 'Encoding Apple ProRes 422 HQ Broadcast Master...' 
    : isUpscaleOnly 
    ? 'Upscaling plate to 4K UHD with Apple Neural Engine...' 
    : 'Compositing H.264 High Profile Master...';

  try {
    let jobId = null;
    if (isUpscaleOnly) {
      const res = await fetch('/api/upscale-4k', {
        method: 'POST',
        headers: await authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          asset_id: asset.id,
          scale: 4,
          engine: 'coreml'
        })
      });
      const data = await res.json();
      jobId = data.output_id;
    } else {
      const res = await fetch('/api/composite-motionvector', {
        method: 'POST',
        headers: await authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          asset_id: asset.id,
          title: elements.inpExportTitle ? elements.inpExportTitle.value : state.overlayConfig.title,
          latex_formula: elements.inpExportFormula ? elements.inpExportFormula.value : state.overlayConfig.formula,
          accent_color: state.overlayConfig.accentColor,
          card_position: state.overlayConfig.position,
          export_4k: state.exportConfig.resolution === '4k',
          export_prores: isProRes,
        })
      });
      const data = await res.json();
      jobId = data.master_id;
    }

    elements.exportProgressBar.style.width = '50%';

    // Poll until complete
    for (let i = 0; i < 40; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const job = await fetchJob(jobId);
      if (job && job.status === 'failed') {
        throw new Error(job.error || 'Export failed');
      }
      if (job && job.status === 'completed') {
        elements.exportProgressBar.style.width = '100%';
        elements.exportStatusText.textContent = `✓ Export Complete: ${isProRes ? 'Apple ProRes 422 HQ Master' : '4K UHD Master'}`;
        elements.exportSpinner.style.display = 'none';
        elements.exportSuccessActions.style.display = 'flex';
        
        if (elements.btnDownloadExported) {
          elements.btnDownloadExported.href = `/api/assets/${encodeURIComponent(jobId)}/file`;
          elements.btnDownloadExported.download = `${jobId}.mp4`;
        }

        if (elements.btnLoadExportedToCanvas) {
          elements.btnLoadExportedToCanvas.onclick = async () => {
            await refreshAssets();
            const match = state.assets.find(a => a.id === jobId);
            if (match) selectAsset(match);
            closeExportMasterDrawer();
          };
        }

        await refreshAssets();
        showToast(`🎉 Master Export Ready: ${jobId}`);
        return;
      }
    }
    throw new Error('Export timed out');
  } catch (err) {
    console.error('Export error', err);
    elements.exportStatusText.textContent = `Export Failed: ${err.message}`;
    elements.exportProgressBar.style.backgroundColor = 'var(--accent-rose, #f43f5e)';
  } finally {
    state.exportConfig.isExporting = false;
    elements.btnStartExport.disabled = false;
    elements.btnStartExportLabel.textContent = 'Export & Render Master';
  }
}

// ── Timeline Ruler & Waveform Generation ─────────────────────
function buildTimelineRuler(totalDuration = 5) {
  const ruler = elements.timelineRuler;
  if (!ruler) return;
  
  // Preserve marker handles when rebuilding tick marks
  const inHandle = elements.markerInHandle;
  const outHandle = elements.markerOutHandle;
  ruler.innerHTML = '';
  if (inHandle) ruler.appendChild(inHandle);
  if (outHandle) ruler.appendChild(outHandle);
  
  const totalSec = Math.max(1, Math.ceil(totalDuration));
  const numMajorTicks = 10;
  const step = Math.max(1, Math.round(totalSec / numMajorTicks));
  
  for (let s = 0; s <= totalSec; s += step) {
    const pct = (s / totalSec) * 100;
    const tick = document.createElement('div');
    tick.className = 'ruler-tick major';
    tick.style.left = `${pct}%`;
    ruler.appendChild(tick);

    const label = document.createElement('div');
    label.className = 'ruler-label';
    label.style.left = `${pct}%`;
    
    const m = Math.floor(s / 60);
    const sec = s % 60;
    label.textContent = `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    ruler.appendChild(label);
  }

  updateInOutVisuals();
}

/**
 * Render a tactile, visually rich audio waveform with rounded bars,
 * gradient fills, and organic speech-like amplitude envelopes.
 */
function renderAudioWaveform() {
  const canvas = elements.audioWaveformCanvas;
  if (!canvas) return;

  // High-DPI canvas scaling
  const dpr = window.devicePixelRatio || 1;
  const displayW = canvas.clientWidth || 800;
  const displayH = canvas.clientHeight || 28;
  canvas.width = displayW * dpr;
  canvas.height = displayH * dpr;

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, displayW, displayH);

  // Tactile bar configuration
  const barCount = Math.floor(displayW / 4);
  const barWidth = Math.max(1.5, (displayW / barCount) - 1);
  const gap = (displayW - barCount * barWidth) / (barCount - 1);
  const maxBarHeight = displayH - 4;

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, displayH);
  grad.addColorStop(0, 'rgba(16, 185, 129, 0.9)');
  grad.addColorStop(0.5, 'rgba(16, 185, 129, 0.6)');
  grad.addColorStop(1, 'rgba(16, 185, 129, 0.3)');

  for (let i = 0; i < barCount; i++) {
    // Generate organic speech envelope: voiced regions with natural pauses
    const t = i / barCount;
    const voiceEnvelope = Math.sin(t * Math.PI) * 0.6 + 0.4;
    const syllable = Math.abs(Math.sin(i * 0.18)) * Math.abs(Math.cos(i * 0.09));
    const breathPause = (Math.sin(i * 0.03) > 0.85) ? 0.15 : 1.0;
    const microVariation = 0.7 + Math.random() * 0.3;

    const amplitude = syllable * voiceEnvelope * breathPause * microVariation;
    const barHeight = Math.max(2, amplitude * maxBarHeight);
    const x = i * (barWidth + gap);
    const y = (displayH - barHeight) / 2;

    ctx.fillStyle = grad;
    ctx.beginPath();
    const r = Math.min(barWidth / 2, 1.5);
    ctx.roundRect(x, y, barWidth, barHeight, r);
    ctx.fill();
  }
}

// ── Command Palette (⌘K) Controller ──────────────────────────
function toggleCommandPalette(open) {
  if (!elements.commandPaletteModal) return;
  elements.commandPaletteModal.style.display = open ? 'flex' : 'none';
  if (open) {
    elements.cmdSearchInput.value = '';
    elements.cmdSearchInput.focus();
  }
}

function executeCommandAction(action) {
  if (action === 'render-all') {
    renderAllStoryboardTakes();
  } else if (action === 'composite-4k' || action === 'export-master') {
    openExportMasterDrawer();
  } else if (action === 'enhance-prompt') {
    elements.btnEnhance.click();
  } else if (action === 'toggle-grid') {
    elements.btnToggleGrid.click();
  } else if (action === 'set-in-point') {
    setInPoint();
  } else if (action === 'set-out-point') {
    setOutPoint();
  } else if (action === 'clear-in-out') {
    clearInOutPoints();
  } else if (action === 'play-pause') {
    togglePlayPause();
  } else if (action === 'shuttle-rewind') {
    shuttleRewind();
  } else if (action === 'shuttle-stop') {
    shuttleStop();
  } else if (action === 'shuttle-forward') {
    shuttleForward();
  }
}

// Start application
window.addEventListener('DOMContentLoaded', init);
