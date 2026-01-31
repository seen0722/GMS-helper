const API_BASE = '/api';

let allClustersData = [];
let currentProductFilter = null;
let allModulesData = [];
let currentViewMode = 'cluster'; // Corrected from user's diff
const MAX_VISIBLE_PAGES = 5; // Added from user's diff
let allRunsData = [];
let allSubmissionsData = []; // New Global
let currentRunsPage = 1;
let currentSubmissionsPage = 1; // New Global
let currentRunsQuery = '';
const runsPerPage = 10;
let allFailuresData = [];
let currentFailuresPage = 1;
let currentFailuresQuery = '';
const failuresPerPage = 50;
let redmineProjectsCache = [];
let isMoveRunsMode = false; 
let currentSubmissionDetails = null; // Store full submission object

async function toggleSubmissionLock(subId) {
    const btn = document.getElementById('btn-lock-toggle');
    const label = document.getElementById('lock-label');
    const helper = document.getElementById('lock-helper-text');
    
    if (!btn) return;
    
    const isLocked = btn.getAttribute('aria-checked') === 'true';
    const newState = !isLocked;
    
    try {
        const response = await fetch(`${API_BASE}/submissions/${subId}/lock`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ is_locked: newState })
        });
        
        if (response.ok) {
            btn.setAttribute('aria-checked', newState);
            
            if (label) {
                label.textContent = newState ? 'Locked' : 'Active';
                label.className = `text-xs font-semibold uppercase tracking-wider transition-colors duration-300 ${newState ? 'text-emerald-600' : 'text-slate-500'}`;
            }
            
            if (helper) {
                helper.textContent = newState ? 'Session Frozen' : 'Accepting Reruns';
                helper.className = `text-[9px] font-medium transition-colors duration-300 ${newState ? 'text-emerald-500' : 'text-slate-400'}`;
            }
            
            // Update global state
            if (currentSubmissionDetails) currentSubmissionDetails.is_locked = newState;
            
            const msg = newState 
                ? 'Session Locked: Future uploads will create a new submission' 
                : 'Session Unlocked: Accepting new reruns';
            showNotification(msg, newState ? 'success' : 'info');
        } else {
            showNotification('Failed to toggle lock', 'error');
        }
    } catch (e) {
        console.error(e);
        showNotification('Error toggling lock', 'error');
    }
}

function enableMoveRunsMode() {
    isMoveRunsMode = !isMoveRunsMode;
    
    // Re-render run list
    const runsListEl = document.getElementById('submission-runs-list');
    const runsEmptyEl = document.getElementById('submission-runs-empty');
    
    if (currentSubmissionDetails && runsListEl) {
        renderSubmissionRuns(runsListEl, runsEmptyEl, currentSubmissionDetails.test_runs || [], currentSubmissionDetails.target_fingerprint);
    }
    
    if (isMoveRunsMode) {
        showNotification('Select runs to split/move', 'info');
        // Auto-switch to runs tab if not active
        switchSubmissionTab('runs');
    }
}

async function executeMoveRuns() {
    const selected = Array.from(document.querySelectorAll('.run-checkbox:checked')).map(cb => parseInt(cb.value));
    
    if (selected.length === 0) {
        showNotification('Please select at least one run', 'error');
        return;
    }
    
    if (!confirm(`Are you sure you want to move ${selected.length} runs to a NEW submission?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/submissions/move-runs`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                run_ids: selected,
                target_submission_id: null // Create New
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            showNotification('Runs moved successfully!', 'success');
            setTimeout(() => {
                router.navigate('submission-detail', { id: data.target_submission_id });
            }, 1000);
        } else {
            showNotification('Failed to move runs', 'error');
        }
    } catch (e) {
        console.error(e);
        showNotification('Error moving runs', 'error');
    }
}

// Java Stack Trace syntax highlighting
function highlightStackTrace(text) {
    if (!text) return '<span class="text-slate-400">No stack trace available.</span>';
    
    // Escape HTML first
    const escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    
    return escaped.split('\n').map(line => {
        // Exception line (e.g., java.lang.AssertionError: message)
        if (line.match(/^[\w.]+(?:Error|Exception|Throwable):/)) {
            const colonIdx = line.indexOf(':');
            const exceptionType = line.substring(0, colonIdx);
            const message = line.substring(colonIdx);
            return `<span class="text-red-400 font-semibold">${exceptionType}</span><span class="text-orange-300">${message}</span>`;
        }
        
        // Exception line without message
        if (line.match(/^[\w.]+(?:Error|Exception|Throwable)$/)) {
            return `<span class="text-red-400 font-semibold">${line}</span>`;
        }
        
        // Stack frame line (e.g., at com.package.Class.method(File.java:123))
        const atMatch = line.match(/^(\s*)(at\s+)([\w.$]+)\.([\w$<>]+)\((.*)\)$/);
        if (atMatch) {
            const [, indent, atKeyword, packageClass, method, location] = atMatch;
            // Highlight file:line if present
            const locHighlighted = location.replace(
                /([\w]+\.java):(\d+)/g,
                '<span class="text-yellow-400">$1</span>:<span class="text-yellow-500">$2</span>'
            ).replace(
                /Native Method|Unknown Source/g,
                '<span class="text-slate-500 italic">$&</span>'
            );
            return `${indent}<span class="text-purple-400">${atKeyword}</span><span class="text-slate-400">${packageClass}.</span><span class="text-cyan-300">${method}</span>(<span>${locHighlighted}</span>)`;
        }
        
        // Caused by line
        if (line.match(/^Caused by:/)) {
            return `<span class="text-orange-500 font-semibold">${line}</span>`;
        }
        
        // "... X more" line
        if (line.match(/^\s*\.\.\. \d+ more$/)) {
            return `<span class="text-slate-500 italic">${line}</span>`;
        }
        
        // Test details header lines (####)
        if (line.match(/^#{3,}/)) {
            return `<span class="text-slate-500">${line}</span>`;
        }
        
        // Key-value lines (e.g., Test Name :- xxx)
        const kvMatch = line.match(/^(\s*)([\w\s]+)\s*(:-|:=|:)\s*(.*)$/);
        if (kvMatch) {
            const [, indent, key, sep, value] = kvMatch;
            return `${indent}<span class="text-slate-500">${key}</span><span class="text-slate-600">${sep}</span> <span class="text-slate-300">${value}</span>`;
        }
        
        return line;
    }).join('\n');
}

// Notification helper (HUD-style Toast)
function showNotification(message, type = 'info') {
    const icons = {
        success: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        error: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        info: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>'
    };
    const colors = {
        success: 'text-green-400',
        error: 'text-red-400',
        info: 'text-blue-400'
    };
    
    const notification = document.createElement('div');
    notification.className = 'fixed top-6 right-6 z-50 toast-hud px-5 py-4 flex items-center gap-3 text-white text-sm font-medium transform translate-x-0 transition-all duration-300';
    notification.innerHTML = `
        <span class="${colors[type] || colors.info}">${icons[type] || icons.info}</span>
        <span>${message}</span>
    `;
    document.body.appendChild(notification);

    // Animate in
    requestAnimationFrame(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateX(0)';
    });

    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(20px)';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// Date Formatting Helper
function formatFriendlyDate(dateString) {
    if (!dateString) return '-';
    
    // Check if input is ALREADY formatted (simple heuristic)
    if (dateString.includes('Today at') || (dateString.length < 20 && !dateString.includes('T'))) {
         // It might be already formatted or simple string
         // Try parsing
         const timestamp = Date.parse(dateString);
         if (isNaN(timestamp)) return dateString; // Return as is if not parseable
    }

    const dateObj = new Date(dateString);
    if (isNaN(dateObj.getTime())) return '-';

    const today = new Date();
    const isToday = dateObj.getDate() === today.getDate() && 
                    dateObj.getMonth() === today.getMonth() && 
                    dateObj.getFullYear() === today.getFullYear();
    
    if (isToday) {
        return `Today at ${dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
    } else {
        return dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }
}

/**
 * Reusable Delete Run Modal
 * Shows a confirmation dialog before deleting a test run and all associated data.
 * 
 * @param {number} runId - The ID of the run to delete
 * @param {object} runDetails - Optional run details for display (totalTests, clusterCount, suiteName)
 * @param {function} onSuccess - Optional callback after successful deletion
 */
function showDeleteRunModal(runId, runDetails = {}, onSuccess = null) {
    const deleteModal = document.getElementById('delete-modal');
    const modalMessage = document.getElementById('delete-modal-message');
    const modalCancel = document.getElementById('modal-cancel');
    const modalConfirm = document.getElementById('modal-confirm');
    
    if (!deleteModal) {
        console.error('Delete modal not found');
        return;
    }
    
    // Build confirmation message
    const totalTests = runDetails.totalTests ? runDetails.totalTests.toLocaleString() : 'all';
    const clusterCount = runDetails.clusterCount || 0;
    const suiteName = runDetails.suiteName || '';
    
    modalMessage.innerHTML = `
        <div class="space-y-4">
            <div class="flex items-center gap-3 p-3 bg-red-50 rounded-lg border border-red-200">
                <div class="flex-shrink-0 w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                    <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                </div>
                <div>
                    <div class="font-bold text-red-800">Delete Run #${runId}${suiteName ? ` (${suiteName})` : ''}</div>
                    <div class="text-sm text-red-600">This action cannot be undone</div>
                </div>
            </div>
            
            <div class="text-sm text-slate-600">
                The following data will be <strong>permanently deleted</strong>:
            </div>
            
            <ul class="space-y-2 text-sm">
                <li class="flex items-center gap-2">
                    <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <span><strong>${totalTests}</strong> test case records</span>
                </li>
                <li class="flex items-center gap-2">
                    <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                    <span><strong>${clusterCount}</strong> AI analysis clusters</span>
                </li>
                <li class="flex items-center gap-2">
                    <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <span>System information & metadata</span>
                </li>
            </ul>
        </div>
    `;
    
    // Reset button state
    modalConfirm.disabled = false;
    modalConfirm.textContent = 'Delete';
    modalConfirm.className = 'px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium';
    
    // Show modal
    deleteModal.classList.remove('hidden');
    document.body.classList.add('modal-open');
    
    // Remove old listeners
    const newCancelBtn = modalCancel.cloneNode(true);
    const newConfirmBtn = modalConfirm.cloneNode(true);
    modalCancel.parentNode.replaceChild(newCancelBtn, modalCancel);
    modalConfirm.parentNode.replaceChild(newConfirmBtn, modalConfirm);
    
    // Add new listeners
    newCancelBtn.addEventListener('click', () => {
        deleteModal.classList.add('hidden');
        document.body.classList.remove('modal-open');
    });
    
    let isDeleting = false;
    newConfirmBtn.addEventListener('click', async () => {
        if (isDeleting) return;
        isDeleting = true;
        
        try {
            newConfirmBtn.disabled = true;
            newConfirmBtn.innerHTML = `
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                Deleting...
            `;
            
            const response = await fetch(`${API_BASE}/reports/runs/${runId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                deleteModal.classList.add('hidden');
                document.body.classList.remove('modal-open');
                showNotification(`Run #${runId} deleted successfully`, 'success');
                
                if (onSuccess) {
                    onSuccess();
                } else {
                    // Default: navigate to dashboard and refresh
                    router.navigate('dashboard');
                }
            } else {
                const error = await response.json();
                showNotification(error.detail || 'Failed to delete test run', 'error');
                newConfirmBtn.disabled = false;
                newConfirmBtn.textContent = 'Delete';
                isDeleting = false;
            }
        } catch (e) {
            console.error("Delete failed", e);
            showNotification('Error deleting test run', 'error');
            newConfirmBtn.disabled = false;
            newConfirmBtn.textContent = 'Delete';
            isDeleting = false;
        }
    });
    
    // Close on outside click
    deleteModal.onclick = (e) => {
        if (e.target === deleteModal) {
            deleteModal.classList.add('hidden');
            document.body.classList.remove('modal-open');
        }
    };
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

async function updateLLMStatus() {
    try {
        const response = await fetch(`${API_BASE}/settings/llm-provider`);
        const data = await response.json();
        
        const badge = document.getElementById('llm-status-badge');
        const providerText = document.getElementById('llm-provider-text');
        const modelText = document.getElementById('llm-model-text');
        
        if (badge && data.provider) {
            providerText.textContent = data.provider_display || data.provider.toUpperCase();
            modelText.textContent = data.active_model;
            badge.classList.remove('hidden');
            
            // Apply different accent color if it's internal
            const icon = badge.querySelector('.llm-badge-icon');
            if (data.provider === 'internal') {
                icon.classList.remove('bg-blue-500', 'shadow-[0_0_8px_rgba(59,130,246,0.5)]');
                icon.classList.add('bg-purple-500', 'shadow-[0_0_8px_rgba(168,85,247,0.5)]');
            } else {
                icon.classList.remove('bg-purple-500', 'shadow-[0_0_8px_rgba(168,85,247,0.5)]');
                icon.classList.add('bg-blue-500', 'shadow-[0_0_8px_rgba(59,130,246,0.5)]');
            }
        }
    } catch (err) {
        console.error('Failed to update LLM status:', err);
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

        // Page Transition: Fade out existing content
        const existingContent = content.firstElementChild;
        if (existingContent) {
            existingContent.classList.add('page-exit');
            setTimeout(() => {
                renderNewPage();
            }, 150); // Match page-exit animation duration
        } else {
            renderNewPage();
        }

        function renderNewPage() {
            // Render new content
            content.innerHTML = '';
            const newContent = tmpl.content.cloneNode(true);
            content.appendChild(newContent);
            
            // Apply fade-in animation to the new page wrapper
            const wrapper = content.firstElementChild;
            if (wrapper) {
                wrapper.classList.add('page-enter');
            }

            // Page specific logic
            if (page === 'dashboard') loadDashboard();
            if (page === 'upload') setupUpload();
            if (page === 'run-details') loadRunDetails(params.id);
            if (page === 'test-case') loadTestCase(params.id);
            if (page === 'settings') loadSettings();
            if (page === 'submissions') loadSubmissions();
            if (page === 'submission-detail') loadSubmissionDetail(params.id);

            // Update Title
            title.textContent = page.charAt(0).toUpperCase() + page.slice(1).replace('-', ' ');
        }
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
    console.log("Loading Dashboard (Submissions View)...");
    // Show Skeletons
    document.getElementById('stat-total-runs').innerHTML = '<div class="h-8 w-16 skeleton rounded-lg"></div>';
    document.getElementById('stat-avg-pass').innerHTML = '<div class="h-8 w-20 skeleton rounded-lg"></div>';
    document.getElementById('stat-total-failures').innerHTML = '<div class="h-8 w-24 skeleton rounded-lg"></div>';
    document.getElementById('stat-total-clusters').innerHTML = '<div class="h-8 w-16 skeleton rounded-lg"></div>';
    document.getElementById('runs-table-body').innerHTML = `
        ${[1, 2, 3, 4, 5].map(() => `
            <tr>
                <td colspan="7" class="px-6 py-4"><div class="h-10 w-full skeleton rounded-lg"></div></td>
            </tr>
        `).join('')}
    `;

    try {
        // Fetch Submissions instead of Runs
        const response = await fetch(`${API_BASE}/submissions?limit=100`); 
        const data = await response.json();
        
        // Handle pagination wrapper if present
        const submissions = Array.isArray(data) ? data : (data.items || []);
        allSubmissionsData = submissions; 
        
        // Reset state for submissions pagination
        currentSubmissionsPage = 1;

        updateDashboardStats(submissions); 
        renderDashboardTable();

        // Setup Search Listener (for submissions)
        const searchInput = document.getElementById('runs-search'); // Reusing runs-search for submissions
        if (searchInput) {
            searchInput.value = '';
            let timeout = null;
            searchInput.oninput = (e) => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    // Implement submission filtering if needed
                    // For now, search is disabled for submissions dashboard
                    // currentRunsQuery = e.target.value.toLowerCase();
                    // currentSubmissionsPage = 1;
                    // renderDashboardTable();
                }, 300);
            };
        }

        // Setup Pagination Listeners (for submissions)
        const prevBtn = document.getElementById('runs-prev');
        const nextBtn = document.getElementById('runs-next');

        if (prevBtn) {
            prevBtn.onclick = () => {
                if (currentSubmissionsPage > 1) {
                    currentSubmissionsPage--;
                    renderDashboardTable();
                }
            };
        }

        if (nextBtn) {
            nextBtn.onclick = () => {
                const filtered = allSubmissionsData; // Or filterSubmissions()
                const maxPage = Math.ceil(filtered.length / runsPerPage);
                if (currentSubmissionsPage < maxPage) {
                    currentSubmissionsPage++;
                    renderDashboardTable();
                }
            };
        }
        
    } catch (e) {
        console.error("Failed to load dashboard", e);
    }
}

function updateDashboardStats(submissions) {
    // Recalculate stats based on Submissions
    // Total Submissions
    const totalSubmissions = submissions.length;
    
    let totalFailures = 0;
    let totalExecuted = 0;
    let totalPassed = 0;
    let totalClusters = 0;
    
    // Arrays for Sparklines (Reverse order: Oldest -> Newest)
    const trendLimit = 10;
    const recentSubs = submissions.slice(0, trendLimit).reverse();
    
    submissions.forEach(sub => {
        totalClusters += sub.cluster_count || 0;

        // sub.suite_summary contains the merged stats
        Object.values(sub.suite_summary).forEach(suite => {
            if (suite.status !== 'missing') {
                totalFailures += suite.failed || 0;
                totalPassed += suite.passed || 0;
                totalExecuted += (suite.failed || 0) + (suite.passed || 0);
            }
        });
    });
    
    // Calculate Trends
    const passRateTrend = recentSubs.map(sub => {
        let sFail = 0, sPass = 0;
        Object.values(sub.suite_summary).forEach(suite => {
             if (suite.status !== 'missing') {
                 sFail += suite.failed || 0;
                 sPass += suite.passed || 0;
             }
        });
        const total = sFail + sPass;
        let rate = total > 0 ? (sPass / total) * 100 : 0;
        
        // Safety: If there ARE failures, NEVER show 100.00%
        if (sFail > 0 && rate > 99.99) {
            rate = 99.99;
        }
        return rate;
    });

    const failuresTrend = recentSubs.map(sub => {
        let sFail = 0;
        Object.values(sub.suite_summary).forEach(suite => {
             if (suite.status !== 'missing') sFail += suite.failed || 0;
        });
        return sFail;
    });

    const clustersTrend = recentSubs.map(sub => sub.cluster_count || 0);
    
    // Update Widgets
    // 1. Total Submissions (was Total Runs)
    const statRuns = document.getElementById('stat-total-runs');
    if (statRuns) statRuns.innerText = totalSubmissions;
    
    // 2. Avg Pass Rate
    const statPassRate = document.getElementById('stat-avg-pass');
    if (statPassRate) {
        let rate = totalExecuted > 0 ? (totalPassed / totalExecuted) * 100 : 0;
        
        // Safety: If there ARE failures, NEVER show 100.00%
        if (totalFailures > 0 && rate > 99.99) {
            rate = 99.99;
        }
        
        statPassRate.innerText = `${rate.toFixed(2)}%`;
    }
    
    // 3. Total Failures
    const statFailures = document.getElementById('stat-total-failures');
    if (statFailures) statFailures.innerText = totalFailures;
    
    // 4. Clusters
    const statClusters = document.getElementById('stat-total-clusters');
    if (statClusters) statClusters.innerText = totalClusters;

    // Render Sparklines (Real Data)
    // For "Total Submissions" sparkline, we don't have historical "total count" snapshots. 
    // We can show the "New Submissions" volume or just hide it. 
    // Let's use "Clusters Trend" for 4th and "Failures" for 3rd.
    // For 1st (Total Submissions), maybe just a flat line or random for now? 
    // Or better: Show "Submissions per day"? Too complex.
    // Let's just use [1,1,1] placeholder for Total Submissions as it is a counter, not a rate.
    renderSparkline('stat-total-runs-sparkline', [0, 0, 0, 0, 0, 0, 0], '#cbd5e1'); // Flat line
    renderSparkline('stat-avg-pass-sparkline', passRateTrend, '#10b981');
    renderSparkline('stat-total-failures-sparkline', failuresTrend, '#ef4444');
    renderSparkline('stat-total-clusters-sparkline', clustersTrend, '#a855f7');
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
    // We reuse pagination controls
    const startEl = document.getElementById('runs-start');
    const endEl = document.getElementById('runs-end');
    const totalEl = document.getElementById('runs-total');
    const prevBtn = document.getElementById('runs-prev');
    const nextBtn = document.getElementById('runs-next');

    if (!tbody) return;

    // Use allSubmissionsData (No filtering for now, or implement filterSubmissions)
    const filtered = allSubmissionsData; 
    const total = filtered.length;
    const maxPage = Math.ceil(total / runsPerPage) || 1;

    if (currentSubmissionsPage > maxPage) currentSubmissionsPage = maxPage;
    if (currentSubmissionsPage < 1) currentSubmissionsPage = 1;

    const start = (currentSubmissionsPage - 1) * runsPerPage;
    const end = Math.min(start + runsPerPage, total);
    const pageItems = filtered.slice(start, end);

    if (startEl) startEl.textContent = total === 0 ? 0 : start + 1;
    if (endEl) endEl.textContent = end;
    if (totalEl) totalEl.textContent = total;

    if (prevBtn) {
        prevBtn.onclick = () => { currentSubmissionsPage--; renderDashboardTable(); };
        prevBtn.disabled = currentSubmissionsPage === 1;
    }
    if (nextBtn) {
        nextBtn.onclick = () => { currentSubmissionsPage++; renderDashboardTable(); };
        nextBtn.disabled = currentSubmissionsPage === maxPage || total === 0;
    }

    tbody.innerHTML = '';

    if (total === 0) {
        // Empty State (Reused)
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="px-8 py-8 text-center">
                    <div class="flex flex-col items-center gap-4 animate-in fade-in zoom-in duration-500">
                        <div class="relative w-32 h-32">
                            <img src="/static/assets/empty_state.png" 
                                 alt="No results" class="w-full h-full object-contain rounded-2xl shadow-lg">
                        </div>
                        <div class="max-w-xs">
                            <h3 class="text-slate-900 text-base font-bold">${currentRunsQuery ? 'No results found' : 'Ready to Analyze'}</h3>
                            <p class="text-slate-400 text-sm mt-1 font-medium">${currentRunsQuery ? 'Try adjusting your search' : 'Upload your first test report to get started'}</p>
                        </div>
                        ${!currentRunsQuery ? `
                        <button onclick="router.navigate('upload')" class="px-5 py-2 bg-blue-600 text-white rounded-full text-sm font-semibold shadow-md hover:shadow-blue-500/30 hover:bg-blue-700 transition-all btn-press">
                            Upload Report
                        </button>` : ''}
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    pageItems.forEach(sub => {
        // Calculate Row Stats
        let rowFailures = 0;
        let rowExecuted = 0;
        let rowPassed = 0;
        let badgesHtml = '';
        
        // Suite Badges
        // sub.suite_summary key is suite name (CTS, CTS GSI)
        Object.entries(sub.suite_summary).forEach(([name, statusObj]) => {
            const status = statusObj.status;
            if (status === 'missing') return;
            
            rowFailures += statusObj.failed || 0;
            rowPassed += statusObj.passed || 0;
            rowExecuted += (statusObj.failed || 0) + (statusObj.passed || 0);

            // Badge Color
            let color = 'bg-slate-100 text-slate-700'; // Default
            if (status === 'fail') color = 'bg-red-100 text-red-700';
            else if (status === 'pass') color = 'bg-green-100 text-green-700';
            
            // Name Color (CTS blue, etc) - optional, use status color for now as per plan
             let borderCls = '';
             if (name.includes('CTS')) borderCls = 'border-blue-200';
             if (name.includes('GSI')) borderCls = 'border-purple-200';

            badgesHtml += `
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${color} border ${borderCls} mr-1" title="${statusObj.failed} failures">
                    ${name}
                    ${status === 'fail' ? `<span class="bg-red-500 text-white text-[9px] px-1 rounded-full">${statusObj.failed}</span>` : ''}
                </span>
            `;
        });

        // Pass Rate
        let passRateCtx = '0.00%';
        let passRateColor = 'bg-slate-100 text-slate-600';
        if (rowExecuted > 0) {
            let rate = (rowPassed / rowExecuted) * 100;
            
            // Safety: If there ARE failures, NEVER show 100.00%
            if (rowFailures > 0 && rate > 99.99) {
                rate = 99.99;
            }
            
            passRateCtx = rate.toFixed(2) + '%';
            if (rate >= 99.5) passRateColor = 'bg-green-100 text-green-700';
            else if (rate >= 90) passRateColor = 'bg-yellow-100 text-yellow-700';
            else passRateColor = 'bg-red-100 text-red-700';
        }

        const date = formatFriendlyDate(sub.updated_at || sub.created_at);

        tbody.innerHTML += `
            <tr class="hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0">
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="font-mono text-xs text-slate-500 font-medium">#${sub.id}</span>
                </td>
                <td class="px-6 py-4">
                    <div class="flex flex-wrap gap-1">
                        ${badgesHtml || '<span class="text-slate-400 text-xs text-center italic">Processing...</span>'}
                    </div>
                </td>
                <td class="px-6 py-4">
                    <div class="flex flex-col">
                        <span class="text-sm font-semibold text-slate-800">${sub.product || (sub.target_fingerprint ? sub.target_fingerprint.split('/')[1] : 'Unknown Product')}</span>
                        <span class="text-xs text-slate-500">${sub.target_fingerprint ? sub.target_fingerprint.split(':')[0] : ''}</span>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                    ${date}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                     <span class="px-2 py-1 rounded-full text-xs font-semibold ${passRateColor}">
                        ${passRateCtx}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex flex-col">
                         <span class="text-sm font-bold ${rowFailures > 0 ? 'text-red-600' : 'text-slate-700'}">
                            ${rowFailures} Failures
                        </span>
                        
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div class="flex items-center justify-end gap-3">
                         <button onclick="router.navigate('submission-detail', { id: ${sub.id} })" 
                                class="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 transition-colors">
                            View
                        </button>
                        <button onclick="if(confirm('Delete Submission and ALL its runs?')) { deleteSubmission(${sub.id}); }" 
                                class="text-slate-400 hover:text-red-600 transition-colors" title="Delete Submission">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
}

// Helper for suite color (kept for run-details, not used in dashboard anymore)
const getSuiteColor = (name) => {
    if (!name) return 'bg-slate-100 text-slate-700';
    const n = name.toUpperCase();
    if (n.includes('CTS')) return 'bg-blue-100 text-blue-700';
    if (n.includes('GTS')) return 'bg-emerald-100 text-emerald-700';
    if (n.includes('VTS')) return 'bg-purple-100 text-purple-700';
    if (n.includes('STS')) return 'bg-orange-100 text-orange-700';
    return 'bg-slate-100 text-slate-700';
};

// identifyRunSuite and renderSparkline are not provided in the diff, assuming they exist elsewhere or are not affected.

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
                                
                                    // Fix: Redirect to Submission Detail to show Merged Report
                                    const targetPage = result.submission_id ? 'submission-detail' : 'run-details';
                                    const targetId = result.submission_id || result.test_run_id;
                                    
                                    const timeoutId = setTimeout(() => {
                                        router.navigate(targetPage, { id: targetId });
                                    }, 1000);
                                    router.cleanup = () => clearTimeout(timeoutId);
                            } else {
                                let errorMsg = 'Import failed';
                                try {
                                    const errorData = await response.json();
                                    errorMsg = errorData.detail || errorData.message || `Import failed with status ${response.status}`;
                                    
                                    // Handle Duplicate (409) specifically
                                    if (response.status === 409) {
                                         // Show meaningful alert instead of generic red error bar if possible, 
                                         // but red bar is also fine if text is clear.
                                         // Let's prepend "Duplicate:" for clarity
                                         errorMsg = `Duplicate Upload: ${errorData.detail || 'This test run already exists.'}`;
                                    }
                                } catch (e) {
                                    errorMsg = `Import failed with status ${response.status}`;
                                }
                                throw new Error(errorMsg);
                            }
                        } catch (uploadError) {
                            console.error('Upload failed', uploadError);
                            renderUploadError(uploadError.message);
                        }
                        
                        worker.terminate();
                    } else if (data.type === 'error') {
                        renderUploadError(data.error);
                        worker.terminate();
                    }
                };
                
                worker.onerror = (error) => {
                    console.error('Worker error:', error);
                    renderUploadError(`Parsing error: ${error.message || 'Unknown error'}`);
                    worker.terminate();
                };
                
                // Start parsing
                worker.postMessage(file);
                
            } catch (e) {
                console.error('Local parsing failed', e);
                renderUploadError(`Error: ${e.message}`);
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

                    const targetPage = result.submission_id ? 'submission-detail' : 'run-details';
                    const targetId = result.submission_id || result.test_run_id;

                    const timeoutId = setTimeout(() => {
                        router.navigate(targetPage, { id: targetId });
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
        // Reset view mode to default (Cluster) on page load
        currentViewMode = 'cluster';

        // Load Run Info
        const runRes = await fetch(`${API_BASE}/reports/runs/${runId}`);
        const run = await runRes.json();

        // Store for Redmine export
        currentRunDetails = run;

        // Back Navigation Logic
        const backBtn = document.getElementById('btn-run-back');
        if (backBtn) {
            if (run.submission_id) {
                backBtn.onclick = () => router.navigate('submission-detail', { id: run.submission_id });
                backBtn.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                    <span>Back to Submission #${run.submission_id}</span>
                `;
            } else {
                 backBtn.onclick = () => router.navigate('dashboard');
                 backBtn.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                    <span>Back to Dashboard</span>
                `;
            }
        }

        // Async Guard: Stop if page changed
        if (router.currentPage !== 'run-details' || router.currentParams.id != runId) return;

        const suiteName = identifyRunSuite(run, run.target_fingerprint);
        const config = SUITE_CONFIGS[suiteName];
        document.getElementById('detail-suite-name').textContent = config ? (config.display_name || suiteName) : (run.test_suite_name || 'Unknown');

        const deviceEl = document.getElementById('detail-device');
        const model = run.build_model || 'Unknown';
        const product = run.build_product || '';
        const fingerprint = run.device_fingerprint || '';

        let deviceHtml = `<span class="font-medium text-slate-900">Device: ${model}</span>`;
        if (product && product !== model) {
            deviceHtml += `<span class="text-xs text-slate-500">(${product})</span>`;
        }
        
        deviceHtml += `
            <div class="flex items-center gap-2 mt-0.5 group">
                <div class="text-[10px] text-slate-400 font-mono break-all selection:bg-blue-100" title="${fingerprint}">${fingerprint}</div>
                ${fingerprint ? `
                <button onclick="copyToClipboard('${fingerprint}')" class="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-blue-500 transition-all p-1 rounded-md hover:bg-slate-100 flex-shrink-0" title="Copy Fingerprint">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                </button>` : ''}
            </div>
            `;
        deviceEl.innerHTML = deviceHtml;
        document.getElementById('detail-date').textContent = formatFriendlyDate(run.start_time);

        // Update View Submission Button
        const viewSubBtn = document.getElementById('btn-view-submission');
        const viewSubName = document.getElementById('detail-submission-name');
        if (viewSubBtn && viewSubName) {
            if (run.submission_id) {
                viewSubBtn.classList.remove('hidden');
                viewSubBtn.onclick = () => router.navigate('submission-detail', { id: run.submission_id });
            } else {
                viewSubBtn.classList.add('hidden');
            }
        }

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
                <div class="bg-white rounded-2xl shadow-sm border border-slate-200 mt-6 overflow-hidden">
                    <div class="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                        <h4 class="font-semibold text-slate-900 text-sm tracking-tight">System Information</h4>
                        ${run.start_display ? '<span class="px-2 py-0.5 rounded-md bg-white border border-green-200 text-green-700 text-[10px] font-medium shadow-sm">Verified Metadata</span>' : ''}
                    </div>
                    
                    <div class="p-6 grid grid-cols-1 lg:grid-cols-2 gap-12">
                        <!-- Left Column: Device Configuration -->
                        <div>
                            <h5 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">Device Configuration</h5>
                            <div class="space-y-4">
                                <div class="grid grid-cols-[120px_1fr] items-baseline">
                                    <span class="text-sm text-slate-500">Product</span>
                                    <span class="text-sm font-medium text-slate-900">${run.build_model || '-'} <span class="text-slate-400 font-normal">(${run.build_product || '-'})</span></span>
                                </div>
                                <div class="grid grid-cols-[120px_1fr] items-baseline">
                                    <span class="text-sm text-slate-500">Build ID</span>
                                    <span class="text-sm font-medium text-slate-900 flex items-center gap-2">
                                        ${run.build_id || '-'}
                                        <span class="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 capitalize border border-slate-200">${run.build_type || 'user'}</span>
                                    </span>
                                </div>
                                <div class="grid grid-cols-[120px_1fr] items-baseline">
                                    <span class="text-sm text-slate-500">Android Version</span>
                                    <div>
                                        <div class="text-sm font-medium text-slate-900">Android ${run.android_version || '-'}${run.build_version_sdk ? ` (SDK ${run.build_version_sdk})` : ''}</div>
                                        ${run.build_version_incremental ? `<div class="text-xs text-slate-400 font-normal mt-0.5">${run.build_version_incremental}</div>` : ''}
                                    </div>
                                </div>
                                <div class="grid grid-cols-[120px_1fr] items-baseline">
                                    <span class="text-sm text-slate-500">Security Patch</span>
                                    <span class="text-sm font-medium text-slate-900">${run.security_patch || '-'}</span>
                                </div>
                                ${run.build_abis ? `
                                <div class="grid grid-cols-[120px_1fr] items-baseline">
                                    <span class="text-sm text-slate-500">ABIs</span>
                                    <div class="flex flex-wrap gap-1">
                                        ${run.build_abis.split(',').map(abi => `<span class="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 text-[10px] font-medium rounded border border-indigo-100">${abi.trim()}</span>`).join('')}
                                    </div>
                                </div>
                                ` : ''}
                            </div>
                        </div>

                        <!-- Right Column: Session Context -->
                        <div>
                            <h5 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">Session Context</h5>
                            <div class="space-y-4">
                                <div class="grid grid-cols-[100px_1fr] items-baseline">
                                    <span class="text-sm text-slate-500">Suite</span>
                                    <div>
                                        <div class="text-sm font-medium text-slate-900">CTS ${run.suite_version || '-'}</div>
                                        <div class="text-xs text-slate-400 mt-1">Build ${run.suite_build_number || '-'} • Plan ${run.suite_plan || '-'}</div>
                                    </div>
                                </div>
                                <div class="grid grid-cols-[100px_1fr] items-baseline">
                                    <span class="text-sm text-slate-500">Host</span>
                                    <span class="text-sm font-medium text-slate-900">${run.host_name || '-'}</span>
                                </div>
                                <div class="grid grid-cols-[100px_1fr] items-start pt-1">
                                    <span class="text-sm text-slate-500 flex items-center gap-1.5">
                                        Duration
                                    </span>
                                    <div class="text-sm">
                                        <div class="font-medium text-slate-900">${run.start_display ? run.start_display : (run.start_time ? new Date(run.start_time).toLocaleString() : '-')}</div>
                                        <div class="text-xs text-slate-400 mt-1 pl-2 border-l-2 border-slate-100">
                                            to ${run.end_display ? run.end_display : (run.end_time ? new Date(run.end_time).toLocaleString() : 'Running...')}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Footer: Fingerprint -->
                    <div class="bg-slate-50 border-t border-slate-100 px-6 py-3">
                         <div class="flex flex-col gap-1">
                            <span class="apple-label">Device Fingerprint</span>
                            <div class="font-mono text-[10px] text-slate-500 break-all select-all leading-relaxed">
                                ${run.device_fingerprint || '-'}
                            </div>
                        </div>
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
                    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                        <div class="text-center p-4 bg-green-50 rounded-lg border border-green-100">
                            <div class="text-2xl font-bold text-green-600">${stats.passed_tests.toLocaleString()}</div>
                            <div class="text-xs text-slate-600 mt-1">Tests Passed</div>
                        </div>
                        <div class="text-center p-4 bg-red-50 rounded-lg border border-red-100">
                            <div class="text-2xl font-bold text-red-600">${stats.failed_tests.toLocaleString()}</div>
                            <div class="text-xs text-slate-600 mt-1">Tests Failed</div>
                        </div>
                        <div class="text-center p-4 bg-purple-50 rounded-lg border border-purple-100">
                            <div class="text-2xl font-bold text-purple-600">${stats.xml_modules_done || 0}/${stats.xml_modules_total || 0}</div>
                            <div class="text-xs text-slate-600 mt-1">Modules Completed</div>
                        </div>
                        <div class="text-center p-4 bg-blue-50 rounded-lg border border-blue-100">
                            <div class="text-2xl font-bold text-blue-600">${stats.passed_modules.toLocaleString()}</div>
                            <div class="text-xs text-slate-600 mt-1">Modules Passed</div>
                        </div>
                        <div class="text-center p-4 bg-orange-50 rounded-lg border border-orange-100">
                            <div class="text-2xl font-bold text-orange-600">${stats.failed_modules.toLocaleString()}</div>
                            <div class="text-xs text-slate-600 mt-1">Modules Failed</div>
                        </div>
                        <div class="text-center p-4 bg-slate-50 rounded-lg border border-slate-200">
                            <div class="text-2xl font-bold text-slate-700">${stats.total_modules.toLocaleString()}</div>
                            <div class="text-xs text-slate-600 mt-1">Module-ABI Total</div>
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

        // Setup Delete Button - use reusable modal function
        const btnDelete = document.getElementById('btn-delete');
        if (btnDelete) {
            btnDelete.onclick = () => {
                showDeleteRunModal(runId, {
                    totalTests: run.total_tests,
                    clusterCount: run.cluster_count || 0,
                    suiteName: run.test_suite_name
                });
            };
        }

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
            const sevColor = sev === 'High' ? 'bg-red-100 text-red-700' : (sev === 'Medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-700');
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
                            <div class="flex items-center gap-2">
                                <div class="text-xs font-semibold text-slate-500">${f.module_name}</div>
                                ${f.module_abi ? `<span class="px-1.5 py-0.5 bg-purple-100 text-purple-700 text-[10px] font-semibold rounded">${f.module_abi}</span>` : ''}
                            </div>
                            <div class="font-medium text-slate-700 font-mono text-sm break-all">${f.class_name}#${f.method_name}</div>
                            <div class="text-sm text-red-600 break-words">${escapeHtml(errorMsg)}</div>
                            <div class="flex items-center gap-4 mt-1">
                                ${stackTrace ? `
                                    <details class="group">
                                        <summary class="text-xs text-blue-600 cursor-pointer hover:underline select-none">Show Stack Trace</summary>
                                        <pre class="mt-2 p-3 bg-slate-900 text-slate-50 rounded text-xs overflow-x-auto code-scroll font-mono max-h-60 whitespace-pre-wrap break-all">${escapeHtml(stackTrace)}</pre>
                                    </details>
                                ` : ''}
                                <a href="#" onclick="event.preventDefault(); router.navigate('test-case', { id: ${f.id} })" 
                                   class="text-xs text-slate-500 hover:text-blue-600 font-medium flex items-center gap-1 transition-colors ml-auto">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                                    View Full Details
                                </a>
                            </div>
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

/**
 * Format multiline text for HTML display.
 * Converts numbered lists and newlines to proper HTML formatting.
 * @param {string} text - Raw text from LLM
 * @returns {string} - HTML formatted text
 */
function formatMultilineText(text) {
    if (!text) return '';
    
    // First escape HTML special characters
    let escaped = escapeHtml(text);
    
    // Convert \n to actual newlines (in case LLM returns escaped newlines)
    escaped = escaped.replace(/\\n/g, '\n');
    
    // Split by newlines
    const lines = escaped.split('\n');
    
    // Check if this looks like a numbered list
    const isNumberedList = lines.some(line => /^\d+\.\s/.test(line.trim()));
    
    if (isNumberedList) {
        // Format as list items
        return lines
            .map(line => {
                const trimmed = line.trim();
                if (!trimmed) return '';
                // Add proper spacing for list items
                if (/^\d+\.\s/.test(trimmed)) {
                    return `<div class="mb-2">${trimmed}</div>`;
                }
                return `<div class="mb-1">${trimmed}</div>`;
            })
            .filter(line => line)
            .join('');
    } else {
        // Just convert newlines to <br>
        return escaped.replace(/\n/g, '<br>');
    }
}


async function loadClusters(runId) {
    // Show Skeleton for Clusters Table
    const tbody = document.getElementById('clusters-table-body');
    if (tbody) {
        tbody.innerHTML = `
            ${[1, 2, 3, 4].map(() => `
                <tr>
                    <td class="px-6 py-4"><div class="h-4 w-8 skeleton rounded"></div></td>
                    <td class="px-6 py-4"><div class="h-4 w-48 skeleton rounded"></div></td>
                    <td class="px-6 py-4"><div class="h-4 w-24 skeleton rounded"></div></td>
                    <td class="px-6 py-4"><div class="h-4 w-16 skeleton rounded"></div></td>
                    <td class="px-6 py-4"><div class="h-4 w-20 skeleton rounded"></div></td>
                    <td class="px-6 py-4 text-right"><div class="h-6 w-16 skeleton rounded ml-auto"></div></td>
                </tr>
            `).join('')}
        `;
    }

    // Show Skeleton for KPIs
    const kpiIds = ['kpi-high-severity', 'kpi-medium-severity', 'kpi-low-severity', 'kpi-top-category', 'kpi-category-dist', 'kpi-todo-count'];
    kpiIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div class="h-6 w-12 skeleton rounded inline-block"></div>';
    });

    try {
        // Fetch both Cluster Data and Module Data (Parallel for speed)
        // Also fetch Redmine Users for resolving assignees in UI
        const [clustersRes, modulesRes] = await Promise.all([
            fetch(`${API_BASE}/analysis/run/${runId}/clusters`),
            fetch(`${API_BASE}/analysis/run/${runId}/clusters/by-module`),
            fetchRedmineUsers() // Pre-fetch users for cache
        ]);

        const clusters = await clustersRes.json();
        const modulesData = await modulesRes.json();

        allClustersData = clusters;
        allModulesData = modulesData.modules || []; // Store module data

        console.log(`[loadClusters] Fetched ${clusters.length} clusters and ${allModulesData.length} modules for run ${runId}`);

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
        document.getElementById('kpi-severity').className = `text-2xl font-display font-bold ${overallSeverity === 'High' ? 'text-red-600' : (overallSeverity === 'Medium' ? 'text-yellow-600' : 'text-green-600')}`;

        document.getElementById('kpi-top-category').textContent = topCategory;
        document.getElementById('kpi-category-dist').textContent = `${topCatPct}% of clusters`;

        document.getElementById('kpi-todo-count').textContent = todoCount;

        // --- 2. Render Table (using current view mode) ---
        const filterCheckbox = document.getElementById('filter-no-redmine');
        renderClustersTable(filterCheckbox ? filterCheckbox.checked : false);

        // Hide/Show analysis and bulk buttons based on cluster existence
        const btnAnalyze = document.getElementById('btn-analyze');
        const btnBulk = document.getElementById('btn-bulk-create-issues');
        if (clusters.length > 0) {
            // Show completed state on Analyze button
            if (btnAnalyze) {
                btnAnalyze.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                    </svg>
                    Re-analyze
                `;
                btnAnalyze.disabled = false;
                btnAnalyze.classList.remove('bg-purple-600', 'hover:bg-purple-700', 'bg-green-600', 'text-white', 'cursor-not-allowed');
                btnAnalyze.classList.add('bg-white', 'text-slate-700', 'border', 'border-slate-300', 'hover:bg-slate-50', 'shadow-sm', 'btn-press');
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
        if (filterCheckbox) {
            filterCheckbox.onchange = (e) => renderClustersTable(e.target.checked);
        }

    } catch (e) {
        console.error("Failed to load clusters", e);
    }
}

// PRD Phase 5: Switch View Mode
function switchViewMode(mode) {
    if (currentViewMode === mode) return;
    
    currentViewMode = mode;
    console.log(`[switchViewMode] Switching to ${mode}`);

    // Update Buttons
    const btnCluster = document.getElementById('view-mode-cluster');
    const btnModule = document.getElementById('view-mode-module');

    if (mode === 'cluster') {
        btnCluster.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 bg-white text-slate-800 shadow-sm";
        btnModule.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
    } else {
        btnModule.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 bg-white text-slate-800 shadow-sm";
        btnCluster.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
    }

    // Re-render
    const filterCheckbox = document.getElementById('filter-no-redmine');
    renderClustersTable(filterCheckbox ? filterCheckbox.checked : false);
}


// Globals for Analysis UI State
let currentSearchQuery = '';
let currentSortKey = 'impact'; // Default sort
let currentSortDir = 'desc';

// Reusable Table Renderer for both Run Details and Submission Analysis
function renderAnalysisTable(tbodyId, viewMode, filterNoRedmine) {
    console.log(`[renderAnalysisTable] Target=${tbodyId} Mode=${viewMode} Filter=${filterNoRedmine} Search=${currentSearchQuery} Sort=${currentSortKey}`);
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    tbody.innerHTML = '';

    const isClusterMode = viewMode === 'cluster';
    let rawData = isClusterMode ? (allClustersData || []) : (allModulesData || []);
    
    if (rawData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="px-4 py-8 text-center text-slate-500">No analysis data found. Click "Run AI Analysis" or "Sync" to refresh.</td></tr>`;
        return;
    }

    // 1. Filter (Search + NoRedmine)
    let processedData = rawData.filter(item => {
        // Redmine Filter
        if (filterNoRedmine) {
            // For Module view, "Unsynced" means has ANY unsynced cluster? Or fully unsynced?
            // PRD doesn't specify deeply. Logic: If module has unsynced clusters?
            // Current RunDetails logic just filtered clusters.
            // For Clusters:
            if (isClusterMode && item.redmine_issue_id) return false;
            // For Modules: Check if ANY cluster is unsynced? Or if the module itself... modules don't have redmine IDs directly usually.
            // Dashboard logic usually filters clusters. Module view might just show modules containing unsynced clusters.
            if (!isClusterMode) {
                 // Check if any cluster in module is unsynced
                 const hasUnsynced = item.clusters && item.clusters.some(c => !c.redmine_issue_id);
                 if (!hasUnsynced) return false;
            }
        }
        
        // Search Filter
        if (currentSearchQuery) {
            const q = currentSearchQuery.toLowerCase();
            if (isClusterMode) {
                const text = `${item.description || ''} ${item.ai_summary || ''} ${item.common_root_cause || ''} ${item.module_names?.join(' ') || ''}`.toLowerCase();
                return text.includes(q);
            } else {
                const text = `${item.name || ''}`.toLowerCase();
                return text.includes(q);
            }
        }
        return true;
    });

    // 2. Sort
    processedData.sort((a, b) => {
        let valA, valB;
        
        if (currentSortKey === 'summary') {
            valA = isClusterMode ? (a.description || a.ai_summary || '') : (a.name || '');
            valB = isClusterMode ? (b.description || b.ai_summary || '') : (b.name || '');
        } else if (currentSortKey === 'impact') {
            valA = isClusterMode ? (a.failures_count || 0) : (a.total_failures || 0);
            valB = isClusterMode ? (b.failures_count || 0) : (b.total_failures || 0);
        } else if (currentSortKey === 'confidence') {
             // Modules don't have confidence usually, maybe avg? Use 0.
             valA = isClusterMode ? (a.confidence_score || 0) : 0;
             valB = isClusterMode ? (b.confidence_score || 0) : 0;
        } else {
            return 0; // Default
        }

        if (valA < valB) return currentSortDir === 'asc' ? -1 : 1;
        if (valA > valB) return currentSortDir === 'asc' ? 1 : -1;
        return 0;
    });
    
    // Update Header Sort Icons (Visual Feedback)
    updateSortIcons(currentSortKey, currentSortDir);

    // Update Count Display (both Submission and Run Details pages)
    const subCountEl = document.getElementById('sub-cluster-count');
    const runCountEl = document.getElementById('run-cluster-count');
    const countEl = subCountEl || runCountEl;
    console.log('[Debug] Count Element:', countEl, 'ProcessedData:', processedData.length);
    
    if (countEl) {
        const count = processedData.length;
        const unit = viewMode === 'module' ? 'Modules' : 'Clusters';
        countEl.textContent = `${count} ${unit}`;
        countEl.classList.remove('hidden');
        countEl.style.display = 'inline-block'; 
    }

    if (processedData.length === 0) {
         tbody.innerHTML = `<tr><td colspan="7" class="px-4 py-8 text-center text-slate-500">No matching records found.</td></tr>`;
         return;
    }

    if (isClusterMode) {
        // Cluster view doesn't need filter flag as data is already filtered
        renderClusterView(tbody, processedData); 
    } else {
        // Module view needs filter flag to filter inner clusters
        renderModuleView(tbody, processedData, filterNoRedmine);
    }
}

function filterAnalysisTable(query) {
    currentSearchQuery = query;
    // Trigger re-render using current state
    const isSub = document.getElementById('sub-analysis-table-body') !== null && !document.getElementById('sub-analysis-table-body').classList.contains('hidden'); // Heuristic
    // Actually we just call renderAnalysisTable on the active table.
    // Run Details uses 'clusters-table-body'. Submission uses 'sub-analysis-table-body'.
    // We can just try to render both or detect?
    // Safer: Call the wrapper that knows the ID.
    if (document.getElementById('sub-analysis-table-body')) {
        renderAnalysisTable('sub-analysis-table-body', currentViewMode, document.getElementById('sub-toggle-no-redmine')?.getAttribute('aria-checked') === 'true');
    }
    // Run details page handling if needed...
}

function sortAnalysisTable(key) {
    if (currentSortKey === key) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortKey = key;
        currentSortDir = 'desc'; // Default desc for new column
    }
    // Trigger render...
    // Same heuristic as filter
    if (document.getElementById('sub-analysis-table-body')) {
        renderAnalysisTable('sub-analysis-table-body', currentViewMode, document.getElementById('sub-toggle-no-redmine')?.getAttribute('aria-checked') === 'true');
    }
}

function updateSortIcons(key, dir) {
    // Reset all headers
    // This requires adding IDs or classes to headers. 
    // For now, I'll skip complex icon manipulation to keep it simple, or just log it.
    // Ideally modification of index.html added IDs. I didn't add IDs in Step 978 explicitly for icons, just onclick.
    // I can assume this is a nice-to-have visual.
}


function renderClustersTable(filterNoRedmine) {
    // Wrapper for Run Details Page (legacy name preserved but calls shared logic)
    renderAnalysisTable('clusters-table-body', currentViewMode, filterNoRedmine);
}

function renderClusterView(tbody, clusters) {
    // Use passed data
    const displayClusters = clusters || [];


    displayClusters.forEach(cluster => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 transition-colors cursor-pointer border-b border-slate-50 last:border-0';
        tr.onclick = () => showClusterDetail(cluster);

        // Severity Badge
        const sev = (cluster.severity || 'Medium');
const sevClass = sev === 'High' ? 'bg-red-100 text-red-700' : (sev === 'Medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-700');
        const sevLabel = sev === 'High' ? 'High' : (sev === 'Medium' ? 'Med' : 'Low');

        // Confidence Heatmap
        const score = cluster.confidence_score || 0;
        let confClass = 'bg-slate-100 text-slate-600';
        let confLabel = 'Low';
        if (score >= 4) { confClass = 'bg-green-100 text-green-700'; confLabel = 'High'; }
        else if (score >= 3) { confClass = 'bg-yellow-100 text-yellow-700'; confLabel = 'Med'; }
        
        // Parse Title
        const fullSummary = cluster.ai_summary || cluster.description || 'No summary available.';
        const summaryTitle = getClusterTitle(fullSummary);

        tr.innerHTML = `
            <td class="px-4 py-3">
                <div class="flex flex-col gap-1.5 items-start">
                    <div class="flex items-start gap-2">
                        <span class="text-[10px] font-mono text-slate-400 mt-0.5">#${cluster.id}</span>
                        <span class="font-medium text-slate-900 text-sm leading-snug" title="${summaryTitle || 'Untitled Cluster'}">${summaryTitle || 'Untitled Cluster'}</span>
                    </div>
                    <div class="flex items-center gap-2 mt-0.5">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${sevClass}">
                            ${sevLabel}
                        </span>
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                            ${cluster.category || 'Uncategorized'}
                        </span>
                    </div>
                </div>
            </td>
            <td class="px-4 py-3">
                <div class="flex flex-col items-start gap-0.5">
                    <div class="text-sm text-slate-600 font-semibold">
                        ${cluster.failures_count || '?'} <span class="text-xs font-normal text-slate-400">tests</span>
                    </div>
                     <div class="text-xs text-slate-500 font-medium" title="${cluster.module_names ? cluster.module_names.join(', ') : ''}">
                        ${cluster.module_names ? cluster.module_names.length : 0} <span class="text-[10px] font-normal text-slate-400">modules</span>
                    </div>
                </div>
            </td>
            <td class="px-4 py-3 text-xs">
                <div class="flex items-center gap-2">
                     <div class="flex gap-0.5 text-slate-300">
                        ${Array(5).fill(0).map((_, i) => 
                            `<svg class="w-3 h-3 ${i < score ? 'text-amber-400' : ''}" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>`
                        ).join('')}
                    </div>
                    <span class="px-1.5 py-0.5 rounded font-bold ${confClass}">${confLabel}</span>
                </div>
            </td>
            <td class="px-4 py-3 text-sm text-slate-500">
                ${cluster.suggested_assignment || '-'}
            </td>
            <td class="px-4 py-3 text-sm text-slate-600">
                ${(() => {
                    // 1. If synced, show actual Redmine Assignee
                    if (cluster.redmine_assignee) return `<span class="font-medium text-slate-700">${cluster.redmine_assignee}</span>`;
                    
                    // 2. If suggested ID exists, try to resolve name
                    if (cluster.suggested_assignee_id) {
                        const user = redmineUsersCache.find(u => u.id === cluster.suggested_assignee_id);
                        const name = user ? (user.firstname && user.lastname ? `${user.firstname} ${user.lastname}` : user.login) : `User ${cluster.suggested_assignee_id}`;
                        
                        // Badge logic
                        let badge = '';
                        if (cluster.suggested_assignee_source === 'module_pattern') {
                            badge = '<span class="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-50 text-blue-600 border border-blue-100">Rule</span>';
                        } else if (cluster.suggested_assignee_source === 'fallback') {
                             badge = '<span class="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-slate-100 text-slate-500 border border-slate-200">Default</span>';
                        }
                        
                        return `
                             <div class="flex items-center">
                                 <span class="text-slate-700 truncate max-w-[120px]" title="${name}">${name}</span>
                                 ${badge}
                             </div>
                        `;
                    }
                    
                    return '-';
                })()}
            </td>
            <td class="px-4 py-3">
                ${cluster.redmine_issue_id && redmineBaseUrl
                ? `<div class="flex flex-col gap-1">
                     <a href="${redmineBaseUrl}/issues/${cluster.redmine_issue_id}" target="_blank" class="text-blue-600 hover:underline text-xs" onclick="event.stopPropagation()">#${cluster.redmine_issue_id}</a>
                     ${cluster.redmine_status ? `<span class="px-1.5 py-0.5 rounded text-[10px] inline-block ${getStatusColor(cluster.redmine_status)}">${cluster.redmine_status}</span>` : ''}
                   </div>`
                : (cluster.redmine_issue_id
                    ? `<span class="text-xs text-slate-600">#${cluster.redmine_issue_id}</span>`
                    : '<span class="text-xs text-slate-400 italic">None</span>')}
            </td>
            <td class="px-4 py-3">
                <button onclick="showClusterDetail(allClustersData.find(c => c.id === ${cluster.id}))" 
                     class="group flex items-center gap-1.5 px-3 py-1.5 text-blue-600 text-xs font-medium rounded-lg hover:bg-blue-50 transition-all">
                    <span>Analyze</span>
                    <svg class="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
                    </svg>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderModuleView(tbody, modules, filterNoRedmine) {
    // Use passed data
    const displayModules = modules || [];
    displayModules.forEach((module, index) => {
        // Calculate aggregated severity (highest among clusters)
        let maxSeverity = 'Low';
        let unsyncedCount = 0;
        
        if (module.clusters) {
            module.clusters.forEach(c => {
                const fullCluster = allClustersData.find(ac => ac.id === c.id);
                if (fullCluster) {
                    // Check for unsynced
                    if (!fullCluster.redmine_issue_id) {
                        unsyncedCount++;
                    }
                    // Track max severity
                    if (fullCluster.severity === 'High') maxSeverity = 'High';
                    else if (fullCluster.severity === 'Medium' && maxSeverity !== 'High') maxSeverity = 'Medium';
                }
            });
        }
        
        // Skip if filtering and all synced
        if (filterNoRedmine && unsyncedCount === 0) return;
        
        // Priority Badge colors
        const priorityColor = module.priority === 'P0' ? 'bg-red-600 text-white' 
                            : (module.priority === 'P1' ? 'bg-orange-500 text-white' 
                            : (module.priority === 'P2' ? 'bg-yellow-500 text-white' : 'bg-slate-500 text-white'));
        
        // Severity indicator color
        const severityDot = maxSeverity === 'High' ? 'bg-red-500' 
                          : (maxSeverity === 'Medium' ? 'bg-yellow-500' : 'bg-green-500');

        const tr = document.createElement('tr');
        tr.className = 'border-b border-slate-100 last:border-0 bg-slate-50/50';
        
        // Table Row for Module Header with Batch Sync Button
        tr.innerHTML = `
            <td colspan="7" class="p-0">
                <div class="flex items-center px-4 py-3 bg-slate-100 hover:bg-slate-200 transition-colors">
                    <!-- Expand Arrow -->
                    <div class="cursor-pointer flex items-center flex-1" onclick="toggleModuleRow('${index}')">
                        <svg id="module-arrow-${index}" class="w-4 h-4 text-slate-500 mr-2 transition-transform transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                        
                        <!-- Priority Badge -->
                        <span class="inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold mr-3 ${priorityColor}">${module.priority}</span>
                        
                        <!-- Severity Dot -->
                        <span class="w-2.5 h-2.5 rounded-full ${severityDot} mr-2" title="Max Severity: ${maxSeverity}"></span>
                        
                        <!-- Module Name & Stats -->
                        <div class="flex-1">
                            <span class="font-bold text-slate-800 text-sm">${module.name}</span>
                            <span class="text-xs text-slate-500 ml-2">(${module.total_failures} failures)</span>
                        </div>
                        
                        <!-- Cluster Count Badge -->
                        <span class="text-xs font-semibold text-purple-600 bg-purple-50 px-2 py-1 rounded-full border border-purple-100 mr-2">
                            ${module.cluster_count} Clusters
                        </span>
                        
                        <!-- Unsynced Badge -->
                        ${unsyncedCount > 0 ? `
                        <span class="text-xs font-semibold text-orange-600 bg-orange-50 px-2 py-1 rounded-full border border-orange-100">
                            ${unsyncedCount} Unsynced
                        </span>
                        ` : `
                        <span class="text-xs font-semibold text-green-600 bg-green-50 px-2 py-1 rounded-full border border-green-100">
                            ✓ All Synced
                        </span>
                        `}
                    </div>
                    
                    <!-- Batch Sync Button (only show if unsynced) -->

                    ${unsyncedCount > 0 ? `
                    <button onclick="event.stopPropagation(); syncModule('${module.name}')" 
                            class="ml-3 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors flex items-center gap-1.5 shadow-sm hover:shadow">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                        </svg>
                        <span>Sync All</span>
                    </button>
                    ` : ''}
                </div>

                
                <!-- Expanded Clusters inside Module -->
                <div id="module-content-${index}" class="hidden pl-8 pr-4 py-2 bg-white border-t border-slate-200">
                    <table class="w-full text-sm text-left">
                        <tbody class="divide-y divide-slate-50">
                             ${renderModuleClusters(module.clusters, filterNoRedmine)}
                        </tbody>
                    </table>
                </div>
            </td>
        `;

        tbody.appendChild(tr);
    });
}

// PRD Phase 5: View Mode
// currentViewMode is defined at top of file

// Ensure UI buttons update on load
document.addEventListener('DOMContentLoaded', () => {
    const btnCluster = document.getElementById('view-mode-cluster');
    const btnModule = document.getElementById('view-mode-module');
    if (btnCluster && btnModule) {
        if (currentViewMode === 'module') {
            btnModule.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 bg-white text-slate-800 shadow-sm";
            btnCluster.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
        } else {
            btnCluster.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 bg-white text-slate-800 shadow-sm";
            btnModule.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
        }
    }
});
// ... (The above is illustrative, I will just update the render function mainly and the variable initialization)


function renderModuleClusters(clusters, filterNoRedmine) {
    const displayClusters = filterNoRedmine 
        ? clusters.filter(c => !allClustersData.find(ac => ac.id === c.id)?.redmine_issue_id)
        : clusters;

    if (displayClusters.length === 0) return `<tr><td colspan="7" class="py-4 text-center text-xs text-slate-400">All clusters in this module are synced.</td></tr>`;

    return displayClusters.map(c => {
        // We need full data which might be in allClustersData matching by ID
        // The cluster object from 'by-module' might be simplified, let's look it up
        const fullC = allClustersData.find(ac => ac.id === c.id) || c; 
        
        // Use fullC for rendering to ensure we have all fields like suggested_assignment etc.
        
const sevClass = fullC.severity === 'High' ? 'bg-red-100 text-red-700' : (fullC.severity === 'Medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-700');
        const sevLabel = fullC.severity === 'High' ? 'High' : (fullC.severity === 'Medium' ? 'Med' : 'Low');
        const summaryTitle = getClusterTitle(fullC.ai_summary || fullC.description);
        
        // Confidence
        const score = fullC.confidence_score || 0;
        let confClass = 'bg-slate-100 text-slate-600';
        let confLabel = 'Low';
        if (score >= 4) { confClass = 'bg-green-100 text-green-700'; confLabel = 'High'; }
        else if (score >= 3) { confClass = 'bg-yellow-100 text-yellow-700'; confLabel = 'Med'; }
        
        return `
        <tr class="hover:bg-slate-50 cursor-pointer transition-colors border-b border-slate-50 last:border-0" onclick="showClusterDetail(allClustersData.find(x => x.id === ${fullC.id}))">
            <td class="px-4 py-3 pl-8"> <!-- Indented slightly -->
                <div class="flex flex-col gap-1.5 items-start">
                    <div class="flex items-center gap-2">
                         <span class="text-[10px] font-mono text-slate-400">#${fullC.id}</span>
                         <span class="font-medium text-slate-900 text-sm leading-snug" title="${summaryTitle || 'Untitled Cluster'}">${summaryTitle || 'Untitled Cluster'}</span>
                    </div>
                    <div class="flex items-center gap-2 mt-0.5">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${sevClass}">
                            ${sevLabel}
                        </span>
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                            ${fullC.category || 'Uncategorized'}
                        </span>
                    </div>
                </div>
            </td>
            <td class="px-4 py-3">
                <div class="text-sm text-slate-600 font-semibold">
                    ${fullC.failures_count || c.failures_in_module || '?'} <span class="text-xs font-normal text-slate-400">tests</span>
                </div>
            </td>
            <td class="px-4 py-3 text-xs">
                <div class="flex items-center gap-2">
                     <div class="flex gap-0.5 text-slate-300">
                        ${Array(5).fill(0).map((_, i) => 
                            `<svg class="w-3 h-3 ${i < score ? 'text-amber-400' : ''}" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>`
                        ).join('')}
                    </div>
                    <span class="px-1.5 py-0.5 rounded font-bold ${confClass}">${confLabel}</span>
                </div>
            </td>
            <td class="px-4 py-3 text-sm text-slate-500">
                ${fullC.suggested_assignment || '-'}
            </td>
            <td class="px-4 py-3 text-sm text-slate-600">
                 ${(() => {
                    if (fullC.redmine_assignee) return `<span class="font-medium text-slate-700">${fullC.redmine_assignee}</span>`;
                    
                    if (fullC.suggested_assignee_id) {
                        const user = redmineUsersCache.find(u => u.id === fullC.suggested_assignee_id);
                        const name = user ? (user.firstname && user.lastname ? `${user.firstname} ${user.lastname}` : user.login) : `User ${fullC.suggested_assignee_id}`;
                        
                        let badge = '';
                        if (fullC.suggested_assignee_source === 'module_pattern') {
                            badge = '<span class="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-50 text-blue-600 border border-blue-100">Rule</span>';
                        } else if (fullC.suggested_assignee_source === 'fallback') {
                             badge = '<span class="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-slate-100 text-slate-500 border border-slate-200">Default</span>';
                        }
                        
                         return `
                             <div class="flex items-center">
                                 <span class="text-slate-700 truncate max-w-[120px]" title="${name}">${name}</span>
                                 ${badge}
                             </div>
                        `;
                    }
                    return '-';
                })()}
            </td>
             <td class="px-4 py-3">
                ${fullC.redmine_issue_id && redmineBaseUrl
                ? `<div class="flex flex-col gap-1">
                     <a href="${redmineBaseUrl}/issues/${fullC.redmine_issue_id}" target="_blank" class="text-blue-600 hover:underline text-xs" onclick="event.stopPropagation()">#${fullC.redmine_issue_id}</a>
                     ${fullC.redmine_status ? `<span class="px-1.5 py-0.5 rounded text-[10px] inline-block ${getStatusColor(fullC.redmine_status)}">${fullC.redmine_status}</span>` : ''}
                   </div>`
                : (fullC.redmine_issue_id
                    ? `<span class="text-xs text-slate-600">#${fullC.redmine_issue_id}</span>`
                    : '<span class="text-xs text-slate-400 italic">None</span>')}
            </td>
            <td class="px-4 py-3">
                <button onclick="showClusterDetail(allClustersData.find(c => c.id === ${fullC.id}))" 
                     class="group flex items-center gap-1.5 px-3 py-1.5 text-blue-600 text-xs font-medium rounded-lg hover:bg-blue-50 transition-all">
                    <span>Analyze</span>
                    <svg class="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
                    </svg>
                </button>
            </td>
        </tr>
        `;
    }).join('');
}

function toggleModuleRow(index) {
    const content = document.getElementById(`module-content-${index}`);
    const arrow = document.getElementById(`module-arrow-${index}`);
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        arrow.classList.add('rotate-90');
    } else {
        content.classList.add('hidden');
        arrow.classList.remove('rotate-90');
    }
}

function renderEmptySyncedState(tbody) {
    tbody.innerHTML = `
    <tr>
        <td colspan="7" class="px-8 py-12 text-center">
             <div class="flex flex-col items-center gap-4 animate-in fade-in zoom-in duration-300">
                 <div class="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center border-4 border-green-50 shadow-sm mb-2">
                     <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                     </svg>
                 </div>
                 <div>
                     <h3 class="text-slate-900 font-bold text-lg">All Issues Synced</h3>
                     <p class="text-slate-500 text-sm mt-1">Great job! All identified clusters have been assigned to Redmine.</p>
                     <button onclick="document.getElementById('filter-no-redmine').click()" class="mt-4 text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline">
                        Show all clusters
                     </button>
                 </div>
             </div>
        </td>
    </tr>`;
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
    document.getElementById('detail-title').textContent = `[#${cluster.id}] ${summaryTitle}`;
    const bodyEl = document.getElementById('detail-summary-body');
    if (summaryBody) {
        bodyEl.innerHTML = summaryBody;
        bodyEl.classList.remove('hidden');
    } else {
        bodyEl.classList.add('hidden');
    }
    document.getElementById('detail-root-cause').innerHTML = formatMultilineText(cluster.common_root_cause || 'Analysis pending...');
    document.getElementById('detail-solution').innerHTML = formatMultilineText(cluster.common_solution || 'No solution suggested yet.');
    document.getElementById('detail-stack-trace').innerHTML = highlightStackTrace(cluster.signature);

    // Show/Hide Assign/Unlink buttons based on whether cluster has Redmine issue
    const assignBtn = document.getElementById('btn-assign-redmine');
    const unlinkBtn = document.getElementById('btn-unlink-redmine-detail');
    const unlinkText = document.getElementById('btn-unlink-redmine-text');

    // Always hide Assign button as per user request (use Sync All instead)
    if (assignBtn) assignBtn.classList.add('hidden');

    if (cluster.redmine_issue_id) {
        // Has issue - show unlink
        if (unlinkBtn) {
            unlinkBtn.classList.remove('hidden');
            if (unlinkText) unlinkText.textContent = `Unlink #${cluster.redmine_issue_id}`;
        }
    } else {
        // No issue - hide unlink
        if (unlinkBtn) unlinkBtn.classList.add('hidden');
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

        // Group for Apple-style display but use Run Details Visual Style
        const failureGroups = new Map();
        failures.forEach(f => {
            const key = `${f.module_name}|${f.module_abi}|${f.class_name}|${f.method_name}`;
            if (!failureGroups.has(key)) {
                failureGroups.set(key, {
                    module_name: f.module_name,
                    module_abi: f.module_abi,
                    class_name: f.class_name,
                    method_name: f.method_name,
                    error_message: f.error_message, // Keep one representative error
                    stack_trace: f.stack_trace,     // Keep one representative stack
                    id: f.id,                       // Keep one ID for linking
                    count: 0,
                    runs: new Set()
                });
            }
            const group = failureGroups.get(key);
            group.count++;
            if (f.test_run_id) group.runs.add(f.test_run_id);
        });

        countSpan.textContent = `${failureGroups.size} unique cases (${failures.length} total failures)`;
        list.innerHTML = ''; // Clear loading state
        list.className = "space-y-2 mt-4"; // Add spacing

        const sortedGroups = Array.from(failureGroups.values()).sort((a,b) => b.count - a.count);

        sortedGroups.forEach(g => {
            const errorMsg = g.error_message || 'No error message';
            const stackTrace = g.stack_trace ? g.stack_trace.trim() : '';
            const runCount = g.runs.size;
            const runIds = Array.from(g.runs).sort((a,b)=>a-b).join(', #');

            const item = document.createElement('div');
            item.className = 'border border-slate-200 rounded-lg overflow-hidden bg-white shadow-sm hover:shadow-md transition-all';
            
            item.innerHTML = `
                <div class="p-4 bg-slate-50/30">
                    <div class="flex flex-col gap-2">
                        <div class="flex items-start justify-between">
                            <div class="flex items-center gap-2">
                                <div class="text-xs font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">${g.module_name}</div>
                                ${g.module_abi ? `<span class="px-1.5 py-0.5 bg-purple-50 text-purple-700 text-[10px] font-semibold rounded border border-purple-100">${g.module_abi}</span>` : ''}
                                ${runCount > 0 ? `<span class="px-1.5 py-0.5 bg-amber-50 text-amber-700 text-[10px] font-semibold rounded border border-amber-100" title="Runs #${runIds}">${runCount} Runs</span>` : ''}
                            </div>
                            <span class="text-[10px] font-bold text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded-full border border-slate-100">${g.count} failures</span>
                        </div>
                        
                        <div class="font-medium text-slate-800 font-mono text-sm break-all">
                             ${g.class_name}#${g.method_name}
                        </div>
                        
                        <div class="text-sm text-red-600 break-words leading-snug bg-red-50/50 p-2 rounded border border-red-50/50">
                            ${escapeHtml(errorMsg)}
                        </div>
                        
                        <div class="flex items-center gap-4 mt-1">
                            ${stackTrace ? `
                                <details class="group w-full">
                                    <summary class="text-xs text-blue-600 cursor-pointer hover:underline select-none flex items-center gap-1 font-medium">
                                        <svg class="w-3 h-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                                        Show Stack Trace
                                    </summary>
                                    <pre class="mt-2 p-3 bg-slate-900 text-slate-50 rounded text-xs overflow-x-auto code-scroll font-mono max-h-60 whitespace-pre-wrap break-all shadow-inner">${escapeHtml(stackTrace)}</pre>
                                </details>
                            ` : ''}
                        </div>
                        
                        <div class="mt-2 pt-2 border-t border-slate-100 flex justify-end">
                             <a href="#" onclick="event.preventDefault(); router.navigate('test-case', { id: ${g.id} })" 
                               class="text-xs text-slate-500 hover:text-blue-600 font-medium flex items-center gap-1 transition-colors">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                                View Full Case Details
                            </a>
                        </div>
                    </div>
                </div>
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
// let allRunsData = []; // Already defined at top
// let currentRunsPage = 1; // Already defined at top
// const runsPerPage = 10; // Already defined at top
// let currentRunsQuery = ''; // Already defined at top

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
    
    // Load Module Owner Map settings
    loadModuleOwnerMap();

    // Load App URL
    loadAppUrl();
}


async function loadAppUrl() {
    try {
        const res = await fetch(`${API_BASE}/settings/app-url`);
        const data = await res.json();
        
        const input = document.getElementById('app-base-url');
        if (input && data.url) {
            input.value = data.url;
        }
    } catch (e) {
        console.error("Failed to load app url", e);
    }
}

async function saveAppUrl() {
    const input = document.getElementById('app-base-url');
    const btn = document.getElementById('btn-save-app-url');
    
    if (!input) return;
    
    const url = input.value.trim();
    if (!url) {
        alert('Please enter a valid URL');
        return;
    }
    
    const originalText = 'Save';
    btn.textContent = 'Saving...';
    btn.disabled = true;
    
    try {
        const res = await fetch(`${API_BASE}/settings/app-url`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        
        if (res.ok) {
            const data = await res.json();
            input.value = data.url; // Update with sanitized URL
            
            btn.textContent = 'Saved!';
            btn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            btn.classList.add('bg-green-600', 'hover:bg-green-700');
            
            setTimeout(() => {
                btn.textContent = originalText;
                btn.classList.remove('bg-green-600', 'hover:bg-green-700');
                btn.classList.add('bg-blue-600', 'hover:bg-blue-700');
                btn.disabled = false;
            }, 2000);
        } else {
            alert('Failed to save App URL');
            btn.textContent = originalText;
            btn.disabled = false;
        }
    } catch (e) {
        console.error("Error saving app url", e);
        alert('Error saving App URL');
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// LLM Provider Functions
async function loadLLMProviderSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings/llm-provider`);
        const data = await res.json();
        
        const internalSettings = document.getElementById('internal-llm-settings');
        const cambrianSettings = document.getElementById('cambrian-llm-settings');
        const urlInput = document.getElementById('internal-llm-url');
        const modelSelect = document.getElementById('internal-llm-model');
        const cambrianModelSelect = document.getElementById('cambrian-model');
        
        // Update Segmented Control visual state
        selectProvider(data.provider, false);
        
        if (urlInput && data.internal_url) urlInput.value = data.internal_url;
        
        // For internal model dropdown: add saved model as an option if it exists
        if (modelSelect && data.internal_model) {
            modelSelect.innerHTML = `
                <option value="">Select a model...</option>
                <option value="${data.internal_model}" selected>${data.internal_model}</option>
            `;
        }
        
        // For cambrian model dropdown
        if (cambrianModelSelect && data.cambrian_model) {
            cambrianModelSelect.innerHTML = `
                <option value="${data.cambrian_model}" selected>${data.cambrian_model}</option>
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
    const segCambrian = document.getElementById('seg-cambrian');
    const internalSettings = document.getElementById('internal-llm-settings');
    const cambrianSettings = document.getElementById('cambrian-llm-settings');
    const openaiSettings = document.getElementById('openai-settings');
    
    // Reset all to inactive using CSS classes
    [segOpenAI, segInternal, segCambrian].forEach(btn => {
        if (btn) {
            btn.classList.remove('active');
        }
    });
    
    // Hide all settings
    if (openaiSettings) openaiSettings.classList.add('hidden');
    if (internalSettings) internalSettings.classList.add('hidden');
    if (cambrianSettings) cambrianSettings.classList.add('hidden');
    
    // Activate selected
    if (provider === 'internal') {
        if (segInternal) segInternal.classList.add('active');
        if (internalSettings) {
            internalSettings.classList.remove('hidden');
            if (animate) internalSettings.classList.add('animate-fadeIn');
        }
    } else if (provider === 'cambrian') {
        if (segCambrian) segCambrian.classList.add('active');
        if (cambrianSettings) {
            cambrianSettings.classList.remove('hidden');
            if (animate) cambrianSettings.classList.add('animate-fadeIn');
        }
    } else {
        // Default to OpenAI
        if (segOpenAI) segOpenAI.classList.add('active');
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
    const segCambrian = document.getElementById('seg-cambrian');
    const urlInput = document.getElementById('internal-llm-url');
    const modelSelect = document.getElementById('internal-llm-model');
    const cambrianTokenInput = document.getElementById('cambrian-token');
    const cambrianModelSelect = document.getElementById('cambrian-model');
    const statusSpan = document.getElementById('llm-provider-status');
    const saveBtn = document.getElementById('btn-save-llm-provider');
    
    // Check which provider is selected by checking the active class
    const isInternal = segInternal?.classList.contains('active');
    const isCambrian = segCambrian?.classList.contains('active');
    
    let provider = 'openai';
    if (isInternal) provider = 'internal';
    else if (isCambrian) provider = 'cambrian';
    
    const internal_url = urlInput?.value.trim() || null;
    const internal_model = modelSelect?.value.trim() || 'llama3.1:8b';
    const cambrian_token = cambrianTokenInput?.value.trim() || null;
    const cambrian_model = cambrianModelSelect?.value.trim() || 'LLAMA 3.3 70B';
    
    if (provider === 'internal' && !internal_url) {
        alert('Please enter the internal LLM server URL');
        return;
    }
    
    if (provider === 'cambrian' && !cambrian_token) {
        alert('Please enter the Cambrian API token');
        return;
    }
    
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    
    try {
        const res = await fetch(`${API_BASE}/settings/llm-provider`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                provider, 
                internal_url, 
                internal_model,
                cambrian_token,
                cambrian_model
            })
        });
        
        if (res.ok) {
            statusSpan.innerHTML = `
                <span class="inline-flex items-center gap-1 text-green-600 success-icon">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path class="success-checkmark" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    Saved
                </span>
            `;
            setTimeout(() => { statusSpan.innerHTML = ''; }, 3000);
            updateLLMStatus();
            // Clear token input after saving
            if (cambrianTokenInput) cambrianTokenInput.value = '';
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
    const segCambrian = document.getElementById('seg-cambrian');
    const urlInput = document.getElementById('internal-llm-url');
    const modelSelect = document.getElementById('internal-llm-model');
    const cambrianTokenInput = document.getElementById('cambrian-token');
    
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
    
    // Check which provider is selected
    const isInternal = segInternal?.classList.contains('active');
    const isCambrian = segCambrian?.classList.contains('active');
    const body = {};
    
    if (isCambrian) {
        body.provider = 'cambrian';
        const token = cambrianTokenInput?.value.trim();
        if (token) body.cambrian_token = token;
    } else if (isInternal) {
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
                // Full success - green checkmark with animation
                statusSpan.innerHTML = `
                    <span class="inline-flex items-center gap-1 text-green-600 success-icon">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path class="success-checkmark" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
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

// Refresh Cambrian model list
async function refreshCambrianModels() {
    const tokenInput = document.getElementById('cambrian-token');
    const modelSelect = document.getElementById('cambrian-model');
    const refreshBtn = document.getElementById('btn-refresh-cambrian-models');
    
    const token = tokenInput?.value.trim();
    
    // Store current selection
    const currentModel = modelSelect?.value || 'LLAMA 3.3 70B';
    
    // Show loading state
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = `
            <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
        `;
    }
    
    try {
        let url = `${API_BASE}/settings/list-cambrian-models`;
        if (token) url += `?token=${encodeURIComponent(token)}`;
        
        const res = await fetch(url);
        const data = await res.json();
        
        // Clear existing options
        modelSelect.innerHTML = '';
        
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
                `;
                setTimeout(() => resetCambrianRefreshButton(), 2000);
            }
        } else {
            // No models found or error
            const option = document.createElement('option');
            option.value = currentModel;
            option.textContent = data.error || currentModel;
            modelSelect.appendChild(option);
            
            if (refreshBtn && data.error) {
                refreshBtn.innerHTML = `
                    <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                `;
                setTimeout(() => resetCambrianRefreshButton(), 2000);
            }
        }
    } catch (e) {
        console.error("Failed to refresh Cambrian model list", e);
        if (refreshBtn) {
            refreshBtn.innerHTML = `
                <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            `;
            setTimeout(() => resetCambrianRefreshButton(), 2000);
        }
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

function resetCambrianRefreshButton() {
    const refreshBtn = document.getElementById('btn-refresh-cambrian-models');
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
            updateLLMStatus();
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
            updateLLMStatus();
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
    updateLLMStatus();
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
    } else if (page === 'test-case' && id) {
        router.navigate('test-case', { id: id });
    } else if (page) {
        router.navigate(page);
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
            // Frontend-facing URL: Replace host.docker.internal with localhost
            redmineBaseUrl = data.url.replace('host.docker.internal', 'localhost');
            
            if (urlInput) urlInput.value = data.url; // Show actual backend config in input
            if (keyInput) keyInput.value = data.masked_key || '';
        } else {
            if (urlInput) urlInput.value = '';
            if (keyInput) keyInput.value = '';
        }
    } catch (e) {
        console.error("Failed to load Redmine settings", e);
    }
}

// Module Owner Map Functions
let currentModuleOwnerMapConfig = null;
let redmineUsersCache = []; // Cache for dropdown options

async function fetchRedmineUsers() {
    if (redmineUsersCache.length > 0) return redmineUsersCache;
    try {
        const res = await fetch(`${API_BASE}/integrations/redmine/users`);
        const data = await res.json();
        if (res.ok && data.users && Array.isArray(data.users)) {
            redmineUsersCache = data.users;
            console.log(`[fetchRedmineUsers] Cached ${data.users.length} users`);
            return data.users;
        }
    } catch (e) {
        console.error("Failed to pre-fetch Redmine users", e);
    }
    return [];
}

async function loadModuleOwnerMap() {
    try {
        const res = await fetch(`${API_BASE}/settings/module-owner-map`);
        const data = await res.json();
        
        currentModuleOwnerMapConfig = data.config;
        
        const projectSelect = document.getElementById('default-project-id');
        const prioritySelect = document.getElementById('default-priority-id');
        const assigneeSelect = document.getElementById('default-assignee-id');
        
        // Extract default settings for dropdowns
        const defaults = data.config?.default_settings || {};
        
        // Set priority dropdown
        if (prioritySelect && defaults.default_priority_id) {
            prioritySelect.value = defaults.default_priority_id;
        }
        
        // Render module mapping table rows
        renderModuleMappingTable();
        
    } catch (e) {
        console.error("Failed to load module owner map", e);
    }
}

function renderModuleMappingTable() {
    const container = document.getElementById('module-mapping-rows');
    if (!container) return;
    
    const patterns = currentModuleOwnerMapConfig?.module_patterns || {};
    const patternKeys = Object.keys(patterns);
    
    if (patternKeys.length === 0) {
        container.innerHTML = `
            <div class="p-4 text-center text-sm text-slate-400">
                No mapping rules. Click "Add Rule" to create one.
            </div>
        `;
        return;
    }
    
    let html = '';
    patternKeys.forEach((pattern, index) => {
        const data = patterns[pattern];
        const userId = data.redmine_user_id || '';
        html += createMappingRowHTML(index, pattern, userId);
    });
    
    container.innerHTML = html;
}

function createMappingRowHTML(index, pattern = '', userId = '') {
    const userOptions = redmineUsersCache.map(u => {
        const name = u.firstname && u.lastname ? `${u.firstname} ${u.lastname}` : u.login;
        const selected = u.id == userId ? 'selected' : '';
        return `<option value="${u.id}" ${selected}>${name}</option>`;
    }).join('');
    
    return `
        <div class="grid grid-cols-12 gap-2 p-2 items-center" data-row-index="${index}">
            <div class="col-span-5">
                <input type="text" value="${pattern}" placeholder="e.g., CtsMedia*"
                    class="module-pattern-input w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
            </div>
            <div class="col-span-5">
                <select class="module-owner-select w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                    <option value="">-- Not Assigned --</option>
                    ${userOptions}
                </select>
            </div>
            <div class="col-span-2 text-center">
                <button onclick="removeModuleMappingRow(this)" 
                    class="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                </button>
            </div>
        </div>
    `;
}

function addModuleMappingRow() {
    const container = document.getElementById('module-mapping-rows');
    if (!container) return;
    
    // If container only has the placeholder message, clear it
    if (container.querySelector('.text-slate-400')) {
        container.innerHTML = '';
    }
    
    const rowCount = container.children.length;
    const newRowHTML = createMappingRowHTML(rowCount, '', '');
    container.insertAdjacentHTML('beforeend', newRowHTML);
}

function removeModuleMappingRow(btn) {
    const row = btn.closest('[data-row-index]');
    if (row) {
        row.remove();
        
        // If no rows left, show placeholder
        const container = document.getElementById('module-mapping-rows');
        if (container && container.children.length === 0) {
            container.innerHTML = `
                <div class="p-4 text-center text-sm text-slate-400">
                    No mapping rules. Click "Add Rule" to create one.
                </div>
            `;
        }
    }
}

async function saveModuleOwnerMap() {
    const projectSelect = document.getElementById('default-project-id');
    const prioritySelect = document.getElementById('default-priority-id');
    const assigneeSelect = document.getElementById('default-assignee-id');
    const statusDiv = document.getElementById('module-map-status');
    const container = document.getElementById('module-mapping-rows');
    
    // Build module_patterns from table rows
    const modulePatterns = {};
    const rows = container?.querySelectorAll('[data-row-index]') || [];
    
    rows.forEach(row => {
        const patternInput = row.querySelector('.module-pattern-input');
        const ownerSelect = row.querySelector('.module-owner-select');
        
        const pattern = patternInput?.value?.trim();
        const ownerId = ownerSelect?.value;
        
        if (pattern) {
            modulePatterns[pattern] = {
                redmine_user_id: ownerId ? parseInt(ownerId) : null
            };
        }
    });
    
    // Build config object
    const config = {
        module_patterns: modulePatterns,
        default_settings: {
            default_project_id: projectSelect?.value ? parseInt(projectSelect.value) : null,
            default_priority_id: prioritySelect?.value ? parseInt(prioritySelect.value) : 4,
            fallback_user_id: assigneeSelect?.value ? parseInt(assigneeSelect.value) : null
        }
    };
    
    try {
        const res = await fetch(`${API_BASE}/settings/module-owner-map`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config })
        });
        
        const data = await res.json();
        
        if (res.ok) {
            if (statusDiv) {
                statusDiv.className = 'text-sm p-3 rounded-lg bg-green-50 text-green-700';
                statusDiv.textContent = `✅ Saved ${Object.keys(modulePatterns).length} mapping rules!`;
                statusDiv.classList.remove('hidden');
            }
            currentModuleOwnerMapConfig = config;
        } else {
            if (statusDiv) {
                statusDiv.className = 'text-sm p-3 rounded-lg bg-red-50 text-red-700';
                statusDiv.textContent = `❌ Failed: ${data.detail || 'Unknown error'}`;
                statusDiv.classList.remove('hidden');
            }
        }
    } catch (e) {
        console.error("Error saving module owner map", e);
        if (statusDiv) {
            statusDiv.className = 'text-sm p-3 rounded-lg bg-red-50 text-red-700';
            statusDiv.textContent = `❌ Error: ${e.message}`;
            statusDiv.classList.remove('hidden');
        }
    }
}

async function resetModuleOwnerMap() {
    if (!confirm('Reset module owner map to default configuration? This will overwrite your current settings.')) {
        return;
    }
    
    const statusDiv = document.getElementById('module-map-status');
    
    try {
        const res = await fetch(`${API_BASE}/settings/module-owner-map/reset`, {
            method: 'POST'
        });
        
        const data = await res.json();
        
        if (res.ok) {
            if (statusDiv) {
                statusDiv.className = 'text-sm p-3 rounded-lg bg-green-50 text-green-700';
                statusDiv.textContent = '✅ Configuration reset to defaults!';
                statusDiv.classList.remove('hidden');
            }
            // Reload the config
            loadModuleOwnerMap();
        } else {
            if (statusDiv) {
                statusDiv.className = 'text-sm p-3 rounded-lg bg-red-50 text-red-700';
                statusDiv.textContent = `❌ Failed: ${data.detail || 'Unknown error'}`;
                statusDiv.classList.remove('hidden');
            }
        }
    } catch (e) {
        console.error("Error resetting module owner map", e);
        if (statusDiv) {
            statusDiv.className = 'text-sm p-3 rounded-lg bg-red-50 text-red-700';
            statusDiv.textContent = `❌ Error: ${e.message}`;
            statusDiv.classList.remove('hidden');
        }
    }
}

// Load Redmine Projects and Users for dropdown selectors
async function loadRedmineDropdownData() {
    const statusSpan = document.getElementById('redmine-data-status');
    const projectSelect = document.getElementById('default-project-id');
    const assigneeSelect = document.getElementById('default-assignee-id');
    const btn = document.getElementById('btn-load-redmine-data');
    
    // First check if Redmine is configured
    if (!redmineBaseUrl) {
        if (statusSpan) {
            statusSpan.textContent = '⚠️ Please configure Redmine URL and API Key first (see above)';
            statusSpan.className = 'text-orange-600 font-medium';
        }
        return;
    }
    
    if (statusSpan) statusSpan.textContent = 'Loading...';
    if (statusSpan) statusSpan.className = 'text-slate-400';
    if (btn) btn.disabled = true;
    
    let projectCount = 0;
    let userCount = 0;
    let errors = [];
    
    try {
        // Fetch projects
        const projectsRes = await fetch(`${API_BASE}/integrations/redmine/projects`);
        const projectsData = await projectsRes.json();
        
        console.log('[loadRedmineDropdownData] Projects response:', projectsData);
        
        if (projectsRes.ok && projectsData.projects && Array.isArray(projectsData.projects)) {
            // Get current value to preserve selection
            const currentProjectId = currentModuleOwnerMapConfig?.default_settings?.default_project_id;
            
            projectSelect.innerHTML = '<option value="">-- Select Project --</option>';
            projectsData.projects.forEach(p => {
                const selected = p.id == currentProjectId ? 'selected' : '';
                projectSelect.innerHTML += `<option value="${p.id}" ${selected}>${p.name} (ID: ${p.id})</option>`;
            });
            projectCount = projectsData.projects.length;
        } else if (projectsData.detail) {
            errors.push(`Projects: ${projectsData.detail}`);
        } else {
            errors.push('Projects: No data returned');
        }
    } catch (e) {
        console.error("Error fetching projects", e);
        errors.push(`Projects: ${e.message}`);
    }
    
    try {
        // Fetch users
        const usersRes = await fetch(`${API_BASE}/integrations/redmine/users`);
        const usersData = await usersRes.json();
        
        console.log('[loadRedmineDropdownData] Users response:', usersData);
        
        if (usersRes.ok && usersData.users && Array.isArray(usersData.users)) {
            // Cache users for table row dropdowns
            redmineUsersCache = usersData.users;
            
            const currentAssigneeId = currentModuleOwnerMapConfig?.default_settings?.fallback_user_id;
            
            assigneeSelect.innerHTML = '<option value="">-- None (Unassigned) --</option>';
            usersData.users.forEach(u => {
                const selected = u.id == currentAssigneeId ? 'selected' : '';
                const name = u.firstname && u.lastname ? `${u.firstname} ${u.lastname}` : u.login;
                assigneeSelect.innerHTML += `<option value="${u.id}" ${selected}>${name} (ID: ${u.id})</option>`;
            });
            userCount = usersData.users.length;
            
            // Re-render table rows with updated user dropdowns
            renderModuleMappingTable();
        } else if (usersData.detail) {
            errors.push(`Users: ${usersData.detail}`);
        } else {
            errors.push('Users: No data returned');
        }
    } catch (e) {
        console.error("Error fetching users", e);
        errors.push(`Users: ${e.message}`);
    }
    
    // Update status
    if (errors.length > 0) {
        if (statusSpan) {
            statusSpan.textContent = `⚠️ ${errors.join('; ')}`;
            statusSpan.className = 'text-red-600';
        }
    } else if (projectCount > 0 || userCount > 0) {
        if (statusSpan) {
            statusSpan.textContent = `✅ Loaded ${projectCount} projects, ${userCount} users`;
            statusSpan.className = 'text-green-600';
        }
    } else {
        if (statusSpan) {
            statusSpan.textContent = '⚠️ No data returned. Check Redmine settings.';
            statusSpan.className = 'text-orange-600';
        }
    }
    
    if (btn) btn.disabled = false;
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
                    const sName = identifyRunSuite(currentRunDetails, currentRunDetails.target_fingerprint);
                    const cfg = SUITE_CONFIGS[sName];
                    // Prefer display name for issue subject? Or short code?
                    // Typically Jira/Redmine uses short code.
                    // If GSI, maybe "CTSonGSI" or just "CTS on GSI"?
                    // Let's use name key which is "CTSonGSI" or "CTS".
                    suiteTag = sName;
                }
                const summary = currentCluster.ai_summary || currentCluster.description;
                const title = getClusterTitle(summary);
                subjectInput.value = `[ ${suiteTag} ] ${title}`;
            }

            if (descInput && !descInput.value) {
                // Get representative stack trace
                const repFailure = (currentCluster.failures && currentCluster.failures[0]) || {};
                const stackTrace = repFailure.stack_trace || 'N/A';
                const truncatedStack = stackTrace.split('\n').slice(0, 50).join('\n') + (stackTrace.split('\n').length > 50 ? '\n... (truncated)' : '');
                
                // Group tests by signature (Apple-style grouping)
                const failureGroups = new Map();
                (currentCluster.failures || []).forEach(f => {
                    const testName = `${f.class_name || 'Unknown'}#${f.method_name || 'unknown'}`;
                    if (!failureGroups.has(testName)) {
                        failureGroups.set(testName, { count: 0, runs: new Set() });
                    }
                    const group = failureGroups.get(testName);
                    group.count++;
                    if (f.test_run_id) group.runs.add(f.test_run_id);
                });

                // Convert groups to sorted list
                const sortedGroups = Array.from(failureGroups.entries())
                    .sort((a, b) => b[1].count - a[1].count) // Sort by frequency
                    .slice(0, 50);

                const failureList = sortedGroups.map(([name, stats], idx) => {
                    let meta = '';
                    if (stats.count > 1) {
                        const runIds = Array.from(stats.runs).sort((a,b)=>a-b).join(', #');
                        // Concise Apple-style secondary text
                        meta = ` (${stats.count} hits in Runs: #${runIds})`;
                    } else if (stats.runs.size > 0) {
                        meta = ` (Run #${Array.from(stats.runs)[0]})`;
                    }
                    return `${idx + 1}. ${name}${meta}`;
                }).join('\n');
                
                const uniqueCount = failureGroups.size;
                const totalCount = (currentCluster.failures || []).length;
                const moreCount = uniqueCount - 50;

                // Helper to quote lines
                const toBlockquote = (text) => {
                    if (!text) return '> N/A';
                    return text.split('\n').map(l => `> ${l}`).join('\n');
                };

                const desc = `### AI Analysis

**Root Cause**
${toBlockquote(currentCluster.common_root_cause)}

**Suggestion**
${toBlockquote(currentCluster.common_solution)}

**Impact Analysis**
* **Severity**: ${currentCluster.severity || 'Medium'}
* **Impact**: ${uniqueCount} unique test case(s) across ${totalCount} failure events (Cluster ID: #${currentCluster.id})

---

### Environment

* **Product**: ${currentRunDetails?.build_product || 'N/A'}
* **Build ID**: ${currentRunDetails?.build_id || 'N/A'}
* **Fingerprint**: ${currentRunDetails?.device_fingerprint || 'N/A'}
* **Suite Version**: ${currentRunDetails?.test_suite_name || 'N/A'}

---

### Technical Details

**Stack Trace Signature**
\`\`\`text
${currentCluster.signature || 'N/A'}
\`\`\`

**Representative Stack Trace**
\`\`\`java
${truncatedStack}
\`\`\`

### Affected Tests (Top 50)
${failureList || 'No failure details available.'}
${moreCount > 0 ? `\n... and ${moreCount} more` : ''}
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
            const data = await res.json();
            const userList = data.users || [];
            assigneeSelect.innerHTML = '<option value="">Unassigned</option>';
            userList.forEach(user => {
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
        redmineProjectsCache = projects.projects || []; // Update cache (Extract from response wrapper)
        console.log("Loaded Redmine Projects:", redmineProjectsCache);

        const select = document.getElementById('redmine-project');
        if (!select) return;

        select.innerHTML = redmineProjectsCache.length > 0
            ? redmineProjectsCache.map(p => `<option value="${p.id}">${p.name}</option>`).join('')
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

    // Check if configuration is loaded, if not try to load it
    if (!currentModuleOwnerMapConfig) {
        try {
            await loadModuleOwnerMap();
        } catch (e) {
            console.error("Failed to load module map on open modal", e);
        }
    }

    // Check if configuration has defaults
    const defaults = currentModuleOwnerMapConfig?.default_settings;
    if (!defaults || !defaults.default_project_id) {
        showAlertModal('Please configure a Target Project in Settings > Module Owner Assignment first.');
        return;
    }

    modal.classList.remove('hidden');

    // Display project info
    const label = document.getElementById('bulk-confirm-project');
    if (label) {
        // Try to find project name from cache if available, else show ID
        const pid = defaults.default_project_id;
        let pName = `ID: ${pid}`;
        
        // Optimistically check cache if empty try loading once
        if (redmineProjectsCache.length === 0) {
             try { await loadRedmineProjects(); } catch(e) {}
        }
        
        const proj = redmineProjectsCache.find(p => p.id == pid);
        if (proj) pName = proj.name;
        
        label.textContent = pName;
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
    const button = document.getElementById('btn-execute-bulk');
    const status = document.getElementById('bulk-create-status');

    const defaults = currentModuleOwnerMapConfig?.default_settings;
    if (!defaults || !defaults.default_project_id) {
        showAlertModal('Missing Target Project configuration. Configure in Settings first.');
        return;
    }
    
    const projectId = defaults.default_project_id;
    // Always create children for bulk actions as per new flow
    const createChildren = true; 

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

// --- Unified Sync Logic with Custom Modal (PRD Phase 5) ---

// Modal Helper
async function showRedmineSyncModal(stats, onConfirm) {
    const modal = document.getElementById('redmine-sync-modal');
    if (!modal) {
        console.error("Redmine sync modal not found in DOM");
        // Fallback to native confirm if modal missing
        if (confirm(`Sync ${stats.count} issues for module ${stats.moduleName}?`)) {
            onConfirm();
        }
        return;
    }

    const urlSpan = document.getElementById('sync-modal-url');
    const projectSpan = document.getElementById('sync-modal-project');
    const moduleSpan = document.getElementById('sync-modal-module');
    const countSpan = document.getElementById('sync-modal-count');
    const confirmBtn = document.getElementById('btn-confirm-sync');
    const cancelBtn = document.getElementById('btn-cancel-sync');

    // Populate Data
    if (urlSpan) urlSpan.textContent = redmineBaseUrl || 'Not configured';

    // Ensure cache is loaded
    if (redmineProjectsCache.length === 0) {
        await loadRedmineProjects();
    }
    
    // Find project name if possible, or show ID
    if (projectSpan) {
        const project = redmineProjectsCache.find(p => p.id == stats.projectId);
        projectSpan.textContent = project ? project.name : (stats.projectId || 'Default');
    }
    
    if (moduleSpan) moduleSpan.textContent = stats.moduleName;
    if (countSpan) countSpan.textContent = stats.count;

    // Show Modal
    modal.classList.remove('hidden');

    // Button Handlers
    const close = () => {
        modal.classList.add('hidden');
        // Cleanup listeners
        if (confirmBtn) confirmBtn.onclick = null;
        if (cancelBtn) cancelBtn.onclick = null;
    };

    if (confirmBtn) {
        confirmBtn.onclick = () => {
            close();
            onConfirm();
        };
    }

    if (cancelBtn) {
        cancelBtn.onclick = () => {
            close();
        };
    }
}

// Unified Sync Function (Replaces batchSyncModule)
async function syncModule(moduleName) {
    // 1. Calculate stats (Count unsynced clusters for this module)
    const runId = router.currentParams.id;
    if (!runId) {
        showNotification('No test run selected', 'error');
        return;
    }

    // Filter clusters for this module that are NOT already synced
    // Note: Clusters have a 'module_names' array, not a single 'module_name'
    const clustersToSync = allClustersData.filter(c => {
        const hasModule = c.module_names && c.module_names.includes(moduleName);
        const unsynced = !c.redmine_issue_id;
        return hasModule && unsynced;
    });

    if (clustersToSync.length === 0) {
        console.warn(`No unsynced clusters found for module: "${moduleName}"`);
        showNotification(`No unsynced clusters found for module "${moduleName || 'Unknown'}".`, 'warning');
        return;
    }

    // 2. Validate Target Project ID
    const defaults = currentModuleOwnerMapConfig?.default_settings;
    if (!defaults || !defaults.default_project_id) {
        showAlertModal('Missing Target Project configuration. Please configure it in Settings > Module Owner Assignment first.');
        return;
    }
    const defaultProjectId = defaults.default_project_id;

    // 3. Show Custom Modal
    console.log("Showing Redmine Sync Modal for module:", moduleName);
    await showRedmineSyncModal({
        moduleName: moduleName,
        count: clustersToSync.length,
        projectId: defaultProjectId,
        url: redmineBaseUrl
    }, async () => {
        // 4. Actual Sync Logic (On Confirm)
        console.log("User confirmed sync for module:", moduleName);
        
        // Find the button to show loading state (search for both syncModule and batchSyncModule for safety)
        const btns = document.querySelectorAll(`button`);
        let targetBtn = null;
        for (let b of btns) {
            const onClickStr = b.getAttribute('onclick') || '';
            if (onClickStr.includes(`syncModule('${moduleName}')`) || onClickStr.includes(`batchSyncModule('${moduleName}')`)) {
                targetBtn = b;
                break;
            }
        }

        const originalContent = targetBtn ? targetBtn.innerHTML : '';
        if (targetBtn) {
            targetBtn.innerHTML = `<svg class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`;
            targetBtn.disabled = true;
        }

        showNotification(`Syncing clusters for ${moduleName}...`, 'info');

        try {
            console.log("Sending sync request to API...");
            const res = await fetch(`${API_BASE}/integrations/redmine/smart-bulk-create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    run_id: parseInt(runId),
                    project_id: defaultProjectId,
                    module_name: moduleName  // Filter to only this module
                })
            });

            console.log("API Response status:", res.status);
            const result = await res.json();
            console.log("API Response body:", result);

            if (res.ok) {
                const createdCount = result.created || 0;
                
                if (createdCount > 0) {
                    showNotification(`✅ Successfully created ${createdCount} issues for ${moduleName}`, 'success');
                } else {
                    showNotification(`ℹ️ No new issues created (checked ${clustersToSync.length} clusters)`, 'info');
                }
                
                // Reload data to reflect changes
                setTimeout(async () => {
                    await loadClusters(runId);
                }, 300);
            } else {
                console.error("Sync failed:", result);
                showNotification(`❌ Sync failed: ${result.detail || 'Unknown error'}`, 'error');
            }
        } catch (e) {
            console.error("Sync error exception", e);
            showNotification(`❌ Error: ${e.message}`, 'error');
        } finally {
            if (targetBtn) {
                targetBtn.innerHTML = originalContent;
                targetBtn.disabled = false;
            }
        }
    });
}

// Alias for backward compatibility if needed
const batchSyncModule = syncModule;

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
    
    // Handle edge cases
    if (!data || data.length < 2) {
        // Render a flat line if insufficient data
        data = [0, 0];
    }

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

async function loadTestCase(testCaseId) {
    try {
        const res = await fetch(`${API_BASE}/reports/test-cases/${testCaseId}`);
        if (!res.ok) throw new Error('Test case not found');
        
        const tc = await res.json();
        
        document.getElementById('tc-name').textContent = `${tc.class_name}.${tc.method_name}`;
        document.getElementById('tc-module').textContent = tc.module_name || 'Unknown Module';
        document.getElementById('tc-run-id').textContent = tc.test_run_id;
        document.getElementById('tc-run-link').onclick = (e) => {
            e.preventDefault();
            router.navigate('run-details', { id: tc.test_run_id });
        };
        
        document.getElementById('tc-error').textContent = tc.error_message || 'No error message';
        document.getElementById('tc-stack').innerHTML = highlightStackTrace(tc.stack_trace || '');
        
        const analysisCard = document.getElementById('tc-analysis-card');
        if (tc.failure_analysis) {
            analysisCard.classList.remove('hidden');
            const fa = tc.failure_analysis;
            
            if (fa.cluster_id) {
                document.getElementById('tc-cluster-id').textContent = fa.cluster_id;
                document.getElementById('tc-cluster-link').onclick = (e) => {
                    e.preventDefault();
                    router.navigate('run-details', { id: tc.test_run_id });
                };
            }
            
            document.getElementById('tc-root-cause').innerHTML = formatMultilineText(fa.root_cause || '-');
            document.getElementById('tc-solution').innerHTML = formatMultilineText(fa.suggested_solution || '-');
        } else {
             analysisCard.classList.add('hidden');
        }
        
    } catch (e) {
        console.error("Failed to load test case", e);
        document.getElementById('app-content').innerHTML = `
            <div class="text-center py-20">
                <div class="text-xl font-bold text-slate-800">Test Case Not Found</div>
                <div class="text-slate-500 mt-2">${e.message}</div>
                <button onclick="router.navigate('dashboard')" class="mt-6 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Go to Dashboard
                </button>
            </div>
        `;
    }
}


// --- Submissions Logic ---

// Current submission being viewed
let currentSubmissionId = null;
let currentSubmissionPage = 1;

// Selection State
let isRunSelectionMode = false;
let selectedRunIds = new Set();

// Required suites for compliance matrix
// Required suites for compliance matrix (Dynamic)
let REQUIRED_SUITES = [];
let SUITE_CONFIGS = {};

async function fetchSuiteConfig() {
    if (REQUIRED_SUITES.length > 0) return;
    try {
        const res = await fetch(`${API_BASE}/config/suites`);
        if (!res.ok) throw new Error("Failed to load suite config");
        const configs = await res.json();
        
        if (configs && configs.length === 0) {
            console.warn("Server returned empty suite config, using fallback defaults.");
            throw new Error("Empty config");
        }
        
        REQUIRED_SUITES = configs.map(c => c.name);
        SUITE_CONFIGS = {};
        configs.forEach(c => SUITE_CONFIGS[c.name] = c);
        console.log("Loaded suites:", REQUIRED_SUITES);
    } catch(e) {
        console.error("Failed to fetch suite config, using fallback", e);
        // Fallback
        REQUIRED_SUITES = ['CTS', 'CTSonGSI', 'VTS', 'GTS', 'STS'];
        SUITE_CONFIGS = {};
        REQUIRED_SUITES.forEach(name => {
            SUITE_CONFIGS[name] = { name: name, display_name: name, match_rule: 'Standard' };
        });
    }
}

async function loadProducts() {
    try {
        const response = await fetch(`${API_BASE}/submissions/products`);
        const products = await response.json();
        const container = document.getElementById('sidebar-products');
        
        if (!container) return; // Not on page with sidebar

        if (!products || products.length === 0) {
            container.innerHTML = `<div class="px-4 py-2 text-xs text-slate-500 italic">No projects found</div>`;
            return;
        }

        let html = `
            <a href="#" onclick="filterByProduct(null)" 
               class="nav-item group flex items-center gap-3 px-4 py-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-all duration-200 ${currentProductFilter === null ? 'bg-white/10 text-white font-bold' : ''}">
                <span class="w-2 h-2 rounded-full bg-slate-500"></span>
                All Projects
            </a>
        `;
        
        products.forEach(p => {
            const isActive = currentProductFilter === p;
            let hash = 0;
            for (let i = 0; i < p.length; i++) hash = p.charCodeAt(i) + ((hash << 5) - hash);
            const hue = Math.abs(hash % 360);
            const colorStyle = `background-color: hsl(${hue}, 70%, 50%)`;
            
            html += `
                <a href="#" onclick="filterByProduct('${p}')" 
                   class="nav-item group flex items-center gap-3 px-4 py-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-all duration-200 ${isActive ? 'bg-white/10 text-white font-bold' : ''}">
                    <span class="w-2 h-2 rounded-full" style="${colorStyle}"></span>
                    ${p}
                </a>
            `;
        });
        container.innerHTML = html;
    } catch (e) {
        console.error("Failed to load products", e);
    }
}

function filterByProduct(product) {
    currentProductFilter = product;
    loadProducts(); // Update Sidebar active state
    // Reload submissions
    if (window.location.hash.includes('submission')) {
         // If detail view, back to list
         router.navigate('submissions'); 
    } else {
         loadSubmissions(1);
    }
}

async function loadSubmissions(page = 1) {
    currentSubmissionPage = page;
    await fetchSuiteConfig();
    const grid = document.getElementById('submissions-grid');
    const emptyState = document.getElementById('submissions-empty');
    const pagination = document.getElementById('submissions-pagination');
    
    if (!grid) return;
    
    // Clear pagination while loading to avoid confusion
    if (pagination) pagination.innerHTML = ''; 
    
    // Show loading skeleton (Apple Style)
    grid.innerHTML = `
        ${[1, 2, 3].map(() => `
            <div class="bg-white rounded-[20px] shadow-sm border border-slate-100 p-6 relative overflow-hidden">
                <div class="flex justify-between items-start mb-4">
                    <div class="space-y-2 w-2/3">
                        <div class="h-5 w-3/4 skeleton rounded-md"></div>
                        <div class="h-3 w-full skeleton rounded-md opacity-60"></div>
                    </div>
                    <div class="h-6 w-20 skeleton rounded-full"></div>
                </div>
                <div class="flex gap-3 mb-4 overflow-hidden">
                    ${[1,2,3,4,5].map(() => `<div class="h-16 w-16 skeleton rounded-2xl flex-shrink-0"></div>`).join('')}
                </div>
                <div class="h-3 w-24 skeleton rounded-md mt-auto opacity-50"></div>
            </div>
        `).join('')}
    `;
    
    try {
        const limit = 20;
        const skip = (page - 1) * limit;
        
        let url = `${API_BASE}/submissions/?skip=${skip}&limit=${limit}`;
        if (currentProductFilter) {
            url += `&product_filter=${encodeURIComponent(currentProductFilter)}`;
        }
        
        const response = await fetch(url);
        const res = await response.json();
        
        // Support both envelope and legacy array (though backend is updated)
        const submissions = res.items || (Array.isArray(res) ? res : []);
        const total = res.total || submissions.length;
        
        if (submissions.length === 0 && page === 1) {
            grid.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }
        
        emptyState.classList.add('hidden');
        grid.innerHTML = submissions.map(sub => renderSubmissionCardV2(sub)).join('');
        
        // Render Pagination
        renderPagination(total, page, limit);
        
        // Scroll to top of grid
        if (page > 1) {
             document.getElementById('submissions-header')?.scrollIntoView({ behavior: 'smooth' });
        }
        
    } catch (e) {
        console.error("Failed to load submissions", e);
        grid.innerHTML = `<div class="col-span-full text-center text-red-500 py-8">Failed to load submissions</div>`;
    }
}

function renderPagination(total, page, pageSize) {
    const container = document.getElementById('submissions-pagination');
    if (!container) return;
    
    const totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = `
        <div class="flex items-center gap-2 bg-white rounded-full p-1 shadow-sm border border-slate-100">
            <button onclick="loadSubmissions(${page - 1})" 
                class="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-slate-600"
                ${page <= 1 ? 'disabled' : ''}>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
            </button>
            
            <div class="px-3 text-xs font-medium text-slate-500 font-mono">
                ${page} / ${totalPages}
            </div>
            
            <button onclick="loadSubmissions(${page + 1})" 
                class="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-slate-600"
                ${page >= totalPages ? 'disabled' : ''}>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
            </button>
        </div>
    `;
}

function renderSubmissionCard(sub) {
    // Status styling
    const statusStyles = {
        draft: { gradient: 'status-gradient-draft', badge: 'bg-slate-100 text-slate-600' },
        analyzing: { gradient: 'status-gradient-analyzing', badge: 'bg-amber-100 text-amber-700 animate-pulse' },
        ready: { gradient: 'status-gradient-ready', badge: 'bg-emerald-100 text-emerald-700' },
        published: { gradient: 'status-gradient-published', badge: 'bg-blue-100 text-blue-700' }
    };
    const style = statusStyles[sub.status] || statusStyles.draft;
    
    // Format date (Friendly)
    const dateStr = formatFriendlyDate(sub.updated_at);
    
    // Mini suite indicators
    const suitesHtml = REQUIRED_SUITES.map(suite => {
        const suiteData = sub.suite_summary?.[suite] || { status: 'missing' };
        
        let bgClass, textClass, displayValue;
        if (suiteData.status === 'pass') {
            bgClass = 'bg-emerald-50';
            textClass = 'text-emerald-700'; // Darker for contrast
            displayValue = '✓';
        } else if (suiteData.status === 'fail') {
            bgClass = 'bg-white border border-red-100'; // Cleaner look
            textClass = 'text-red-600';
            displayValue = suiteData.failed;
        } else {
            bgClass = 'bg-slate-50';
            textClass = 'text-slate-300';
            displayValue = '-';
        }
        
        return `
            <div class="flex flex-col items-center justify-center p-2 rounded-lg ${bgClass} min-w-[60px] flex-1">
                <div class="text-[9px] font-bold uppercase tracking-wider ${textClass} mb-0.5">${suite}</div>
                <div class="text-sm font-bold ${textClass}">${displayValue}</div>
            </div>
        `;
    }).join('');
    
    return `
        <div class="submission-card bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden cursor-pointer hover:shadow-md transition-shadow duration-200"
             onclick="router.navigate('submission-detail', { id: ${sub.id} })">
            
            <div class="p-5">
                <!-- Header: Name & Status Badge -->
                <div class="flex justify-between items-start mb-3">
                    <div class="flex-1 min-w-0 pr-3">
                        <h3 class="font-bold text-slate-800 text-base truncate leading-tight">
                            <span class="text-slate-400 font-mono text-xs mr-1 opacity-75">#${sub.id}</span>
                            ${escapeHtml(sub.name || 'Unnamed Submission')}
                        </h3>
                        <!-- Darker contrast for fingerprint, mono font -->
                        <div class="mt-1.5 flex items-center">
                             <code class="text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100 truncate max-w-full font-mono">
                                ${escapeHtml(sub.target_fingerprint || '-')}
                             </code>
                        </div>
                    </div>
                    <span class="${style.badge} px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider flex-shrink-0 shadow-sm border border-transparent">
                        ${sub.status || 'draft'}
                    </span>
                </div>
                
                <!-- Compliance Matrix Mini View: Moved to Flex Wrap for better rhythm -->
                <div class="flex flex-wrap gap-2 mb-4">
                    ${suitesHtml}
                </div>
                
                <!-- Footer: Meta Info -->
                <div class="flex items-center justify-between text-[11px] text-slate-400 font-medium pt-3 border-t border-slate-50">
                    <span class="flex items-center gap-1.5 ">
                        <svg class="w-3.5 h-3.5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2"/>
                        </svg>
                        ${sub.run_count || 0} runs
                    </span>
                    <span>${dateStr}</span>
                </div>
            </div>
        </div>
    `;
}

// Global state for analysis filter
let currentAnalysisSuiteFilter = 'All';

async function loadSubmissionDetail(id) {
    await fetchSuiteConfig();
    currentSubmissionId = id;
    currentAnalysisSuiteFilter = 'All'; // Reset filter on load

    
    const nameEl = document.getElementById('submission-name');
    const statusBadge = document.getElementById('submission-status-badge');
    const statusBar = document.getElementById('submission-status-bar');
    const fingerprintEl = document.getElementById('submission-fingerprint');
    const dateEl = document.getElementById('submission-date');
    const statusControl = document.getElementById('submission-status-control');
    const matrixEl = document.getElementById('compliance-matrix');
    const runsListEl = document.getElementById('submission-runs-list');
    const runsEmptyEl = document.getElementById('submission-runs-empty');
    
    // Show loading state
    if (nameEl) nameEl.textContent = 'Loading...';
    if (matrixEl) matrixEl.innerHTML = `
        <div class="col-span-4 flex justify-center py-8">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/submissions/${id}`);
        if (!response.ok) throw new Error('Submission not found');
        const sub = await response.json();
        currentSubmissionDetails = sub;
        
        // Render Compliance Matrix
        renderComplianceMatrix(sub);
        
        // Status styling
        const statusStyles = {
            draft: { gradient: 'status-gradient-draft', badge: 'bg-slate-100 text-slate-600' },
            analyzing: { gradient: 'status-gradient-analyzing', badge: 'bg-amber-100 text-amber-700 animate-pulse' },
            ready: { gradient: 'status-gradient-ready', badge: 'bg-emerald-100 text-emerald-700' },
            published: { gradient: 'status-gradient-published', badge: 'bg-blue-100 text-blue-700' }
        };
        const style = statusStyles[sub.status] || statusStyles.draft;
        
        // Update header
        if (nameEl) {
            nameEl.innerHTML = `
                <span class="text-slate-300 font-display font-light mr-3 text-3xl">#${sub.id}</span>
                <span class="text-3xl font-display font-bold text-slate-900 tracking-tight">${escapeHtml(sub.name || 'Unnamed Submission')}</span>
            `;
        }

        
        const editBtn = document.getElementById('btn-edit-submission');
        if (editBtn) {
            editBtn.onclick = () => editSubmissionName(sub.name || 'Unnamed Submission');
        }

        if (statusBadge) {
            statusBadge.textContent = sub.status || 'draft';
            statusBadge.className = `${style.badge} px-3 py-1 rounded-full text-xs font-bold uppercase`;
        }
        if (statusBar) {
            statusBar.className = `absolute top-0 left-0 w-full h-1.5 ${style.gradient}`;
        }
        if (fingerprintEl) {
            // Apply refined Apple-style pill processing
            const fp = sub.target_fingerprint || '-';
            // User requested full display, so removed truncation
            
            fingerprintEl.textContent = fp;
            fingerprintEl.title = "Click to copy"; // Tooltip
            
            // Add click-to-copy implicit behavior
            fingerprintEl.parentElement.onclick = copyFingerprint;
            fingerprintEl.parentElement.className = "group flex items-center gap-2 px-3 py-1.5 bg-slate-100/50 hover:bg-slate-100 text-slate-500 rounded-full transition-all cursor-pointer border border-transparent hover:border-slate-200 select-none max-w-full";
            fingerprintEl.className = "font-mono text-xs truncate"; // Ensure it respects container but tries to show all
            // Actually, remove truncate if we want full wrap, or keep truncate if we want it to fit?
            // "please make sure display the full fingerprint info" implies NO truncation.
            fingerprintEl.className = "font-mono text-xs break-all"; 
        }
        if (dateEl) dateEl.textContent = formatFriendlyDate(sub.created_at || sub.updated_at);
        
        // Update Lock State
        // Update Lock State
        const lockBtn = document.getElementById('btn-lock-toggle');
        const lockLabel = document.getElementById('lock-label');
        const lockHelper = document.getElementById('lock-helper-text');
        
        if (lockBtn && lockLabel) {
            const isLocked = !!sub.is_locked;
            lockBtn.setAttribute('aria-checked', isLocked);
            lockLabel.textContent = isLocked ? 'Locked' : 'Active';
            lockLabel.className = `text-xs font-semibold uppercase tracking-wider transition-colors duration-300 ${isLocked ? 'text-emerald-600' : 'text-slate-500'}`;
            
            if (lockHelper) {
                lockHelper.textContent = isLocked ? 'Session Frozen' : 'Accepting Reruns';
                lockHelper.className = `text-[9px] font-medium transition-colors duration-300 ${isLocked ? 'text-emerald-500' : 'text-slate-400'}`;
            }
        }
        
        // Update status control
        if (statusControl) {
            statusControl.querySelectorAll('.segmented-item').forEach(btn => {
                const btnStatus = btn.dataset.status;
                if (btnStatus === sub.status) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
        
        // Render Warnings (Phase 3 Intelligence)
        renderSubmissionWarnings(sub.warnings || []);
        
        // Render Compliance Matrix

        
        // Render Test Runs List
        renderSubmissionRuns(runsListEl, runsEmptyEl, sub.test_runs || [], sub.target_fingerprint);
        
        // Load Consolidated Report
        loadConsolidatedReport(id);
        
        // Load AI Analysis
        loadSubmissionAnalysis(id);
        
        // Ensure UI state matches default tab
        switchSubmissionTab('consolidated');
        
    } catch (e) {
        console.error("Failed to load submission detail", e);
        if (nameEl) nameEl.textContent = 'Error loading submission';
    }
}

function renderSubmissionWarnings(warnings) {
    const container = document.getElementById('submission-warnings');
    if (!container) return;
    
    if (!warnings || warnings.length === 0) {
        container.classList.add('hidden');
        container.innerHTML = '';
        return;
    }
    
    container.classList.remove('hidden');
    
    // Generate HTML with opacity-0 for animation
    container.innerHTML = warnings.map((w, index) => {
        const isError = w.severity === 'error';
        const bgClass = isError ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200';
        const iconColor = isError ? 'text-red-500' : 'text-amber-500';
        const textColor = isError ? 'text-red-800' : 'text-amber-800';
        
        const icon = isError 
            ? `<svg class="w-5 h-5 ${iconColor}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                       d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
               </svg>`
            : `<svg class="w-5 h-5 ${iconColor}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                       d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
               </svg>`;
        
        // Add animation delay based on index
        const animationStyle = `style="animation: slideDown 0.3s ease-out ${index * 0.1}s forwards; opacity: 0; transform: translateY(-10px);"`;
        
        return `
            <div class="flex items-start gap-3 px-4 py-3 rounded-2xl border-l-4 ${bgClass.replace('border', 'shadow-sm bg-opacity-60 backdrop-blur-md')}" ${animationStyle}>
                <div class="mt-0.5">${icon}</div>
                <div class="flex-1">
                     <h4 class="text-sm font-bold ${textColor} mb-0.5">${isError ? 'Action Required' : 'Notice'}</h4>
                     <p class="text-xs font-medium ${textColor} opacity-90 leading-relaxed">${escapeHtml(w.message)}</p>
                </div>
            </div>
        `;
    }).join('');
}

function copyFingerprint() {
    const text = document.getElementById('submission-fingerprint').innerText;
    if (text && text !== '-') {
        navigator.clipboard.writeText(text).then(() => {
            // Show toast or subtle feedback
            const btn = document.querySelector('button[onclick="copyFingerprint()"]');
            const originalHtml = btn.innerHTML;
            
            // Temporary checkmark
            btn.innerHTML = `
                <svg class="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
            `;
            
            setTimeout(() => {
                btn.innerHTML = originalHtml;
            }, 2000);
        });
    }
}



// Helper to identify which suite a run belongs to (considering GSI rules)
// Helper to identify which suite a run belongs to (considering GSI rules)
function identifyRunSuite(run, targetFingerprint) {
    const runName = (run.test_suite_name || '').toUpperCase();
    const plan = (run.suite_plan || '').toLowerCase();
    
    // Check against all configured suites in order
    for (const suiteName of REQUIRED_SUITES) {
        const config = SUITE_CONFIGS[suiteName];
        if (!config) continue;
        
        // Backend now returns device_product / device_model
        // Use those or fallback to build_product if available (though backend sends device_product)
        const product = (run.device_product || run.build_product || '').toLowerCase();
        const model = (run.device_model || run.build_model || '').toLowerCase();
        
        // GSI Detection Logic
        const isGsiPlan = plan.includes('cts-on-gsi');
        const hasGsiTag = product.includes('gsi') || model.includes('gsi');
        
        let isMatch = false;
        
        if (config.match_rule === 'GSI') {
             // 1. Plan Name (Strongest) or 2. Product/Model Tag
             // We REMOVED fingerprint mismatch check to avoid misclassifying Native runs 
             // when the submission target happens to be the GSI fingerprint.
             const isGsi = isGsiPlan || hasGsiTag;
             
             isMatch = runName.includes('CTS') && isGsi;
        
        } else if (config.name === 'CTS') {
             // Standard CTS: Matches CTS AND NOT GSI
             const isGsi = isGsiPlan || hasGsiTag;
             
             isMatch = runName.includes('CTS') && !isGsi;
        } else {
             isMatch = runName.includes(suiteName);
        }
        
        if (isMatch) return suiteName;
    }
    
    return run.test_suite_name; // Fallback
}

// --- Submission AI Analysis Logic ---

function switchSubmissionTab(tabName) {
    // Buttons
    ['consolidated', 'runs', 'analysis'].forEach(t => {
        const btn = document.getElementById(`sub-tab-btn-${t}`);
        if (btn) {
            if (t === tabName) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    });
    
    // Content
    ['sub-tab-consolidated', 'sub-tab-runs', 'sub-tab-analysis'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (id === `sub-tab-${tabName}`) el.classList.remove('hidden');
            else el.classList.add('hidden');
        }
    });
}

async function loadSubmissionAnalysis(subId, suiteFilter = null) {
    if (suiteFilter) {
        currentAnalysisSuiteFilter = suiteFilter;
    } else {
        suiteFilter = currentAnalysisSuiteFilter;
    }
    
    const container = document.getElementById('submission-analysis-content');
    // Optional: Show loading state inside content if switching tabs
    // if (container) container.classList.add('opacity-50', 'pointer-events-none');

    try {
        // 1. Fetch Report (Static) for Summary/Risks (Global Context)
        const reportRes = await fetch(`${API_BASE}/reports/submissions/${subId}/analysis`);
        let report = reportRes.ok ? await reportRes.json() : {};

        // 2. Fetch Live Clusters (Filtered)
        const query = suiteFilter !== 'All' ? `?suite_filter=${encodeURIComponent(suiteFilter)}` : '';
        const clustersRes = await fetch(`${API_BASE}/analysis/submission/${subId}/clusters${query}`);
        const clusters = clustersRes.ok ? await clustersRes.json() : [];

        // 3. Merge Data
        // If we found live clusters, use them. 
        // We override the static report's clusters with the live, filtered ones.
        const data = {
            ...report,
            analyzed_clusters: clusters
        };
        console.log("Loaded Analysis Data:", data); // Debug link
        
        // Re-calculate local stats for the view if needed (Severity Score etc.)
        // For now, we rely on the global score or just display what we have.
        // Ideally, we should recalculate the top breakdown based on filtered valid clusters.

        if (data) {
            renderSubmissionAnalysis(data);
        } else {
            renderSubmissionAnalysis(null); 
        }

    } catch (e) {
        console.error("Failed to load analysis", e);
    } finally {
        // if (container) container.classList.remove('opacity-50', 'pointer-events-none');
    }
}

async function triggerSubmissionAnalysis(subId) {
    const btn = document.querySelector('button[onclick^="triggerSubmissionAnalysis"]');
    const originalText = btn ? btn.innerHTML : 'Analyze';
    
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            Analyzing...
        `;
    }
    
    try {
        showNotification('AI Analysis started... request sent.', 'info');
        const response = await fetch(`${API_BASE}/reports/submissions/${subId}/analyze`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Analysis request failed');
        
        await response.json();
        
        // Poll for completion of background clustering tasks
        if (btn) btn.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            Processing Clusters...
        `;
        
        await pollSubmissionClustering(subId);

        // Reload full data to ensure we get proper DB clusters with IDs
        await loadSubmissionAnalysis(subId);
        showNotification('Analysis Complete!', 'success');
        
    } catch (e) {
        console.error(e);
        showNotification('Analysis failed. Please try again.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

async function pollSubmissionClustering(subId) {
    const maxRetries = 60; // 2 minutes (2s interval)
    let retries = 0;
    
    while (retries < maxRetries) {
        try {
            const res = await fetch(`${API_BASE}/submissions/${subId}`);
            if (!res.ok) break;
            const sub = await res.json();
            
            const runs = sub.test_runs || [];
            if (runs.length === 0) return; 
            
            // Check if ANY run is still analyzing
            const pending = runs.some(r => r.analysis_status === 'analyzing' || r.analysis_status === 'pending');
            
            if (!pending) {
                return; // All done!
            }
        } catch (e) {
            console.warn("Polling error", e);
        }
        
        // Wait 2s
        await new Promise(r => setTimeout(r, 2000));
        retries++;
    }
    console.warn("Polling timed out, proceeding with available data");
}


// Helper for Submission Analysis Click
function showSubmissionClusterDetail(clusterId) {
    if (!allClustersData || allClustersData.length === 0) {
        console.error("[showSubmissionClusterDetail] allClustersData is empty");
        showNotification("Error: Cluster data not loaded properly.", "error");
        return;
    }
    const cluster = allClustersData.find(c => c.id === clusterId);
    if (cluster) {
        showClusterDetail(cluster);
    } else {
        console.error("[showSubmissionClusterDetail] Cluster not found:", clusterId);
    }
}

function renderSubmissionAnalysis(data) {
    const emptyState = document.getElementById('submission-analysis-empty');
    const contentState = document.getElementById('submission-analysis-content');
    
    // Store clusters globally for detail view lookup
    if (data && data.analyzed_clusters) {
        allClustersData = data.analyzed_clusters;
        // Group by Module for Module View
        allModulesData = groupClustersByModule(allClustersData);
    }

    if (!data && !data.analyzed_clusters) {
        if (emptyState) emptyState.classList.remove('hidden');
        if (contentState) contentState.classList.add('hidden');
        return;
    }
    
    if (emptyState) emptyState.classList.add('hidden');
    if (contentState) contentState.classList.remove('hidden');
    
    // 0. Render Suite Tabs (New Feature)
    // We inject this before the Executive Summary
    let tabsHeader = document.getElementById('analysis-suite-tabs');
    if (!tabsHeader) {
        tabsHeader = document.createElement('div');
        tabsHeader.id = 'analysis-suite-tabs';
        tabsHeader.className = 'flex items-center gap-2 mb-6 border-b border-slate-200 pb-1';
        
        // Insert before the KPI grid (first child of contentState)
        contentState.insertBefore(tabsHeader, contentState.firstChild);
    }
    
    const availableSuites = detectAvailableSuites(currentSubmissionDetails);
    tabsHeader.innerHTML = availableSuites.map(suite => {
        const isActive = currentAnalysisSuiteFilter === suite;
        const activeClass = "text-indigo-600 border-b-2 border-indigo-600 font-bold bg-indigo-50/50";
        const inactiveClass = "text-slate-500 hover:text-slate-700 hover:bg-slate-50 border-b-2 border-transparent font-medium";
        
        return `
            <button onclick="loadSubmissionAnalysis(${currentSubmissionId}, '${suite}')" 
                class="px-4 py-2 text-sm rounded-t-lg transition-all duration-200 ${isActive ? activeClass : inactiveClass}">
                ${suite}
            </button>
        `;
    }).join('');

    // Re-calculate KPI metrics based on filtered clusters if we are filtering
    const clusters = data.analyzed_clusters || [];
    let highVal = 0, medVal = 0;
    clusters.forEach(c => {
        if(c.severity === 'High') highVal++;
        else if(c.severity === 'Medium') medVal++;
    });
    
    // Heuristic Score recalculation (simple version)
    // If filtering, calculate local severity. If All, use report score or recalc.
    // Score = 0 (perfect) to 100 (bad). 
    // High = 10pts, Med = 5pts. Cap at 100.
    const calculatedScore = Math.min((highVal * 10) + (medVal * 3), 100);
    const score = data.severity_score !== undefined && currentAnalysisSuiteFilter === 'All' ? data.severity_score : calculatedScore;

    // 1. Severity Score UI
    const scoreEl = document.getElementById('sub-kpi-severity');
    const scoreBar = document.getElementById('sub-kpi-severity-bar');
    const scoreLabel = document.getElementById('sub-kpi-severity-label');
    
    if (scoreEl) scoreEl.textContent = score;
    if (scoreBar) {
        scoreBar.style.width = `${score}%`;
        scoreBar.className = `h-full rounded-full transition-all duration-1000 ${
            score < 20 ? 'bg-emerald-500' : 
            score < 50 ? 'bg-yellow-500' : 
            score < 80 ? 'bg-orange-500' : 'bg-red-600'
        }`;
    }
    if (scoreLabel) {
        let labelText = 'Unknown';
        if (score < 20) labelText = 'Excellent Stability';
        else if (score < 50) labelText = 'Monitor closely';
        else if (score < 80) labelText = 'Significant Issues';
        else labelText = 'Critical State';
        scoreLabel.textContent = labelText;
    }
    
    // 2. Executive Summary (Only show if ALL, or static)
    // 2. Executive Summary (Only show if ALL, or static)
    const summaryEl = document.getElementById('sub-ai-summary');
    const summaryCard = document.getElementById('card-executive-summary');
    if (summaryEl) {
        if (currentAnalysisSuiteFilter === 'All') {
            if (summaryCard) summaryCard.classList.remove('hidden');
            summaryEl.innerHTML = formatMultilineText(data.executive_summary || 'No summary available.');
        } else {
            // Hide the entire card for suite-specific views to avoid confusion
            if (summaryCard) summaryCard.classList.add('hidden');
        }
    }
    
    // 3. Top Risks
    // 3. Top Risks
    const risksEl = document.getElementById('sub-ai-risks');
    const risksCard = document.getElementById('card-top-risks');
    if (risksEl) {
        if (currentAnalysisSuiteFilter === 'All') {
            if (risksCard) risksCard.classList.remove('hidden');
             const risks = data.top_risks || [];
            if (risks.length === 0) {
                risksEl.innerHTML = '<li class="text-sm text-slate-400 italic">No significant risks identified.</li>';
            } else {
                risksEl.innerHTML = risks.map(risk => `
                    <li class="flex items-start gap-2 text-sm text-slate-700">
                        <span class="mt-1.5 w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
                        <span>${risk}</span>
                    </li>
                `).join('');
            }
        } else {
             // Hide card
             if (risksCard) risksCard.classList.add('hidden');
        }
    }
    
    // 4. Recommendations
    // 4. Recommendations
    const recsEl = document.getElementById('sub-ai-recommendations');
    const recsCard = document.getElementById('card-recommendations');
    if (recsEl) {
         if (currentAnalysisSuiteFilter === 'All') {
            if (recsCard) recsCard.classList.remove('hidden');
            const recs = data.recommendations || [];
            if (recs.length === 0) {
                recsEl.innerHTML = '<li class="text-sm text-slate-400 italic">No specific recommendations.</li>';
            } else {
                recsEl.innerHTML = recs.map(rec => `
                    <li class="flex items-start gap-2 text-sm text-slate-700">
                        <span class="mt-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0"></span>
                        <span>${rec}</span>
                    </li>
                `).join('');
            }
         } else {
              // Hide card
              if (recsCard) recsCard.classList.add('hidden');
         }
    }
    
    // 5. Render Table View (PRD REQ-01 Code Reuse)
    // Compute Module Data for Module View support (REQ-02)
    const moduleMap = new Map();
    (allClustersData || []).forEach(cluster => {
        const modules = cluster.module_names || ['Unknown'];
        modules.forEach(modName => {
            if (!moduleMap.has(modName)) {
                moduleMap.set(modName, {
                    name: modName,
                    priority: 'P2', // Default, logic can be enhanced
                    total_failures: 0,
                    clusters: [],
                    cluster_count: 0
                });
            }
            const mod = moduleMap.get(modName);
            // check if cluster already added to avoid dups? 
            // renderModuleView expects full cluster objects.
            // But we are pushing the SAME cluster object to multiple modules. That is fine.
            mod.clusters.push(cluster);
            mod.cluster_count++;
            mod.total_failures += (cluster.failures_count || 1); 
        });
    });
    
    // Set global allModulesData for renderAnalysisTable usage
    allModulesData = Array.from(moduleMap.values()).sort((a,b) => b.total_failures - a.total_failures);

    // Call the shared renderer
    // Ensure we use the current View Mode (or default to cluster if undefined)
    if (!currentViewMode) currentViewMode = 'cluster';
    
    // Initial Render
    renderAnalysisTable('sub-analysis-table-body', currentViewMode, false);
    
    // Update Toggle UI State
    updateViewModeButtons('sub-view-mode');
}

// UI Helpers for Submission Analysis View
function switchSubmissionViewMode(mode) {
    currentViewMode = mode;
    renderAnalysisTable('sub-analysis-table-body', currentViewMode, document.getElementById('sub-toggle-no-redmine').getAttribute('aria-checked') === 'true');
    updateViewModeButtons('sub-view-mode');
}

function toggleSubmissionFilter(btn) {
    const isChecked = btn.getAttribute('aria-checked') === 'true';
    const newState = !isChecked;
    btn.setAttribute('aria-checked', newState);
    
    // Trigger render
    renderAnalysisTable('sub-analysis-table-body', currentViewMode, newState);
}

function updateViewModeButtons(prefix) {
    const btnCluster = document.getElementById(`${prefix}-cluster`);
    const btnModule = document.getElementById(`${prefix}-module`);
    
    if (btnCluster && btnModule) {
        if (currentViewMode === 'cluster') {
            btnCluster.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 bg-white text-slate-800 shadow-sm";
            btnModule.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
        } else {
            btnCluster.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
            btnModule.className = "px-3 py-1.5 text-xs font-bold rounded-md transition-all duration-200 bg-white text-slate-800 shadow-sm";
        }
    }
}
function detectAvailableSuites(sub) {
    const suites = new Set(['All']);
    if (sub && sub.test_runs) {
        sub.test_runs.forEach(r => {
             // Use identifyRunSuite for consistent logic (detects CTSonGSI via fingerprint)
             const suiteName = identifyRunSuite(r, sub.target_fingerprint);
             if (suiteName) suites.add(suiteName);
        });
    }
    
    // Sort logic: All -> CTS -> CTSonGSI -> GTS -> VTS -> STS -> Others
    const order = ['All', 'CTS', 'CTSonGSI', 'GTS', 'VTS', 'STS'];
    return Array.from(suites).sort((a, b) => {
        const ia = order.indexOf(a);
        const ib = order.indexOf(b);
        if (ia !== -1 && ib !== -1) return ia - ib;
        if (ia !== -1) return -1;
        if (ib !== -1) return 1;
        return a.localeCompare(b);
    });
}

async function triggerSubmissionBulkSync(subId, suiteFilter) {
    if (!confirm(`Are you sure you want to create Redmine issues for all unsynced clusters in ${suiteFilter}?`)) return;
    
    // Show Optimistic Loading
    showNotification('Starting bulk sync...', 'info');
    
    try {
        const response = await fetch(`${API_BASE}/integrations/redmine/submission/bulk-create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                submission_id: subId,
                project_id: 1, // Phase 1: Default Project ID or resolve dynamically? Assuming 1 or user setting.
                // TODO: Get project_id from settings or prompt user. For now, assume backend uses default if not provided, or strict.
                // The backend requires project_id. Let's fetch settings first or default to 1.
                // Correction: In real app, we should probably fetch default project from settings.
                // Let's hardcode 1 for now as per MVP or existing bulk logic.
                suite_filter: suiteFilter
            })
        });
        
        const res = await response.json();
        
        if (response.ok) {
            showNotification(`Successfully created ${res.created} issues.`, 'success');
            // Reload analysis to show links
            loadSubmissionAnalysis(subId, suiteFilter);
        } else {
            throw new Error(res.detail || 'Sync failed');
        }
    } catch (e) {
        console.error("Bulk sync error", e);
        showNotification('Failed to sync issues: ' + e.message, 'error');
    }
}


// selectedRunIds is declared globally

function toggleRunSelection(runId) {
    if (selectedRunIds.has(runId)) {
        selectedRunIds.delete(runId);
    } else {
        selectedRunIds.add(runId);
    }
    // Re-render to update UI state
    // Ideally we just update the specific row or checkbox, but re-render is safer for now
    const dummyContainer = document.createElement('div'); // dummy
    // We need to re-call renderSubmissionRuns with the actual container
    // This is tricky because we don't have the refs easily. 
    // Better strategy: Just toggle the visual state directly
    const checkbox = document.querySelector(`.run-checkbox[value="${runId}"]`);
    if (checkbox) checkbox.checked = selectedRunIds.has(runId);
    
    // Update container style
    const row = checkbox.closest('.run-row');
    if (row) {
        if (selectedRunIds.has(runId)) row.classList.add('bg-indigo-50/50');
        else row.classList.remove('bg-indigo-50/50');
    }
    
    updateFloatingActionState();
}

function updateFloatingActionState() {
    let fab = document.getElementById('fab-move-runs');
    if (!fab) {
        // Create it
        fab = document.createElement('div');
        fab.id = 'fab-move-runs';
        fab.className = 'fixed bottom-8 right-8 z-50 transition-all duration-300 transform translate-y-20 opacity-0';
        fab.innerHTML = `
            <button onclick="executeMoveRuns()" class="btn-primary bg-indigo-600 text-white px-6 py-3 rounded-full shadow-apple-elevated font-bold flex items-center gap-3 hover:bg-indigo-700">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" /></svg>
                Move Selected Runs
            </button>
        `;
        document.body.appendChild(fab);
    }
    
    if (selectedRunIds.size > 0 && isMoveRunsMode) {
        fab.classList.remove('translate-y-20', 'opacity-0');
    } else {
        fab.classList.add('translate-y-20', 'opacity-0');
    }
}

function renderSubmissionRuns(container, emptyEl, runs, targetFingerprint) {
    if (!container) return;
    
    // Clear selection when re-rendering not triggered by selection logic (rough heuristic)
    // Actually we should preserve it if just switching views, but for simplicity let's keep it.
    
    if (runs.length === 0) {
        container.innerHTML = '';
        if (emptyEl) emptyEl.classList.remove('hidden');
        return;
    }
    
    if (emptyEl) emptyEl.classList.add('hidden');
    
    // Group runs by suite
    const runsBySuite = {};
    runs.forEach(run => {
        const suiteName = identifyRunSuite(run, targetFingerprint);
        if (!runsBySuite[suiteName]) runsBySuite[suiteName] = [];
        runsBySuite[suiteName].push(run);
    });

    // Custom order for suites if desired, or just alphabetical/defined order
    const sortedSuites = Object.keys(runsBySuite).sort();

    container.innerHTML = sortedSuites.map(suiteName => {
        const suiteRuns = runsBySuite[suiteName];
        
        // Suite Header
        const config = SUITE_CONFIGS[suiteName];
        const displayName = config ? (config.display_name || suiteName) : suiteName;
        
        const runsHtml = suiteRuns.map(run => {
            const totalTests = (run.passed_tests || 0) + (run.failed_tests || 0);
            const passRate = totalTests > 0 ? ((run.passed_tests / totalTests) * 100).toFixed(1) : '0.0';
            const date = run.start_time ? new Date(run.start_time).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '-';
            const statusColor = run.failed_tests > 0 ? 'text-red-600' : 'text-emerald-600';
            
            let badgeColor = 'bg-slate-100 text-slate-700';
            if (suiteName.includes('CTS')) badgeColor = 'bg-blue-100 text-blue-700';
            if (suiteName.includes('CTSonGSI')) badgeColor = 'bg-purple-100 text-purple-700'; 
            if (suiteName.includes('GTS')) badgeColor = 'bg-emerald-100 text-emerald-700';
            if (suiteName.includes('VTS')) badgeColor = 'bg-purple-100 text-purple-700';
            if (suiteName.includes('STS')) badgeColor = 'bg-orange-100 text-orange-700';
            
            const isSelected = selectedRunIds.has(run.id);

            // Checkbox HTML
            const checkboxHtml = isMoveRunsMode ? `
                <div class="mr-4 flex-shrink-0" onclick="event.stopPropagation()">
                    <input type="checkbox" class="run-checkbox rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-5 h-5 cursor-pointer" 
                        value="${run.id}" ${isSelected ? 'checked' : ''} onchange="toggleRunSelection(${run.id})"> 
                </div>
            ` : '';

            // Row Click Action
            const rowClick = isMoveRunsMode 
                ? `onclick="toggleRunSelection(${run.id})"`
                : `onclick="router.navigate('run-details', { id: ${run.id} })"`;
                
            return `
                <div class="run-row px-6 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors cursor-pointer border-b border-slate-50 last:border-0 ${isSelected ? 'bg-indigo-50/50' : ''}"
                     ${rowClick}>
                    <div class="flex items-center">
                        ${checkboxHtml}
                        <div class="flex items-center gap-4">
                            <!-- Run ID Badge -->
                            <div class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-500">
                                #${run.id}
                            </div>
                            <div>
                                <div class="text-sm font-medium text-slate-700">${run.test_suite_name || 'Unknown Log'}</div>
                                <div class="text-xs text-slate-400">${date}</div>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-6">
                        <div class="text-right">
                            <div class="text-sm font-bold ${statusColor}">${passRate}%</div>
                            <div class="text-[10px] text-slate-400">${run.failed_tests || 0} failures</div>
                        </div>
                        ${!isMoveRunsMode ? `
                        <svg class="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                        </svg>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="mb-4 last:mb-0">
                <div class="px-6 py-2 bg-slate-50 border-y border-slate-100 flex justify-between items-center">
                    <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">${displayName}</span>
                    <span class="text-[10px] text-slate-400 bg-white px-2 py-0.5 rounded-full border border-slate-200 shadow-sm">${suiteRuns.length} Runs</span>
                </div>
                <div class="bg-white">
                    ${runsHtml}
                </div>
            </div>
        `;
    }).join('');
    
    // Ensure FAB state is correct
    updateFloatingActionState();
}

async function updateSubmissionStatus(newStatus) {
    if (!currentSubmissionId) return;
    
    // Optimistic UI Update
    const statusControl = document.getElementById('submission-status-control');
    if (statusControl) {
        statusControl.querySelectorAll('.segmented-item').forEach(btn => {
            if (btn.dataset.status === newStatus) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
    
    // Update status bar and badge styles
    const statusStyles = {
        draft: { gradient: 'status-gradient-draft', badge: 'bg-slate-100 text-slate-600' },
        analyzing: { gradient: 'status-gradient-analyzing', badge: 'bg-amber-100 text-amber-700' },
        ready: { gradient: 'status-gradient-ready', badge: 'bg-emerald-100 text-emerald-700' },
        published: { gradient: 'status-gradient-published', badge: 'bg-blue-100 text-blue-700' }
    };
    const style = statusStyles[newStatus] || statusStyles.draft;
    
    const statusBar = document.getElementById('submission-status-bar');
    const statusBadge = document.getElementById('submission-status-badge');
    
    if (statusBar) statusBar.className = `absolute top-0 left-0 w-full h-1.5 ${style.gradient}`;
    if (statusBadge) {
        statusBadge.textContent = newStatus;
        statusBadge.className = `${style.badge} px-3 py-1 rounded-full text-xs font-bold uppercase`;
    }

    // Call Backend
    try {
        const response = await fetch(`${API_BASE}/submissions/${currentSubmissionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (!response.ok) throw new Error('Failed to update status');
        
        showNotification(`Status updated to "${newStatus}"`, 'success');
    } catch (e) {
        console.error('Status update failed', e);
        showNotification('Failed to update status', 'error');
        // Revert UI could happen here, but keeping it simple for now
    }
}

// --- Global UI Helpers ---

function showAlertModal(message) {
    const modal = document.getElementById('alert-modal');
    const msgDiv = document.getElementById('alert-modal-message');
    const okBtn = document.getElementById('alert-modal-ok');
    
    if (!modal || !msgDiv) {
        console.warn('Alert modal not found, falling back to window.alert');
        alert(message); // Fallback
        return;
    }
    
    // Set message
    msgDiv.textContent = message;
    
    // Show modal
    modal.classList.remove('hidden');
    
    // Close handler
    const close = () => {
        modal.classList.add('hidden');
        // Clean up events to avoid duplicates/leaks if reused? 
        // Actually simplistic approach is fine here as it's just add hidden
    };
    
    if (okBtn) okBtn.onclick = close;
    
    // Click outside to close
    modal.onclick = (e) => {
        if (e.target === modal) close();
    };
    
    // Add Esc key listener one-time? 
    // Usually handled globally, but for now this suffices.
}

function renderSubmissionCardV2(sub) {
    // Status styling (Apple Pills)
    const statusStyles = {
        draft: { bg: 'bg-slate-100', text: 'text-slate-600', dot: 'bg-slate-400' },
        analyzing: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
        ready: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
        published: { bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500' }
    };
    const style = statusStyles[sub.status] || statusStyles.draft;
    
    const date = sub.updated_at ? new Date(sub.updated_at).toISOString().slice(0, 10) : '-';
    // Use test_runs length logic if available, or fallback
    const runsCount = sub.test_runs ? sub.test_runs.length : (sub.run_count || 0);
    
    // Mini suite indicators
    const suitesHtml = REQUIRED_SUITES.map(suite => {
        // Handle name mismatch (CTSonGSI vs CTSonGSI in config vs backend response)
        let suiteData = sub.suite_summary?.[suite];
        if (!suiteData) {
             // Try case-insensitive lookup
             const key = Object.keys(sub.suite_summary || {}).find(k => k.toLowerCase() === suite.toLowerCase());
             suiteData = key ? sub.suite_summary[key] : { status: 'missing' };
        }
        
        // Dynamic config lookup for clean names
        const config = SUITE_CONFIGS[suite];
        const displayName = config ? (config.display_name || suite).replace(' on ', ' ') : suite;
        
        let bgClass, textClass, contentHtml, borderClass;
        
        // Logic for Recovered Status
        const initial = suiteData.initial_failed || 0;
        const recovered = suiteData.recovered || 0;
        const remaining = suiteData.failed || 0;
        const isRecovered = initial > 0 && remaining === 0;
        const hasPartialRecovery = remaining > 0 && recovered > 0;
        
        if (suiteData.status === 'pass') {
            if (isRecovered) {
                // All recovered!
                bgClass = 'bg-emerald-50/80';
                textClass = 'text-emerald-700';
                borderClass = 'border-emerald-100';
                contentHtml = `
                    <div class="flex flex-col items-center">
                        <span class="text-lg font-bold">0 <span class="text-xs">FAIL</span></span>
                        <span class="text-[9px] font-bold bg-emerald-100 px-1.5 py-0.5 rounded-full text-emerald-800 mt-0.5">
                            ${recovered} Recovered
                        </span>
                    </div>`;
            } else {
                // Vanilla Pass
                bgClass = 'bg-emerald-50/80';
                textClass = 'text-emerald-700';
                borderClass = 'border-emerald-100';
                contentHtml = `<span class="text-lg font-bold">100<span class="text-[10px]">%</span></span>`;
            }
        } else if (suiteData.status === 'fail') {
            bgClass = 'bg-red-50/80';
            textClass = 'text-red-700';
            borderClass = 'border-red-100';
            
            let subText = 'FAIL';
            if (hasPartialRecovery) {
                subText = `${recovered} Recov.`;
            }
            
            contentHtml = `
                <span class="text-lg font-bold">${remaining}</span>
                <span class="text-[9px] font-medium opacity-70">${subText}</span>`;
        } else {
            bgClass = 'bg-slate-50';
            textClass = 'text-slate-400';
            borderClass = 'border-slate-100';
            contentHtml = `<span class="text-lg font-bold text-slate-300">—</span>`;
        }
        
        return `
            <div class="flex flex-col items-center justify-center p-2 rounded-2xl ${bgClass} border ${borderClass} min-w-[72px] h-[72px] transition-transform hover:scale-105">
                <div class="text-[9px] font-bold uppercase tracking-widest ${textClass} opacity-80 mb-0.5 max-w-full truncate px-1 text-center">${displayName}</div>
                <div class="flex flex-col items-center leading-none ${textClass} w-full">
                    ${contentHtml}
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="group relative bg-white rounded-[24px] p-6 shadow-sm border border-slate-100/60 hover:shadow-apple-elevated hover:border-blue-100/50 transition-all duration-300 cursor-pointer overflow-hidden backdrop-blur-xl"
             onclick="router.navigate('submission-detail', { id: ${sub.id} })">
             
             <!-- Hover Glow -->
             <div class="absolute -inset-1 bg-gradient-to-r from-blue-50 to-purple-50 opacity-0 group-hover:opacity-20 transition-opacity duration-500 blur-xl pointer-events-none"></div>
             
             <!-- Header -->
             <div class="relative flex justify-between items-start mb-5">
                 <div class="min-w-0 pr-4">
                     <h3 class="font-display font-bold text-lg text-slate-900 leading-tight tracking-tight truncate group-hover:text-blue-600 transition-colors">
                         ${escapeHtml(sub.name || 'Unnamed')}
                     </h3>
                     <div class="flex items-center gap-2 mt-1.5">
                         <div class="font-mono text-[10px] text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100 whitespace-nowrap">
                             ${escapeHtml(sub.target_fingerprint || 'No Fingerprint')}
                         </div>
                     </div>
                 </div>
                 
                 <!-- Status Pill -->
                 <span class="flex-shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide ${style.bg} ${style.text} border border-white shadow-sm">
                     <span class="w-1.5 h-1.5 rounded-full ${style.dot} animate-pulse"></span>
                     ${sub.status}
                 </span>
             </div>
             
             <!-- Matrix Row (Grid Layout 4-col) -->
             <div class="grid grid-cols-4 gap-3 mb-4">
                 ${suitesHtml}
             </div>
             
             <!-- Footer -->
             <div class="relative mt-4 pt-4 border-t border-slate-50 flex justify-between items-center text-xs text-slate-400 font-medium">
                 <div class="flex items-center gap-1.5 hover:text-slate-600 transition-colors">
                     <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                     <span>${runsCount} Runs</span>
                 </div>
                 <div class="flex items-center gap-1.5">
                     <span>Updated ${date}</span>
                 </div>
             </div>
        </div>
    `;
}    

function confirmDelete(id) {
    const deleteModal = document.getElementById('delete-modal');
    const modalMessage = document.getElementById('delete-modal-message');
    const modalCancel = document.getElementById('modal-cancel');
    const modalConfirm = document.getElementById('modal-confirm');
    
    if (!deleteModal) {
        if(confirm('Are you sure you want to delete this submission?')) deleteSubmission(id);
        return;
    }

    // Build confirmation message
    modalMessage.innerHTML = `
        <div class="space-y-4">
            <div class="flex items-center gap-3 p-3 bg-red-50 rounded-lg border border-red-200">
                <div class="flex-shrink-0 w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                    <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                </div>
                <div>
                    <div class="font-bold text-red-800">Delete Submission #${id}</div>
                    <div class="text-sm text-red-600">This action cannot be undone</div>
                </div>
            </div>
            
            <div class="text-sm text-slate-600">
                This will properly delete the submission and <strong>all contained test runs</strong>.
            </div>
        </div>
    `;
    
    // Reset button state
    modalConfirm.disabled = false;
    modalConfirm.textContent = 'Delete Submission';
    modalConfirm.className = 'px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium';
    
    // Show modal
    deleteModal.classList.remove('hidden');
    document.body.classList.add('modal-open');
    
    // Remove old listeners
    const newCancelBtn = modalCancel.cloneNode(true);
    const newConfirmBtn = modalConfirm.cloneNode(true);
    modalCancel.parentNode.replaceChild(newCancelBtn, modalCancel);
    modalConfirm.parentNode.replaceChild(newConfirmBtn, modalConfirm);
    
    // Add new listeners
    newCancelBtn.addEventListener('click', () => {
        deleteModal.classList.add('hidden');
        document.body.classList.remove('modal-open');
    });
    
    let isDeleting = false;
    newConfirmBtn.addEventListener('click', async () => {
        if (isDeleting) return;
        isDeleting = true;
        
        try {
            newConfirmBtn.disabled = true;
            newConfirmBtn.innerHTML = `
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                Deleting...
            `;
            
            await deleteSubmission(id);
            // deleteSubmission handles navigation and error alerts by itself, 
            // but we need to close modal if it didn't crash.
            // Actually deleteSubmission closes early if fetch fails?
            // Let's rely on deleteSubmission to throw if failed, or handle UI here?
            // Existing deleteSubmission navigates on success.
            
            deleteModal.classList.add('hidden');
            document.body.classList.remove('modal-open');
            
        } catch (e) {
             // Handled in deleteSubmission or here?
             // deleteSubmission catches errors inside itself. 
             // We should probably modify deleteSubmission to propagate or handle UI state?
             // To be safe, let's keep simple. The user just wants the modal.
             // If deleteSubmission fails, it alerts. We just reset button.
             newConfirmBtn.disabled = false;
             newConfirmBtn.textContent = 'Delete Submission';
             isDeleting = false;
        }
    });

    // Close on outside click
    deleteModal.onclick = (e) => {
        if (e.target === deleteModal) {
            deleteModal.classList.add('hidden');
            document.body.classList.remove('modal-open');
        }
    };
}

async function deleteSubmission(id) {
        const response = await fetch(`${API_BASE}/submissions/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to delete submission');
        }
        
        // Success
        showNotification('Submission deleted successfully', 'success');
        router.navigate('submissions');
}

function editSubmissionName(name) {
    const newName = prompt("Rename submission:", name);
    if (newName && newName.trim() !== "" && newName !== name) {
        updateSubmissionName(newName.trim());
    }
}

async function updateSubmissionName(newName) {
    if (!currentSubmissionId) return;

    try {
        const response = await fetch(`${API_BASE}/submissions/${currentSubmissionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        
        if (!response.ok) throw new Error('Failed to update name');
        
        // Update UI
        const nameEl = document.getElementById('submission-name');
        if (nameEl) {
             nameEl.innerHTML = `
                <span class="text-slate-400 font-mono mr-2">#${currentSubmissionId}</span>
                ${escapeHtml(newName)}
            `;
        }
        
        // Update edit button onclick to have new name
        const editBtn = document.getElementById('btn-edit-submission');
        if (editBtn) {
            editBtn.onclick = () => editSubmissionName(newName);
        }

        showNotification('Submission renamed successfully', 'success');
    } catch (e) {
        console.error('Rename failed', e);
        showNotification('Failed to rename submission', 'error');
    }
}

// --- Run Move / Merge Logic ---

function toggleRunSelectionMode() {
    isRunSelectionMode = !isRunSelectionMode;
    selectedRunIds.clear();
    
    const btnSelect = document.getElementById('btn-select-runs');
    const btnMove = document.getElementById('btn-move-runs');
    
    if (isRunSelectionMode) {
        btnSelect.textContent = 'Cancel Selection';
        btnSelect.className = "text-xs bg-slate-200 hover:bg-slate-300 text-slate-800 px-3 py-1.5 rounded-lg font-medium transition-all";
        btnMove.classList.remove('hidden');
    } else {
        btnSelect.textContent = 'Select Runs';
        btnSelect.className = "text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg font-medium transition-all";
        btnMove.classList.add('hidden');
    }
    
    // Re-render list
    loadSubmissionDetail(currentSubmissionId); // This might be overkill, but ensures data refresh
}

// Duplicate toggleRunSelection removed. Using the optimized definition above.

async function openMoveRunsModal() {
    if (selectedRunIds.size === 0) {
        showNotification('Please select at least one run to move', 'warning');
        return;
    }
    
    const modal = document.getElementById('move-runs-modal');
    const countDisplay = document.getElementById('move-count-display');
    const select = document.getElementById('move-target-select');
    
    if (countDisplay) countDisplay.textContent = selectedRunIds.size;
    if (modal) modal.classList.remove('hidden');
    
    // Fetch potential targets
    try {
        // We'll use the existing /submissions endpoint. Ideally we should have a lightweight endpoint.
        const response = await fetch(`${API_BASE}/submissions/?limit=100`); 
        const submissions = await response.json();
        
        if (select) {
            select.innerHTML = '<option value="" disabled selected>Select a target...</option>' + 
                submissions
                    .filter(s => s.id !== currentSubmissionId) // Exclude current
                    .map(s => {
                        const date = s.created_at ? new Date(s.created_at).toISOString().slice(0, 10) : '';
                        return `<option value="${s.id}">#${s.id} - ${escapeHtml(s.name)} (${date})</option>`;
                    })
                    .join('');
        }
    } catch (e) {
        console.error('Failed to load targets', e);
        showNotification('Failed to load target submissions', 'error');
    }
}

function closeMoveRunsModal() {
    const modal = document.getElementById('move-runs-modal');
    if (modal) modal.classList.add('hidden');
}

function exportSubmission(id) {
    if (!id) return;
    // Trigger download by navigation
    window.location.href = `${API_BASE}/export/submission/${id}/excel`;
}

async function submitMoveRuns() {
    const select = document.getElementById('move-target-select');
    if (!select || !select.value) {
        showNotification('Please select a target submission', 'warning');
        return;
    }
    
    const targetId = parseInt(select.value);
    
    try {
        const response = await fetch(`${API_BASE}/submissions/runs/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                run_ids: Array.from(selectedRunIds),
                target_submission_id: targetId
            })
        });
        
        if (!response.ok) throw new Error('Move failed');
        
        const result = await response.json();
        showNotification(result.message, 'success');
        
        closeMoveRunsModal();
        isRunSelectionMode = false; 
        selectedRunIds.clear();
        toggleRunSelectionMode(); // Reset UI
        
        // Reload current page
        loadSubmissionDetail(currentSubmissionId);
        
    } catch (e) {
        console.error('Move failed', e);
        showNotification('Failed to move runs', 'error');
    }
}

// --- Consolidated Report Logic ---
let currentConsolidatedData = null;
let currentConsolidatedFilter = 'persistent'; // default

// Duplicate switchSubmissionTab removed. Using the central definition above.


let currentConsolidatedView = 'list'; // 'list' or 'triage'

async function loadConsolidatedReport(submissionId) {
    const tableBody = document.getElementById('consolidated-tbody');
    const container = document.getElementById('consolidated-table-container'); // Need to find parent
    if (!tableBody) return;
    
    // Set Header
    const headerEl = document.getElementById('header-matrix-runs');
    if(headerEl) headerEl.textContent = "Run History";
    
    tableBody.innerHTML = '<tr><td colspan="100" class="text-center py-8"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div></td></tr>';
    
    try {
        const response = await fetch(`${API_BASE}/submissions/${submissionId}/merge_report`);
        if (!response.ok) throw new Error('Failed to load report');
        
        currentConsolidatedData = await response.json();
        
        // Populate global clusters data for re-use of renderClusterView
        if (currentConsolidatedData.clusters) {
            allClustersData = currentConsolidatedData.clusters;
        } else {
            allClustersData = [];
        }
        
        renderConsolidatedTable();
        
    } catch (e) {
        console.error(e);
        tableBody.innerHTML = '<tr><td colspan="100" class="text-center py-8 text-red-500">Failed to load consolidated report</td></tr>';
    }
}

function toggleConsolidatedView(mode) {
    currentConsolidatedView = mode;
    renderConsolidatedTable();
}

function filterConsolidated(mode) {
    currentConsolidatedFilter = mode;
    // Update filter UI
    ['all', 'persistent', 'recovered'].forEach(m => {
        const btn = document.getElementById(`filter-btn-${m}`);
        if(btn) {
            if (m === mode) {
                 btn.classList.add('bg-white', 'shadow-sm', 'font-bold');
                 btn.classList.remove('font-medium');
                 if (m === 'persistent') btn.classList.add('text-red-600');
                 if (m === 'recovered') btn.classList.add('text-emerald-600');
            } else {
                 btn.classList.remove('bg-white', 'shadow-sm', 'font-bold', 'text-red-600', 'text-emerald-600');
                 btn.classList.add('font-medium', 'text-slate-600');
            }
        }
    });
    renderConsolidatedTable();
}

function renderConsolidatedTable() {
    const data = currentConsolidatedData;
    const tableBody = document.getElementById('consolidated-tbody');
    const emptyState = document.getElementById('consolidated-empty');
    
    // Inject Toggle UI if not exists
    const filterContainer = document.getElementById('consolidated-filters'); // Assuming ID based on observation, checking surrounding code might be needed
    // Actually, I'll inject it via JS to be safe if I can't find the container easily in code
    // Let's assume the filters exist in HTML. Using a safer way to update the filter buttons row.
    const filterRow = document.querySelector('#sub-detail-view .flex.gap-2.mb-4'); 
    
    if (filterRow && !document.getElementById('view-toggle-triage')) {
        // Create Triage Toggle
        const toggleHtml = `
            <div class="h-6 w-px bg-slate-200 mx-2"></div>
            <div class="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200/60">
                <button onclick="toggleConsolidatedView('list')" id="view-toggle-list" class="px-3 py-1 text-xs font-bold rounded-md transition-all duration-200 bg-white shadow-sm text-slate-700">List</button>
                <button onclick="toggleConsolidatedView('triage')" id="view-toggle-triage" class="px-3 py-1 text-xs font-medium rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700">Triage (AI)</button>
            </div>
        `;
        // Only append if data.clusters exists
        if (data && data.clusters && data.clusters.length > 0) {
           // Insert after the existing filters
           // Use a specific selector or append
           // Since I don't have the exact HTML, I will verify if I can just append to the filter container
           // Assuming the filter container is where filter buttons are.
           const lastBtn = document.getElementById('filter-btn-recovered');
           if(lastBtn && lastBtn.parentNode) {
               const wrapper = document.createElement('div');
               wrapper.className = "flex items-center";
               wrapper.innerHTML = toggleHtml;
               lastBtn.parentNode.appendChild(wrapper);
           }
        }
    }
    
    // Update Toggle State
    const btnList = document.getElementById('view-toggle-list');
    const btnTriage = document.getElementById('view-toggle-triage');
    if (btnList && btnTriage) {
        if (currentConsolidatedView === 'triage') {
            btnTriage.className = "px-3 py-1 text-xs font-bold rounded-md transition-all duration-200 bg-white shadow-sm text-blue-700";
            btnList.className = "px-3 py-1 text-xs font-medium rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
        } else {
            btnList.className = "px-3 py-1 text-xs font-bold rounded-md transition-all duration-200 bg-white shadow-sm text-slate-700";
            btnTriage.className = "px-3 py-1 text-xs font-medium rounded-md transition-all duration-200 text-slate-500 hover:text-slate-700";
        }
    }

    if (!data || !data.suites || data.suites.length === 0) {
        tableBody.innerHTML = '';
        if(emptyState) {
            emptyState.classList.remove('hidden');
             emptyState.querySelector('p').textContent = "No failures recorded in this submission.";
        }
        return;
    }
    if(emptyState) emptyState.classList.add('hidden');
    
    // RENDER TRIAGE VIEW
    if (currentConsolidatedView === 'triage') {
        tableBody.innerHTML = '';
        // Reuse renderClusterView logic
        // We pass 'false' for filterNoRedmine
        renderClusterView(tableBody, false);
        return;
    }

    // RENDER LIST VIEW (Original)
    let html = '';
    let hasVisibleRows = false;
    
    data.suites.forEach(suite => {
        // Filter items
        const filteredItems = suite.items.filter(item => {
            if (currentConsolidatedFilter === 'all') return true;
            if (currentConsolidatedFilter === 'persistent') return !item.is_recovered;
            if (currentConsolidatedFilter === 'recovered') return item.is_recovered;
            return true;
        });
        
        if (filteredItems.length === 0) return;
        hasVisibleRows = true;
        
        // Suite Header
        html += `
            <tr class="bg-slate-50 border-b border-slate-100">
                <td colspan="100" class="px-6 py-3">
                    <div class="flex items-center gap-3">
                        <span class="font-bold text-slate-700 font-display">${suite.suite_name}</span>
                        <div class="flex gap-2 text-xs">
                             <span class="px-2 py-0.5 bg-red-100 text-red-700 rounded font-bold">${suite.summary.remaining} Fail</span>
                             <span class="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded font-bold">${suite.summary.recovered} Recovered</span>
                        </div>
                    </div>
                </td>
            </tr>
        `;
        
        // Items
        filteredItems.forEach(item => {
            const isRecovered = item.is_recovered;
            
            // Build Run Columns Visualization (Mini sparkline or dots)
            // Build Run Columns Visualization (Mini sparkline or dots)
            const runsViz = item.status_history.map((status, idx) => {
                let color = 'bg-red-400';
                if (status === 'pass') color = 'bg-emerald-400';
                else if (status === 'not_executed') color = 'bg-slate-300';
                
                return `<span class="w-2.5 h-2.5 rounded-full ${color} inline-block" title="Run ${idx+1}: ${status.toUpperCase()}"></span>`;
            }).join('<span class="w-4 h-px bg-slate-200 mx-1"></span>'); // connector
            
            html += `
                <tr class="hover:bg-slate-50 transition-colors border-b border-slate-50/50">
                    <td class="px-6 py-3">
                        <div class="font-mono text-xs text-slate-600 break-all">
                            <span class="text-slate-500 hover:text-blue-600 transition-colors cursor-text select-all">${item.module_name}</span><br>
                            <span class="font-bold text-slate-800 hover:text-blue-600 transition-colors cursor-text select-all">${item.test_method}</span>
                             <div class="text-[10px] text-slate-400 mt-0.5 truncate max-w-lg cursor-help" title="${item.test_class}">${item.test_class}</div>
                        </div>
                    </td>
                    <td class="px-6 py-3 text-center">
                        <div class="flex items-center justify-center">
                            ${runsViz}
                        </div>
                    </td>
                    <td class="px-6 py-3 text-center">
                         ${isRecovered 
                            ? `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-100/50">
                                 <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                                 Recovered
                               </span>`
                            : `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-red-50 text-red-700 text-xs font-bold border border-red-100/50">
                                 <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                                 Failed
                               </span>`
                         }
                    </td>
                </tr>
            `;
        });
    });
    
    if (!hasVisibleRows) {
         tableBody.innerHTML = '';
         if(emptyState) {
             emptyState.classList.remove('hidden');
             emptyState.querySelector('p').textContent = `No ${currentConsolidatedFilter} failures found.`;
         }
    } else {
        tableBody.innerHTML = html;
    }
}

// Initialize Product Filter
document.addEventListener('DOMContentLoaded', () => {
    loadProducts();
});

// --- Upload Helper Functions (Apple UI) ---

// Helper to extract Run ID from error string (e.g. "... (Run #123).")
function extractRunId(text) {
    const match = text.match(/\(Run #(\d+)\)/);
    return match ? match[1] : null;
}

function renderUploadError(messageText) {
    const statusDiv = document.getElementById('upload-status');
    const isDuplicate = messageText.includes('Duplicate Upload');
    const runId = isDuplicate ? extractRunId(messageText) : null;
    
    // Apple-style Error/Warning Card
    // Using Amber for Duplicate (Warning), Red for others (Error)
    const theme = isDuplicate ? 'amber' : 'red';
    const bgClass = isDuplicate ? 'bg-amber-50 border-amber-100' : 'bg-red-50 border-red-100';
    const textClass = isDuplicate ? 'text-amber-800' : 'text-red-800';
    const iconColor = isDuplicate ? 'text-amber-500' : 'text-red-500';
    const title = isDuplicate ? 'Report Already Exists' : 'Upload Failed';
    
    // Clean up message for display
    let displayMsg = messageText.replace(/^Error: /, '').replace(/^Duplicate Upload: /, '');
    if (isDuplicate) {
         // Simplify the detailed backend message for the subtitle
         displayMsg = "You have already uploaded this result file. No new data was created.";
    }

    statusDiv.innerHTML = `
        <div class="rounded-2xl ${bgClass} border p-5 text-left animate-in fade-in zoom-in-95 duration-300">
            <div class="flex items-start gap-4">
                <div class="flex-shrink-0 mt-0.5">
                    <svg class="w-6 h-6 ${iconColor}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        ${isDuplicate 
                            ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' 
                            : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>'
                        }
                    </svg>
                </div>
                <div class="flex-1">
                    <h4 class="text-base font-bold ${textClass}">${title}</h4>
                    <p class="text-sm ${textClass} mt-1 opacity-90 leading-relaxed">
                        ${displayMsg}
                    </p>
                    
                    ${runId ? `
                    <div class="mt-4 flex gap-3">
                        <button onclick="router.navigate('run-details', {id: ${runId}})" 
                            class="px-4 py-2 bg-white border border-amber-200 shadow-sm rounded-lg text-sm font-semibold text-amber-700 hover:bg-amber-50 transition-all flex items-center gap-2">
                            <span>View Run #${runId}</span>
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                        </button>
                         <button onclick="setupUpload()" class="px-4 py-2 text-sm font-medium text-amber-600 hover:text-amber-800 transition-colors">
                            Try Another File
                        </button>
                    </div>
                    ` : `
                    <button onclick="setupUpload()" class="mt-3 text-sm font-bold underline decoration-2 underline-offset-2 hover:decoration-4 transition-all">
                        Try Again
                    </button>
                    `}
                </div>
            </div>
        </div>
    `;
    statusDiv.classList.remove('hidden');
}

// --- Compliance Matrix Rendering ---

function renderComplianceMatrix(sub) {
    const matrixEl = document.getElementById('compliance-matrix');
    if (!matrixEl) return;
    
    let html = '';
    
    const displaySuites = REQUIRED_SUITES.length > 0 ? REQUIRED_SUITES : Object.keys(SUITE_CONFIGS);
    
    displaySuites.forEach(suiteName => {
        const config = SUITE_CONFIGS[suiteName];
        if (!config) return;
        
        let status = 'Missing';
        let statusColor = 'bg-slate-50 border-slate-200/60';
        let progressColor = 'bg-slate-200';
        let contentHtml = '';
        let passRatePercent = 0;
        let onClickAction = '';  
        let cursorClass = 'cursor-default';
        let runCountBadge = '';
        
        // Use backend pre-calculated summary if available
        const summary = sub.suite_summary ? sub.suite_summary[suiteName] : null;
        
        if (summary && summary.status !== 'missing') {
             const isFail = summary.failed > 0;
             const total = summary.passed + summary.failed;
             passRatePercent = total > 0 ? (summary.passed / total) * 100 : 0;
             
             if (isFail) {
                 status = 'Fail';
                 statusColor = 'bg-red-50 border-red-200 hover:border-red-300 hover:shadow-red-100/50';
                 progressColor = 'bg-red-500';
             } else {
                 status = 'Pass';
                 statusColor = 'bg-emerald-50 border-emerald-200 hover:border-emerald-300 hover:shadow-emerald-100/50';
                 progressColor = 'bg-emerald-500';
             }
             
             // Top Right Badge: Runs Count & Merged Status
             const runLabel = summary.run_count === 1 ? 'Run' : 'Runs';
             
             runCountBadge = `
                <div class="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/60 border border-black/5 text-[10px] font-semibold text-slate-600 shadow-sm backdrop-blur-sm" title="Combined result of ${summary.run_count} runs">
                    <svg class="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    ${summary.run_count} ${runLabel}
                </div>
             `;
             
             // Content Stats
             contentHtml = `
                <div class="mt-4 space-y-3">
                     <!-- Micro Progress Bar -->
                     <div class="w-full h-1.5 bg-black/5 rounded-full overflow-hidden">
                        <div class="h-full ${progressColor} transition-all duration-500" style="width: ${passRatePercent}%"></div>
                     </div>
                     
                     <div class="flex justify-between items-end">
                         <div class="flex flex-col">
                            <span class="apple-label">Failures</span>
                            <div class="flex items-center gap-1.5">
                                <span class="text-lg font-bold ${isFail ? 'text-red-700' : 'text-slate-700'}">${summary.failed.toLocaleString()}</span>
                                ${summary.recovered > 0 ? `<div class="px-1.5 py-0.5 rounded text-[9px] font-bold text-emerald-700 bg-emerald-100/80" title="${summary.recovered} issues fixed in later runs">-${summary.recovered}</div>` : ''}
                            </div>
                         </div>
                         
                         <div class="flex flex-col items-end text-right">
                            <span class="apple-label">Total Tests</span>
                            <span class="text-sm font-semibold text-slate-600">${total.toLocaleString()}</span>
                         </div>
                     </div>
                </div>
                
                <!-- Hover Chevron -->
                <div class="absolute bottom-4 right-4 text-slate-400 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </div>
             `;
             
             // Make card clickable
             if (summary.latest_run_id) {
                 onClickAction = `onclick="router.navigate('run-details', {id: ${summary.latest_run_id}})"`;
                 cursorClass = 'cursor-pointer btn-press';
             } else {
                 cursorClass = 'cursor-default';
             }
             
        } else {
            // Missing
             contentHtml = `
                <div class="flex flex-col items-center justify-center h-20 text-center mt-2">
                    <button onclick="router.navigate('upload'); event.stopPropagation();" class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 px-4 py-2 rounded-lg border border-indigo-100 transition-all">
                        + Upload Result
                    </button>
                </div>
            `;
            cursorClass = 'cursor-default';
        }
        
        html += `
        <div class="relative group rounded-2xl p-5 border shadow-sm hover:shadow-lg transition-all duration-300 ${statusColor} ${cursorClass}" ${onClickAction}>
            <div class="flex justify-between items-start">
                <div class="flex flex-col">
                     <span class="apple-label opacity-50 mb-1">${config.display_name || suiteName}</span>
                     ${summary && summary.status !== 'missing' ? 
                        `<span class="text-3xl font-display font-black text-slate-800 tracking-tight">${summary.status === 'pass' ? 'PASS' : 'FAIL'}</span>` : 
                        `<span class="text-3xl font-display font-black text-slate-300">-</span>`
                     }
                </div>
                <!-- Top Right Badge -->
                ${summary && summary.status !== 'missing' ? runCountBadge : ''}
            </div>
            ${contentHtml}
        </div>
        `;
    });
    
    matrixEl.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 mb-8';
    matrixEl.innerHTML = html;
}

// Helper to group clusters by module for client-side module view
function groupClustersByModule(clusters) {
    if (!clusters) return [];
    
    const modulesMap = {};
    
    clusters.forEach(c => {
        const modNames = c.module_names && c.module_names.length > 0 ? c.module_names : ['Unknown'];
        
        modNames.forEach(mName => {
            if (!modulesMap[mName]) {
                modulesMap[mName] = {
                    name: mName,
                    total_failures: 0,
                    priority: 'P3', // Default
                    cluster_count: 0,
                    clusters: []
                };
            }
            
            // Avoid duplicates in same module list
            const existing = modulesMap[mName].clusters.find(existing => existing.id === c.id);
            if (!existing) {
                modulesMap[mName].clusters.push(c);
                modulesMap[mName].cluster_count++;
                modulesMap[mName].total_failures += (c.failures_count || 0);
            }
        });
    });
    
    // Convert to array and calc priority
    return Object.values(modulesMap).map(m => {
        // Priority Logic
        const hasHigh = m.clusters.some(c => c.severity === 'High');
        if (hasHigh) m.priority = 'P0';
        else if (m.total_failures > 15) m.priority = 'P1';
        else if (m.total_failures >= 5) m.priority = 'P2';
        else m.priority = 'P3';
        
        return m;
    }).sort((a, b) => b.total_failures - a.total_failures);
}
