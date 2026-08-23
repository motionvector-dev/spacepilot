document.addEventListener('DOMContentLoaded', () => {
    initThemeSwitcher();
    initCodeSnippetSwitcher();
    initSearchFilter();
    initHardwareProbe();
    initStickyNav();
});

// 1. Theme Switcher (Dark / Light / System) synced with localStorage
function initThemeSwitcher() {
    const themeBtns = document.querySelectorAll('.theme-btn');
    const root = document.documentElement;
    
    // Check localStorage or default to 'dark'
    const savedTheme = localStorage.getItem('spacepilot-theme') || 'dark';
    applyTheme(savedTheme);

    themeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.getAttribute('data-theme-val');
            applyTheme(theme);
        });
    });

    function applyTheme(theme) {
        // Update active button state
        themeBtns.forEach(b => b.classList.remove('active'));
        const activeBtn = document.querySelector(`.theme-btn[data-theme-val="${theme}"]`);
        if (activeBtn) activeBtn.classList.add('active');

        // Apply theme to DOM
        if (theme === 'system') {
            const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            root.setAttribute('data-theme', systemDark ? 'dark' : 'light');
        } else {
            root.setAttribute('data-theme', theme);
        }

        // Save preference
        localStorage.setItem('spacepilot-theme', theme);
    }

    // Listen for system theme changes if set to system
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (localStorage.getItem('spacepilot-theme') === 'system') {
            root.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        }
    });
}

// 2. Multi-Language Code Snippet Switcher + Copy
function initCodeSnippetSwitcher() {
    const blocks = document.querySelectorAll('.code-block');

    blocks.forEach(block => {
        const langBtns = block.querySelectorAll('.code-lang-btn');
        const contents = block.querySelectorAll('.snippet-content');
        const copyBtn = block.querySelector('.copy-btn');

        langBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active classes
                langBtns.forEach(b => b.classList.remove('active'));
                if (contents.length > 0) {
                    contents.forEach(c => c.style.display = 'none');
                }

                // Set active
                btn.classList.add('active');
                const lang = btn.getAttribute('data-lang');
                const targetContent = block.querySelector(`.snippet-content[data-lang="${lang}"]`);
                
                if (targetContent) {
                    targetContent.style.display = 'block';
                }
            });
        });

        if (copyBtn) {
            copyBtn.addEventListener('click', async () => {
                let textToCopy = '';
                if (contents.length > 0) {
                    // Find visible block
                    const activeContent = Array.from(contents).find(c => c.style.display !== 'none');
                    if (activeContent) {
                        textToCopy = activeContent.textContent;
                    }
                } else {
                    // Single block
                    const pre = block.querySelector('pre');
                    if (pre) textToCopy = pre.textContent;
                }

                if (textToCopy) {
                    try {
                        await navigator.clipboard.writeText(textToCopy);
                        const originalText = copyBtn.textContent;
                        copyBtn.textContent = 'Copied!';
                        setTimeout(() => copyBtn.textContent = originalText, 2000);
                    } catch (err) {
                        console.error('Failed to copy text: ', err);
                    }
                }
            });
        }
    });
}

// 3. Instant Search Filter
function initSearchFilter() {
    const searchInput = document.getElementById('doc-search');
    const sections = document.querySelectorAll('.doc-section');
    const navItems = document.querySelectorAll('.nav-item');

    searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();

        sections.forEach(section => {
            const text = section.textContent.toLowerCase();
            const id = section.id;
            
            // Toggle section visibility
            if (text.includes(term)) {
                section.style.display = 'block';
                
                // Highlight corresponding nav item
                navItems.forEach(item => {
                    const link = item.querySelector('.nav-link');
                    if (link && link.getAttribute('href') === `#${id}`) {
                        item.style.display = 'block';
                    }
                });
            } else {
                section.style.display = 'none';
                
                // Hide corresponding nav item
                navItems.forEach(item => {
                    const link = item.querySelector('.nav-link');
                    if (link && link.getAttribute('href') === `#${id}`) {
                        item.style.display = 'none';
                    }
                });
            }
        });
        
        // Ensure groups with all hidden items are also hidden (optional refinement)
        document.querySelectorAll('.nav-group').forEach(group => {
            const visibleItems = group.querySelectorAll('.nav-item[style="display: block;"], .nav-item:not([style*="display: none"])');
            if (visibleItems.length === 0 && term !== '') {
                group.style.display = 'none';
            } else {
                group.style.display = 'block';
            }
        });
    });
}

// 4. Interactive Live Hardware Probe Widget
async function initHardwareProbe() {
    const vramEl = document.getElementById('probe-vram');
    const gpuEl = document.getElementById('probe-gpu');
    const engineEl = document.getElementById('probe-engine');
    const statusDot = document.getElementById('probe-status');

    async function pollHardware() {
        try {
            const res = await fetch('/api/compute/local-profile');
            if (res.ok) {
                const profile = await res.json();
                vramEl.textContent = `${profile.vram_usable_gb || profile.vram_total_gb || 0} GB Usable`;
                gpuEl.textContent = profile.device_name || (profile.backend === 'metal_mps' ? 'Apple Metal (MPS)' : 'CUDA GPU');
                
                const usable = profile.vram_usable_gb || 0;
                let rec = 'Kokoro TTS + SPAN-4K';
                if (usable >= 32) rec = 'HunyuanVideo (13B)';
                else if (usable >= 24) rec = 'Wan2.1 (14B DiT)';
                else if (usable >= 14) rec = 'LTX-Video 2.5 (13B)';
                else if (usable >= 8) rec = 'Wan2.1 (1.3B) + Qwen2.5';
                
                engineEl.textContent = rec;
                statusDot.style.backgroundColor = "var(--success)";
            } else {
                vramEl.textContent = "Offline";
                gpuEl.textContent = "Offline";
                engineEl.textContent = "Offline";
                statusDot.style.backgroundColor = "var(--error)";
            }
            
            // Flash status dot to indicate polling
            statusDot.style.opacity = '0.3';
            setTimeout(() => statusDot.style.opacity = '1', 300);
            
        } catch (error) {
            console.warn('Hardware probe failed to connect:', error);
            vramEl.textContent = "Offline";
            gpuEl.textContent = "Offline";
            engineEl.textContent = "Offline";
            statusDot.style.backgroundColor = "var(--error)";
        }
    }

    // Initial poll
    await pollHardware();
    
    // Poll every 8s
    setInterval(pollHardware, 8000);
}

// 5. Responsive Sticky Table of Contents & Navigation Sidebar
function initStickyNav() {
    const sections = document.querySelectorAll('.doc-section');
    const navLinks = document.querySelectorAll('.nav-link');

    // Observer options
    const observerOptions = {
        root: null,
        rootMargin: '-20% 0px -60% 0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Remove active from all
                navLinks.forEach(link => link.classList.remove('active'));
                
                // Add active to current
                const activeLink = document.querySelector(`.nav-link[href="#${entry.target.id}"]`);
                if (activeLink) {
                    activeLink.classList.add('active');
                }
            }
        });
    }, observerOptions);

    sections.forEach(section => {
        observer.observe(section);
    });

    // Smooth scrolling for sidebar links
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').substring(1);
            const targetSection = document.getElementById(targetId);
            
            if (targetSection) {
                window.scrollTo({
                    top: targetSection.offsetTop - 20,
                    behavior: 'smooth'
                });
            }
        });
    });
}
