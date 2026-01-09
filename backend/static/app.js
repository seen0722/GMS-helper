const API_BASE = '/api';



let allClustersData = [];
let allFailuresData = [];
let currentFailuresPage = 1;
let currentFailuresQuery = '';
const failuresPerPage = 50;

// Notification helper
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 px-6 py-4 rounded-lg shadow-lg transition-all duration-300 ${type === 'success' ? 'bg-green-600 text-white' :
        type === 'error' ? 'bg-red-600 text-white' :
            'bg-blue-600 text-white'
        }`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// Copy to Clipboard helper
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard', 'success');
    } catch (err) {
        console.error('Failed to copy: ', err);
        showNotification('Failed to copy', 'error');
    }
}

function toggleFilter(el) {
    const isChecked = el.getAttribute('aria-checked') === 'true';
    const nextState = !isChecked;
    el.setAttribute('aria-checked', nextState.toString());
    
    // Sync with hidden checkbox
    const checkbox = document.getElementById('filter-no-redmine');
    if (checkbox) {
        checkbox.checked = nextState;
        checkbox.dispatchEvent(new Event('change'));
    }
}


const router = {
    cleanup: null,
    currentPage: null,
    currentParams: {},
    navigate: (page, params = {}) => {
        if (router.cleanup) {
            router.cleanup();
            router.cleanup = null;
        }
        router.currentPage = page;
        router.currentParams = params;

        // Update URL
        const url = new URL(window.location);
        url.searchParams.set('page', page);
        if (params.id) {
            url.searchParams.set('id', params.id);
        } else {
            url.searchParams.delete('id');
        }
        window.history.pushState({}, '', url);

        const content = document.getElementById('app-content');
        const title = document.getElementById('page-title');
        const tmpl = document.getElementById(`tmpl-${page}`);

        if (!tmpl) {
            console.error(`Template ${page} not found`);
            return;
        }

        // Update Nav
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('nav-item-active', 'bg-white/10', 'text-white'));
        const navItem = document.getElementById(`nav-${page}`);
        if (navItem) {
            navItem.classList.add('nav-item-active');
            navItem.classList.add('bg-white/10');
            navItem.classList.add('text-white');
        }

        // Render
        content.innerHTML = '';
        content.appendChild(tmpl.content.cloneNode(true));

        // Page specific logic
        if (page === 'dashboard') loadDashboard();
        if (page === 'upload') setupUpload();
        if (page === 'run-details') loadRunDetails(params.id);
        if (page === 'settings') loadSettings();

        // Update Title
        title.textContent = page.charAt(0).toUpperCase() + page.slice(1).replace('-', ' ');
    }
};

// Helper to extract a short title from a long summary
function getClusterTitle(fullSummary) {
    if (!fullSummary) return 'No summary available.';

    let summaryLines = fullSummary.split('\n');
    let summaryTitle = '';

    if (summaryLines.length > 1) {
        summaryTitle = summaryLines[0];
    } else {
        // Fallback logic
        let text = summaryLines[0];
        text = text.replace(/^Analysis:\s*/i, '').replace(/^\*\*\s*Analysis:?\s*\*\*\s*/i, '');

        const firstPeriodIndex = text.indexOf('. ');
        const bodyStartRegex = /\s+(The test|This test|The failure|This failure|The error|This error)\b/i;
        const match = text.match(bodyStartRegex);

        if (match && match.index < 150) {
            summaryTitle = text.substring(0, match.index);
        } else if (firstPeriodIndex > 0 && firstPeriodIndex < 150) {
            summaryTitle = text.substring(0, firstPeriodIndex + 1);
        } else {
            if (text.length < 100) {
                summaryTitle = text;
            } else {
                summaryTitle = text.substring(0, 100) + '...';
            }
        }
    }
    return summaryTitle;
}



// --- Dashboard Logic ---
async function loadDashboard() {
    // Show Skeletons
    document.getElementById('stat-total-runs').innerHTML = '<div class="h-8 w-16 skeleton rounded-lg"></div>';
    document.getElementById('stat-avg-pass').innerHTML = '<div class="h-8 w-20 skeleton rounded-lg"></div>';
    document.getElementById('stat-total-failures').innerHTML = '<div class="h-8 w-24 skeleton rounded-lg"></div>';
    document.getElementById('stat-total-clusters').innerHTML = '<div class="h-8 w-16 skeleton rounded-lg"></div>';
    document.getElementById('runs-table-body').innerHTML = `
        ${[1, 2, 3, 4, 5].map(() => `
            <tr>
                <td colspan="6" class="px-6 py-4"><div class="h-10 w-full skeleton rounded-lg"></div></td>
            </tr>
        `).join('')}
    `;

    try {
        const response = await fetch(`${API_BASE}/reports/runs?limit=1000`);
        allRunsData = await response.json();

        // Reset state
        currentRunsPage = 1;
        currentRunsQuery = '';

        // Calculate Stats (on all data)
        let totalRuns = allRunsData.length;
        let totalClusters = 0;
        let totalPassed = 0;
        let totalFailures = 0;

        allRunsData.forEach(run => {
            totalFailures += run.failed_tests;
            totalPassed += run.passed_tests;
            totalClusters += (run.cluster_count || 0);
        });

        let avgPassRate = '0.00';
        const totalExecuted = totalPassed + totalFailures;

        if (totalExecuted > 0) {
            const rawRate = (totalPassed / totalExecuted) * 100;
            avgPassRate = rawRate.toFixed(2);

            // Edge case: If we have failures but rate rounds to 100.00, show 99.99
            if (totalFailures > 0 && avgPassRate === '100.00') {
                avgPassRate = '99.99';
            }
        }

        // Update Stats UI
        document.getElementById('stat-total-runs').textContent = totalRuns;
        document.getElementById('stat-avg-pass').textContent = `${avgPassRate}%`;
        document.getElementById('stat-total-failures').textContent = totalFailures.toLocaleString();
        document.getElementById('stat-total-clusters').textContent = totalClusters.toLocaleString();
 
        // Render Sparklines (Phase 2)
        renderSparkline('stat-total-runs-sparkline', [2, 5, 3, 8, 5, 9, 7], '#3b82f6');
        renderSparkline('stat-avg-pass-sparkline', [70, 75, 72, 85, 80, 88, 92], '#10b981');
        renderSparkline('stat-total-failures-sparkline', [10, 8, 12, 5, 7, 3, 2], '#ef4444');
        renderSparkline('stat-total-clusters-sparkline', [4, 3, 5, 2, 3, 1, 1], '#f59e0b');

        // Setup Search Listener
        const searchInput = document.getElementById('runs-search');
        if (searchInput) {
            searchInput.value = '';
            let timeout = null;
            searchInput.oninput = (e) => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    currentRunsQuery = e.target.value.toLowerCase();
                    currentRunsPage = 1;
                    renderDashboardTable();
                }, 300);
            };
        }

        // Setup Pagination Listeners
        const prevBtn = document.getElementById('runs-prev');
        const nextBtn = document.getElementById('runs-next');

        if (prevBtn) {
            prevBtn.onclick = () => {
                if (currentRunsPage > 1) {
                    currentRunsPage--;
                    renderDashboardTable();
                }
            };
        }

        if (nextBtn) {
            nextBtn.onclick = () => {
                const filtered = filterRuns();
                const maxPage = Math.ceil(filtered.length / runsPerPage);
                if (currentRunsPage < maxPage) {
                    currentRunsPage++;
                    renderDashboardTable();
                }
            };
        }

        renderDashboardTable();

    } catch (e) {
        console.error("Failed to load dashboard", e);
    }
}

function filterRuns() {
    if (!currentRunsQuery) return allRunsData;

    return allRunsData.filter(run =>
        (run.test_suite_name && run.test_suite_name.toLowerCase().includes(currentRunsQuery)) ||
        (run.device_fingerprint && run.device_fingerprint.toLowerCase().includes(currentRunsQuery)) ||
        (String(run.id).includes(currentRunsQuery))
    );
}

function renderDashboardTable() {
    const tbody = document.getElementById('runs-table-body');
    const startEl = document.getElementById('runs-start');
    const endEl = document.getElementById('runs-end');
    const totalEl = document.getElementById('runs-total');
    const prevBtn = document.getElementById('runs-prev');
    const nextBtn = document.getElementById('runs-next');

    if (!tbody) return;

    const filtered = filterRuns();
    const total = filtered.length;
    const maxPage = Math.ceil(total / runsPerPage) || 1;

    // Ensure page is valid
    if (currentRunsPage > maxPage) currentRunsPage = maxPage;
    if (currentRunsPage < 1) currentRunsPage = 1;

    const start = (currentRunsPage - 1) * runsPerPage;
    const end = Math.min(start + runsPerPage, total);
    const pageItems = filtered.slice(start, end);

    // Update UI Stats
    if (startEl) startEl.textContent = total === 0 ? 0 : start + 1;
    if (endEl) endEl.textContent = end;
    if (totalEl) totalEl.textContent = total;

    // Update Buttons
    if (prevBtn) prevBtn.disabled = currentRunsPage === 1;
    if (nextBtn) nextBtn.disabled = currentRunsPage === maxPage || total === 0;

    tbody.innerHTML = '';

            if (total === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="px-8 py-20 text-center">
                            <div class="flex flex-col items-center gap-6 animate-in fade-in zoom-in duration-700">
                                <div class="relative w-64 h-64">
                                    <img src="/static/assets/empty_state.png" 
                                         alt="No results" class="w-full h-full object-contain rounded-3xl shadow-2xl">
                                    <div class="absolute inset-0 rounded-3xl ring-1 ring-inset ring-white/10 glass-dark opacity-10"></div>
                                </div>
                                <div class="max-w-xs">
                                    <h3 class="text-slate-900 text-lg font-bold">${currentRunsQuery ? 'No results found' : 'All Clear'}</h3>
                                    <p class="text-slate-400 text-sm mt-2 font-medium leading-relaxed">${currentRunsQuery ? 'Try adjusting your search criteria' : 'Connect your first test report to begin the analyzer experience'}</p>
                                </div>
                                ${!currentRunsQuery ? `
                                <button onclick="router.navigate('upload')" class="mt-4 px-6 py-2.5 bg-blue-600 text-white rounded-full font-semibold shadow-lg hover:shadow-blue-500/30 transition-all btn-press">
                                    Get Started
                                </button>` : ''}
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }

    // Helper for suite color
    const getSuiteColor = (name) => {
        if (!name) return 'bg-slate-100 text-slate-700';
        const n = name.toUpperCase();
        if (n.includes('CTS')) return 'bg-blue-100 text-blue-700';
        if (n.includes('GTS')) return 'bg-emerald-100 text-emerald-700';
        if (n.includes('VTS')) return 'bg-purple-100 text-purple-700';
        if (n.includes('STS')) return 'bg-orange-100 text-orange-700';
        return 'bg-slate-100 text-slate-700';
    };

    pageItems.forEach(run => {
        const executed = run.passed_tests + run.failed_tests;
        let passRate = 0;
        if (executed > 0) {
            const rate = (run.passed_tests / executed) * 100;
            const twoDecimals = rate.toFixed(2);
            passRate = (twoDecimals === "100.00" && run.failed_tests > 0) ? rate.toFixed(4) : twoDecimals;
        }
        const date = new Date(run.start_time).toLocaleDateString();

        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 transition-colors border-b border-slate-50 last:border-0';
        tr.innerHTML = `
            <td class="px-6 py-4 font-medium text-slate-900">#${run.id}</td>
            <td class="px-6 py-4">
                <span class="px-2 py-1 rounded text-xs font-semibold ${getSuiteColor(run.test_suite_name)}">
                    ${run.test_suite_name || 'Unknown'}
                </span>
            </td>
            <td class="px-6 py-4 text-slate-600">
                <div class="font-medium text-slate-900">${run.build_model || 'Unknown'}</div>
                ${(run.build_product && run.build_product !== run.build_model) ? `<div class="text-xs text-slate-500">${run.build_product}</div>` : ''}
                <div class="text-[10px] text-slate-400 break-all mt-0.5">${run.device_fingerprint || ''}</div>
            </td>
            <td class="px-6 py-4 text-slate-500">${date}</td>
            <td class="px-6 py-4 text-center">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${passRate > 90 ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}">
                    ${passRate}%
                </span>
            </td>
            <td class="px-6 py-4 text-center">
                <div class="flex flex-col items-center">
                    <span class="text-sm font-bold text-red-600">${run.failed_tests} Failures</span>
                    <span class="text-xs text-slate-500">in ${run.cluster_count || 0} Clusters</span>
                </div>
            </td>
            <td class="px-6 py-4 text-right">
                <button onclick="router.navigate('run-details', {id: ${run.id}})" class="text-blue-600 hover:text-blue-900 font-medium">View</button>
            </td>
`;
        tbody.appendChild(tr);
    });
}

// --- Upload Logic ---
function setupUpload() {
    const input = document.getElementById('file-input');
    const statusDiv = document.getElementById('upload-status');
    const progressBar = document.getElementById('upload-progress');
    const message = document.getElementById('upload-message');

    input.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        statusDiv.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressBar.classList.remove('bg-red-600');
        progressBar.classList.add('bg-blue-600');
        message.classList.remove('text-red-600', 'text-green-600');

        // Check if it's an XML file for local parsing
        const isXML = file.name.toLowerCase().endsWith('.xml');

        if (isXML) {
            // Use browser-side parsing
            message.textContent = `Parsing ${file.name} locally...`;
            
            try {
                const worker = new Worker('/static/xml-parser.worker.js');
                
                worker.onmessage = async (event) => {
                    const data = event.data;
                    
                    if (data.type === 'progress') {
                        progressBar.style.width = `${Math.min(data.percent * 0.9, 90)}%`;
                        const mbProcessed = (data.bytesRead / 1024 / 1024).toFixed(1);
                        const mbTotal = (data.totalBytes / 1024 / 1024).toFixed(1);
                        message.textContent = `Parsing... ${data.percent}% (${mbProcessed}/${mbTotal} MB, ${data.testsProcessed.toLocaleString()} tests)`;
                    } else if (data.type === 'complete') {
                        progressBar.style.width = '95%';
                        message.textContent = `Uploading results (${data.result.failures.length} failures)...`;
                        
                        try {
                            // Upload parsed JSON
                            const response = await fetch(`${API_BASE}/import`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(data.result)
                            });
                            
                            if (response.ok) {
                                const result = await response.json();
                                progressBar.style.width = '100%';
                                message.textContent = 'Import complete!';
                                message.classList.add('text-green-600');
                                
                                const timeoutId = setTimeout(() => {
                                    router.navigate('run-details', { id: result.test_run_id });
                                }, 1000);
                                router.cleanup = () => clearTimeout(timeoutId);
                            } else {
                                let errorMsg = 'Import failed';
                                try {
                                    const errorData = await response.json();
                                    errorMsg = errorData.detail || errorData.message || `Import failed with status ${response.status}`;
                                } catch (e) {
                                    errorMsg = `Import failed with status ${response.status}`;
                                }
                                throw new Error(errorMsg);
                            }
                        } catch (uploadError) {
                            throw uploadError;
                        }
                        
                        worker.terminate();
                    } else if (data.type === 'error') {
                        throw new Error(data.error);
                    }
                };
                
                worker.onerror = (error) => {
                    console.error('Worker error:', error);
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('bg-blue-600');
                    progressBar.classList.add('bg-red-600');
                    message.textContent = `Parsing error: ${error.message || 'Unknown error'}`;
                    message.classList.add('text-red-600');
                    worker.terminate();
                };
                
                // Start parsing
                worker.postMessage(file);
                
            } catch (e) {
                progressBar.style.width = '100%';
                progressBar.classList.remove('bg-blue-600');
                progressBar.classList.add('bg-red-600');
                message.textContent = `Error: ${e.message}`;
                message.classList.add('text-red-600');
                console.error('Local parsing failed', e);
            }
        } else {
            // Fallback to server-side upload for non-XML files
            message.textContent = `Uploading ${file.name}...`;
            progressBar.style.width = '10%';

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch(`${API_BASE}/upload`, {
                    method: 'POST',
                    body: formData
                });

                progressBar.style.width = '80%';

                if (response.ok) {
                    const result = await response.json();
                    progressBar.style.width = '100%';
                    message.textContent = 'Upload complete! Processing...';
                    message.classList.add('text-green-600');

                    const timeoutId = setTimeout(() => {
                        router.navigate('run-details', { id: result.test_run_id });
                    }, 1000);
                    router.cleanup = () => clearTimeout(timeoutId);
                } else {
                    let errorMsg = 'Upload failed';
                    try {
                        const errorData = await response.json();
                        errorMsg = errorData.detail || errorData.message || `Upload failed with status ${response.status}`;
                    } catch (e) {
                        errorMsg = `Upload failed with status ${response.status}`;
                    }
                    throw new Error(errorMsg);
                }
            } catch (e) {
                progressBar.style.width = '100%';
                progressBar.classList.remove('bg-blue-600');
                progressBar.classList.add('bg-red-600');
                message.textContent = `Error: ${e.message}`;
                message.classList.add('text-red-600');
                console.error('Upload failed', e);
                alert(`Upload failed: ${e.message}`);
            }
        }
    });
}

// --- Run Details Logic ---
async function loadRunDetails(runId) {
    try {
        // Load Run Info
        const runRes = await fetch(`${API_BASE}/reports/runs/${runId}`);
        const run = await runRes.json();

        // Store for Redmine export
        currentRunDetails = run;

        // Async Guard: Stop if page changed
        if (router.currentPage !== 'run-details' || router.currentParams.id != runId) return;

        document.getElementById('detail-suite-name').textContent = run.test_suite_name;

        const deviceEl = document.getElementById('detail-device');
        const model = run.build_model || 'Unknown';
        const product = run.build_product || '';
        const fingerprint = run.device_fingerprint || '';

        let deviceHtml = `<span class="font-medium text-slate-900">Device: ${model}</span>`;
        if (product && product !== model) {
            deviceHtml += `<span class="text-xs text-slate-500">(${product})</span>`;
        }
        
        // Truncated Fingerprint (Phase 4)
        const displayFingerprint = fingerprint.length > 40 ? fingerprint.substring(0, 40) + '...' : fingerprint;
        deviceHtml += `
            <div class="flex items-center gap-2 mt-0.5">
                <div class="text-[10px] text-slate-400 font-mono" title="${fingerprint}">${displayFingerprint}</div>
                ${fingerprint ? `
                <button onclick="copyToClipboard('${fingerprint}')" class="text-slate-400 hover:text-blue-500 transition-colors p-1 rounded-md hover:bg-slate-100" title="Copy Fingerprint">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"></path></svg>
                </button>` : ''}
            </div>
        `;
        deviceEl.innerHTML = deviceHtml;
        document.getElementById('detail-date').textContent = new Date(run.start_time).toLocaleString();

        // Inject System Info Card
        const infoContainer = document.getElementById('system-info-container');
        // Delete Confirmation Modal
        const deleteModalHtml = `
    <div id="delete-modal"
class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 class="text-lg font-bold text-slate-800 mb-4">Confirm Deletion</h3>
        <div id="delete-modal-message" class="text-sm text-slate-600 mb-6"></div>
        <div class="flex gap-3 justify-end">
            <button id="modal-cancel"
                class="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors">
                Cancel
            </button>
            <button id="modal-confirm"
                class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">
                Delete
            </button>
        </div>
    </div>
            </div>
    `;
        // Append the modal HTML to the body if it doesn't exist
        if (!document.getElementById('delete-modal')) {
            document.body.insertAdjacentHTML('beforeend', deleteModalHtml);
        }

        if (infoContainer) {
            infoContainer.innerHTML = `
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-100 mt-6">
                    <h4 class="font-semibold text-slate-800 mb-4">System Information</h4>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                            <div class="text-slate-500">Model</div>
                            <div class="font-medium text-slate-900">${run.build_model || '-'}</div>
                        </div>
                        <div>
                            <div class="text-slate-500">Build ID</div>
                            <div class="font-medium text-slate-900">${run.build_id || '-'}</div>
                        </div>
                        <div>
                            <div class="text-slate-500">Android Version</div>
                            <div class="font-medium text-slate-900">${run.android_version || '-'}</div>
                        </div>
                        <div>
                            <div class="text-slate-500">Security Patch</div>
                            <div class="font-medium text-slate-900">${run.security_patch || '-'}</div>
                        </div>
                        <div>
                            <div class="text-slate-500">Suite Version</div>
                            <div class="font-medium text-slate-900">${run.suite_version || '-'}</div>
                        </div>
                        <div>
                            <div class="text-slate-500">Host Name</div>
                            <div class="font-medium text-slate-900">${run.host_name || '-'}</div>
                        </div>
                    </div>
                </div>
    `;
        }

        // Fetch and display detailed statistics
        const statsRes = await fetch(`${API_BASE}/reports/runs/${runId}/stats`);
        const stats = await statsRes.json();

        const statsContainer = document.getElementById('test-stats-container');
        if (statsContainer && stats) {
            // Check if module stats are available
            const hasModuleStats = stats.total_modules > 0;

            statsContainer.innerHTML = `
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-100 mt-6">
                    <h4 class="font-semibold text-slate-800 mb-4">Test Results Summary</h4>
                    ${hasModuleStats ? `
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div class="text-center p-4 bg-green-50 rounded-lg border border-green-100">
                            <div class="text-3xl font-bold text-green-600">${stats.passed_tests.toLocaleString()}</div>
                            <div class="text-sm text-slate-600 mt-1">Tests Passed</div>
                        </div>
                        <div class="text-center p-4 bg-red-50 rounded-lg border border-red-100">
                            <div class="text-3xl font-bold text-red-600">${stats.failed_tests.toLocaleString()}</div>
                            <div class="text-sm text-slate-600 mt-1">Tests Failed</div>
                        </div>
                        <div class="text-center p-4 bg-blue-50 rounded-lg border border-blue-100">
                            <div class="text-3xl font-bold text-blue-600">${stats.passed_modules.toLocaleString()}</div>
                            <div class="text-sm text-slate-600 mt-1">Modules Done</div>
                        </div>
                        <div class="text-center p-4 bg-slate-50 rounded-lg border border-slate-200">
                            <div class="text-3xl font-bold text-slate-700">${stats.total_modules.toLocaleString()}</div>
                            <div class="text-sm text-slate-600 mt-1">Modules Total</div>
                        </div>
                    </div>
                    ` : `
                    <div class="grid grid-cols-2 gap-4">
                        <div class="text-center p-4 bg-green-50 rounded-lg border border-green-100">
                            <div class="text-3xl font-bold text-green-600">${stats.passed_tests.toLocaleString()}</div>
                            <div class="text-sm text-slate-600 mt-1">Tests Passed</div>
                        </div>
                        <div class="text-center p-4 bg-red-50 rounded-lg border border-red-100">
                            <div class="text-3xl font-bold text-red-600">${stats.failed_tests.toLocaleString()}</div>
                            <div class="text-sm text-slate-600 mt-1">Tests Failed</div>
                        </div>
                    </div>
                    <div class="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
                        <strong>Note:</strong> Module statistics are not available for this run (processed before the feature was added). Upload a new test file to see module-level details.
                    </div>
                    `}
                </div>
            `;
        }


        // Status Handling
        const statusBadge = document.createElement('span');
        statusBadge.className = 'ml-2 px-2 py-1 text-xs rounded-full font-medium';

        if (run.status === 'processing' || run.status === 'pending') {
            statusBadge.className += ' bg-blue-100 text-blue-800';
            statusBadge.textContent = 'Processing...';
            document.getElementById('detail-suite-name').appendChild(statusBadge);

            // Poll for updates
            const timeoutId = setTimeout(() => loadRunDetails(runId), 2000);
            router.cleanup = () => clearTimeout(timeoutId);
            return; // Don't load other details yet
        } else if (run.status === 'failed') {
            statusBadge.className += ' bg-red-100 text-red-800';
            statusBadge.textContent = 'Failed';
            document.getElementById('detail-suite-name').appendChild(statusBadge);
        } else {
            statusBadge.className += ' bg-green-100 text-green-800';
            statusBadge.textContent = 'Completed';
            // document.getElementById('detail-suite-name').appendChild(statusBadge); // Optional
        }

        const executed = run.passed_tests + run.failed_tests;
        let passRate = 0;
        if (executed > 0) {
            const rate = (run.passed_tests / executed) * 100;
            const twoDecimals = rate.toFixed(2);
            // If it rounds to 100.00 but there are failures, show more precision
            passRate = (twoDecimals === "100.00" && run.failed_tests > 0) ? rate.toFixed(4) : twoDecimals;
        }
        document.getElementById('detail-pass-rate').textContent = `${passRate}%`;

        // Setup Analysis Button
        const btnAnalyze = document.getElementById('btn-analyze');
        if (btnAnalyze) {
            btnAnalyze.onclick = async () => {
                btnAnalyze.disabled = true;
                btnAnalyze.innerHTML = `
                    <svg class="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Analyzing...
                `;
                btnAnalyze.classList.remove('bg-purple-600', 'hover:bg-purple-700');
                btnAnalyze.classList.add('bg-slate-400', 'cursor-not-allowed');

                try {
                    const res = await fetch(`${API_BASE}/analysis/run/${runId}`, {
                        method: 'POST'
                    });

                    if (res.ok) {
                        // Start polling for results
                        pollForAnalysis(runId);
                    } else {
                        alert('Failed to start analysis');
                        btnAnalyze.disabled = false;
                        btnAnalyze.innerHTML = `
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                            Run AI Analysis
                        `;
                        btnAnalyze.classList.add('bg-purple-600', 'hover:bg-purple-700');
                        btnAnalyze.classList.remove('bg-slate-400', 'cursor-not-allowed');
                    }
                } catch (e) {
                    console.error("Analysis trigger failed", e);
                    alert('Error starting analysis');
                    btnAnalyze.disabled = false;
                    btnAnalyze.innerHTML = `
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                        Run AI Analysis
                    `;
                    btnAnalyze.classList.add('bg-purple-600', 'hover:bg-purple-700');
                    btnAnalyze.classList.remove('bg-slate-400', 'cursor-not-allowed');
                }
            };
        }

        // Setup Delete Button with Custom Modal
        const btnDelete = document.getElementById('btn-delete');
        const deleteModal = document.getElementById('delete-modal');
        const modalMessage = document.getElementById('delete-modal-message');
        const modalCancel = document.getElementById('modal-cancel');
        const modalConfirm = document.getElementById('modal-confirm');

        // Store handler references for cleanup
        const showModalHandler = () => {
            // Show modal with details
            modalMessage.innerHTML = `
                Are you sure you want to delete <strong>Run #${runId}</strong>?<br><br>
                This will permanently remove:<br>
                • All test case data (${run.total_tests.toLocaleString()} tests)<br>
                • Analysis results and clusters<br>
                • System information
            `;
            deleteModal.classList.remove('hidden');
            document.body.classList.add('modal-open');
        };

        const cancelHandler = () => {
            deleteModal.classList.add('hidden');
        };

        // Flag to prevent duplicate execution - must be outside handler
        let isDeleting = false;

        const confirmHandler = async () => {
            if (isDeleting) return; // Prevent duplicate execution
            isDeleting = true;

            try {
                modalConfirm.disabled = true;
                modalConfirm.textContent = 'Deleting...';

                const response = await fetch(`${API_BASE}/reports/runs/${runId}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    deleteModal.classList.add('hidden');
                    alert('Test run deleted successfully');
                    router.navigate('dashboard');
                } else {
                    alert('Failed to delete test run');
                    modalConfirm.disabled = false;
                    modalConfirm.textContent = 'Delete';
                    isDeleting = false;
                }
            } catch (e) {
                console.error("Delete failed", e);
                alert('Error deleting test run');
                modalConfirm.disabled = false;
                modalConfirm.textContent = 'Delete';
                isDeleting = false;
            }
        };

        const outsideClickHandler = (e) => {
            if (e.target === deleteModal) {
                deleteModal.classList.add('hidden');
            }
        };

        // Add event listeners
        if (btnDelete) btnDelete.addEventListener('click', showModalHandler);
        if (modalCancel) modalCancel.addEventListener('click', cancelHandler);
        if (modalConfirm) modalConfirm.addEventListener('click', confirmHandler);
        if (deleteModal) deleteModal.addEventListener('click', outsideClickHandler);

        // Store cleanup function to remove listeners when navigating away
        const oldCleanup = router.cleanup;
        router.cleanup = () => {
            if (oldCleanup) oldCleanup();
            if (btnDelete) btnDelete.removeEventListener('click', showModalHandler);
            if (modalCancel) modalCancel.removeEventListener('click', cancelHandler);
            if (modalConfirm) modalConfirm.removeEventListener('click', confirmHandler);
            if (deleteModal) deleteModal.removeEventListener('click', outsideClickHandler);
        };

        // Check if we should poll (if no clusters but status is completed/processing)
        // For now, just load clusters. If empty, user can click button.
        loadClusters(runId);

        // Load All Failures List
        loadAllFailures(runId);

        // Initialize Tabs
        switchTab('overview');

    } catch (e) {
        console.error("Failed to load run details", e);
    }
}

// Helper function to get status color based on Redmine status name
function getStatusColor(status) {
    if (!status) return 'bg-slate-100 text-slate-600';
    const statusLower = status.toLowerCase();

    // Common Redmine statuses
    if (statusLower.includes('new')) return 'bg-blue-100 text-blue-700';
    if (statusLower.includes('in progress') || statusLower.includes('assigned')) return 'bg-purple-100 text-purple-700';
    if (statusLower.includes('resolved') || statusLower.includes('fixed')) return 'bg-green-100 text-green-700';
    if (statusLower.includes('closed')) return 'bg-slate-200 text-slate-700';
    if (statusLower.includes('feedback') || statusLower.includes('pending')) return 'bg-yellow-100 text-yellow-700';
    if (statusLower.includes('reject') || statusLower.includes('wont')) return 'bg-red-100 text-red-700';

    // Default
    return 'bg-slate-100 text-slate-600';
}



function switchTab(tabName) {
    console.log(`[switchTab] Switching to ${tabName}. Current Page: ${router.currentPage}. Failures Data Length: ${allFailuresData ? allFailuresData.length : 'undefined'}`);

    // Hide all tab content
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('hidden');
    });

    // Show selected tab content
    const selectedContent = document.getElementById(`tab-${tabName}`);
    if (selectedContent) {
        // Delay slighty for transition overlap
        setTimeout(() => {
            selectedContent.classList.remove('hidden');
        }, 50);
    }

    // Update tab buttons (Segmented Control style)
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const selectedBtn = document.getElementById(`tab-btn-${tabName}`);
    if (selectedBtn) {
        selectedBtn.classList.add('active');
    }

    // Lazy load failures if needed
    // Force load if empty OR if we just want to be sure
    if (tabName === 'failures') {
        if (!allFailuresData || allFailuresData.length === 0) {
            console.log("[switchTab] Failures data empty. Triggering load...");
            if (router.currentParams && router.currentParams.id) {
                loadAllFailures(router.currentParams.id);
            } else {
                console.error("[switchTab] No run ID found in params!");
            }
        } else {
            console.log("[switchTab] Failures data already loaded. Re-rendering...");
            renderFailuresTable();
        }
    }
}

async function loadAllFailures(runId) {
    console.log(`Loading failures for run ${runId}...`);
    try {
        const res = await fetch(`${API_BASE}/reports/runs/${runId}/failures`);
        allFailuresData = await res.json();
        console.log(`Loaded ${allFailuresData.length} failures.`);

        // Reset state
        currentFailuresPage = 1;
        currentFailuresQuery = '';

        // Setup Search Listener
        const searchInput = document.getElementById('failures-search');
        if (searchInput) {
            searchInput.value = '';
            // Debounce search
            let timeout = null;
            searchInput.oninput = (e) => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    currentFailuresQuery = e.target.value.toLowerCase();
                    currentFailuresPage = 1;
                    renderFailuresTable();
                }, 300);
            };
        }

        // Setup Pagination Listeners
        const prevBtn = document.getElementById('failures-prev');
        const nextBtn = document.getElementById('failures-next');

        if (prevBtn) {
            prevBtn.onclick = () => {
                if (currentFailuresPage > 1) {
                    currentFailuresPage--;
                    renderFailuresTable();
                }
            };
        }

        if (nextBtn) {
            nextBtn.onclick = () => {
                const filtered = filterFailures();
                const maxPage = Math.ceil(filtered.length / failuresPerPage);
                if (currentFailuresPage < maxPage) {
                    currentFailuresPage++;
                    renderFailuresTable();
                }
            };
        }

        renderFailuresTable();

    } catch (e) {
        console.error("Failed to load all failures", e);
        const container = document.getElementById('failures-list-container');
        if (container) {
            container.innerHTML = `<div class="text-center py-12 text-red-500">Error loading failures: ${e.message}</div>`;
        }
    }
}

function filterFailures() {
    if (!currentFailuresQuery) return allFailuresData;

    return allFailuresData.filter(f =>
        (f.module_name && f.module_name.toLowerCase().includes(currentFailuresQuery)) ||
        (f.class_name && f.class_name.toLowerCase().includes(currentFailuresQuery)) ||
        (f.method_name && f.method_name.toLowerCase().includes(currentFailuresQuery)) ||
        (f.error_message && f.error_message.toLowerCase().includes(currentFailuresQuery))
    );
}

function renderFailuresTable() {
    const container = document.getElementById('failures-list-container');
    const countBadge = document.getElementById('failures-count-badge');
    const startEl = document.getElementById('failures-start');
    const endEl = document.getElementById('failures-end');
    const totalEl = document.getElementById('failures-total');
    const prevBtn = document.getElementById('failures-prev');
    const nextBtn = document.getElementById('failures-next');

    if (!container) {
        console.error("Failures list container not found!");
        return;
    }

    const filtered = filterFailures();

    const groupBy = document.getElementById('failures-group-by')?.value || 'module';

    // Group by module or cluster
    const groups = {};
    filtered.forEach(f => {
        let groupKey = '';
        let groupName = '';

        if (groupBy === 'cluster') {
            if (f.failure_analysis && f.failure_analysis.cluster) {
                const c = f.failure_analysis.cluster;
                groupKey = `cluster-${c.id}`;
                // Use cleaner title format using helper
                let summary = c.ai_summary || c.description || 'No Summary';
                groupName = getClusterTitle(summary);

                // Store cluster for badge rendering
                if (!groups[groupKey]) {
                    groups[groupKey] = {
                        name: groupName,
                        failures: [],
                        cluster: c
                    };
                }
            } else {
                groupKey = 'unclustered';
                groupName = 'Unclustered';
            }
        } else {
            groupKey = f.module_name || 'Unknown Module';
            groupName = groupKey;
        }

        if (!groups[groupKey]) {
            groups[groupKey] = {
                name: groupName,
                failures: [],
                cluster: null
            };
        }
        groups[groupKey].failures.push(f);
    });

    // Convert to array and sort by count desc
    const sortedGroups = Object.values(groups).sort((a, b) => b.failures.length - a.failures.length);
    const totalModules = sortedGroups.length;
    const maxPage = Math.ceil(totalModules / failuresPerPage) || 1;

    // Ensure page is valid
    if (currentFailuresPage > maxPage) currentFailuresPage = maxPage;
    if (currentFailuresPage < 1) currentFailuresPage = 1;

    const start = (currentFailuresPage - 1) * failuresPerPage;
    const end = Math.min(start + failuresPerPage, totalModules);
    const pageGroups = sortedGroups.slice(start, end);

    // Update UI Stats
    if (countBadge) countBadge.textContent = `${filtered.length} failures`;
    if (startEl) startEl.textContent = totalModules === 0 ? 0 : start + 1;
    if (endEl) endEl.textContent = end;
    if (totalEl) totalEl.textContent = totalModules;

    // Update Buttons
    if (prevBtn) prevBtn.disabled = currentFailuresPage === 1;
    if (nextBtn) nextBtn.disabled = currentFailuresPage === maxPage || totalModules === 0;

    container.innerHTML = '';

    if (totalModules === 0) {
        container.innerHTML = `
            <div class="text-center py-12 bg-slate-50 rounded-lg border border-slate-200 text-slate-500">
                ${currentFailuresQuery ? 'No matching failures found.' : 'No failures found in this run.'}
            </div>
        `;
        return;
    }

    pageGroups.forEach((group, index) => {
        const groupEl = document.createElement('div');
        groupEl.className = 'border border-slate-200 rounded-lg overflow-hidden bg-white shadow-sm';

        // Header
        const headerId = `header-group-${index}`;
        const contentId = `content-group-${index}`;

        // Determine Badges
        let badgesHtml = '';
        if (group.cluster) {
            const sev = group.cluster.severity || 'Medium';
            const sevColor = sev === 'High' ? 'bg-red-100 text-red-700' : (sev === 'Medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700');
            badgesHtml += `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold ${sevColor} flex-shrink-0">${sev}</span>`;

            const cat = group.cluster.category || 'Uncategorized';
            badgesHtml += `<span class="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 flex-shrink-0">${cat}</span>`;
        }

        groupEl.innerHTML = `
            <div class="bg-slate-50 px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-slate-100 transition-colors"
                onclick="
                    document.getElementById('${contentId}').classList.toggle('hidden'); 
                    this.querySelector('svg').classList.toggle('rotate-180');
                    const titleSpan = this.querySelector('.cluster-title');
                    titleSpan.classList.toggle('truncate');
                    titleSpan.classList.toggle('whitespace-normal');
                ">
                <div class="flex items-center gap-3 overflow-hidden min-w-0 flex-1">
                    ${group.cluster ? `<span class="font-mono text-xs text-slate-500 flex-shrink-0">#${group.cluster.id}</span>` : ''}
                    <span class="font-semibold text-slate-800 truncate cluster-title" title="${group.name}">${group.name}</span>
                    
                    <div class="flex gap-2 items-center flex-shrink-0">
                        ${badgesHtml}
                        <span class="px-2 py-0.5 bg-slate-200 text-slate-700 text-xs font-medium rounded-full border border-slate-300">
                            ${group.failures.length} failures
                        </span>
                    </div>
                </div>
                <svg class="w-5 h-5 text-slate-400 transition-transform duration-200 flex-shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                </svg>
            </div>
            <div id="${contentId}" class="hidden divide-y divide-slate-100 border-t border-slate-200">
                ${group.failures.map(f => {
            const errorMsg = f.error_message || 'No error message';
            const stackTrace = f.stack_trace ? f.stack_trace.trim() : '';
            return `
                    <div class="p-4 hover:bg-slate-50 transition-colors">
                        <div class="flex flex-col gap-2">
                            <div class="text-xs font-semibold text-slate-500">${f.module_name}</div>
                            <div class="font-medium text-slate-700 font-mono text-sm break-all">${f.class_name}#${f.method_name}</div>
                            <div class="text-sm text-red-600 break-words">${escapeHtml(errorMsg)}</div>
                            ${stackTrace ? `
                                <details class="group mt-1">
                                    <summary class="text-xs text-blue-600 cursor-pointer hover:underline select-none w-fit">Show Stack Trace</summary>
                                    <pre class="mt-2 p-3 bg-slate-900 text-slate-50 rounded text-xs overflow-x-auto code-scroll font-mono max-h-60 whitespace-pre-wrap break-all">${escapeHtml(stackTrace)}</pre>
                                </details>
                            ` : ''}
                        </div>
                    </div>
                    `;
        }).join('')}
            </div>
        `;
        container.appendChild(groupEl);
    });
}



function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function loadClusters(runId) {
    try {
        const res = await fetch(`${API_BASE}/analysis/run/${runId}/clusters`);
        const clusters = await res.json();
        allClustersData = clusters;

        console.log(`[loadClusters] Fetched ${clusters.length} clusters for run ${runId}`);

        // --- 1. Calculate KPIs ---
        let highSeverityCount = 0;
        let mediumSeverityCount = 0;
        let lowSeverityCount = 0;
        let categoryCounts = {};
        let todoCount = 0;

        clusters.forEach(c => {
            // Severity
            const sev = (c.severity || 'Medium').toLowerCase();
            if (sev === 'high') highSeverityCount++;
            else if (sev === 'medium') mediumSeverityCount++;
            else lowSeverityCount++;

            // Category
            const cat = c.category || 'Uncategorized';
            categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;

            // To-Do (High/Medium severity, no Redmine - assuming no field yet means no issue)
            // TODO: Check actual Redmine field when available
            if (sev === 'high' || sev === 'medium') {
                todoCount++;
            }
        });

        // Determine Overall Severity
        let overallSeverity = 'Low';
        if (highSeverityCount > 0) overallSeverity = 'High';
        else if (mediumSeverityCount > 5) overallSeverity = 'Medium';

        // Determine Top Category
        let topCategory = '-';
        let maxCatCount = 0;
        for (const [cat, count] of Object.entries(categoryCounts)) {
            if (count > maxCatCount) {
                maxCatCount = count;
                topCategory = cat;
            }
        }
        const totalClusters = clusters.length;
        const topCatPct = totalClusters > 0 ? Math.round((maxCatCount / totalClusters) * 100) : 0;

        // Update KPI Tiles
        document.getElementById('kpi-severity').textContent = overallSeverity;
        document.getElementById('kpi-severity').className = `text-2xl font-bold ${overallSeverity === 'High' ? 'text-red-600' : (overallSeverity === 'Medium' ? 'text-yellow-600' : 'text-green-600')}`;

        document.getElementById('kpi-top-category').textContent = topCategory;
        document.getElementById('kpi-category-dist').textContent = `${topCatPct}% of clusters`;

        document.getElementById('kpi-todo-count').textContent = todoCount;

        // --- 2. Populate Table ---
        const tbody = document.getElementById('clusters-table-body');
        tbody.innerHTML = '';

        if (clusters.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="px-4 py-8 text-center text-slate-500">No analysis data found. Click "Run AI Analysis" to start.</td></tr>`;
            return;
        }

        const renderTable = (filterNoRedmine) => {
            console.log(`[renderTable] Rendering ${clusters.length} clusters, filter=${filterNoRedmine}`);
            tbody.innerHTML = '';
            clusters.forEach(cluster => {
                // Filter logic
                // if (filterNoRedmine && cluster.redmine_issue) return; 

                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-50 transition-colors cursor-pointer border-b border-slate-50 last:border-0';
                tr.onclick = () => showClusterDetail(cluster);

                // Severity Badge
                const sev = (cluster.severity || 'Medium');
                const sevColor = sev === 'High' ? 'bg-red-100 text-red-700' : (sev === 'Medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700');

                // Confidence Stars with Heat-map
                const confidence = cluster.confidence_score || 0;
                let confColor = 'text-slate-300'; // Gray for 0
                if (confidence >= 5) confColor = 'text-green-500';
                else if (confidence === 4) confColor = 'text-emerald-400';
                else if (confidence === 3) confColor = 'text-yellow-400';
                else if (confidence === 2) confColor = 'text-orange-400';
                else if (confidence === 1) confColor = 'text-red-400';

                const stars = '★'.repeat(confidence) + '☆'.repeat(5 - confidence);

                // Parse Summary Title
                // Parse Summary Title
                const fullSummary = cluster.ai_summary || cluster.description || 'No summary available.';
                const summaryTitle = getClusterTitle(fullSummary);

                tr.innerHTML = `
                    <td class="px-4 py-3 font-mono text-xs text-slate-500">#${cluster.id}</td>
                    <td class="px-4 py-3">
                        <div class="font-medium text-slate-800" title="${fullSummary.replace(/"/g, '&quot;')}">${summaryTitle}</div>
                        <div class="text-xs text-slate-500 mt-0.5 flex gap-2">
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold ${sevColor}">${sev}</span>
                            <span class="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600">${cluster.category || 'Uncategorized'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-3">
                        <div class="text-sm text-slate-600 font-semibold">
                            ${cluster.failures_count || '?'} <span class="text-xs font-normal text-slate-400">tests</span>
                        </div>
                    </td>
                    <td class="px-4 py-3 ${confColor} text-xs tracking-widest font-bold" title="Confidence: ${cluster.confidence_score}/5">${stars}</td>
                    <td class="px-4 py-3 text-sm text-slate-600">${cluster.suggested_assignment || '-'}</td>
                    <td class="px-4 py-3">
                        ${cluster.redmine_issue_id && redmineBaseUrl
                        ? `<div class="flex flex-col gap-1">
                             <a href="${redmineBaseUrl}/issues/${cluster.redmine_issue_id}" target="_blank" class="text-blue-600 hover:underline text-xs">#${cluster.redmine_issue_id}</a>
                             ${cluster.redmine_status ? `<span class="px-1.5 py-0.5 rounded text-[10px] inline-block ${getStatusColor(cluster.redmine_status)}">${cluster.redmine_status}</span>` : ''}
                           </div>`
                        : (cluster.redmine_issue_id
                            ? `<span class="text-xs text-slate-600">#${cluster.redmine_issue_id}</span>`
                            : '<span class="text-xs text-slate-400 italic">None</span>')}
                    </td>
                    <td class="px-4 py-3">
                        <button class="px-3 py-1 bg-blue-50 text-blue-600 rounded-md hover:bg-blue-100 font-medium text-xs transition-all active:scale-95">
                            Analyze
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        };

        // Initial Render
        renderTable(false);

        // Hide/Show analysis and bulk buttons based on cluster existence
        const btnAnalyze = document.getElementById('btn-analyze');
        const btnBulk = document.getElementById('btn-bulk-create-issues');
        if (clusters.length > 0) {
            // Show completed state on Analyze button
            if (btnAnalyze) {
                btnAnalyze.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    Analysis Complete
                `;
                btnAnalyze.disabled = true;
                btnAnalyze.classList.remove('bg-purple-600', 'hover:bg-purple-700');
                btnAnalyze.classList.add('bg-green-600', 'text-white');
                // Ensure it's visible
                btnAnalyze.classList.remove('hidden');
            }
            if (btnBulk) btnBulk.classList.remove('hidden');
        } else {
            if (btnAnalyze) {
                btnAnalyze.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                    </svg>
                    Run AI Analysis
                `;
                btnAnalyze.disabled = false;
                btnAnalyze.classList.remove('bg-green-600', 'text-white');
                btnAnalyze.classList.add('bg-purple-600', 'hover:bg-purple-700');
                btnAnalyze.classList.remove('hidden');
            }
            if (btnBulk) btnBulk.classList.add('hidden');
        }

        // Filter Listener
        const filterCheckbox = document.getElementById('filter-no-redmine');
        filterCheckbox.onchange = (e) => renderTable(e.target.checked);

    } catch (e) {
        console.error("Failed to load clusters", e);
    }
}

async function showClusterDetail(cluster) {
    // Show the detail view
    const view = document.getElementById('analysis-detail-view');
    view.classList.remove('hidden');
    currentCluster = cluster; // Store for Redmine modal

    // Scroll to view
    view.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Parse Summary
    const fullSummary = cluster.ai_summary || cluster.description || 'No summary available.';
    let summaryLines = fullSummary.split('\n');
    let summaryTitle = '';
    let summaryBody = '';

    if (summaryLines.length > 1) {
        summaryTitle = summaryLines[0];
        summaryBody = summaryLines.slice(1).join('<br>');
    } else {
        // Fallback logic
        let text = summaryLines[0];
        text = text.replace(/^Analysis:\s*/i, '').replace(/^\*\*\s*Analysis:?\s*\*\*\s*/i, '');

        const firstPeriodIndex = text.indexOf('. ');
        const bodyStartRegex = /\s+(The test|This test|The failure|This failure|The error|This error)\b/i;
        const match = text.match(bodyStartRegex);

        if (match && match.index < 150) {
            summaryTitle = text.substring(0, match.index);
            summaryBody = text.substring(match.index + 1);
        } else if (firstPeriodIndex > 0 && firstPeriodIndex < 150) {
            summaryTitle = text.substring(0, firstPeriodIndex + 1);
            summaryBody = text.substring(firstPeriodIndex + 1).trim();
        } else {
            if (text.length < 100) {
                summaryTitle = text;
                summaryBody = '';
            } else {
                summaryTitle = text.substring(0, 100) + '...';
                summaryBody = text;
            }
        }
    }

    // Populate Fields
    document.getElementById('detail-title').textContent = summaryTitle;
    const bodyEl = document.getElementById('detail-summary-body');
    if (summaryBody) {
        bodyEl.innerHTML = summaryBody;
        bodyEl.classList.remove('hidden');
    } else {
        bodyEl.classList.add('hidden');
    }
    document.getElementById('detail-root-cause').textContent = cluster.common_root_cause || 'Analysis pending...';
    document.getElementById('detail-solution').textContent = cluster.common_solution || 'No solution suggested yet.';
    document.getElementById('detail-stack-trace').textContent = cluster.signature || 'No stack trace available.';

    // Show/Hide Assign/Unlink buttons based on whether cluster has Redmine issue
    const assignBtn = document.getElementById('btn-assign-redmine');
    const unlinkBtn = document.getElementById('btn-unlink-redmine-detail');
    const unlinkText = document.getElementById('btn-unlink-redmine-text');

    if (cluster.redmine_issue_id) {
        // Has issue - hide assign, show unlink
        if (assignBtn) assignBtn.classList.add('hidden');
        if (unlinkBtn) {
            unlinkBtn.classList.remove('hidden');
            if (unlinkText) unlinkText.textContent = `Unlink #${cluster.redmine_issue_id}`;
        }
    } else {
        // No issue - show assign, hide unlink
        if (assignBtn) assignBtn.classList.remove('hidden');
        if (unlinkBtn) unlinkBtn.classList.add('hidden');
    }

    // Code Hint (Simple heuristic for now)
    const codeHintDiv = document.getElementById('detail-code-hint');
    if (cluster.common_root_cause && cluster.common_root_cause.includes('.java')) {
        // Extract potential file names
        const matches = cluster.common_root_cause.match(/[\w]+\.java:\d+/g);
        codeHintDiv.textContent = matches ? matches.join(', ') : 'No specific code location detected.';
    } else {
        codeHintDiv.textContent = 'No specific code context detected.';
    }

    // Fetch failures for this cluster
    const list = document.getElementById('detail-failure-list');
    const countSpan = document.getElementById('detail-failure-count');
    list.innerHTML = '<div class="p-4 text-center text-slate-400 text-xs">Loading failures...</div>';

    try {
        const res = await fetch(`${API_BASE}/analysis/cluster/${cluster.id}/failures`);
        const failures = await res.json();

        // Store failures in currentCluster for Redmine export
        if (currentCluster && currentCluster.id === cluster.id) {
            currentCluster.failures = failures;
        }

        countSpan.textContent = failures.length;
        list.innerHTML = '';

        if (failures.length === 0) {
            list.innerHTML = '<div class="p-2 text-xs text-slate-500">No specific test cases found.</div>';
            return;
        }

        failures.forEach(f => {
            const item = document.createElement('div');
            item.className = 'p-2 border-b border-slate-50 last:border-0 hover:bg-slate-50 text-xs font-mono text-slate-600 break-all';
            item.innerHTML = `
                <span class="font-semibold text-slate-800">${f.module_name}</span> 
                <span class="text-slate-400 mx-1">/</span> 
                ${f.class_name}#${f.method_name}
            `;
            list.appendChild(item);
        });

    } catch (e) {
        console.error("Failed to load cluster failures", e);
        list.innerHTML = '<div class="text-red-500 text-xs p-2">Error loading failures.</div>';
    }
}

function pollForAnalysis(runId) {
    let attempts = 0;
    const maxAttempts = 150; // 5 minutes max
    const interval = setInterval(async () => {
        attempts++;
        try {
            // Check analysis status first
            const statusRes = await fetch(`${API_BASE}/analysis/run/${runId}/status`);
            const statusData = await statusRes.json();
            const analysisStatus = statusData.analysis_status || statusData.status;
            console.log(`[pollForAnalysis] status=${analysisStatus}`);

            if (analysisStatus === 'completed') {
                clearInterval(interval);
                // Fetch final clusters
                const clustersRes = await fetch(`${API_BASE}/analysis/run/${runId}/clusters`);
                const clusters = await clustersRes.json();
                console.log(`[pollForAnalysis] final clusters=${clusters.length}`);
                loadClusters(runId);
                loadAllFailures(runId); // Reload failures to update grouping
                const btn = document.getElementById('btn-analyze');
                if (btn) {
                    btn.innerHTML = `
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                        Analysis Complete
                    `;
                    btn.classList.remove('bg-slate-400', 'cursor-not-allowed');
                    btn.classList.add('bg-green-600', 'text-white');
                }
                showNotification(`Analysis complete! Created ${clusters.length} failure cluster${clusters.length !== 1 ? 's' : ''}.`, 'success');
            } else if (analysisStatus === 'failed') {
                clearInterval(interval);
                const btn = document.getElementById('btn-analyze');
                if (btn) {
                    btn.innerHTML = `
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Analysis Failed
                    `;
                    btn.classList.remove('bg-slate-400', 'cursor-not-allowed');
                    btn.classList.add('bg-red-600', 'text-white');
                }
                showNotification('Analysis failed. Please check logs.', 'error');
            } else if (attempts >= maxAttempts) {
                clearInterval(interval);
                const btn = document.getElementById('btn-analyze');
                if (btn) {
                    btn.innerHTML = `
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Analysis Timeout
                    `;
                    btn.disabled = false;
                    btn.classList.remove('bg-slate-400', 'cursor-not-allowed');
                    btn.classList.add('bg-orange-500', 'text-white');
                }
                showNotification('Analysis timed out.', 'error');
            }
        } catch (e) {
            console.error("Polling error", e);
        }
    }, 2000);
    router.cleanup = () => clearInterval(interval);
}

// --- Settings Logic ---
let storedFullAPIKey = null; // Store the full key for toggling

// --- Failures Logic ---
// Variables moved to top of file

// --- Dashboard Logic ---
let allRunsData = [];
let currentRunsPage = 1;
const runsPerPage = 10; // Show 10 runs per page
let currentRunsQuery = '';

async function loadSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings/openai-key`);
        const data = await res.json();

        const currentKeyInput = document.getElementById('current-api-key');
        const deleteBtn = document.getElementById('btn-delete-key');
        const toggleBtn = document.getElementById('btn-toggle-key');

        if (data.is_set && data.masked_key) {
            currentKeyInput.value = data.masked_key;
            deleteBtn.disabled = false;
            if (toggleBtn) toggleBtn.disabled = false;
            storedFullAPIKey = null; // Reset to masked state
        } else {
            currentKeyInput.value = '';
            currentKeyInput.placeholder = 'No API key set';
            deleteBtn.disabled = true;
            if (toggleBtn) toggleBtn.disabled = true;
            storedFullAPIKey = null;
        }
    } catch (e) {
        console.error("Failed to load settings", e);
    }

    // Load Redmine settings
    loadRedmineSettings();
    
    // Load LLM Provider settings
    loadLLMProviderSettings();
}

// LLM Provider Functions
async function loadLLMProviderSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings/llm-provider`);
        const data = await res.json();
        
        const internalSettings = document.getElementById('internal-llm-settings');
        const urlInput = document.getElementById('internal-llm-url');
        const modelSelect = document.getElementById('internal-llm-model');
        
        // Update Segmented Control visual state
        selectProvider(data.provider === 'internal' ? 'internal' : 'openai', false);
        
        if (urlInput && data.internal_url) urlInput.value = data.internal_url;
        
        // For dropdown: add saved model as an option if it exists
        if (modelSelect && data.internal_model) {
            modelSelect.innerHTML = `
                <option value="">Select a model...</option>
                <option value="${data.internal_model}" selected>${data.internal_model}</option>
            `;
        }
        
    } catch (e) {
        console.error("Failed to load LLM provider settings", e);
    }
}

// Apple-style Segmented Control handler
function selectProvider(provider, animate = true) {
    const segOpenAI = document.getElementById('seg-openai');
    const segInternal = document.getElementById('seg-internal');
    const internalSettings = document.getElementById('internal-llm-settings');
    
    // Active styles
    const activeClass = 'bg-white text-slate-800 shadow-sm';
    const inactiveClass = 'text-slate-600 hover:text-slate-800';
    
    // Get settings sections
    const openaiSettings = document.getElementById('openai-settings');
    
    if (provider === 'internal') {
        // Update segmented control
        segInternal.className = `px-5 py-2 text-sm font-medium rounded-md transition-all duration-200 ${activeClass}`;
        segOpenAI.className = `px-5 py-2 text-sm font-medium rounded-md transition-all duration-200 ${inactiveClass}`;
        // Show internal settings, hide OpenAI
        if (internalSettings) {
            internalSettings.classList.remove('hidden');
            if (animate) internalSettings.classList.add('animate-fadeIn');
        }
        if (openaiSettings) openaiSettings.classList.add('hidden');
    } else {
        // Update segmented control
        segOpenAI.className = `px-5 py-2 text-sm font-medium rounded-md transition-all duration-200 ${activeClass}`;
        segInternal.className = `px-5 py-2 text-sm font-medium rounded-md transition-all duration-200 ${inactiveClass}`;
        // Hide internal settings, show OpenAI
        if (internalSettings) internalSettings.classList.add('hidden');
        if (openaiSettings) openaiSettings.classList.remove('hidden');
    }
}

// Legacy function for backward compatibility
function toggleLLMProvider(provider) {
    selectProvider(provider);
}

async function refreshModelList() {
    const urlInput = document.getElementById('internal-llm-url');
    const modelSelect = document.getElementById('internal-llm-model');
    const refreshBtn = document.getElementById('btn-refresh-models');
    
    const url = urlInput?.value.trim();
    
    if (!url) {
        alert('Please enter the Server URL first');
        return;
    }
    
    // Store current selection
    const currentModel = modelSelect?.value;
    
    // Show loading state
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = `
            <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            Loading...
        `;
    }
    
    try {
        const res = await fetch(`${API_BASE}/settings/list-models?url=${encodeURIComponent(url)}`);
        const data = await res.json();
        
        // Clear existing options
        modelSelect.innerHTML = '<option value="">-- Select Model --</option>';
        
        if (data.models && data.models.length > 0) {
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                if (model === currentModel) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
            
            // Show success indicator
            if (refreshBtn) {
                refreshBtn.innerHTML = `
                    <svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    ${data.models.length} found
                `;
                setTimeout(() => resetRefreshButton(), 2000);
            }
        } else {
            // No models found or error
            const option = document.createElement('option');
            option.value = "";
            option.textContent = data.error || "No models found";
            option.disabled = true;
            modelSelect.appendChild(option);
            
            if (refreshBtn) {
                refreshBtn.innerHTML = `
                    <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                `;
                setTimeout(() => resetRefreshButton(), 2000);
            }
        }
    } catch (e) {
        console.error("Failed to refresh model list", e);
        modelSelect.innerHTML = '<option value="">-- Error loading models --</option>';
        if (refreshBtn) {
            refreshBtn.innerHTML = `
                <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            `;
            setTimeout(() => resetRefreshButton(), 2000);
        }
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

function resetRefreshButton() {
    const refreshBtn = document.getElementById('btn-refresh-models');
    if (refreshBtn) {
        refreshBtn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15">
                </path>
            </svg>
        `;
    }
}

async function saveLLMProvider() {
    const segInternal = document.getElementById('seg-internal');
    const urlInput = document.getElementById('internal-llm-url');
    const modelSelect = document.getElementById('internal-llm-model');
    const statusSpan = document.getElementById('llm-provider-status');
    const saveBtn = document.getElementById('btn-save-llm-provider');
    
    // Check if internal is selected by checking the button class
    const isInternal = segInternal?.className.includes('bg-white');
    const provider = isInternal ? 'internal' : 'openai';
    const internal_url = urlInput?.value.trim() || null;
    const internal_model = modelSelect?.value.trim() || 'llama3.1:8b';
    
    if (provider === 'internal' && !internal_url) {
        alert('Please enter the internal LLM server URL');
        return;
    }
    
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    
    try {
        const res = await fetch(`${API_BASE}/settings/llm-provider`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, internal_url, internal_model })
        });
        
        if (res.ok) {
            statusSpan.innerHTML = `
                <span class="inline-flex items-center gap-1 text-green-600">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    Saved
                </span>
            `;
            setTimeout(() => { statusSpan.innerHTML = ''; }, 3000);
        } else {
            const error = await res.json();
            alert(`Failed to save: ${error.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error("Failed to save LLM provider", e);
        alert('Error saving LLM provider settings');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Settings';
    }
}

async function testLLMConnection() {
    const testBtn = document.getElementById('btn-test-llm');
    const testIcon = document.getElementById('test-icon');
    const testText = document.getElementById('test-text');
    const statusSpan = document.getElementById('llm-provider-status');
    const segInternal = document.getElementById('seg-internal');
    const urlInput = document.getElementById('internal-llm-url');
    const modelSelect = document.getElementById('internal-llm-model');
    
    // Show loading state with spinner
    testBtn.disabled = true;
    if (testIcon) testIcon.innerHTML = `
        <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
    `;
    if (testText) testText.textContent = 'Testing...';
    statusSpan.innerHTML = '';
    
    // Check if internal is selected by checking the button class
    const isInternal = segInternal?.className.includes('bg-white');
    const body = {};
    
    if (isInternal) {
        const url = urlInput?.value.trim();
        const model = modelSelect?.value;
        
        if (!url) {
            statusSpan.innerHTML = `
                <span class="inline-flex items-center gap-1 text-red-500">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    Enter Server URL first
                </span>
            `;
            resetTestButton();
            return;
        }
        
        body.url = url;
        if (model) body.model = model;
    }
    
    try {
        const res = await fetch(`${API_BASE}/settings/test-llm-connection`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        
        if (data.success) {
            if (data.model_valid === false) {
                // Connection OK but model not found - yellow warning
                statusSpan.innerHTML = `
                    <span class="inline-flex items-center gap-1 text-yellow-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                        ${data.message}
                    </span>
                `;
            } else {
                // Full success - green checkmark
                statusSpan.innerHTML = `
                    <span class="inline-flex items-center gap-1 text-green-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                        ${data.message}
                    </span>
                `;
            }
        } else {
            // Failure - red X
            statusSpan.innerHTML = `
                <span class="inline-flex items-center gap-1 text-red-500">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    ${data.message}
                </span>
            `;
        }
    } catch (e) {
        console.error("Test connection failed", e);
        statusSpan.innerHTML = `
            <span class="inline-flex items-center gap-1 text-red-500">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                Connection failed
            </span>
        `;
    } finally {
        resetTestButton();
    }
}

function resetTestButton() {
    const testBtn = document.getElementById('btn-test-llm');
    const testIcon = document.getElementById('test-icon');
    const testText = document.getElementById('test-text');
    
    if (testBtn) testBtn.disabled = false;
    if (testIcon) testIcon.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
        </svg>
    `;
    if (testText) testText.textContent = 'Test Connection';
}

async function toggleAPIKeyVisibility() {
    const currentKeyInput = document.getElementById('current-api-key');
    const toggleBtn = document.getElementById('btn-toggle-key');

    if (storedFullAPIKey) {
        // Currently showing full key, switch to masked
        loadSettings(); // Reload to get masked version
        if (toggleBtn) toggleBtn.textContent = 'Show';
    } else {
        // Currently showing masked, fetch and show full key
        if (toggleBtn) {
            toggleBtn.disabled = true;
            toggleBtn.textContent = 'Loading...';
        }

        try {
            const res = await fetch(`${API_BASE}/settings/openai-key?show_full=true`);
            const data = await res.json();

            if (data.full_key) {
                storedFullAPIKey = data.full_key;
                currentKeyInput.value = storedFullAPIKey;
                if (toggleBtn) toggleBtn.textContent = 'Hide';
            } else {
                alert('Failed to retrieve full API key');
                if (toggleBtn) toggleBtn.textContent = 'Show';
            }
        } catch (e) {
            console.error("Failed to fetch full API key", e);
            alert('Error fetching full API key');
            if (toggleBtn) toggleBtn.textContent = 'Show';
        } finally {
            if (toggleBtn) toggleBtn.disabled = false;
        }
    }
}

async function saveAPIKey() {
    const newKeyInput = document.getElementById('new-api-key');
    const apiKey = newKeyInput.value.trim();

    if (!apiKey) {
        alert('Please enter an API key');
        return;
    }

    const saveBtn = document.getElementById('btn-save-key');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const res = await fetch(`${API_BASE}/settings/openai-key`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey })
        });

        if (res.ok) {
            alert('API key saved successfully');
            newKeyInput.value = '';
            // Remove from localStorage since we're using server-side storage now
            localStorage.removeItem('openai_api_key');
            loadSettings(); // Reload to show masked key
        } else {
            const error = await res.json();
            alert(`Failed to save API key: ${error.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error("Failed to save API key", e);
        alert('Error saving API key');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

async function deleteAPIKey(event) {
    if (event) event.preventDefault();

    if (!confirm('Are you sure you want to delete the stored API key?')) {
        return;
    }

    const deleteBtn = document.getElementById('btn-delete-key');
    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.textContent = 'Deleting...';
    }

    try {
        const res = await fetch(`${API_BASE}/settings/openai-key`, {
            method: 'DELETE'
        });

        if (res.ok) {
            alert('API key deleted successfully');
            loadSettings(); // Reload to clear display
        } else {
            alert('Failed to delete API key');
        }
    } catch (e) {
        console.error("Failed to delete API key", e);
        alert('Error deleting API key');
    } finally {
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = 'Delete';
        }
    }
}

async function resetSystem() {
    try {
        const res = await fetch(`${API_BASE}/system/reset`, { method: 'POST' });
        if (res.ok) {
            alert('System reset successfully.');
            router.navigate('dashboard');
            loadDashboard();
        } else {
            alert('Failed to reset system.');
        }
    } catch (e) {
        console.error('Reset failed', e);
        alert('Error resetting system.');
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    // Reset Data button handling
    const resetBtn = document.getElementById('btn-reset');
    const resetModal = document.getElementById('reset-modal');
    const resetCancel = document.getElementById('reset-modal-cancel');
    const resetConfirm = document.getElementById('reset-modal-confirm');
    const resetMessage = document.getElementById('reset-modal-message');

    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            // Prepare and show modal
            resetMessage.textContent = 'Are you sure you want to delete ALL data? This cannot be undone.';
            resetModal.classList.remove('hidden');
        });
    }
    if (resetCancel) {
        resetCancel.addEventListener('click', () => resetModal.classList.add('hidden'));
    }
    if (resetConfirm) {
        resetConfirm.addEventListener('click', () => {
            resetModal.classList.add('hidden');
            resetSystem();
        });
    }

    loadRedmineSettings(); // Load Redmine settings globally
    loadRedmineSettings(); // Load Redmine settings globally

    // Check URL params for routing
    const urlParams = new URLSearchParams(window.location.search);
    const page = urlParams.get('page');
    const id = urlParams.get('id');

    if (page === 'run-details' && id) {
        router.navigate('run-details', { id: id });
    } else {
        router.navigate('dashboard');
    }
});

// --- Redmine Integration Functions ---
let currentCluster = null;
let currentRunDetails = null;
let redmineBaseUrl = null;

async function loadRedmineSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings/redmine`);
        const data = await res.json();

        const urlInput = document.getElementById('current-redmine-url');
        const keyInput = document.getElementById('current-redmine-key');

        if (data.is_set && data.url) {
            redmineBaseUrl = data.url; // Store for link generation
            if (urlInput) urlInput.value = data.url;
            if (keyInput) keyInput.value = data.masked_key || '';
        } else {
            if (urlInput) urlInput.value = '';
            if (keyInput) keyInput.value = '';
        }
    } catch (e) {
        console.error("Failed to load Redmine settings", e);
    }
}

async function saveRedmineSettings() {
    const url = document.getElementById('new-redmine-url').value.trim();
    const key = document.getElementById('new-redmine-key').value.trim();

    if (!url || !key) {
        alert('Please enter both URL and API key');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/settings/redmine`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, api_key: key })
        });

        if (res.ok) {
            alert('Redmine settings saved successfully');
            document.getElementById('new-redmine-url').value = '';
            document.getElementById('new-redmine-key').value = '';
            loadRedmineSettings();
        } else {
            alert('Failed to save settings');
        }
    } catch (e) {
        console.error("Error saving Redmine settings", e);
        alert('Error saving settings');
    }
}

async function testRedmineConnection() {
    try {
        const res = await fetch(`${API_BASE}/integrations/redmine/test`, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            alert('✅ Connection successful!');
        } else {
            alert('❌ Connection failed. Check your settings.');
        }
    } catch (e) {
        console.error("Test connection error", e);
        alert('❌ Connection failed. Check your settings.');
    }
}

function openRedmineModal() {
    const modal = document.getElementById('redmine-modal');
    if (!modal) return;

    if (!currentCluster) {
        console.error("No cluster selected");
        alert("Error: No cluster selected. Please try refreshing the page.");
        return;
    }

    modal.classList.remove('hidden');

    // Show/Hide tabs based on whether issue is already linked
    const createTab = document.getElementById('redmine-tab-create');
    if (createTab) {
        if (currentCluster.redmine_issue_id) {
            // Already linked - hide create tab
            createTab.classList.add('hidden');
        } else {
            // Not linked - show create tab
            createTab.classList.remove('hidden');
        }
    }

    // Show/Hide Unlink Button
    const unlinkBtn = document.getElementById('btn-unlink-issue');
    if (unlinkBtn) {
        if (currentCluster.redmine_issue_id) {
            unlinkBtn.classList.remove('hidden');
            unlinkBtn.textContent = `Unlink Issue #${currentCluster.redmine_issue_id}`;
        } else {
            unlinkBtn.classList.add('hidden');
        }
    }

    switchRedmineTab('link');
    loadRedmineProjects();
}

function closeRedmineModal() {
    const modal = document.getElementById('redmine-modal');
    if (modal) modal.classList.add('hidden');
}

async function unlinkRedmineIssue() {
    if (!currentCluster || !currentCluster.redmine_issue_id) return;

    const modal = document.getElementById('unlink-modal');
    const message = document.getElementById('unlink-modal-message');
    const confirmBtn = document.getElementById('unlink-modal-confirm');
    const cancelBtn = document.getElementById('unlink-modal-cancel');

    if (modal && message && confirmBtn) {
        message.textContent = `Are you sure you want to unlink Issue #${currentCluster.redmine_issue_id}?`;
        modal.classList.remove('hidden');

        // Handle Confirm
        const handleConfirm = async () => {
            confirmBtn.removeEventListener('click', handleConfirm);
            modal.classList.add('hidden');

            try {
                const res = await fetch(`${API_BASE}/integrations/redmine/unlink`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cluster_id: currentCluster.id })
                });

                if (res.ok) {
                    // Update current cluster state
                    currentCluster.redmine_issue_id = null;

                    // Update button visibility immediately
                    const assignBtn = document.getElementById('btn-assign-redmine');
                    const unlinkBtnDetail = document.getElementById('btn-unlink-redmine-detail');
                    if (assignBtn) assignBtn.classList.remove('hidden');
                    if (unlinkBtnDetail) unlinkBtnDetail.classList.add('hidden');

                    closeRedmineModal();
                    // Reload clusters to refresh the table
                    const runId = router.currentParams.id;
                    if (runId) loadClusters(runId);
                } else {
                    alert('Failed to unlink issue');
                }
            } catch (e) {
                console.error("Unlink error", e);
                alert('Error unlinking issue');
            }
        };

        // Handle Cancel
        const handleCancel = () => {
            cancelBtn.removeEventListener('click', handleCancel);
            modal.classList.add('hidden');
        };

        // Remove old listeners to prevent duplicates (simple approach)
        const newConfirm = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirm, confirmBtn);
        newConfirm.addEventListener('click', handleConfirm);

        const newCancel = cancelBtn.cloneNode(true);
        cancelBtn.parentNode.replaceChild(newCancel, cancelBtn);
        newCancel.addEventListener('click', handleCancel);
    }
}

function switchRedmineTab(tab) {
    // Update tabs
    document.querySelectorAll('.redmine-tab').forEach(t => {
        t.classList.remove('border-blue-500', 'text-blue-600');
        t.classList.add('border-transparent', 'text-slate-500');
    });
    document.getElementById(`redmine-tab-${tab}`).classList.add('border-blue-500', 'text-blue-600');
    document.getElementById(`redmine-tab-${tab}`).classList.remove('border-transparent', 'text-slate-500');

    // Update content
    document.querySelectorAll('.redmine-content').forEach(c => c.classList.add('hidden'));
    document.getElementById(`redmine-content-${tab}`).classList.remove('hidden');

    // Auto-populate if switching to create tab
    if (tab === 'create') {
        // Load users if project is selected, otherwise load projects first then users
        const projectSelect = document.getElementById('redmine-project');
        if (projectSelect && projectSelect.value) {
            loadRedmineUsers(projectSelect.value);
        }

        if (currentCluster) {
            const subjectInput = document.getElementById('redmine-subject');
            const descInput = document.getElementById('redmine-description');

            if (subjectInput && !subjectInput.value) {
                let suiteTag = 'GMS';
                if (currentRunDetails && currentRunDetails.test_suite_name) {
                    // Format suite name: "Cts" -> "CTS", "Gts" -> "GTS", etc.
                    suiteTag = currentRunDetails.test_suite_name.toUpperCase();
                    // Handle common cases to ensure they look good
                    if (suiteTag.includes('CTS')) suiteTag = 'CTS';
                    else if (suiteTag.includes('GTS')) suiteTag = 'GTS';
                    else if (suiteTag.includes('VTS')) suiteTag = 'VTS';
                    else if (suiteTag.includes('STS')) suiteTag = 'STS';
                    else suiteTag = currentRunDetails.test_suite_name; // Fallback to original if not standard
                }
                const summary = currentCluster.ai_summary || currentCluster.description;
                const title = getClusterTitle(summary);
                subjectInput.value = `[ ${suiteTag} ] ${title}`;
            }

            if (descInput && !descInput.value) {
                const desc = `h2. Failure Analysis Report

h3. Cluster Summary

|_. Property|_. Value|
|Cluster ID|#${currentCluster.id}|
|Severity|${currentCluster.severity || 'Unknown'}|
|Category|${currentCluster.category || 'Uncategorized'}|
|Confidence|${currentCluster.confidence_score}/5|
|Impact|${currentCluster.failures_count || '?'} failures|

h3. System Information

|_. Property|_. Value|
|Fingerprint|@${currentRunDetails?.device_fingerprint || 'N/A'}@|
|Build ID|@${currentRunDetails?.build_id || 'N/A'}@|
|Product|${currentRunDetails?.build_product || 'N/A'}|
|Model|${currentRunDetails?.build_model || 'N/A'}|
|Android Version|${currentRunDetails?.android_version || 'N/A'}|
|Security Patch|${currentRunDetails?.security_patch || 'N/A'}|
|Test Suite|${currentRunDetails?.test_suite_name || 'N/A'}|

h3. AI Analysis

*Summary:*
${currentCluster.ai_summary || 'N/A'}

*Root Cause:*
<pre>
${currentCluster.common_root_cause || 'N/A'}
</pre>

*Suggested Solution:*
${currentCluster.common_solution || 'N/A'}

h3. Technical Details

*Stack Trace Signature:*
<pre><code>
${currentCluster.signature || 'N/A'}
</code></pre>

h3. Affected Test Cases

${currentCluster.failures && currentCluster.failures.length > 0 ? currentCluster.failures.slice(0, 5).map((f, idx) => `
h4. Failure ${idx + 1}

* *Module:* @${f.module_name}@
* *Test Case:* @${f.class_name}#${f.method_name}@
* *Stack Trace:*

<pre><code class="java">
${f.stack_trace ? f.stack_trace.substring(0, 800) + (f.stack_trace.length > 800 ? '\n...\n(truncated)' : '') : 'N/A'}
</code></pre>
`).join('\n') : 'No failure details available.'}
${currentCluster.failures && currentCluster.failures.length > 5 ? `\np(. _... and ${currentCluster.failures.length - 5} more failures not shown_` : ''}
`;
                descInput.value = desc;
            }
        }
    }
}

async function loadRedmineUsers(projectId) {
    const assigneeSelect = document.getElementById('redmine-assignee');
    if (!assigneeSelect) return;

    assigneeSelect.innerHTML = '<option value="">Loading...</option>';
    assigneeSelect.disabled = true;

    try {
        let url = `${API_BASE}/integrations/redmine/users`;
        if (projectId) {
            url += `?project_id=${projectId}`;
        }

        const res = await fetch(url);
        if (res.ok) {
            const users = await res.json();
            assigneeSelect.innerHTML = '<option value="">Unassigned</option>';
            users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = user.name || `${user.firstname} ${user.lastname}`;
                assigneeSelect.appendChild(option);
            });
        } else {
            console.error("Failed to fetch users");
            assigneeSelect.innerHTML = '<option value="">Failed to load users</option>';
        }
    } catch (e) {
        console.error("Error loading users", e);
        assigneeSelect.innerHTML = '<option value="">Error loading users</option>';
    } finally {
        assigneeSelect.disabled = false;
    }
}

async function loadRedmineProjects() {
    try {
        const res = await fetch(`${API_BASE}/integrations/redmine/projects`);
        const projects = await res.json();

        const select = document.getElementById('redmine-project');
        if (!select) return;

        select.innerHTML = projects.length > 0
            ? projects.map(p => `<option value="${p.id}">${p.name}</option>`).join('')
            : '<option value="">No projects found</option>';
    } catch (e) {
        console.error("Failed to load projects", e);
        alert("Failed to load Redmine projects. Please check your connection and settings.");
    }
}

async function searchRedmineIssues() {
    const query = document.getElementById('redmine-search-query').value.trim();
    const resultsDiv = document.getElementById('redmine-search-results');

    if (!query) {
        resultsDiv.innerHTML = '<div class="p-4 text-center text-slate-500 text-sm">Enter keywords and click Search</div>';
        return;
    }

    resultsDiv.innerHTML = '<div class="p-4 text-center text-slate-500 text-sm">Searching...</div>';

    try {
        const res = await fetch(`${API_BASE}/integrations/redmine/search?query=${encodeURIComponent(query)}`);
        const issues = await res.json();

        if (issues.length === 0) {
            resultsDiv.innerHTML = '<div class="p-4 text-center text-slate-500 text-sm">No issues found</div>';
            return;
        }

        resultsDiv.innerHTML = issues.map(issue => `
            <div class="p-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer" onclick="linkToRedmineIssue(${issue.id})">
                <div class="font-medium text-slate-800">#${issue.id}: ${issue.subject}</div>
                <div class="text-xs text-slate-500 mt-1">Status: ${issue.status.name} | Priority: ${issue.priority.name}</div>
            </div>
        `).join('');
    } catch (e) {
        console.error("Search error", e);
        resultsDiv.innerHTML = '<div class="p-4 text-center text-red-500 text-sm">Search failed</div>';
    }
}

async function linkToRedmineIssue(issueId) {
    if (!currentCluster) {
        alert('No cluster selected');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/integrations/redmine/link`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ issue_id: issueId, cluster_id: currentCluster.id })
        });

        if (res.ok) {
            const data = await res.json();

            // Update current cluster state
            currentCluster.redmine_issue_id = issueId;

            // Update button visibility immediately
            const assignBtn = document.getElementById('btn-assign-redmine');
            const unlinkBtnDetail = document.getElementById('btn-unlink-redmine-detail');
            const unlinkText = document.getElementById('btn-unlink-redmine-text');
            if (assignBtn) assignBtn.classList.add('hidden');
            if (unlinkBtnDetail) {
                unlinkBtnDetail.classList.remove('hidden');
                if (unlinkText) unlinkText.textContent = `Unlink #${issueId}`;
            }

            closeRedmineModal();
            // Reload clusters to show updated Redmine link
            const runId = router.currentParams.id;
            if (runId) loadClusters(runId);
        } else {
            alert('Failed to link issue');
        }
    } catch (e) {
        console.error("Link error", e);
        alert('Error linking issue');
    }
}

async function createRedmineIssue(event) {
    event.preventDefault(); // Prevent default button behavior

    const projectId = document.getElementById('redmine-project').value;
    const subject = document.getElementById('redmine-subject').value;
    const description = document.getElementById('redmine-description').value;
    const createChildren = document.getElementById('redmine-create-children').checked;
    const assigneeId = document.getElementById('redmine-assignee').value;

    if (!projectId || !subject || !description) {
        alert('Please fill in all required fields');
        return;
    }

    if (!currentCluster) {
        alert('No cluster selected');
        return;
    }

    const btn = event.target; // Assuming button triggered this
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Creating...';
    btn.classList.add('opacity-50', 'cursor-not-allowed');

    try {
        const res = await fetch(`${API_BASE}/integrations/redmine/issue`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cluster_id: currentCluster.id,
                project_id: parseInt(projectId),
                subject: subject,
                description: description,
                create_children: createChildren,
                assigned_to_id: assigneeId ? parseInt(assigneeId) : null
            })
        });

        if (res.ok) {
            const issue = await res.json();

            // Update current cluster state
            currentCluster.redmine_issue_id = issue.id;

            // Update button visibility immediately
            const assignBtn = document.getElementById('btn-assign-redmine');
            const unlinkBtnDetail = document.getElementById('btn-unlink-redmine-detail');
            const unlinkText = document.getElementById('btn-unlink-redmine-text');
            if (assignBtn) assignBtn.classList.add('hidden');
            if (unlinkBtnDetail) {
                unlinkBtnDetail.classList.remove('hidden');
                if (unlinkText) unlinkText.textContent = `Unlink #${issue.id}`;
            }

            closeRedmineModal();
            // Reload clusters to show updated Redmine link
            const runId = router.currentParams.id;
            if (runId) loadClusters(runId);
        } else {
            const errorData = await res.json();
            alert(`Failed to create issue: ${errorData.detail || 'Unknown error'}`);
            // Re-enable button on error
            if (btn) {
                btn.disabled = false;
                btn.textContent = originalText;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }
    } catch (e) {
        console.error("Create issue error", e);
        alert('Error creating issue');
        if (btn) {
            btn.disabled = false;
            btn.textContent = originalText;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }
}


async function openBulkCreateModal() {
    const modal = document.getElementById('bulk-create-modal');
    if (!modal) return;

    modal.classList.remove('hidden');

    // Load projects
    await loadRedmineProjects();
    const projectSelect = document.getElementById('bulk-create-project');
    const redmineSelect = document.getElementById('redmine-project');
    if (projectSelect && redmineSelect) {
        projectSelect.innerHTML = redmineSelect.innerHTML;
    }
}

function closeBulkCreateModal() {
    const modal = document.getElementById('bulk-create-modal');
    if (modal) modal.classList.add('hidden');

    // Reset status
    const status = document.getElementById('bulk-create-status');
    if (status) {
        status.classList.add('hidden');
        status.textContent = '';
    }
}

async function executeBulkCreate() {
    const projectId = parseInt(document.getElementById('bulk-create-project').value);
    const createChildren = document.getElementById('bulk-create-children').checked;
    const button = document.getElementById('btn-execute-bulk');
    const status = document.getElementById('bulk-create-status');

    if (!projectId) {
        alert('Please select a project');
        return;
    }

    if (!router.currentParams || !router.currentParams.id) {
        alert('No test run selected');
        return;
    }

    // Disable button and show progress
    button.disabled = true;
    button.textContent = 'Creating...';
    status.classList.remove('hidden');
    status.className = 'mt-2 text-sm text-blue-600';
    status.textContent = 'Creating issues, please wait...';

    try {
        const res = await fetch(`${API_BASE}/integrations/redmine/bulk-create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                run_id: parseInt(router.currentParams.id),
                project_id: projectId,
                create_children: createChildren
            })
        });

        const result = await res.json();

        if (res.ok) {
            status.className = 'mt-2 text-sm text-green-600';
            status.textContent = `✅ ${result.message}`;

            // Reset button state
            button.disabled = false;
            button.textContent = 'Create Issues';

            // Reload clusters after a delay
            setTimeout(() => {
                closeBulkCreateModal();
                const runId = router.currentParams.id;
                if (runId) loadClusters(runId);
            }, 2000);
        } else {
            status.className = 'mt-2 text-sm text-red-600';
            status.textContent = `❌ Failed: ${result.message || 'Unknown error'}`;
            button.disabled = false;
            button.textContent = 'Create Issues';
        }
    } catch (e) {
        console.error("Bulk create error", e);
        status.className = 'mt-2 text-sm text-red-600';
        status.textContent = `❌ Error: ${e.message}`;
        button.disabled = false;
        button.textContent = 'Create Issues';
    }
}

// --- Export Report ---
function exportRunReport() {
    if (!currentRunDetails) {
        alert('Run details not loaded.');
        return;
    }

    const run = currentRunDetails;
    const clusters = allClustersData || [];
    const failures = allFailuresData || [];

    // Calculate Stats
    const total = run.total_tests || 0;
    const passed = run.passed_tests || 0;
    const failed = run.failed_tests || 0;
    const executed = passed + failed;

    let passRate = '0.00';
    if (executed > 0) {
        const rate = (passed / executed) * 100;
        const twoDecimals = rate.toFixed(2);
        // Handle 99.99% edge case (if failed > 0 but rounds to 100.00)
        passRate = (twoDecimals === "100.00" && failed > 0) ? rate.toFixed(4) : twoDecimals;
    }

    // AI Stats
    const aiSeverity = document.getElementById('kpi-severity')?.textContent || '-';
    const aiTopCategory = document.getElementById('kpi-top-category')?.textContent || '-';

    const html = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Run Report - #${run.id}</title>
            <style>
                body { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; color: #1e293b; line-height: 1.5; padding: 40px; max-width: 1000px; margin: 0 auto; }
                h1 { font-size: 24px; font-weight: bold; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
                h2 { font-size: 18px; font-weight: 600; margin-top: 30px; margin-bottom: 15px; color: #334155; }
                .header-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px; }
                .stat-box { background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; }
                .stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
                .stat-value { font-size: 20px; font-weight: bold; color: #0f172a; }
                .cluster-item { margin-bottom: 30px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px; page-break-inside: avoid; background: #fff; }
                .cluster-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; }
                .cluster-title { font-weight: 700; color: #0f172a; font-size: 16px; line-height: 1.4; }
                .cluster-meta { font-size: 12px; color: #64748b; margin-top: 4px; }
                .cluster-summary { font-size: 14px; color: #334155; background: #f8fafc; padding: 15px; border-radius: 6px; margin-bottom: 15px; border-left: 4px solid #3b82f6; }
                .tag { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; margin-right: 6px; vertical-align: middle; }
                .tag-high { background: #fee2e2; color: #991b1b; }
                .tag-medium { background: #fef3c7; color: #92400e; }
                .tag-low { background: #dcfce7; color: #166534; }
                .failures-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; }
                .failures-table th { text-align: left; padding: 8px; background: #f1f5f9; color: #475569; font-weight: 600; border-bottom: 1px solid #e2e8f0; }
                .failures-table td { padding: 8px; border-bottom: 1px solid #e2e8f0; color: #334155; vertical-align: top; }
                .failures-table tr:last-child td { border-bottom: none; }
                .module-name { font-weight: 600; color: #475569; }
                .test-case { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
                .print-footer { margin-top: 50px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 20px; }
                @media print {
                    body { padding: 0; }
                    .no-print { display: none; }
                    .cluster-item { break-inside: avoid; }
                }
            </style>
        </head>
        <body>
            <h1>Test Run Report #${run.id}</h1>
            
            <div class="header-grid">
                <div>
                    <div class="stat-box">
                        <div class="stat-label">Test Suite</div>
                        <div class="stat-value">${run.test_suite_name || 'Unknown'}</div>
                    </div>
                </div>
                <div>
                    <div class="stat-box">
                        <div class="stat-label">Device</div>
                        <div class="stat-value">${run.build_model || 'Unknown'}</div>
                        <div style="font-size: 12px; color: #64748b; margin-top: 2px;">${run.device_fingerprint || ''}</div>
                    </div>
                </div>
            </div>

            <div class="header-grid" style="grid-template-columns: repeat(4, 1fr);">
                <div class="stat-box">
                    <div class="stat-label">Pass Rate</div>
                    <div class="stat-value" style="color: ${passRate > 90 ? '#16a34a' : '#ca8a04'}">${passRate}%</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Failures</div>
                    <div class="stat-value" style="color: #dc2626">${failed}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">AI Severity</div>
                    <div class="stat-value">${aiSeverity}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Top Category</div>
                    <div class="stat-value" style="font-size: 16px;">${aiTopCategory}</div>
                </div>
            </div>

            <h2>System Information</h2>
            <div class="header-grid" style="grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 30px;">
                <div class="stat-box">
                    <div class="stat-label">Build ID</div>
                    <div class="stat-value" style="font-size: 14px;">${run.build_id || '-'}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Android Version</div>
                    <div class="stat-value" style="font-size: 14px;">${run.android_version || '-'}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Security Patch</div>
                    <div class="stat-value" style="font-size: 14px;">${run.security_patch || '-'}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Suite Version</div>
                    <div class="stat-value" style="font-size: 14px;">${run.suite_version || '-'}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Host Name</div>
                    <div class="stat-value" style="font-size: 14px;">${run.host_name || '-'}</div>
                </div>
                 <div class="stat-box">
                    <div class="stat-label">Total Modules</div>
                    <div class="stat-value" style="font-size: 14px;">${run.total_modules || 0}</div>
                </div>
            </div>

            <h2>Test Statistics</h2>
             <div class="header-grid" style="grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px;">
                <div class="stat-box">
                    <div class="stat-label">Total Tests</div>
                    <div class="stat-value" style="font-size: 16px;">${run.total_tests?.toLocaleString() || 0}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Passed</div>
                    <div class="stat-value" style="font-size: 16px; color: #16a34a;">${run.passed_tests?.toLocaleString() || 0}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Failed</div>
                    <div class="stat-value" style="font-size: 16px; color: #dc2626;">${run.failed_tests?.toLocaleString() || 0}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Ignored</div>
                    <div class="stat-value" style="font-size: 16px; color: #94a3b8;">${run.ignored_tests?.toLocaleString() || 0}</div>
                </div>
            </div>

            <h2>AI Failure Analysis</h2>
            ${clusters.length > 0 ? clusters.map(c => {
        // Get failures for this cluster
        const clusterFailures = failures.filter(f => f.failure_analysis && f.failure_analysis.cluster_id === c.id);

        // Parse Summary Title (First line)
        // Parse Summary Title (First line)
        const fullSummary = c.ai_summary || 'No summary available.';
        // Split by actual newline character
        let summaryLines = fullSummary.split('\n');

        let summaryTitle = '';
        let summaryBody = '';

        if (summaryLines.length > 1) {
            summaryTitle = summaryLines[0];
            summaryBody = summaryLines.slice(1).join('<br>');
        } else {
            // Fallback for old data or missing newline
            let text = summaryLines[0];
            // Remove common prefixes
            text = text.replace(/^Analysis:\s*/i, '').replace(/^\*\*\s*Analysis:?\s*\*\*\s*/i, '');

            // Try to split by first sentence (period + space)
            const firstPeriodIndex = text.indexOf('. ');

            // Heuristic: Check for common "body start" phrases if no period or period is too far
            // e.g. "Title Text The test..." -> Split before "The test"
            const bodyStartRegex = /\s+(The test|This test|The failure|This failure|The error|This error)\b/i;
            const match = text.match(bodyStartRegex);

            if (match && match.index < 150) {
                // Found a likely body start, split there
                summaryTitle = text.substring(0, match.index);
                summaryBody = text.substring(match.index + 1); // +1 to skip the space
            } else if (firstPeriodIndex > 0 && firstPeriodIndex < 150) {
                summaryTitle = text.substring(0, firstPeriodIndex + 1);
                summaryBody = text.substring(firstPeriodIndex + 1).trim();
            } else {
                // No clear sentence break, just use text as title if short, or truncate
                if (text.length < 100) {
                    summaryTitle = text;
                    summaryBody = '';
                } else {
                    summaryTitle = text.substring(0, 100) + '...';
                    summaryBody = text;
                }
            }
        }

        return `
                <div class="cluster-item">
                    <div class="cluster-header">
                        <div>
                            <div class="cluster-title">
                                <span class="tag tag-${(c.severity || 'low').toLowerCase()}">${c.severity || 'Low'}</span>
                                ${summaryTitle}
                            </div>
                            <div class="cluster-meta">${c.failures_count} failures • ${c.module_names?.length || 0} modules • ${c.category || 'Uncategorized'}</div>
                        </div>
                    </div>
                    
                    ${summaryBody ? `<div class="cluster-summary">${summaryBody}</div>` : ''}
                    
                    ${c.recommendation ? `
                    <div style="margin-bottom: 15px; font-size: 13px; color: #475569; background: #fffbeb; padding: 10px; border-radius: 6px; border: 1px solid #fcd34d;">
                        <strong>Recommendation:</strong> ${c.recommendation}
                    </div>` : ''}

                    <table class="failures-table">
                        <thead>
                            <tr>
                                <th style="width: 30%">Module</th>
                                <th style="width: 70%">Test Case</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${clusterFailures.map(f => `
                                <tr>
                                    <td class="module-name">${f.module_name}</td>
                                    <td class="test-case">${f.class_name}#${f.method_name}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `}).join('') : '<p style="color: #64748b; font-style: italic;">No failure clusters identified.</p>'}

            <div class="print-footer">
                Generated by GMS Analysis App • ${new Date().toLocaleString()}
            </div>

            <script>
                window.onload = function() { window.print(); }
            </script>
        </body>
        </html>
    `;

    const win = window.open('', '_blank');
    win.document.write(html);
    win.document.close();
}

function renderSparkline(containerId, data, color) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const width = 96;
    const height = 40;
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    
    const points = data.map((val, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((val - min) / range) * (height * 0.8) - (height * 0.1);
        return `${x},${y}`;
    }).join(' ');
 
    container.innerHTML = `
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="overflow: visible;">
            <defs>
                <linearGradient id="grad-${containerId}" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:${color};stop-opacity:0.2" />
                    <stop offset="100%" style="stop-color:${color};stop-opacity:0" />
                </linearGradient>
            </defs>
            <path d="${points.split(' ').map((p, i) => (i === 0 ? 'M' : 'L') + p).join(' ')}" 
                  fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M 0,${height} L ${points.split(' ').map(p => 'L' + p).join(' ')} L ${width},${height} L 0,${height} Z" 
                  fill="url(#grad-${containerId})" stroke="none" />
        </svg>
    `;
}
