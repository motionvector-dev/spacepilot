document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const navGpuDot = document.getElementById('nav-gpu-dot');
  const navGpuText = document.getElementById('nav-gpu-text');

  const badgeInstance = document.getElementById('badge-instance');
  const valInstanceId = document.getElementById('val-instance-id');
  const valInstanceIp = document.getElementById('val-instance-ip');
  const valInstanceType = document.getElementById('val-instance-type');

  const badgeWorker = document.getElementById('badge-worker');
  const valVram = document.getElementById('val-vram');
  const barVramFill = document.getElementById('bar-vram-fill');
  const valDevice = document.getElementById('val-device');

  const valCost = document.getElementById('val-cost');
  const valUptime = document.getElementById('val-uptime');
  const valRate = document.getElementById('val-rate');

  const btnRefresh = document.getElementById('btn-refresh');
  const btnLaunchBox = document.getElementById('btn-launch-box');
  const btnDeployWorker = document.getElementById('btn-deploy-worker');
  const btnSyncOutputs = document.getElementById('btn-sync-outputs');
  const btnCopySsh = document.getElementById('btn-copy-ssh');
  const btnTerminateBox = document.getElementById('btn-terminate-box');

  const terminalBody = document.getElementById('terminal-body');
  const btnClearTerm = document.getElementById('btn-clear-term');
  const btnPauseTerm = document.getElementById('btn-pause-term');

  
  const cfgProvider = document.getElementById('cfg-provider');
  const cfgShadeformKey = document.getElementById('cfg-shadeform-key');
  const cfgRunpodKey = document.getElementById('cfg-runpod-key');
  const cfgAwsProfile = document.getElementById('cfg-aws-profile');
  const cfgLocalHost = document.getElementById('cfg-local-host');
  
  const modalOnboarding = document.getElementById('modal-onboarding');
  const providerCards = document.querySelectorAll('.provider-card');
  const modalOnboardingConfirm = document.getElementById('modal-onboarding-confirm');
  
  let selectedOnboardProvider = null;

  const cfgRegion = document.getElementById('cfg-region');
  const cfgInstanceType = document.getElementById('cfg-instance-type');
  const cfgKeyFile = document.getElementById('cfg-key-file');
  const cfgDuration = document.getElementById('cfg-duration');
  const cfgStg = document.getElementById('cfg-stg');
  const cfgModality = document.getElementById('cfg-modality');
  const cfgIdleShutdown = document.getElementById('cfg-idle-shutdown');
  const btnSaveCfg = document.getElementById('btn-save-cfg');

  // Spot rate lookup — mirrors sidebar.js INSTANCE_TYPES catalogue
  const SPOT_RATES = {
    'g4dn.xlarge': 0.16, 'g4dn.2xlarge': 0.23, 'g4dn.4xlarge': 0.38, 'g4dn.12xlarge': 1.48,
    'g5.xlarge': 0.51,   'g5.2xlarge': 0.76,   'g5.4xlarge': 1.21,   'g5.12xlarge': 4.23,
    'g6e.xlarge': 0.75,  'g6e.2xlarge': 1.10,  'g6e.4xlarge': 1.60,  'g6e.8xlarge': 2.35, 'g6e.12xlarge': 4.80,
    'p4d.24xlarge': 9.83, 'p5.48xlarge': 43.04,
  };

  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toast-msg');

  let currentSshCmd = null;
  let logStreamPaused = false;
  let eventSource = null;

  // Toast Helper
  function showToast(msg) {
    toastMsg.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3500);
  }

  // Append Log Line to Terminal
  function appendLog(line, type = 'info') {
    if (logStreamPaused) return;
    const div = document.createElement('div');
    div.className = `terminal-line ${type}`;
    div.textContent = line;
    terminalBody.appendChild(div);
    terminalBody.scrollTop = terminalBody.scrollHeight;
  }

  // 1. Telemetry Polling
  async function fetchCockpitStatus() {
    try {
      const res = await fetch('/api/cockpit/status');
      if (!res.ok) return;
      const data = await res.json();

      const inst = data.instance || {};
      const worker = data.worker || {};
      const isRunning = inst.state === 'running';

      // Header Pill
      if (isRunning && data.worker_ready) {
        navGpuDot.className = 'gpu-dot online';
        /* navGpuText handled by global ticker */
      } else if (isRunning) {
        navGpuDot.className = 'gpu-dot busy';
        /* navGpuText handled by global ticker */
      } else {
        navGpuDot.className = 'gpu-dot';
        /* navGpuText handled by global ticker */
      }

      // Instance Card
      if (isRunning) {
        badgeInstance.className = 'badge-status badge-online';
        badgeInstance.textContent = 'Running';
        valInstanceId.textContent = inst.id || 'Active Box';
        valInstanceIp.textContent = inst.ip || '--';
        valInstanceType.textContent = `${inst.type || 'g6e.xlarge'} · ${data.config?.region || 'us-east-1'}`;

        btnLaunchBox.disabled = true;
        btnDeployWorker.disabled = false;
        btnSyncOutputs.disabled = false;
        btnCopySsh.disabled = false;
        btnTerminateBox.disabled = false;
      } else {
        badgeInstance.className = 'badge-status badge-offline';
        badgeInstance.textContent = inst.state || 'Offline';
        valInstanceId.textContent = inst.id ? `${inst.id} (${inst.state})` : 'No Active Box';
        valInstanceIp.textContent = '--';
        valInstanceType.textContent = `${data.config?.instance_type || 'g6e.xlarge'} · ${data.config?.region || 'us-east-1'}`;

        btnLaunchBox.disabled = false;
        btnDeployWorker.disabled = true;
        btnSyncOutputs.disabled = true;
        btnCopySsh.disabled = true;
        btnTerminateBox.disabled = true;
      }

      // Worker & VRAM Card
      if (worker.ok || worker.loaded) {
        badgeWorker.className = 'badge-status badge-online';
        badgeWorker.textContent = 'Resident Ready';
        const used = worker.vram_used_gib || 28.4;
        const total = worker.vram_total_gib || 48.0;
        valVram.textContent = `${used.toFixed(1)} / ${total.toFixed(1)} GiB`;
        const pct = Math.min(100, Math.round((used / total) * 100));
        barVramFill.style.width = `${pct}%`;
        valDevice.textContent = worker.device_name || 'NVIDIA L40S';
      } else {
        badgeWorker.className = 'badge-status badge-offline';
        badgeWorker.textContent = isRunning ? 'Starting...' : 'Offline';
        valVram.textContent = '0.0 / 48.0 GiB';
        barVramFill.style.width = '0%';
        valDevice.textContent = isRunning ? 'NVIDIA L40S' : 'None';
      }

      // Billing Card
      /* valCost handled by global ticker */
      /* valUptime handled by global ticker */
      valRate.textContent = `$${(data.config?.spot_hourly_rate || 0.75).toFixed(2)} / hr`;

      currentSshCmd = data.ssh_command;
    } catch (e) {
      console.warn('Telemetry error:', e);
    }
  }

  // 2. Fetch Auth Token Helper
  async function getAuthToken() {
    try {
      const res = await fetch('/api/token');
      if (res.ok) {
        const data = await res.json();
        return data.token;
      }
    } catch (e) {}
    return null;
  }

  // Modal Elements
  const modalLaunch = document.getElementById('modal-launch');
  const modalLaunchType = document.getElementById('modal-launch-type');
  const modalLaunchRegion = document.getElementById('modal-launch-region');
  const modalLaunchRate = document.getElementById('modal-launch-rate');
  const modalLaunchCancel = document.getElementById('modal-launch-cancel');
  const modalLaunchConfirm = document.getElementById('modal-launch-confirm');

  const modalTerminate = document.getElementById('modal-terminate');
  const modalTerminateId = document.getElementById('modal-terminate-id');
  const modalTerminateUptime = document.getElementById('modal-terminate-uptime');
  const modalTerminateInput = document.getElementById('modal-terminate-input');
  const modalTerminateCancel = document.getElementById('modal-terminate-cancel');
  const modalTerminateConfirm = document.getElementById('modal-terminate-confirm');

  // Modal Helpers
  function openLaunchModal() {
    const selectedType = cfgInstanceType?.value || 'g6e.xlarge';
    const selectedRegion = cfgRegion?.value || 'us-east-1';
    const rate = SPOT_RATES[selectedType] || 0.75;

    if (modalLaunchType) modalLaunchType.textContent = `${selectedType}`;
    if (modalLaunchRegion) modalLaunchRegion.textContent = selectedRegion;
    if (modalLaunchRate) modalLaunchRate.textContent = `~$${rate.toFixed(2)} / hr`;

    modalLaunch.classList.add('open');
  }

  function closeLaunchModal() {
    modalLaunch.classList.remove('open');
  }

  function openTerminateModal() {
    if (modalTerminateId) modalTerminateId.textContent = valInstanceId.textContent;
    if (modalTerminateUptime) modalTerminateUptime.textContent = valUptime.textContent;
    if (modalTerminateInput) {
      modalTerminateInput.value = '';
      modalTerminateConfirm.disabled = true;
    }
    modalTerminate.classList.add('open');
    setTimeout(() => modalTerminateInput?.focus(), 50);
  }

  function closeTerminateModal() {
    modalTerminate.classList.remove('open');
  }

  modalTerminateInput?.addEventListener('input', (e) => {
    const val = e.target.value.trim().toUpperCase();
    modalTerminateConfirm.disabled = val !== 'TERMINATE';
  });

  modalLaunchCancel?.addEventListener('click', closeLaunchModal);
  modalTerminateCancel?.addEventListener('click', closeTerminateModal);

  // Close modals on backdrop click
  modalLaunch?.addEventListener('click', (e) => {
    if (e.target === modalLaunch) closeLaunchModal();
  });
  modalTerminate?.addEventListener('click', (e) => {
    if (e.target === modalTerminate) closeTerminateModal();
  });

  // 3. Actions
  btnLaunchBox.addEventListener('click', () => {
    openLaunchModal();
  });

  modalLaunchConfirm.addEventListener('click', async () => {
    closeLaunchModal();
    btnLaunchBox.disabled = true;
    appendLog('[Cockpit] Dispatching Spot GPU Launch with explicit confirmation...', 'system');
    showToast('Launching AWS Spot GPU box...');
    const token = await getAuthToken();
    try {
      const res = await fetch('/api/gpu/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token },
        body: JSON.stringify({ confirm: true })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Launch failed');
      }
      appendLog(`[Cockpit] ${data.message || data.status}`, 'success');
      showToast('GPU box launching (billing started)');
      setTimeout(fetchCockpitStatus, 2000);
    } catch (err) {
      appendLog(`[Cockpit] Launch error: ${err.message}`, 'error');
      showToast(`Launch error: ${err.message}`);
      btnLaunchBox.disabled = false;
    }
  });

  btnDeployWorker.addEventListener('click', async () => {
    btnDeployWorker.disabled = true;
    appendLog('[Cockpit] Hot-deploying ltx_worker.py to remote GPU box...', 'system');
    showToast('Deploying worker code...');
    const token = await getAuthToken();
    try {
      const res = await fetch('/api/gpu/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token }
      });
      const data = await res.json();
      appendLog(`[Cockpit] ${data.message || data.status}`, 'success');
      showToast('Worker deployment triggered in background');
    } catch (err) {
      appendLog(`[Cockpit] Deploy error: ${err.message}`, 'error');
    } finally {
      setTimeout(() => { btnDeployWorker.disabled = false; }, 3000);
    }
  });

  btnSyncOutputs.addEventListener('click', async () => {
    btnSyncOutputs.disabled = true;
    appendLog('[Cockpit] Rsyncing /scratch/out/ to local outputs/...', 'system');
    showToast('Syncing remote outputs...');
    const token = await getAuthToken();
    try {
      const res = await fetch('/api/gpu/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token }
      });
      const data = await res.json();
      appendLog(`[Cockpit] ${data.message}`, 'success');
      showToast('Sync complete');
    } catch (err) {
      appendLog(`[Cockpit] Sync error: ${err.message}`, 'error');
    } finally {
      btnSyncOutputs.disabled = false;
    }
  });

  btnCopySsh.addEventListener('click', () => {
    if (currentSshCmd) {
      navigator.clipboard.writeText(currentSshCmd);
      showToast('Copied SSH command to clipboard');
      appendLog(`[Cockpit] Copied: ${currentSshCmd}`, 'info');
    }
  });

  btnTerminateBox.addEventListener('click', () => {
    openTerminateModal();
  });

  modalTerminateConfirm.addEventListener('click', async () => {
    closeTerminateModal();
    btnTerminateBox.disabled = true;
    appendLog('[Cockpit] Terminating GPU box with explicit confirmation...', 'system');
    showToast('Terminating instance...');
    const token = await getAuthToken();
    try {
      const res = await fetch('/api/gpu/terminate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token },
        body: JSON.stringify({ confirm: true })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Termination failed');
      }
      appendLog(`[Cockpit] ${data.message}`, 'success');
      showToast('GPU box terminated. Billing stopped.');
      fetchCockpitStatus();
    } catch (err) {
      appendLog(`[Cockpit] Terminate error: ${err.message}`, 'error');
      showToast(`Terminate error: ${err.message}`);
      btnTerminateBox.disabled = false;
    }
  });

  btnRefresh.addEventListener('click', () => {
    fetchCockpitStatus();
    showToast('Telemetry refreshed');
  });

  // 4. Log Stream SSE
  function startLogStream() {
    if (eventSource) eventSource.close();
    try {
      eventSource = new EventSource('/api/gpu/logs/stream');
      eventSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          appendLog(data.line, data.type || 'info');
        } catch (err) {
          appendLog(e.data, 'info');
        }
      };
      eventSource.onerror = () => {
        // Silent reconnect
      };
    } catch (e) {}
  }

  btnClearTerm.addEventListener('click', () => {
    terminalBody.innerHTML = '';
  });

  btnPauseTerm.addEventListener('click', () => {
    logStreamPaused = !logStreamPaused;
    btnPauseTerm.textContent = logStreamPaused ? 'Resume' : 'Pause';
    if (!logStreamPaused) {
      appendLog('[Cockpit] Log stream resumed.', 'system');
    }
  });

  // 5. Load and Save Config
  
  async function loadConfig() {
    try {
      const res = await fetch('/api/cockpit/config');
      if (res.ok) {
        const data = await res.json();
        const cfg = data.config || {};
        
        if (!cfg.provider && !localStorage.getItem('spacepilot_onboarded')) {
          showOnboardingModal();
        }
        
        if (cfg.provider) {
          cfgProvider.value = cfg.provider;
          localStorage.setItem('spacepilot_onboarded', 'true');
        }
        if (cfg.shadeform_api_key) cfgShadeformKey.value = cfg.shadeform_api_key;
        if (cfg.runpod_api_key) cfgRunpodKey.value = cfg.runpod_api_key;
        if (cfg.aws_profile) cfgAwsProfile.value = cfg.aws_profile;
        if (cfg.local_host) cfgLocalHost.value = cfg.local_host;
        
        updateProviderVisibility();
        
        if (cfg.region) cfgRegion.value = cfg.region;
        if (cfg.instance_type) cfgInstanceType.value = cfg.instance_type;
        if (cfg.key_file) cfgKeyFile.value = cfg.key_file;
        if (cfg.default_duration) cfgDuration.value = cfg.default_duration.toString();
        if (cfg.default_stg) cfgStg.value = cfg.default_stg.toString();
      }
    } catch (e) {}
  }
  
  function updateProviderVisibility() {
    if (!cfgProvider) return;
    document.querySelectorAll('.provider-setting').forEach(el => {
      el.style.display = el.dataset.prov === cfgProvider.value ? 'block' : 'none';
    });
  }
  
  if (cfgProvider) {
    cfgProvider.addEventListener('change', updateProviderVisibility);
  }
  
  function showOnboardingModal() {
    if(modalOnboarding) modalOnboarding.style.display = 'flex';
  }
  
  providerCards.forEach(card => {
    card.addEventListener('click', () => {
      providerCards.forEach(c => {
         c.style.borderColor = 'var(--border-light)';
         c.style.background = 'transparent';
         const input = c.querySelector('input');
         if(input) input.style.display = 'none';
         const p = c.querySelector('#onboard-local-msg');
         if(p) p.style.display = 'none';
      });
      card.style.borderColor = 'var(--accent-blue)';
      card.style.background = 'rgba(59, 130, 246, 0.05)';
      
      const input = card.querySelector('input');
      if(input) {
        input.style.display = 'block';
        input.focus();
      }
      const p = card.querySelector('#onboard-local-msg');
      if(p) p.style.display = 'block';
      
      selectedOnboardProvider = card.dataset.provider;
      modalOnboardingConfirm.disabled = false;
    });
  });
  
  if(modalOnboardingConfirm) {
    modalOnboardingConfirm.addEventListener('click', async () => {
      let keyData = {};
      keyData.provider = selectedOnboardProvider;
      if (selectedOnboardProvider === 'shadeform') {
         keyData.shadeform_api_key = document.getElementById('onboard-shadeform-key').value;
      } else if (selectedOnboardProvider === 'aws') {
         keyData.aws_profile = document.getElementById('onboard-aws-profile').value;
      }
      
      const token = await getAuthToken();
      try {
        await fetch('/api/cockpit/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token },
          body: JSON.stringify({ config: keyData })
        });
        localStorage.setItem('spacepilot_onboarded', 'true');
        modalOnboarding.style.display = 'none';
        loadConfig();
        showToast('Provider connected successfully');
      } catch (e) {
        showToast('Error saving provider settings');
      }
    });
  }

  
  btnSaveCfg.addEventListener('click', async () => {
    const token = await getAuthToken();
    const updated = {
      provider: cfgProvider.value,
      shadeform_api_key: cfgShadeformKey.value,
      runpod_api_key: cfgRunpodKey.value,
      aws_profile: cfgAwsProfile.value,
      local_host: cfgLocalHost.value,
      region: cfgRegion.value,
      instance_type: cfgInstanceType.value,
      key_file: cfgKeyFile.value,
      default_duration: parseFloat(cfgDuration.value),
      default_stg: parseFloat(cfgStg.value)
    };
    try {
      const res = await fetch('/api/cockpit/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token },
        body: JSON.stringify({ config: updated })
      });
      if (res.ok) {
        showToast('✓ Settings saved');
        loadConfig();
      }
    } catch (e) {
      showToast('Error saving settings');
    }
  });

  // 6. Live Hot-Reload Listener
  try {
    const reloadSource = new EventSource('/api/live-reload');
    reloadSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === 'reload-css') {
        document.querySelectorAll('link[rel="stylesheet"]').forEach(l => {
          const u = new URL(l.href);
          u.searchParams.set('t', Date.now());
          l.href = u.toString();
        });
      } else if (data.event === 'reload-full') {
        window.location.reload();
      }
    };
  } catch (e) {}

  // Init
  fetchCockpitStatus();
  loadConfig();
  startLogStream();
  setInterval(fetchCockpitStatus, 5000);

  // ------------------------------------------------------------------
  // Inspect Mode Drawer
  // ------------------------------------------------------------------
  const btnInspectGpu = document.getElementById('btn-inspect-gpu');
  const drawerInspect = document.getElementById('drawer-inspect');
  const btnCloseInspect = document.getElementById('btn-close-inspect');
  const tabBtns = document.querySelectorAll('.drawer-tabs .tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const inspectIp = document.getElementById('inspect-ip');
  let xterm = null;
  let sshWs = null;

  if (btnInspectGpu) {
    btnInspectGpu.addEventListener('click', () => {
      drawerInspect.style.display = 'flex';
      const valInstanceIp = document.getElementById('val-instance-ip');
      inspectIp.textContent = valInstanceIp ? valInstanceIp.textContent : '--';
      if (!xterm) {
        initTerminal();
      }
    });
  }

  if (btnCloseInspect) {
    btnCloseInspect.addEventListener('click', () => {
      drawerInspect.style.display = 'none';
    });
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      tabBtns.forEach(b => {
        b.classList.remove('active');
        b.style.borderBottomColor = 'transparent';
        b.style.color = 'var(--text-muted)';
      });
      const targetBtn = e.target;
      targetBtn.classList.add('active');
      targetBtn.style.borderBottomColor = 'var(--accent-blue)';
      targetBtn.style.color = 'var(--text-main)';

      tabPanes.forEach(p => p.style.display = 'none');
      const targetId = targetBtn.getAttribute('data-tab');
      document.getElementById(targetId).style.display = 'block';

      if (targetId === 'tab-metrics') {
        fetchMetrics();
      }
    });
  });

  async function initTerminal() {
    const container = document.getElementById('terminal-container');
    container.innerHTML = ''; // clear

    xterm = new Terminal({
      cursorBlink: true,
      theme: { background: '#000000', foreground: '#ffffff' },
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 13
    });
    xterm.open(container);

    const token = await getAuthToken();
    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    sshWs = new WebSocket(`${wsProto}//${location.host}/api/gpu/inspect/shell`);

    sshWs.onopen = () => {
      sshWs.send(JSON.stringify({ type: 'auth', token }));
      sshWs.send(JSON.stringify({ type: 'resize', cols: xterm.cols, rows: xterm.rows }));
    };

    sshWs.onmessage = (e) => {
      xterm.write(e.data);
    };

    sshWs.onclose = () => {
      xterm.write('\r\n[Disconnected from SSH bridge]\r\n');
    };

    xterm.onData(data => {
      if (sshWs && sshWs.readyState === WebSocket.OPEN) {
        sshWs.send(data);
      }
    });

    xterm.onResize(size => {
      if (sshWs && sshWs.readyState === WebSocket.OPEN) {
        sshWs.send(JSON.stringify({ type: 'resize', cols: size.cols, rows: size.rows }));
      }
    });
  }

  async function fetchMetrics() {
    const btnRefresh = document.getElementById('btn-refresh-metrics');
    if (btnRefresh) btnRefresh.disabled = true;
    
    document.getElementById('metric-gpu-temp').textContent = 'Loading...';
    document.getElementById('metric-vram').textContent = 'Loading...';
    document.getElementById('metric-disk').textContent = 'Loading...';
    document.getElementById('metric-ram').textContent = 'Loading...';

    const token = await getAuthToken();
    try {
      const res = await fetch('/api/gpu/inspect/metrics', {
        headers: { 'X-SpacePilot-Token': token }
      });
      const data = await res.json();
      if (res.ok && data.gpu) {
        document.getElementById('metric-gpu-temp').textContent = data.gpu.temperature + ' °C';
        document.getElementById('metric-vram').textContent = data.gpu.memory_used + ' / ' + data.gpu.memory_total;
        document.getElementById('metric-disk').textContent = data.disk || 'Unavailable';
        document.getElementById('metric-ram').textContent = data.memory || 'Unavailable';
      } else {
        document.getElementById('metric-gpu-temp').textContent = 'Error';
        document.getElementById('metric-vram').textContent = 'Error';
        document.getElementById('metric-disk').textContent = data.detail || 'Unavailable';
      }
    } catch (e) {
      document.getElementById('metric-gpu-temp').textContent = 'Err';
    } finally {
      if (btnRefresh) btnRefresh.disabled = false;
    }
  }

  const btnRefreshMetrics = document.getElementById('btn-refresh-metrics');
  if (btnRefreshMetrics) {
    btnRefreshMetrics.addEventListener('click', fetchMetrics);
  }

  document.querySelectorAll('.action-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const action = e.target.getAttribute('data-action');
      const outDiv = document.getElementById('action-output');
      const outText = document.getElementById('action-output-text');
      
      e.target.disabled = true;
      e.target.textContent = 'Running...';
      outDiv.style.display = 'block';
      outText.textContent = `Executing ${action}...`;

      const token = await getAuthToken();
      try {
        const res = await fetch('/api/gpu/inspect/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token },
          body: JSON.stringify({ action })
        });
        const data = await res.json();
        outText.textContent = data.output || data.message || data.detail || 'Done';
      } catch (err) {
        outText.textContent = `Error: ${err.message}`;
      } finally {
        e.target.disabled = false;
        if (action === 'clear_tmp') e.target.textContent = 'Clear';
        else e.target.textContent = 'Restart';
      }
    });
  });

  // Enable/Disable inspect button based on instance state
  const observer = new MutationObserver(() => {
    const badge = document.getElementById('badge-instance');
    if (badge && badge.classList.contains('badge-online')) {
      if (btnInspectGpu) btnInspectGpu.disabled = false;
    } else {
      if (btnInspectGpu) btnInspectGpu.disabled = true;
      if (drawerInspect && drawerInspect.style.display !== 'none') {
        drawerInspect.style.display = 'none';
      }
    }
  });
  // ─────────────────────────────────────────────────────────────────────────
  // SkyPilot Multi-Cloud Spot Arbitrage & Preemption Failover
  // ─────────────────────────────────────────────────────────────────────────
  const skyTbody = document.getElementById('sky-arbitrage-tbody');
  const skyActiveName = document.getElementById('sky-active-name');
  const skyActiveBadge = document.getElementById('sky-active-badge');
  const skyFailoverCount = document.getElementById('sky-failover-count');
  const btnSkyFailover = document.getElementById('btn-sky-failover');
  const btnSkyYaml = document.getElementById('btn-sky-yaml');

  async function fetchSkyStatus() {
    try {
      const res = await fetch('/api/sky/status');
      if (!res.ok) return;
      const data = await res.json();
      if (skyActiveName) {
        skyActiveName.textContent = data.active ? `${data.cluster_name} (${data.provider})` : 'Auto-Arbitrage Mode';
      }
      if (skyActiveBadge) {
        skyActiveBadge.textContent = data.active ? `● ${data.spot_hourly_rate_usd ? '$' + data.spot_hourly_rate_usd + '/hr' : 'Active'} · R2 Synced` : '● R2 Checkpoint Synced';
        skyActiveBadge.style.color = data.active ? 'var(--accent-emerald)' : 'var(--text-dim)';
      }
      if (skyFailoverCount) {
        skyFailoverCount.textContent = data.preemption_failover_count || '0';
      }
    } catch (e) {
      console.warn('SkyPilot status fetch error:', e);
    }
  }

  async function fetchSkyClouds() {
    if (!skyTbody) return;
    try {
      const res = await fetch('/api/sky/clouds');
      if (!res.ok) return;
      const data = await res.json();
      const clouds = data.arbitrage_matrix || [];

      skyTbody.innerHTML = '';
      clouds.forEach(cloud => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border-light)';
        
        const riskColor = cloud.preemption_risk === 'very-low' ? 'var(--accent-emerald)' : (cloud.preemption_risk === 'low' ? 'var(--accent-cyan)' : 'var(--accent-amber)');
        const isBestBadge = cloud.is_cheapest ? '<span style="background: rgba(16,185,129,0.2); color: var(--accent-emerald); font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-left: 6px;">Cheapest</span>' : '';

        tr.innerHTML = `
          <td style="padding: 8px; font-weight: 600; color: var(--text-main);">${cloud.name} ${isBestBadge}</td>
          <td style="padding: 8px; color: var(--text-muted);">${cloud.accelerator}</td>
          <td style="padding: 8px; color: var(--text-dim);">${cloud.vram_gb} GB</td>
          <td style="padding: 8px; font-weight: 700; color: var(--accent-emerald);">$${cloud.spot_price_usd.toFixed(2)}</td>
          <td style="padding: 8px; color: var(--text-dim); text-decoration: line-through;">$${cloud.ondemand_price_usd.toFixed(2)}</td>
          <td style="padding: 8px; color: ${riskColor}; font-weight: 600;">${cloud.preemption_risk.toUpperCase()} (${cloud.preemption_rate_pct}%)</td>
          <td style="padding: 8px;">
            <button class="btn-action btn-sky-launch" data-provider="${cloud.provider}" data-accel="${cloud.accelerator}" style="font-size: 11px; padding: 3px 8px;">
              Route
            </button>
          </td>
        `;
        skyTbody.appendChild(tr);
      });

      // Attach launch handlers
      document.querySelectorAll('.btn-sky-launch').forEach(b => {
        b.addEventListener('click', async (e) => {
          const prov = e.target.getAttribute('data-provider');
          const accel = e.target.getAttribute('data-accel');
          e.target.disabled = true;
          e.target.textContent = 'Scheduling...';
          const token = await getAuthToken();
          try {
            const schedRes = await fetch('/api/sky/schedule', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token },
              body: JSON.stringify({ task_name: `spacepilot-${prov}-worker`, provider: prov, accelerator: accel, use_spot: true })
            });
            const sData = await schedRes.json();
            showToast(sData.message || `Scheduled on ${prov}`);
            fetchSkyStatus();
          } catch (err) {
            showToast(`SkyPilot dispatch error: ${err.message}`);
          } finally {
            e.target.disabled = false;
            e.target.textContent = 'Route';
          }
        });
      });

    } catch (e) {
      console.warn('SkyPilot clouds fetch error:', e);
    }
  }

  if (btnSkyFailover) {
    btnSkyFailover.addEventListener('click', async () => {
      btnSkyFailover.disabled = true;
      btnSkyFailover.textContent = 'Failing over...';
      const token = await getAuthToken();
      try {
        const res = await fetch('/api/sky/failover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-SpacePilot-Token': token },
          body: JSON.stringify({ reason: 'Simulated spot preemption / arbitrage rebalance' })
        });
        const data = await res.json();
        showToast(data.message || 'Preemption failover complete');
        fetchSkyStatus();
        fetchSkyClouds();
      } catch (err) {
        showToast(`Failover error: ${err.message}`);
      } finally {
        btnSkyFailover.disabled = false;
        btnSkyFailover.textContent = '⚡ Trigger Preemption Failover';
      }
    });
  }

  if (btnSkyYaml) {
    btnSkyYaml.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/sky/yaml?cloud=lambda&accelerators=L40S:1');
        const data = await res.json();
        alert(`📄 Declarative SkyPilot YAML Specification (infra/skypilot.yaml):\n\n${data.yaml}`);
      } catch (e) {
        showToast('Failed to load SkyPilot YAML');
      }
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Local Compute & Model Registry
  // ─────────────────────────────────────────────────────────────────────────
  async function loadLocalComputeProfile() {
    try {
      const res = await fetch('/api/compute/models/recommended');
      if (!res.ok) return;
      const data = await res.json();
      
      const dev = data.device || {};
      const recs = data.recommendations || [];

      const badgeBackend = document.getElementById('badge-local-backend');
      const badgeUsable = document.getElementById('badge-local-usable');
      const devName = document.getElementById('local-device-name');
      const memStats = document.getElementById('local-memory-stats');
      const isaStats = document.getElementById('local-isa-stats');
      const cacheQuota = document.getElementById('local-cache-quota');
      const tableBody = document.getElementById('table-local-models-body');

      if (badgeBackend) {
        badgeBackend.textContent = dev.backend === 'metal_mps' ? 'Apple Metal (MPS)' : (dev.backend === 'cuda' ? 'NVIDIA CUDA' : 'CPU Only');
      }
      if (badgeUsable) {
        badgeUsable.textContent = `${dev.vram_usable_gb || 0} GB Usable`;
      }
      if (devName) {
        devName.textContent = dev.device_name || 'Host Compute';
      }
      if (memStats) {
        memStats.textContent = `${dev.ram_total_gb || 0} GB Total / ${dev.ram_free_gb || 0} GB Free`;
      }
      if (isaStats) {
        isaStats.textContent = dev.isa_flags || 'Standard SIMD';
      }
      if (cacheQuota && data.cache_dir) {
        cacheQuota.textContent = data.cache_dir.replace(/^.*(?=\/\.cache)/, '~');
      }

      if (tableBody) {
        tableBody.innerHTML = '';
        recs.forEach(m => {
          const row = document.createElement('tr');
          row.style.cssText = 'border-bottom: 1px solid var(--mv-border);';

          const fitColor = m.execution_route === 'local' ? 'var(--accent-emerald)' : (m.execution_route === 'local_constrained' ? 'var(--accent-amber)' : 'var(--mv-text-muted)');
          const isDownloaded = m.is_downloaded;

          row.innerHTML = `
            <td style="padding: 10px 14px; font-weight: 700; color: var(--mv-text); text-transform: capitalize;">${m.task.replace('_', ' ')}</td>
            <td style="padding: 10px 14px; font-family: var(--font-mono); color: var(--mv-text);">${m.name} <span style="font-size: 10px; color: var(--mv-text-muted);">(${m.precision})</span></td>
            <td style="padding: 10px 14px; font-family: var(--font-mono); color: var(--mv-text-muted);">${m.size_gb} GB</td>
            <td style="padding: 10px 14px; font-family: var(--font-mono); font-size: 11px; color: ${fitColor};">${m.fit_label}</td>
            <td style="padding: 10px 14px; text-align: right;">
              <button class="btn-action btn-download-model" data-id="${m.model_id}" style="padding: 4px 10px; font-size: 11px; ${isDownloaded ? 'background: rgba(16,185,129,0.15); color: var(--accent-emerald); border-color: rgba(16,185,129,0.3);' : ''}">
                ${isDownloaded ? '✓ Cached' : '⬇ Download'}
              </button>
            </td>
          `;
          tableBody.appendChild(row);
        });

        // Wire download buttons
        document.querySelectorAll('.btn-download-model').forEach(btn => {
          btn.addEventListener('click', async (e) => {
            const modelId = e.currentTarget.dataset.id;
            e.currentTarget.disabled = true;
            e.currentTarget.textContent = '⏳ Downloading...';
            
            try {
              const token = await getAuthToken();
              const dlRes = await fetch('/api/compute/models/download', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'X-SpacePilot-Token': token
                },
                body: JSON.stringify({ model_id: modelId })
              });
              if (dlRes.ok) {
                showToast(`Model ${modelId} cached successfully`);
                loadLocalComputeProfile();
              } else {
                showToast(`Failed to download model ${modelId}`);
                e.currentTarget.disabled = false;
                e.currentTarget.textContent = '⬇ Download';
              }
            } catch (err) {
              showToast(`Error downloading model: ${err}`);
              e.currentTarget.disabled = false;
              e.currentTarget.textContent = '⬇ Download';
            }
          });
        });
      }
    } catch (e) {
      console.warn('Failed to load local compute profile:', e);
    }
  }

  // Initial fetch
  fetchSkyStatus();
  fetchSkyClouds();
  loadLocalComputeProfile();

});


