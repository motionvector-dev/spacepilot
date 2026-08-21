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

  const cfgRegion = document.getElementById('cfg-region');
  const cfgInstanceType = document.getElementById('cfg-instance-type');
  const cfgKeyFile = document.getElementById('cfg-key-file');
  const cfgDuration = document.getElementById('cfg-duration');
  const cfgStg = document.getElementById('cfg-stg');
  const cfgModality = document.getElementById('cfg-modality');
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
        headers: { 'Content-Type': 'application/json', 'X-Pluto-Token': token },
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
        headers: { 'Content-Type': 'application/json', 'X-Pluto-Token': token }
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
        headers: { 'Content-Type': 'application/json', 'X-Pluto-Token': token }
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
        headers: { 'Content-Type': 'application/json', 'X-Pluto-Token': token },
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
        if (cfg.region) cfgRegion.value = cfg.region;
        if (cfg.instance_type) cfgInstanceType.value = cfg.instance_type;
        if (cfg.key_file) cfgKeyFile.value = cfg.key_file;
        if (cfg.default_duration) cfgDuration.value = cfg.default_duration.toString();
        if (cfg.default_stg) cfgStg.value = cfg.default_stg.toString();
      }
    } catch (e) {}
  }

  btnSaveCfg.addEventListener('click', async () => {
    const token = await getAuthToken();
    const updated = {
      region: cfgRegion.value,
      instance_type: cfgInstanceType.value,
      key_file: cfgKeyFile.value,
      default_duration: parseFloat(cfgDuration.value),
      default_stg: parseFloat(cfgStg.value)
    };
    try {
      const res = await fetch('/api/cockpit/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Pluto-Token': token },
        body: JSON.stringify({ config: updated })
      });
      if (res.ok) {
        showToast('✓ Settings saved');
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
});

