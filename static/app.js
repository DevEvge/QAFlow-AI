const app = {
    state: {
        currentModule: null,
        currentCaseId: null,
        failedCaseText: null,
        currentProject: localStorage.getItem('currentProject') || null,
        uploadController: null,
        isRetest: false,

        // UI State
        selectedCases: new Set(),
        currentPage: 1,
        limit: 20,
        totalCases: 0,
        theme: localStorage.getItem('theme') || 'dark',
        allBugs: [],
        allCasesData: [],
        uploadQueue: [],
        projects: [],
        stats: null,
        isProcessingQueue: false
    },

    async init() {
        this.applyTheme();
        await this.loadProjects(); // Load projects first
        await this.loadModules();
        await this.loadStats();

        this.setupDragAndDrop();
        this.setupKeyboardShortcuts();

        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
                .then(reg => console.log('Service Worker Registered'))
                .catch(err => console.log('SW Registration Failed', err));
        }

        // Mobile Sidebar Close on Click Outside
        document.addEventListener('click', (e) => {
            const sidebar = document.getElementById('sidebar');
            const btn = document.querySelector('.mobile-header .btn');
            if (sidebar && btn && sidebar.classList.contains('open') && !sidebar.contains(e.target) && !btn.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
    },

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only work in testing view
            if (!document.getElementById('testing-view').classList.contains('active')) return;

            if (e.key.toLowerCase() === 'p') {
                this.handlePass();
            } else if (e.key.toLowerCase() === 'f' && !this.state.isRetest) {
                this.handleFail();
            } else if (e.key.toLowerCase() === 's' && this.state.isRetest) {
                this.skipCase();
            } else if (e.key === 'Escape') {
                this.goHome();
            }
        });
    },

    // --- THEME ENGINE ---
    toggleTheme() {
        this.state.theme = this.state.theme === 'dark' ? 'light' : 'dark';
        this.applyTheme();
        localStorage.setItem('theme', this.state.theme);
    },

    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.state.theme);
        const btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            btn.innerHTML = this.state.theme === 'dark' ? '🌙 Dark Mode' : '☀️ Light Mode';
        }
    },

    // --- PROJECT MANAGEMENT ---
    async loadProjects() {
        try {
            const res = await fetch('/api/projects');
            const data = await res.json();
            this.state.projects = data.projects || [];

            // Check if no projects exist - show onboarding
            if (this.state.projects.length === 0) {
                this.showOnboarding();
                return;
            }

            // Hide onboarding if it was shown
            document.getElementById('onboarding-view').style.display = 'none';
            this.state.inOnboarding = false;
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('locked'));

            // Populate sidebar selector
            const selector = document.getElementById('project-select');
            if (selector) {
                selector.innerHTML = this.state.projects.map(p =>
                    `<option value="${p.name}">${p.name}</option>`
                ).join('');

                // Set current project
                if (!this.state.currentProject || !this.state.projects.find(p => p.name === this.state.currentProject)) {
                    this.state.currentProject = this.state.projects[0].name;
                    localStorage.setItem('currentProject', this.state.currentProject);
                }
                selector.value = this.state.currentProject;
            }

            // Also update settings page projects list
            this.renderProjectsList();
        } catch (e) {
            console.error('Failed to load projects:', e);
        }
    },

    showOnboarding() {
        // Hide all views completely
        document.querySelectorAll('.view-section').forEach(v => {
            v.classList.remove('active');
            v.style.display = 'none';
        });

        // Show only onboarding
        const onboarding = document.getElementById('onboarding-view');
        if (onboarding) {
            onboarding.style.display = 'block';
            onboarding.classList.add('active');
        }

        // Update sidebar to show no projects and lock navigation visuals
        const selector = document.getElementById('project-select');
        if (selector) selector.innerHTML = '<option value="">No projects</option>';

        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.id !== 'nav-dashboard') { // Allow dashboard/onboarding view
                item.classList.add('locked');
            }
        });

        // Set onboarding mode to lock navigation
        this.state.inOnboarding = true;
    },

    async createProjectFromOnboarding() {
        const input = document.getElementById('onboarding-project-name');
        const name = input.value.trim();

        if (!name || name.length < 2) {
            this.showErrorModal("Invalid Name", "Project name must be at least 2 characters.");
            return;
        }

        try {
            const res = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Failed to create project');
            }

            input.value = '';
            this.showToast(`✅ Project "${name}" created!`);

            // Reload projects and switch to new one
            this.state.currentProject = name;
            localStorage.setItem('currentProject', name);
            await this.loadProjects();
            this.goHome();
        } catch (e) {
            this.showErrorModal("Create Failed", e.message);
        }
    },

    renderProjectsList() {
        const list = document.getElementById('projects-list');
        if (!list) return;

        list.innerHTML = '';
        this.state.projects.forEach(p => {
            const el = document.createElement('div');
            el.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; margin-bottom: 0.5rem; background: var(--card-hover); border-radius: 8px; border: 1px solid var(--border-color);';
            el.innerHTML = `
                <div>
                    <div style="font-weight: 600; color: var(--text-primary);">📁 ${p.name}</div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">Created: ${p.created_at ? new Date(p.created_at).toLocaleDateString() : 'Unknown'}</div>
                </div>
                <button class="btn btn-ghost" onclick="app.deleteProjectConfirm('${p.name}')" style="color: var(--danger); padding: 0.25rem 0.5rem;">🗑️</button>
            `;
            list.appendChild(el);
        });

        if (this.state.projects.length === 0) {
            list.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 1rem;">No projects yet. Create one above!</div>';
        }
    },

    async createProject() {
        const input = document.getElementById('new-project-name');
        const name = input.value.trim();

        if (!name || name.length < 2) {
            this.showErrorModal("Invalid Name", "Project name must be at least 2 characters.");
            return;
        }

        try {
            const res = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Failed to create project');
            }

            input.value = '';
            this.showToast(`✅ Project "${name}" created!`);
            await this.loadProjects();

            // Switch to new project
            this.switchProject(name);
        } catch (e) {
            this.showErrorModal("Create Failed", e.message);
        }
    },

    deleteProjectConfirm(name) {
        const code = prompt(`Type "DELETE" to permanently delete project "${name}" and ALL its data:`);
        if (code !== 'DELETE') return;
        this.deleteProject(name);
    },

    async deleteProject(name) {
        try {
            const res = await fetch('/api/projects', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Failed to delete project');
            }

            this.showToast(`🗑️ Project "${name}" deleted`);

            // If deleted current project, switch to first available
            if (this.state.currentProject === name) {
                await this.loadProjects();
                if (this.state.projects.length > 0) {
                    this.switchProject(this.state.projects[0].name);
                } else {
                    this.state.currentProject = null;
                }
            } else {
                await this.loadProjects();
            }
        } catch (e) {
            this.showErrorModal("Delete Failed", e.message);
        }
    },

    async loadStats() {
        if (!this.state.currentProject) return;

        try {
            const res = await fetch(`/api/stats?project=${this.state.currentProject}`);
            this.state.stats = await res.json();
        } catch (e) {
            console.error('Failed to load stats:', e);
        }
    },

    exportCSV() {
        if (!this.state.currentProject) {
            this.showErrorModal("No Project", "Please select a project first.");
            return;
        }

        window.location.href = `/api/export/csv?project=${encodeURIComponent(this.state.currentProject)}`;
        this.showToast("📥 Downloading CSV...");
    },

    switchProject(projectName) {
        if (this.state.uploadController) {
            this.state.uploadController.abort();
            this.state.uploadController = null;
            this.resetUploadUI();
            this.showToast("Previous upload cancelled", "info");
        }

        this.state.currentProject = projectName;
        localStorage.setItem('currentProject', projectName);
        this.showToast(`Switched to ${projectName}`);
        this.goHome();
    },

    setupDragAndDrop() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const uploadArea = document.querySelector('.upload-area');

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = 'var(--accent-primary)';
            uploadArea.style.background = 'rgba(59, 130, 246, 0.1)';
        });

        dropZone.addEventListener('dragleave', () => {
            uploadArea.style.borderColor = 'var(--border-color)';
            uploadArea.style.background = '';
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = 'var(--border-color)';
            uploadArea.style.background = '';
            const files = Array.from(e.dataTransfer.files).slice(0, 5);
            if (files.length) {
                this.handleMultipleFiles(files);
            }
        });

        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files).slice(0, 5);
            if (files.length) {
                this.handleMultipleFiles(files);
            }
            e.target.value = '';
        });
    },

    handleMultipleFiles(files) {
        const currentCount = this.state.uploadQueue.length;
        const available = 5 - currentCount;

        if (available <= 0) {
            this.showErrorModal("Queue Full", "Max 5 files can be in the queue at once.");
            return;
        }

        const filesToAdd = Array.from(files).slice(0, available);
        if (files.length > available) {
            this.showToast(`Only added ${available} files. Limit is 5.`, "warning");
        }

        const newEntries = filesToAdd.map((file, idx) => ({
            file,
            id: Date.now() + Math.random(),
            status: 'pending',
            result: null
        }));

        this.state.uploadQueue = [...this.state.uploadQueue, ...newEntries];
        this.renderUploadQueue();
        this.processUploadQueue();
    },

    renderUploadQueue() {
        const queueContainer = document.getElementById('upload-queue');
        const queueList = document.getElementById('queue-list');

        if (!this.state.uploadQueue || this.state.uploadQueue.length === 0) {
            queueContainer.style.display = 'none';
            return;
        }

        queueContainer.style.display = 'block';
        queueList.innerHTML = '';

        this.state.uploadQueue.forEach(item => {
            const el = document.createElement('div');
            el.className = 'queue-item';
            el.style.cssText = 'padding: 1rem; margin-bottom: 0.75rem; background: var(--card-hover); border-radius: 12px; border: 1px solid var(--border-color); position: relative; overflow: hidden;';

            const statusLabels = {
                'pending': '⏳ Waiting...',
                'uploading': '🚀 Uploading...',
                'ai_analyzing': '🧠 AI Analyzing...',
                'extracting': '🔍 Extracting...',
                'saving': '💾 Saving...',
                'done': '✅ Done',
                'error': '❌ Error'
            };
            const statusLabel = statusLabels[item.status] || item.status;
            const statusColor = item.status === 'error' ? 'var(--danger)' :
                (item.status === 'done' ? 'var(--success)' : 'var(--accent-primary)');

            const progressMap = {
                'pending': 0,
                'uploading': 25,
                'ai_analyzing': 55,
                'extracting': 85,
                'saving': 95,
                'done': 100,
                'error': 100
            };
            const progress = progressMap[item.status] || 0;
            const safeFileName = item.file.name.replace(/\s+/g, '-').replace(/[^\w-]/g, '');

            el.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; padding-right: 2.2rem;">
                    <div style="font-weight: 600; font-size: 0.9rem; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 170px;">
                        📄 ${item.file.name}
                    </div>
                    <div style="font-size: 0.75rem; font-weight: 700; color: ${statusColor}; text-transform: uppercase; letter-spacing: 0.5px;">
                        ${statusLabel}
                    </div>
                </div>

                ${(item.status === 'pending' || item.status === 'error' || item.status === 'done') ?
                    `<button class="btn-remove-queue" onclick="app.removeFromQueue('${item.file.name}')" title="Remove from list">✕</button>` : ''}

                <div style="height: 6px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 4px; overflow: hidden; position: relative; margin-top: 0.8rem;">
                    <div id="pb-${safeFileName}"
                         style="height: 100%; width: ${progress}%;
                                background: ${statusColor}; transition: width 1.2s cubic-bezier(0.4, 0, 0.2, 1);
                                ${['uploading', 'ai_analyzing', 'extracting', 'saving'].includes(item.status) ? 'animation: shimmer 2s infinite linear;' : ''}">
                    </div>
                    ${['ai_analyzing', 'extracting'].includes(item.status) ?
                    `<style>
                            @keyframes creep-${safeFileName} {
                                from { width: ${progress}%; }
                                to { width: ${Math.min(progress + 15, 90)}%; }
                            }
                            #pb-${safeFileName} {
                                animation: creep-${safeFileName} 30s linear forwards, shimmer 2s infinite linear;
                            }
                        </style>` : ''}
                </div>
                ${item.status === 'error' ? `<div style="font-size: 0.7rem; color: var(--danger); margin-top: 0.4rem; line-height: 1.2; word-break: break-word;">${item.error}</div>` : ''}
            `;
            queueList.appendChild(el);
        });
    },

    removeFromQueue(fileName) {
        this.state.uploadQueue = this.state.uploadQueue.filter(i => i.file.name !== fileName);
        this.renderUploadQueue();
    },

    async processUploadQueue() {
        if (this.state.isProcessingQueue) return;
        this.state.isProcessingQueue = true;

        while (true) {
            const item = this.state.uploadQueue.find(i => i.status === 'pending');
            if (!item) break;

            item.status = 'uploading';
            this.renderUploadQueue();

            try {
                // Check if still in queue (user might have removed it)
                if (!this.state.uploadQueue.find(i => i.file.name === item.file.name)) continue;

                const formData = new FormData();
                formData.append('file', item.file);
                formData.append('project', this.state.currentProject);

                // Simulate lifecycle
                const lifecycle = [
                    { status: 'ai_analyzing', delay: 1200 },
                    { status: 'extracting', delay: 4000 }
                ];

                lifecycle.forEach(step => {
                    setTimeout(() => {
                        if (['uploading', 'ai_analyzing'].includes(item.status)) {
                            item.status = step.status;
                            this.renderUploadQueue();
                        }
                    }, step.delay);
                });

                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `Server Error: ${response.status}`);
                }

                item.status = 'saving';
                this.renderUploadQueue();

                const data = await response.json();
                item.status = 'done';
                item.result = data;
                this.showToast(`✅ ${item.file.name}: ${data.count} cases`);
                await this.loadModules();
            } catch (e) {
                item.status = 'error';
                let msg = e.message;
                if (msg.includes('429') || msg.includes('RESOURCE_EXHAUSTED')) {
                    msg = "⚠️ AI Quota Exceeded. Please try later.";
                } else if (msg.includes('{')) {
                    try {
                        const match = msg.match(/"message":\s*"([^"]+)"/);
                        if (match && match[1]) msg = match[1];
                    } catch (err) { }
                }
                item.error = msg;
                this.showErrorModal(`Upload Failed: ${item.file.name}`, msg);
            }

            this.renderUploadQueue();
        }

        this.state.isProcessingQueue = false;

        // Cleanup done items after 5 seconds
        if (this.state.uploadQueue.length > 0) {
            setTimeout(() => {
                // Keep only errors, clear successful ones to clean UI
                const hasProcessing = this.state.uploadQueue.some(i => ['pending', 'uploading', 'ai_analyzing', 'saving'].includes(i.status));
                if (!hasProcessing) {
                    this.state.uploadQueue = this.state.uploadQueue.filter(i => i.status === 'error');
                    this.renderUploadQueue();
                }
            }, 5000);
        }
    },

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('project', this.state.currentProject);

        this.state.uploadController = new AbortController();
        const signal = this.state.uploadController.signal;

        document.querySelector('.upload-area').style.opacity = '0.5';
        const loader = document.getElementById('upload-loader');
        loader.style.display = 'block';

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
                signal: signal
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Server Error: ${response.status}`);
            }

            const data = await response.json();
            this.showToast(`Success! ${data.count} cases generated.`);
            await this.loadModules();
        } catch (e) {
            if (e.name === 'AbortError') {
                console.log("Upload aborted by user switching projects.");
            } else {
                console.error(e);
                this.showErrorModal("Upload Failed", e.message);
            }
        } finally {
            this.state.uploadController = null;
            this.resetUploadUI();
        }
    },

    resetUploadUI() {
        document.querySelector('.upload-area').style.opacity = '1';
        document.getElementById('upload-loader').style.display = 'none';
    },

    async loadModules() {
        const list = document.getElementById('modules-list');
        list.innerHTML = `
            <div class="skeleton" style="margin-bottom: 1rem"></div>
            <div class="skeleton" style="margin-bottom: 1rem; opacity: 0.7"></div>
            <div class="skeleton" style="margin-bottom: 1rem; opacity: 0.4"></div>
        `;

        try {
            const res = await fetch(`/api/modules?project=${this.state.currentProject}`);
            const data = await res.json();

            list.innerHTML = '';
            if (!data.modules || data.modules.length === 0) {
                list.innerHTML = `
                <div style="text-align:center; padding: 2rem; color: var(--text-secondary)">
                No active modules found in <b>${this.state.currentProject}</b>.<br>Upload a document to get started.
                </div>`;
                return;
            }

            // Sort modules: Incomplete (progress < 100) first, then by name
            const sortedModules = data.modules.sort((a, b) => {
                const aDone = a.progress === 100;
                const bDone = b.progress === 100;
                if (aDone !== bDone) return aDone ? 1 : -1;
                return a.name.localeCompare(b.name);
            });

            sortedModules.forEach(mod => {
                const el = document.createElement('div');
                el.className = 'module-row';

                const isDone = mod.progress === 100;
                const progressColor = isDone ? 'var(--success)' : 'var(--accent-primary)';

                el.innerHTML = `
                <div style="flex-grow: 1;" onclick="app.startModule('${mod.name}')">
                    <div class="module-name">📦 ${mod.name}</div>
                    <div style="margin-top: 0.5rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.25rem;">
                            <span>${mod.passed}/${mod.total} passed</span>
                            <span>${mod.progress}%</span>
                        </div>
                        <div style="background: var(--card-bg); height: 6px; border-radius: 99px; overflow: hidden;">
                            <div style="background: ${progressColor}; height: 100%; width: ${mod.progress}%; transition: width 0.3s ease;"></div>
                        </div>
                    </div>
                </div>
                ${isDone ?
                        `<button class="btn btn-ghost" onclick="app.retestModule('${mod.name}')" style="background: var(--card-hover); font-size: 0.8rem; border: 1px solid var(--success); color: var(--success); margin-left:1rem; padding: 0.5rem 1rem;">
                        <span>🔄</span> Retest
                    </button>` :
                        `<button class="btn btn-primary" onclick="app.startModule('${mod.name}')" style="padding: 0.5rem 1rem; font-size: 0.8rem; margin-left: 1rem;">
                        Start Testing →
                    </button>`
                    }
                `;
                list.appendChild(el);
            });
        } catch (e) {
            list.innerHTML = `<div style="color: var(--danger); text-align:center">Error loading modules: ${e.message}</div>`;
        }
    },

    async startModule(moduleName) {
        this.state.currentModule = moduleName;
        this.hideAllViews();
        const testingView = document.getElementById('testing-view');
        testingView.style.display = 'block';
        testingView.classList.add('active');
        document.getElementById('current-module-badge').innerText = moduleName;
        this.fetchNextCase();
    },

    async retestModule(moduleName) {
        if (!confirm(`Reset all progress for module "${moduleName}" and re-run all tests?`)) {
            return;
        }

        try {
            const res = await fetch('/api/modules/retest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: this.state.currentProject,
                    module_name: moduleName
                })
            });

            const data = await res.json();
            if (data.success) {
                this.showToast(`Module "${moduleName}" reset! 🎉`);
                this.loadModules();
                this.updateDashboardStats();
            } else {
                this.showErrorModal("Retest Failed", data.error || "Unknown error");
            }
        } catch (e) {
            this.showErrorModal("Retest Failed", e.message);
        }
    },

    async fetchNextCase() {
        document.getElementById('case-content-area').style.display = 'none';
        document.getElementById('case-loader').style.display = 'block';

        try {
            const res = await fetch('/api/start-module', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    module_name: this.state.currentModule,
                    project: this.state.currentProject
                })
            });

            const data = await res.json();

            if (data.finished) {
                this.showToast("Module Complete! 🎉");
                setTimeout(() => this.goHome(), 1000);
                return;
            }

            this.state.currentCaseId = data.case.id;
            this.state.failedCaseText = data.case.text;
            this.state.isRetest = data.case.is_retest || false;

            document.getElementById('case-id').innerText = "#" + data.case.id;

            // Parse for structured format: "Steps" and "Result"
            const rawText = data.case.text || "";
            let steps = rawText;
            let result = "Див. опис кейсу";

            // Improved split logic (handles both <br> and textual "Очікуваний результат")
            const resultLabel = "Очікуваний результат:";
            let parts = [];

            if (rawText.toLowerCase().includes("<br>")) {
                parts = rawText.split(/<br>/i);
            } else if (rawText.toLowerCase().includes(resultLabel.toLowerCase())) {
                const index = rawText.toLowerCase().indexOf(resultLabel.toLowerCase());
                parts = [
                    rawText.substring(0, index),
                    rawText.substring(index)
                ];
            }

            if (parts.length >= 2) {
                steps = parts[0].replace(/Кроки[:\s]*/i, "").trim();
                result = parts[1].replace(/Очікуваний результат[:\s]*/i, "").trim();
            }

            // Convert legacy semicolons to newlines with bullets if detected
            if (steps.includes(';') && !steps.includes('\n')) {
                steps = steps.split(';').map(s => s.trim()).filter(s => s).map(s => `• ${s}`).join('\n');
            }

            document.getElementById('case-steps').innerText = steps;
            document.getElementById('case-result').innerText = result;

            // Update action bar for retest mode
            const actionBar = document.querySelector('.action-bar');
            if (this.state.isRetest) {
                actionBar.innerHTML = `
                    <button class="btn btn-ghost" onclick="app.skipCase()" style="background: var(--card-hover); height: 60px;">
                        <span>⏭️</span> Skip (Retest)
                    </button>
                    <button class="btn btn-success" onclick="app.handlePass()">
                        <span>✔</span> Pass (Fixed)
                    </button>
                `;
            } else {
                actionBar.innerHTML = `
                    <button class="btn btn-danger" onclick="app.handleFail()">
                        <span>✖</span> Failed
                    </button>
                    <button class="btn btn-success" onclick="app.handlePass()">
                        <span>✔</span> Pass
                    </button>
                `;
            }

        } catch (e) {
            console.error(e);
            this.showToast("Error fetching case", "error");
        } finally {
            document.getElementById('case-loader').style.display = 'none';
            document.getElementById('case-content-area').style.display = 'block';
        }
    },

    skipCase() {
        this.showToast("Case skipped");
        this.fetchNextCase();
    },

    async handlePass() {
        await this.submitResult("Pass");
    },

    handleFail() {
        const modalTitle = document.querySelector('#bug-modal .card-title');
        if (modalTitle) modalTitle.innerText = "🐛 Report Defect";

        const btn = document.querySelector('#bug-modal .btn-primary');
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.onclick = () => this.submitBug();
        newBtn.innerText = "Submit Report";

        document.getElementById('bug-modal').classList.add('open');
        document.getElementById('bug-desc').value = '';
        document.getElementById('bug-desc').focus();
    },

    closeModal() {
        document.getElementById('bug-modal').classList.remove('open');
        document.getElementById('bug-desc').value = '';
    },

    async submitBug() {
        const desc = document.getElementById('bug-desc').value;
        if (!desc) return this.showErrorModal("Missing Description", "Please describe the bug before submitting.");

        const btn = document.querySelector('#bug-modal .btn-primary');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-sm"></span> Generating...`;

        try {
            await this.submitResult("Failed", desc);
            this.closeModal();
        } catch (e) {
            console.error(e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    },

    async submitResult(status, bugDescription = null) {
        try {
            const response = await fetch('/api/submit-result', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    case_id: this.state.currentCaseId,
                    status: status,
                    project: this.state.currentProject,
                    failed_case_text: this.state.failedCaseText,
                    bug_description: bugDescription
                })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Failed to submit result");
            }

            this.showToast(status === "Pass" ? "Case Passed" : "Bug Reported ✅");
            this.fetchNextCase();
        } catch (e) {
            console.error(e);
            this.showErrorModal("AI Report Error", e.message.includes("429") ?
                "Gemini is currently overloaded (Quota limit). Bug status saved, but AI report failed." :
                e.message);

            // If it was pass, we still want to continue
            if (status === "Pass") this.fetchNextCase();
        }
    },

    // --- VIEW MANAGEMENT ---
    hideAllViews() {
        document.querySelectorAll('.view-section').forEach(el => {
            el.classList.remove('active');
            el.style.display = 'none';
        });
    },

    updateNavState(viewId) {
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        if (viewId === 'dashboard-view') document.getElementById('nav-dashboard').classList.add('active');
        if (viewId === 'all-cases-view') document.getElementById('nav-all').classList.add('active');
        if (viewId === 'bug-tracker-view') document.getElementById('nav-bugs').classList.add('active');
        if (viewId === 'settings-view') document.getElementById('nav-settings').classList.add('active');

        // Mobile: Close sidebar on navigation
        document.getElementById('sidebar').classList.remove('open');
    },

    toggleSidebar() {
        document.getElementById('sidebar').classList.toggle('open');
    },

    goHome() {
        if (this.state.inOnboarding) return;
        this.hideAllViews();
        document.getElementById('dashboard-view').style.display = 'block';
        document.getElementById('dashboard-view').classList.add('active');
        this.updateNavState('dashboard-view');
        this.loadModules();
    },

    showBugTracker() {
        if (this.state.inOnboarding) return;
        this.hideAllViews();
        document.getElementById('bug-tracker-view').style.display = 'block';
        document.getElementById('bug-tracker-view').classList.add('active');
        this.updateNavState('bug-tracker-view');
        this.loadBugs();
    },

    showSettings() {
        if (this.state.inOnboarding) return;
        this.hideAllViews();
        document.getElementById('settings-view').style.display = 'block';
        document.getElementById('settings-view').classList.add('active');
        this.updateNavState('settings-view');
        this.applyTheme(); // Refresh button text
    },

    async loadBugs() {
        const list = document.getElementById('bugs-list');
        list.innerHTML = '<div class="spinner" style="margin: 2rem auto;"></div>';

        try {
            const res = await fetch(`/api/bugs?project=${this.state.currentProject}`);
            const data = await res.json();

            // Store all bugs for filtering
            this.state.allBugs = data.bugs || [];

            // Populate module filter
            const moduleFilter = document.getElementById('bug-module-filter');
            const modules = [...new Set(this.state.allBugs.map(b => b.module))];
            moduleFilter.innerHTML = '<option value="all">All Modules</option>' +
                modules.map(m => `<option value="${m}">${m}</option>`).join('');

            this.renderBugs();
        } catch (e) {
            list.innerHTML = `<div style="text-align:center; color: var(--danger);">Error loading bugs: ${e.message}</div>`;
        }
    },

    renderBugs() {
        const list = document.getElementById('bugs-list');
        const moduleFilter = document.getElementById('bug-module-filter').value;

        let filtered = this.state.allBugs;
        if (moduleFilter !== 'all') {
            filtered = filtered.filter(b => b.module === moduleFilter);
        }

        list.innerHTML = '';
        if (filtered.length === 0) {
            list.innerHTML = '<div style="text-align:center; color: var(--text-secondary); width: 100%;">No bugs found.</div>';
            return;
        }

        filtered.forEach(bug => {
            const card = document.createElement('div');
            card.className = 'glass-card';
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; margin-bottom: 1rem;">
                    <span class="status-badge" style="background: rgba(239, 68, 68, 0.1); color: var(--danger); border-color: rgba(239, 68, 68, 0.2);">
                       #${bug.id} ${bug.module}
                    </span>
                    <div style="display:flex; gap:0.5rem">
                        <button class="btn btn-ghost" style="padding:0.25rem 0.5rem;" onclick="app.editBug(${bug.id}, this)">✏️</button>
                        <button class="btn btn-ghost" style="padding:0.25rem 0.5rem; color: var(--danger);" onclick="app.deleteBug(${bug.id})">🗑️</button>
                    </div>
                </div>
                <div style="margin-bottom: 1rem; color: var(--text-secondary); font-size: 0.9rem;">
                    ${bug.case_text}
                </div>
                <div class="bug-report-text" style="background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color); white-space: pre-wrap;">${bug.bug_report || "No report generated yet."}</div>
            `;
            list.appendChild(card);
        });
    },

    filterBugs() {
        this.renderBugs();
    },

    async deleteBug(caseId) {
        if (!confirm("Are you sure?")) return;
        try {
            await fetch('/api/bugs', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ case_id: caseId, project: this.state.currentProject })
            });
            this.showToast("Bug deleted");
            this.loadBugs();
        } catch (e) { console.error(e); }
    },

    // --- ALL CASES VIEW & SELECTION ---

    showAllCases() {
        if (this.state.inOnboarding) return;
        this.hideAllViews();
        document.getElementById('all-cases-view').style.display = 'block';
        document.getElementById('all-cases-view').classList.add('active');
        this.updateNavState('all-cases-view');
        this.state.currentPage = 1;
        this.state.selectedCases.clear();
        document.getElementById('case-status-filter').value = 'all';
        document.getElementById('case-module-filter').value = 'all';
        this.updateSelectionUI();
        this.loadAllCases();
    },

    async loadAllCases() {
        const list = document.getElementById('all-cases-list');
        list.innerHTML = '<div class="spinner" style="margin: 2rem auto;"></div>';

        const statusFilter = document.getElementById('case-status-filter').value;
        const statusParam = statusFilter !== 'all' ? `&status=${statusFilter}` : '';

        try {
            const res = await fetch(`/api/cases?project=${this.state.currentProject}&page=${this.state.currentPage}&limit=${this.state.limit}${statusParam}`);
            const data = await res.json();

            this.state.totalCases = data.total;
            this.state.allCasesData = data.cases || [];

            // Rebuild module filter - always on fresh project load or if 'all' is selected
            const moduleFilter = document.getElementById('case-module-filter');
            const modules = data.all_modules || [];

            const currentVal = moduleFilter.value;
            moduleFilter.innerHTML = '<option value="all">All Modules</option>' +
                modules.map(m => `<option value="${m}">${m}</option>`).join('');

            // Restore previous value if it still exists in the new list, otherwise 'all'
            if (Array.from(moduleFilter.options).some(opt => opt.value === currentVal)) {
                moduleFilter.value = currentVal;
            } else {
                moduleFilter.value = 'all';
            }

            this.renderCases();
        } catch (e) {
            list.innerHTML = `<div style="text-align:center; color: var(--danger);">Error loading cases: ${e.message}</div>`;
        }
    },

    renderCases() {
        const list = document.getElementById('all-cases-list');
        const moduleFilter = document.getElementById('case-module-filter').value;
        const statusFilter = document.getElementById('case-status-filter').value;

        let filtered = this.state.allCasesData;
        if (moduleFilter !== 'all') {
            filtered = filtered.filter(c => c.module === moduleFilter);
        }
        // Status filtering is now handled by the server for loadAllCases, 
        // but we keep this client-side filter here in case module filter is applied locally.
        if (statusFilter !== 'all') {
            filtered = filtered.filter(c => c.status === statusFilter);
        }

        this.renderPagination();

        list.innerHTML = '';
        if (filtered.length === 0) {
            list.innerHTML = '<div style="text-align:center; color: var(--text-secondary);">No cases found.</div>';
            return;
        }

        filtered.forEach(c => {
            let statusColor = 'var(--text-secondary)';
            let statusBg = 'rgba(255,255,255,0.05)';
            if (c.status === 'Pass') { statusColor = 'var(--success)'; statusBg = 'rgba(16, 185, 129, 0.1)'; }
            if (c.status === 'FAILED') { statusColor = 'var(--danger)'; statusBg = 'rgba(239, 68, 68, 0.1)'; }

            const isSelected = this.state.selectedCases.has(c.id);

            const el = document.createElement('div');
            el.className = `glass-card case-row ${isSelected ? 'selected' : ''}`;
            if (isSelected) el.style.borderColor = 'var(--accent-primary)';

            el.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; gap: 1rem;">
                <input type="checkbox" class="case-checkbox" ${isSelected ? 'checked' : ''} onchange="app.toggleSelection(${c.id}, this)">
                
                <div style="flex-grow:1" onclick="app.toggleSelection(${c.id})">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.5rem">
                        <div style="font-weight:bold; color: var(--accent-primary); font-size: 0.9rem;">${c.module}</div>
                        <div style="font-size:0.8rem; padding:0.25rem 0.5rem; border-radius:8px; color:${statusColor}; background:${statusBg}">${c.status}</div>
                    </div>
                    <div style="font-size:0.95rem;">${c.content}</div>
                </div>
            </div>
            `;
            list.appendChild(el);
        });
    },

    filterCases() {
        this.state.currentPage = 1;
        this.loadAllCases();
    },

    renderPagination() {
        const container = document.getElementById('pagination-controls');
        container.innerHTML = '';

        if (this.state.totalCases === 0) return; // Hide if empty
        if (this.state.totalCases <= this.state.limit) return; // Hide if only one page

        const totalPages = Math.ceil(this.state.totalCases / this.state.limit);

        // Prev Button
        const prevBtn = document.createElement('button');
        prevBtn.innerText = '←';
        prevBtn.className = 'btn btn-ghost';
        prevBtn.disabled = this.state.currentPage === 1;
        prevBtn.onclick = () => this.changePage(-1);
        container.appendChild(prevBtn);

        // Page Indicator
        const span = document.createElement('span');
        span.innerText = `Page ${this.state.currentPage} of ${totalPages}`;
        span.style.color = 'var(--text-secondary)';
        container.appendChild(span);

        // Next Button
        const nextBtn = document.createElement('button');
        nextBtn.innerText = '→';
        nextBtn.className = 'btn btn-ghost';
        nextBtn.disabled = this.state.currentPage >= totalPages;
        nextBtn.onclick = () => this.changePage(1);
        container.appendChild(nextBtn);
    },

    changePage(delta) {
        this.state.currentPage += delta;
        this.loadAllCases();
    },

    toggleSelection(id, checkboxEl = null) {
        // Handle click on div vs checkbox
        if (!checkboxEl) {
            const row = document.querySelector(`.case-checkbox[onchange*="app.toggleSelection(${id}"]`);
            if (row) {
                row.checked = !row.checked;
                checkboxEl = row;
            }
        }

        if (checkboxEl && checkboxEl.checked) {
            this.state.selectedCases.add(id);
            checkboxEl.closest('.glass-card').style.borderColor = 'var(--accent-primary)';
        } else if (checkboxEl) {
            this.state.selectedCases.delete(id);
            checkboxEl.closest('.glass-card').style.borderColor = 'var(--border-color)';
        }
        this.updateSelectionUI();
    },

    updateSelectionUI() {
        const bar = document.getElementById('floating-action-bar');
        const count = this.state.selectedCases.size;

        if (count > 0) {
            bar.classList.add('visible');
            document.getElementById('selected-count').innerText = `${count} selected`;
        } else {
            bar.classList.remove('visible');
        }
    },

    async bulkDelete() {
        if (!confirm(`Delete ${this.state.selectedCases.size} items?`)) return;

        try {
            await fetch('/api/cases/batch/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ case_ids: Array.from(this.state.selectedCases) })
            });
            this.showToast("Items deleted");
            this.state.selectedCases.clear();
            this.updateSelectionUI();
            this.loadAllCases();
        } catch (e) { this.showErrorModal("Delete Error", "Failed to delete items."); }
    },

    async bulkStatus(status) {
        try {
            await fetch('/api/cases/batch/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    case_ids: Array.from(this.state.selectedCases),
                    status: status
                })
            });
            this.showToast("Status updated");
            this.state.selectedCases.clear();
            this.updateSelectionUI();
            this.loadAllCases();
        } catch (e) { this.showErrorModal("Update Error", "Failed to update status."); }
    },

    async deleteAllProjectCases() {
        const code = prompt(`Type "DELETE" to confirm wiping ALL cases for project: ${this.state.currentProject}`);
        if (code !== "DELETE") return;

        try {
            await fetch('/api/cases/all/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project: this.state.currentProject })
            });
            this.showToast("All project data wiped 🗑️");
            this.state.selectedCases.clear();
            this.updateSelectionUI();
            // Since we are likely on settings page, we don't need to reload cases unless we are there
            // But good practice to reset state
            this.state.totalCases = 0;
            this.state.currentPage = 1;
        } catch (e) { this.showErrorModal("Wipe Error", "Failed to delete all data."); }
    },

    // --- Helper ---

    editBug(caseId, btnEl) {
        // Same edit bug logic as before...
        const card = btnEl.closest('.glass-card');
        const currentText = card.querySelector('.bug-report-text').innerText;
        const modalTitle = document.querySelector('#bug-modal .card-title');
        modalTitle.innerText = "✏️ Edit Defect Report";
        const descArea = document.getElementById('bug-desc');
        descArea.value = currentText.trim();
        const btn = document.querySelector('#bug-modal .btn-primary');
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.innerText = "Save Changes";
        newBtn.onclick = async () => {
            try {
                const res = await fetch('/api/bugs', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        case_id: caseId,
                        project: this.state.currentProject,
                        new_text: descArea.value
                    })
                });
                if (res.ok) {
                    this.showToast("Bug report updated");
                    this.closeModal();
                    this.loadBugs();
                }
            } catch (e) { alert("Error saving changes"); }
        };
        document.getElementById('bug-modal').classList.add('open');
    },

    showToast(msg, type = 'success') {
        const toast = document.getElementById('toast');
        const msgEl = document.getElementById('toast-msg');
        msgEl.innerText = msg;
        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 3000);
    },
    showErrorModal(title, message) {
        let cleanMsg = message;

        // Sanitize Gemini JSON/Blob errors
        if (typeof message === 'string') {
            if (message.includes('429') || message.includes('RESOURCE_EXHAUSTED')) {
                cleanMsg = "⚠️ AI Quota Exceeded. All free models are currently overloaded. Please try later. Your data is not lost.";
            } else if (message.includes('{') && message.includes('error')) {
                // Try to extract internal error message from JSON blob
                try {
                    const match = message.match(/"message":\s*"([^"]+)"/);
                    if (match && match[1]) cleanMsg = match[1];
                } catch (e) { }
            }
        }

        document.querySelector('#error-modal .error-title').innerText = title;
        document.getElementById('error-msg-text').innerText = cleanMsg;
        document.getElementById('error-modal').classList.add('visible');
    },

    closeErrorModal() {
        document.getElementById('error-modal').classList.remove('visible');
    }
};

document.addEventListener('DOMContentLoaded', () => app.init());
