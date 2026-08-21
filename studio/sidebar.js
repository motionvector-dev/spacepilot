/**
 * Pluto Studio — Shared Config Sidebar
 * Mounts a collapsible left-panel on every page.
 * Reads/writes config via GET|POST /api/cockpit/config
 * Polls GPU status via GET /api/cockpit/status
 */
(function () {
  'use strict';

  // ── Instance type catalogue ────────────────────────────────────────────
  const INSTANCE_TYPES = [
    // Budget tier — T4 / A10G
    { value: 'g4dn.xlarge',   label: 'g4dn.xlarge',   gpu: 'T4 16GB',       rate: 0.16,  tier: 'Budget' },
    { value: 'g4dn.2xlarge',  label: 'g4dn.2xlarge',  gpu: 'T4 16GB',       rate: 0.23,  tier: 'Budget' },
    { value: 'g4dn.4xlarge',  label: 'g4dn.4xlarge',  gpu: 'T4 16GB',       rate: 0.38,  tier: 'Budget' },
    { value: 'g4dn.12xlarge', label: 'g4dn.12xlarge', gpu: '4×T4 64GB',     rate: 1.48,  tier: 'Budget' },
    // Performance tier — A10G
    { value: 'g5.xlarge',     label: 'g5.xlarge',     gpu: 'A10G 24GB',     rate: 0.51,  tier: 'Performance' },
    { value: 'g5.2xlarge',    label: 'g5.2xlarge',    gpu: 'A10G 24GB',     rate: 0.76,  tier: 'Performance' },
    { value: 'g5.4xlarge',    label: 'g5.4xlarge',    gpu: 'A10G 24GB',     rate: 1.21,  tier: 'Performance' },
    { value: 'g5.12xlarge',   label: 'g5.12xlarge',   gpu: '4×A10G 96GB',   rate: 4.23,  tier: 'Performance' },
    // Pro tier — L40S (recommended for LTX-2.5)
    { value: 'g6e.xlarge',    label: 'g6e.xlarge',    gpu: 'L40S 48GB',     rate: 0.75,  tier: 'Pro (LTX-2.5)' },
    { value: 'g6e.2xlarge',   label: 'g6e.2xlarge',   gpu: 'L40S 48GB',     rate: 1.10,  tier: 'Pro (LTX-2.5)' },
    { value: 'g6e.4xlarge',   label: 'g6e.4xlarge',   gpu: 'L40S 48GB',     rate: 1.60,  tier: 'Pro (LTX-2.5)' },
    { value: 'g6e.8xlarge',   label: 'g6e.8xlarge',   gpu: 'L40S 48GB',     rate: 2.35,  tier: 'Pro (LTX-2.5)' },
    { value: 'g6e.12xlarge',  label: 'g6e.12xlarge',  gpu: '4×L40S 192GB',  rate: 4.80,  tier: 'Pro (LTX-2.5)' },
    // Flagship tier — H100
    { value: 'p4d.24xlarge',  label: 'p4d.24xlarge',  gpu: '8×A100 320GB',  rate: 9.83,  tier: 'Flagship' },
    { value: 'p5.48xlarge',   label: 'p5.48xlarge',   gpu: '8×H100 640GB',  rate: 43.04, tier: 'Flagship' },
  ];

  const REGIONS = [
    { value: 'us-east-1',      label: 'us-east-1 (N. Virginia)' },
    { value: 'us-east-2',      label: 'us-east-2 (Ohio)' },
    { value: 'us-west-1',      label: 'us-west-1 (N. California)' },
    { value: 'us-west-2',      label: 'us-west-2 (Oregon)' },
    { value: 'eu-west-1',      label: 'eu-west-1 (Ireland)' },
    { value: 'eu-west-2',      label: 'eu-west-2 (London)' },
    { value: 'eu-central-1',   label: 'eu-central-1 (Frankfurt)' },
    { value: 'ap-northeast-1', label: 'ap-northeast-1 (Tokyo)' },
    { value: 'ap-southeast-1', label: 'ap-southeast-1 (Singapore)' },
    { value: 'ap-south-1',     label: 'ap-south-1 (Mumbai)' },
  ];

  // ── Utility ─────────────────────────────────────────────────────────────
  function esc(str) {
    return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function currentPage() {
    const p = location.pathname.replace(/\/$/, '') || '/';
    if (p === '' || p === '/') return 'home';
    return p.slice(1).split('/')[0]; // 'create' | 'studio' | 'cockpit' | 'editor'
  }

  function rateColor(rate) {
    if (rate < 0.5) return '#10b981';
    if (rate < 1.5) return '#f59e0b';
    return '#f43f5e';
  }

  // ── Global Custom MotionVector Dialogs (Replaces browser alert/confirm) ──
  window.mvDialog = {
    confirm: function ({
      title = 'Confirm Action',
      subtitle = 'Are you sure you want to proceed?',
      message = '',
      type = 'danger', // 'danger' | 'launch' | 'warning' | 'info'
      confirmText = 'Confirm',
      requireTypedText = null, // e.g. 'TERMINATE'
      onConfirm = () => {},
      onCancel = () => {},
    }) {
      let backdrop = document.getElementById('mv-global-dialog-backdrop');
      if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.id = 'mv-global-dialog-backdrop';
        backdrop.className = 'mv-modal-backdrop';
        document.body.appendChild(backdrop);
      }

      const isDanger = type === 'danger';
      const isLaunch = type === 'launch';
      const iconClass = isLaunch ? 'launch' : 'terminate';
      const iconSvg = isLaunch
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;

      const confirmBtnClass = isLaunch ? 'mv-modal-btn-confirm-launch' : 'mv-modal-btn-confirm-terminate';

      backdrop.innerHTML = `
        <div class="mv-modal-card">
          <div class="mv-modal-header">
            <div class="mv-modal-icon-wrap ${iconClass}">
              ${iconSvg}
            </div>
            <div>
              <h3 class="mv-modal-title">${esc(title)}</h3>
              <p class="mv-modal-subtitle">${esc(subtitle)}</p>
            </div>
          </div>
          <div class="mv-modal-body">
            ${message ? `<p>${message}</p>` : ''}
            ${requireTypedText ? `
              <div class="mv-modal-type-confirm">
                <label class="mv-modal-type-label">Type <strong style="color:var(--text-main);">${esc(requireTypedText)}</strong> to confirm:</label>
                <input type="text" id="mv-dialog-type-input" class="mv-modal-type-input" placeholder="${esc(requireTypedText)}" autocomplete="off" spellcheck="false">
              </div>
            ` : ''}
          </div>
          <div class="mv-modal-actions">
            <button id="mv-dialog-btn-cancel" class="mv-modal-btn mv-modal-btn-cancel">Cancel</button>
            <button id="mv-dialog-btn-confirm" class="mv-modal-btn ${confirmBtnClass}" ${requireTypedText ? 'disabled' : ''}>${esc(confirmText)}</button>
          </div>
        </div>
      `;

      const btnCancel = backdrop.querySelector('#mv-dialog-btn-cancel');
      const btnConfirm = backdrop.querySelector('#mv-dialog-btn-confirm');
      const typeInput = backdrop.querySelector('#mv-dialog-type-input');

      function close() {
        backdrop.classList.remove('open');
      }

      if (typeInput) {
        typeInput.addEventListener('input', (e) => {
          btnConfirm.disabled = e.target.value.trim().toUpperCase() !== requireTypedText.toUpperCase();
        });
        setTimeout(() => typeInput.focus(), 50);
      }

      btnCancel.addEventListener('click', () => {
        close();
        onCancel();
      });

      btnConfirm.addEventListener('click', () => {
        close();
        onConfirm();
      });

      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) {
          close();
          onCancel();
        }
      });

      backdrop.classList.add('open');
    },

    alert: function (message, title = 'Notice') {
      this.confirm({
        title: title,
        subtitle: 'Pluto Studio',
        message: esc(message),
        type: 'launch',
        confirmText: 'Acknowledge',
        onConfirm: () => {},
      });
      // Hide cancel button for alerts
      const cancelBtn = document.getElementById('mv-dialog-btn-cancel');
      if (cancelBtn) cancelBtn.style.display = 'none';
    }
  };

  // ── Build instance-type grouped <select> ─────────────────────────────────
  function buildInstanceOptions(selectedValue) {
    const tiers = {};
    INSTANCE_TYPES.forEach(it => {
      if (!tiers[it.tier]) tiers[it.tier] = [];
      tiers[it.tier].push(it);
    });
    return Object.entries(tiers).map(([tier, items]) => {
      const options = items.map(it => {
        const sel = it.value === selectedValue ? ' selected' : '';
        return `<option value="${esc(it.value)}"${sel}>${esc(it.label)} — ${esc(it.gpu)} · ~$${it.rate.toFixed(2)}/hr</option>`;
      }).join('');
      return `<optgroup label="${esc(tier)}">${options}</optgroup>`;
    }).join('');
  }

  // ── Build region <select> ────────────────────────────────────────────────
  function buildRegionOptions(selectedValue) {
    return REGIONS.map(r => {
      const sel = r.value === selectedValue ? ' selected' : '';
      return `<option value="${esc(r.value)}"${sel}>${esc(r.label)}</option>`;
    }).join('');
  }

  // ── HTML template ────────────────────────────────────────────────────────
  function sidebarHTML() {
    const page = currentPage();
    const navLinks = [
      { href: '/',        icon: `<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>`, label: 'Home' },
      { href: '/create',  icon: `<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>`, label: 'Create' },
      { href: '/studio',  icon: `<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>`, label: 'Pro Studio' },
      { href: '/cockpit', icon: `<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>`, label: 'Cockpit' },
    ];
    const navHTML = navLinks.map(n => {
      const activePage = page === (n.href === '/' ? 'home' : n.href.slice(1));
      return `<a href="${n.href}" class="sidebar-nav-link${activePage ? ' active' : ''}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${n.icon}</svg>
        ${esc(n.label)}
      </a>`;
    }).join('');

    return `
<div class="pluto-sidebar-backdrop" id="plutoSidebarBackdrop"></div>
<aside class="pluto-sidebar" id="plutoSidebar" aria-label="Config sidebar">
  <div class="sidebar-header">
    <span class="sidebar-brand">Pluto Studio</span>
  </div>

  <!-- GPU Status Pill -->
  <div class="sidebar-gpu-pill">
    <span class="sidebar-gpu-dot offline" id="sbGpuDot"></span>
    <span class="sidebar-gpu-label" id="sbGpuLabel">Checking GPU...</span>
  </div>
  <div class="sidebar-gpu-actions">
    <button class="sidebar-btn launch" id="sbBtnLaunch">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      Launch
    </button>
    <button class="sidebar-btn terminate" id="sbBtnTerminate">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
      Terminate
    </button>
  </div>

  <div class="sidebar-body">
    <!-- Navigation -->
    <div class="sidebar-section">
      <div class="sidebar-section-title">Navigate</div>
      ${navHTML}
    </div>

    <!-- AWS Config -->
    <div class="sidebar-section">
      <div class="sidebar-section-title">AWS Spot Config</div>
      <div class="sidebar-form-group">
        <label class="sidebar-label" for="sbRegion">Region</label>
        <select id="sbRegion" class="sidebar-select">${buildRegionOptions('us-east-1')}</select>
      </div>
      <div class="sidebar-form-group">
        <label class="sidebar-label" for="sbInstanceType">Instance Type</label>
        <select id="sbInstanceType" class="sidebar-select">${buildInstanceOptions('g6e.xlarge')}</select>
        <div class="sidebar-rate-badge" id="sbRateBadge">~$0.75 / hr Spot</div>
      </div>
      <div class="sidebar-form-group">
        <label class="sidebar-label" for="sbKeyFile">SSH Key Path</label>
        <input id="sbKeyFile" class="sidebar-input" type="text" placeholder="~/.ssh/pluto-key.pem" spellcheck="false">
      </div>
    </div>

    <!-- Generation Defaults -->
    <div class="sidebar-section">
      <div class="sidebar-section-title">Generation Defaults</div>
      <div class="sidebar-form-group">
        <label class="sidebar-label" for="sbDuration">Default Duration</label>
        <select id="sbDuration" class="sidebar-select">
          <option value="4.0">4.0 s</option>
          <option value="6.0">6.0 s</option>
          <option value="8.0">8.0 s</option>
          <option value="10.0">10.0 s</option>
          <option value="16.0">16.0 s</option>
        </select>
      </div>
      <div class="sidebar-form-group">
        <label class="sidebar-label" for="sbStg">STG Scale <span style="color:var(--text-faint);font-size:9px">(0 = distilled, 0.8 = dev)</span></label>
        <input id="sbStg" class="sidebar-input" type="number" min="0" max="5" step="0.1" value="0.8">
      </div>
      <div class="sidebar-form-group">
        <label class="sidebar-label" for="sbModality">Modality Scale <span style="color:var(--text-faint);font-size:9px">(image fidelity)</span></label>
        <input id="sbModality" class="sidebar-input" type="number" min="0" max="5" step="0.1" value="1.0">
      </div>
      <button class="sidebar-save-btn" id="sbBtnSave">Save Settings</button>
    </div>
  </div>
</aside>
<div class="sidebar-toast" id="sbToast"></div>
`;
  }

  // ── Mount ────────────────────────────────────────────────────────────────
  function mount() {
    // Inject CSS if not already loaded
    if (!document.querySelector('link[href*="sidebar.css"]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/sidebar.css';
      document.head.appendChild(link);
    }

    // Inject HTML
    const container = document.createElement('div');
    container.innerHTML = sidebarHTML();
    document.body.prepend(...container.childNodes);

    // Inject toggle button
    const toggle = document.createElement('button');
    toggle.id = 'sidebarToggle';
    toggle.className = 'sidebar-toggle';
    toggle.setAttribute('aria-label', 'Toggle config sidebar');
    toggle.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
    </svg>`;
    document.body.appendChild(toggle);

    wire();
  }

  // ── Wire events ──────────────────────────────────────────────────────────
  function wire() {
    const sidebar     = document.getElementById('plutoSidebar');
    const backdrop    = document.getElementById('plutoSidebarBackdrop');
    const toggle      = document.getElementById('sidebarToggle');
    const sbRegion    = document.getElementById('sbRegion');
    const sbInstance  = document.getElementById('sbInstanceType');
    const sbKeyFile   = document.getElementById('sbKeyFile');
    const sbDuration  = document.getElementById('sbDuration');
    const sbStg       = document.getElementById('sbStg');
    const sbModality  = document.getElementById('sbModality');
    const sbSave      = document.getElementById('sbBtnSave');
    const sbLaunch    = document.getElementById('sbBtnLaunch');
    const sbTerminate = document.getElementById('sbBtnTerminate');
    const sbRateBadge = document.getElementById('sbRateBadge');

    let isOpen = false;
    function open()  { isOpen = true;  sidebar.classList.add('is-open'); backdrop.classList.add('is-open'); toggle.classList.add('is-open'); }
    function close() { isOpen = false; sidebar.classList.remove('is-open'); backdrop.classList.remove('is-open'); toggle.classList.remove('is-open'); }
    toggle.addEventListener('click', () => isOpen ? close() : open());
    backdrop.addEventListener('click', close);
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && isOpen) close(); });

    // Update rate badge when instance type changes
    function updateRateBadge() {
      const it = INSTANCE_TYPES.find(i => i.value === sbInstance.value);
      if (!it) return;
      sbRateBadge.style.color = rateColor(it.rate);
      sbRateBadge.style.borderColor = rateColor(it.rate) + '33';
      sbRateBadge.style.background = rateColor(it.rate) + '18';
      sbRateBadge.textContent = `~$${it.rate.toFixed(2)} / hr Spot · ${it.gpu}`;
    }
    sbInstance.addEventListener('change', updateRateBadge);

    // Toast
    function toast(msg, isError = false) {
      const el = document.getElementById('sbToast');
      el.textContent = msg;
      el.style.borderColor = isError ? 'rgba(244,63,94,0.35)' : 'var(--border-medium)';
      el.classList.add('show');
      setTimeout(() => el.classList.remove('show'), 3000);
    }

    // Load config from API
    async function loadConfig() {
      try {
        const res = await fetch('/api/cockpit/config');
        if (!res.ok) return;
        const { config: cfg } = await res.json();
        if (cfg.region)           { sbRegion.value = cfg.region; }
        if (cfg.instance_type)    {
          sbInstance.innerHTML = buildInstanceOptions(cfg.instance_type);
          updateRateBadge();
        }
        if (cfg.key_file)         { sbKeyFile.value = cfg.key_file; }
        if (cfg.default_duration) { sbDuration.value = String(cfg.default_duration); }
        if (cfg.default_stg !== undefined)      { sbStg.value = String(cfg.default_stg); }
        if (cfg.default_modality !== undefined) { sbModality.value = String(cfg.default_modality); }
      } catch (_) {}
    }

    // Save config
    sbSave.addEventListener('click', async () => {
      const it = INSTANCE_TYPES.find(i => i.value === sbInstance.value);
      const body = {
        config: {
          region:            sbRegion.value,
          instance_type:     sbInstance.value,
          spot_hourly_rate:  it ? it.rate : 0.75,
          key_file:          sbKeyFile.value,
          default_duration:  parseFloat(sbDuration.value),
          default_stg:       parseFloat(sbStg.value),
          default_modality:  parseFloat(sbModality.value),
        }
      };
      try {
        const res = await fetch('/api/cockpit/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (res.ok) {
          toast('Settings saved');
          // Broadcast to page-level components (create.js, studio.js) via event
          window.dispatchEvent(new CustomEvent('pluto:config-saved', { detail: body.config }));
        } else {
          toast('Save failed', true);
        }
      } catch (e) {
        toast('Save failed: ' + e.message, true);
      }
    });

    // GPU status polling
    const gpuDot   = document.getElementById('sbGpuDot');
    const gpuLabel = document.getElementById('sbGpuLabel');

    async function pollGpu() {
      try {
        const res = await fetch('/api/cockpit/status');
        if (!res.ok) throw new Error();
        const data = await res.json();
        const inst  = data.instance || {};
        const state = inst.state || 'offline';
        gpuDot.className = 'sidebar-gpu-dot';
        if (state === 'running') {
          gpuDot.classList.add('online');
          gpuLabel.textContent = `${inst.type || sbInstance.value} · ${inst.ip || 'booting'}`;
          sbLaunch.disabled = true;
          sbTerminate.disabled = false;
        } else if (state === 'pending' || state === 'launching') {
          gpuDot.classList.add('busy');
          gpuLabel.textContent = 'Launching…';
          sbLaunch.disabled = true;
          sbTerminate.disabled = true;
        } else {
          gpuDot.classList.add('offline');
          gpuLabel.textContent = 'No GPU · Offline';
          sbLaunch.disabled = false;
          sbTerminate.disabled = true;
        }
      } catch (_) {
        gpuDot.className = 'sidebar-gpu-dot offline';
        gpuLabel.textContent = 'Status unavailable';
      }
    }

    // Launch / Terminate
    const token = document.querySelector('meta[name="pluto-token"]')?.content || '';
    const headers = { 'Content-Type': 'application/json', ...(token ? { 'X-Pluto-Token': token } : {}) };

    sbLaunch.addEventListener('click', () => {
      if (sbLaunch.disabled) return;
      const typeVal = sbInstanceType.value;
      const match = INSTANCE_TYPES.find(t => t.value === typeVal) || { rate: 0.75, label: typeVal };
      window.mvDialog.confirm({
        title: 'Authorize AWS GPU Launch',
        subtitle: 'Start Spot GPU compute & warm VRAM',
        message: `Provision spot instance <strong>${esc(match.label)}</strong> in <strong>${esc(sbRegion.value)}</strong> (~$${match.rate.toFixed(2)}/hr). Billing starts immediately upon boot.`,
        type: 'launch',
        confirmText: 'Authorize & Launch Box',
        onConfirm: async () => {
          sbLaunch.disabled = true;
          gpuDot.className = 'sidebar-gpu-dot busy';
          gpuLabel.textContent = 'Launching…';
          toast('GPU launch initiated — ~2 min to warm');
          try {
            await fetch('/api/gpu/launch', {
              method: 'POST',
              headers,
              body: JSON.stringify({ confirm: true })
            });
            setTimeout(pollGpu, 3000);
          } catch (_) {
            sbLaunch.disabled = false;
          }
        }
      });
    });

    sbTerminate.addEventListener('click', () => {
      window.mvDialog.confirm({
        title: 'Terminate GPU Box',
        subtitle: 'Halt cloud billing and destroy instance',
        message: '<span style="color:#f43f5e;font-weight:600;">⚠️ Warning:</span> Terminating destroys the temporary NVMe scratch volume. Any unsynced video renders will be permanently lost.',
        type: 'danger',
        requireTypedText: 'TERMINATE',
        confirmText: 'Destroy & Stop Billing',
        onConfirm: async () => {
          sbTerminate.disabled = true;
          toast('Terminating…');
          try {
            await fetch('/api/gpu/terminate', {
              method: 'POST',
              headers,
              body: JSON.stringify({ confirm: true })
            });
            setTimeout(pollGpu, 3000);
          } catch (_) {
            sbTerminate.disabled = false;
          }
        }
      });
    });

    // Init
    updateRateBadge();
    loadConfig();
    pollGpu();
    setInterval(pollGpu, 15000);
  }

  // ── Auto-mount when DOM ready ────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
