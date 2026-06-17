/**
 * HydroSafe Dashboard - Interactive Client Controller
 */

// Global Chart.js Instances (tracked to prevent overlap flicker bugs)
let shapChartInstance = null;
let dashRatioChartInstance = null;
let analyticsTrendChartInstance = null;
let analyticsBarChartInstance = null;
let rocChartInstance = null;
let importanceChartInstance = null;

// Global History State
let historyData = [];

// Global IoT Simulation Interval and Sector Index
let iotInterval = null;
let currentSectorIdx = 0;

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // 2. Initialize Navigation system
    initNavigation();

    // 3. Initialize Theme system (Dark/Light mode)
    initTheme();

    // 4. Initialize Range Sliders
    initRangeSliders();

    // 5. Connect Form Handler
    initFormHandler();

    // 6. Connect History search and buttons
    initHistoryControls();

    // 7. Load Initial database history
    refreshHistoryLogs();

    // 8. Load Performance Page data (lazy loads)
    loadPerformanceTelemetry();

    // 9. Init Smart City visualizers & node listeners
    updateSmartCityUI();
    initHeatmapNodeClicks();
    initIoTSimulator();
});

/**
 * Navigation System - Handles tab routing with animations
 */
function initNavigation() {
    const sidebarLinks = document.querySelectorAll('.sidebar-link');
    const tabContents = document.querySelectorAll('.tab-content');
    
    const pageMetadata = {
        home: { title: "Home Dashboard", desc: "Water chemical diagnostics SaaS overview." },
        dashboard: { title: "Executive Dashboard", desc: "Telemetry analytics and summary ratios." },
        analyze: { title: "Chemical Analysis", desc: "Ingest parameters to run predictions." },
        smartcity: { title: "Smart City Grid", desc: "Municipal safety heatmap and zone monitoring." },
        analytics: { title: "Historical Analytics", desc: "Longitudinal safety trends and parameter distributions." },
        performance: { title: "Model Performance", desc: "Comparative telemetry metrics for 5 trained classifiers." },
        history: { title: "Ingestion History Logs", desc: "Auditing index database records." },
        about: { title: "About Platform", desc: "Scientific methodology and guidelines definitions." }
    };

    const switchTab = (tabId) => {
        // Update sidebar links
        sidebarLinks.forEach(link => {
            if (link.getAttribute('data-tab') === tabId) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        // Toggle contents with smooth transition
        tabContents.forEach(tab => {
            if (tab.id === `tab-${tabId}`) {
                tab.style.display = 'flex';
                // Trigger reflow for CSS transition
                tab.offsetHeight;
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
                tab.style.display = 'none';
            }
        });

        // Update top bar text
        const meta = pageMetadata[tabId] || pageMetadata.home;
        document.getElementById('page-title').textContent = meta.title;
        document.getElementById('page-description').textContent = meta.desc;

        // Render responsive charts when their parent tabs are visible
        if (tabId === 'dashboard' || tabId === 'analytics') {
            rebuildDashboardCharts();
        }

        // Fetch location analytics on Smart City tab load
        if (tabId === 'smartcity') {
            updateSmartCityUI();
        }
    };

    // Listen to sidebar clicks
    sidebarLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            const tabId = link.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // Listen to home CTA card clicks
    document.querySelectorAll('.action-card').forEach(card => {
        card.addEventListener('click', () => {
            const action = card.getAttribute('data-action');
            if (action === 'go-analyze') switchTab('analyze');
            if (action === 'go-performance') switchTab('performance');
        });
    });

    // Handle initial tab loaded from Flask
    const startTab = typeof INITIAL_TAB !== 'undefined' ? INITIAL_TAB : 'home';
    switchTab(startTab);
}

/**
 * Theme Manager - Dark & Light mode toggle
 */
function initTheme() {
    const toggleBtn = document.getElementById('theme-toggle');
    const iconEl = document.getElementById('theme-icon');
    
    // Check saved theme
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Default to dark theme if no preference is saved
    const isDark = savedTheme ? savedTheme === 'dark' : systemPrefersDark || true;
    
    if (!isDark) {
        document.body.classList.add('light-theme');
        if (iconEl) {
            iconEl.setAttribute('data-lucide', 'moon');
        }
    } else {
        document.body.classList.remove('light-theme');
        if (iconEl) {
            iconEl.setAttribute('data-lucide', 'sun');
        }
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    toggleBtn.addEventListener('click', () => {
        const currentlyLight = document.body.classList.toggle('light-theme');
        localStorage.setItem('theme', currentlyLight ? 'light' : 'dark');
        
        if (currentlyLight) {
            iconEl.setAttribute('data-lucide', 'moon');
        } else {
            iconEl.setAttribute('data-lucide', 'sun');
        }
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        // Rebuild active charts to adjust gridline colors dynamically
        rebuildDashboardCharts();
        loadPerformanceTelemetry();
    });
}

/**
 * Sliders visual feedback binder
 */
function initRangeSliders() {
    const sliderConfigs = [
        { id: 'ph', badgeId: 'ph-badge', suffix: '', decimals: 1 },
        { id: 'solids', badgeId: 'solids-badge', suffix: ' ppm', decimals: 0 },
        { id: 'chloramines', badgeId: 'chloramines-badge', suffix: ' ppm', decimals: 1 },
        { id: 'sulfate', badgeId: 'sulfate-badge', suffix: ' mg/L', decimals: 0 },
        { id: 'turbidity', badgeId: 'turbidity-badge', suffix: ' NTU', decimals: 1 }
    ];

    sliderConfigs.forEach(config => {
        const slider = document.getElementById(config.id);
        const badge = document.getElementById(config.badgeId);
        
        if (slider && badge) {
            const updateBadge = () => {
                const val = parseFloat(slider.value);
                badge.textContent = `${val.toFixed(config.decimals)}${config.suffix}`;
            };
            
            slider.addEventListener('input', updateBadge);
            updateBadge();
        }
    });
}

/**
 * Form submit interceptor for AJAX assessments
 */
function initFormHandler() {
    const form = document.getElementById('ingestionForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const idlePanel = document.getElementById('assessment-idle');
        const loadingPanel = document.getElementById('assessment-loading');
        const resultsPanel = document.getElementById('assessment-results');

        if (!idlePanel || !loadingPanel || !resultsPanel) return;

        // Start loading
        idlePanel.style.display = 'none';
        resultsPanel.style.display = 'none';
        loadingPanel.style.display = 'flex';

        // Gather metrics
        const ph = parseFloat(document.getElementById('ph').value) || 7.0;
        const solids = parseFloat(document.getElementById('solids').value) || 0.0;
        const chloramines = parseFloat(document.getElementById('chloramines').value) || 0.0;
        const sulfate = parseFloat(document.getElementById('sulfate').value) || 0.0;
        const turbidity = parseFloat(document.getElementById('turbidity').value) || 0.0;

        const safetyScore = calculateSafetyScore(ph, solids, chloramines, sulfate, turbidity);
        
        const formData = new FormData();
        formData.append('ph', ph);
        formData.append('solids', solids);
        formData.append('chloramines', chloramines);
        formData.append('sulfate', sulfate);
        formData.append('turbidity', turbidity);

        let isPotable = safetyScore >= 80;
        let predictionResult = isPotable ? "Potable" : "Not Potable";
        let anomalies = [];
        let suggestions = [];
        let confidence = 0.5;
        let category = getSafetyCategory(safetyScore);
        let shapExplanation = null;

        try {
            const response = await fetch('/', {
                method: 'POST',
                body: formData,
                headers: { 'Accept': 'application/json' }
            });

            if (response.ok) {
                const data = await response.json();
                predictionResult = data.prediction || predictionResult;
                anomalies = data.reasons || [];
                suggestions = data.suggestions || [];
                confidence = data.confidence_score || confidence;
                category = data.water_safety_category || category;
                shapExplanation = data.shap_explanation || null;
                isPotable = (predictionResult === "Potable");

                // Update PDF Download Button
                const downloadPdfBtn = document.getElementById('btn-download-pdf');
                if (downloadPdfBtn) {
                    if (data.id) {
                        downloadPdfBtn.href = `/api/report/${data.id}`;
                        downloadPdfBtn.style.display = 'inline-flex';
                    } else {
                        downloadPdfBtn.style.display = 'none';
                    }
                }
            } else {
                throw new Error("API runtime error.");
            }
        } catch (err) {
            console.warn("Server offline. Using local heuristics:", err);
            // Heuristic fallbacks
            if (ph < 6.5) anomalies.push(`pH level (${ph.toFixed(1)}) is acidic (WHO limit: 6.5–8.5).`);
            else if (ph > 8.5) anomalies.push(`pH level (${ph.toFixed(1)}) is alkaline (WHO limit: 6.5–8.5).`);
            if (solids > 1000) anomalies.push(`Dissolved Solids (${solids.toFixed(0)} ppm) exceeds the WHO standard safe limit (1,000 ppm).`);
            if (chloramines > 4.0) anomalies.push(`Chloramines content (${chloramines.toFixed(1)} ppm) exceeds safe levels (4.0 ppm).`);
            if (sulfate > 250) anomalies.push(`Sulfate concentration (${sulfate.toFixed(0)} mg/L) exceeds safe guidelines (250 mg/L).`);
            if (turbidity > 5.0) anomalies.push(`Turbidity reading (${turbidity.toFixed(1)} NTU) exceeds WHO clarity threshold (5.0 NTU).`);

            if (anomalies.length === 0) {
                suggestions.push("All metrics within guidelines. Standard filtration monitoring advised.");
            } else {
                if (ph < 6.5) suggestions.push("Raise pH using a soda ash or limestone contact calcite filter.");
                if (ph > 8.5) suggestions.push("Lower pH with food-grade carbon dioxide or acid injection.");
                if (solids > 1000) suggestions.push("Install a reverse osmosis (RO) system or deionization beds.");
                if (chloramines > 4) suggestions.push("Deploy active catalytic granular activated carbon (GAC) block filters.");
                if (sulfate > 250) suggestions.push("Lower sulfates with reverse osmosis or strong-base anion exchange resins.");
                if (turbidity > 5) suggestions.push("Inject alum coagulant, allow settling, and run backwash multimedia sand filters.");
            }

            const downloadPdfBtn = document.getElementById('btn-download-pdf');
            if (downloadPdfBtn) {
                downloadPdfBtn.style.display = 'none';
            }
        }

        // Render outcomes
        loadingPanel.style.display = 'none';
        resultsPanel.style.display = 'flex';

        updateSafetyGauge(safetyScore, category);
        renderSafetyBadge(isPotable, safetyScore);
        renderDiagnostics(anomalies, suggestions);
        renderWhoTable(ph, solids, chloramines, sulfate, turbidity);
        renderShapExplanation(shapExplanation, predictionResult, confidence);
        renderMitigationPlanner(ph, solids, chloramines, sulfate, turbidity);
        
        // Reload history telemetry to reflect the newly ingested run
        refreshHistoryLogs();
    });
}

/**
 * Database Fetch & Telemetry Analytics Rebuilders
 */
async function refreshHistoryLogs() {
    try {
        const response = await fetch('/api/history');
        if (response.ok) {
            historyData = await response.json();
            
            // Build main History Table
            populateHistoryTable(historyData);
            
            // Update Dashboard cards stats
            populateDashboardCards(historyData);

            // Rebuild charts if they are visible
            rebuildDashboardCharts();
        }
    } catch (e) {
        console.error("Failed to query DB history logs:", e);
    }
}

function populateHistoryTable(data) {
    const tbody = document.getElementById('history-tbody');
    if (!tbody) return;

    if (data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 2rem;">No historical records found in index.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.map(row => {
        const isSafe = row.prediction === "Potable";
        const statusClass = isSafe ? "small-status-safe" : "small-status-unsafe";
        const scoreColor = isSafe ? "var(--emerald)" : "var(--rose)";
        const dateStr = row.timestamp ? new Date(row.timestamp).toLocaleString() : 'N/A';

        return `
            <tr>
                <td style="color:var(--text-secondary);">${dateStr}</td>
                <td>${row.user_location || 'Unknown'}</td>
                <td>${row.ph.toFixed(1)}</td>
                <td>${row.solids.toFixed(0)}</td>
                <td>${row.chloramines.toFixed(1)}</td>
                <td>${row.sulfate.toFixed(0)}</td>
                <td>${row.turbidity.toFixed(1)}</td>
                <td>
                    <div style="font-weight: 800; color: ${scoreColor}">
                        ${row.water_safety_score}%
                    </div>
                </td>
                <td>
                    <span class="small-status-badge ${statusClass}">
                        ${row.prediction}
                    </span>
                </td>
            </tr>
        `;
    }).join('');
}

function populateDashboardCards(data) {
    const totalRuns = document.getElementById('dash-total-runs');
    const avgScore = document.getElementById('dash-avg-score');
    const criticalCount = document.getElementById('dash-critical-count');
    
    if (totalRuns) totalRuns.textContent = data.length;
    
    if (data.length > 0) {
        const mean = data.reduce((acc, row) => acc + row.water_safety_score, 0) / data.length;
        if (avgScore) avgScore.textContent = `${mean.toFixed(0)}%`;
        
        const critical = data.filter(row => row.water_safety_score <= 40).length;
        if (criticalCount) criticalCount.textContent = critical;
    } else {
        if (avgScore) avgScore.textContent = "--";
        if (criticalCount) criticalCount.textContent = "0";
    }

    // Populate dashboard recent assessments list (max 4 rows)
    const dashTbody = document.getElementById('dash-recent-tbody');
    if (dashTbody) {
        if (data.length === 0) {
            dashTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No submissions yet.</td></tr>`;
            return;
        }
        const recent = data.slice(0, 4);
        dashTbody.innerHTML = recent.map(row => {
            const isSafe = row.prediction === "Potable";
            const scoreColor = isSafe ? "var(--emerald)" : "var(--rose)";
            const statusClass = isSafe ? "small-status-safe" : "small-status-unsafe";
            return `
                <tr>
                    <td>${row.ph.toFixed(1)}</td>
                    <td>${row.solids.toFixed(0)}</td>
                    <td>${row.sulfate.toFixed(0)}</td>
                    <td style="font-weight:700; color:${scoreColor}">${row.water_safety_score}%</td>
                    <td><span class="small-status-badge ${statusClass}">${row.prediction}</span></td>
                </tr>
            `;
        }).join('');
    }
}

/**
 * Dashboard & Analytics Charts Builder
 */
function rebuildDashboardCharts() {
    const isDark = !document.body.classList.contains('light-theme');
    const textHex = isDark ? '#94a3b8' : '#475569';
    const gridHex = isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(15, 23, 42, 0.05)';

    // 1. Dashboard Potability Ratio Chart
    const ratioCanvas = document.getElementById('dashRatioChart');
    if (ratioCanvas && historyData.length > 0) {
        const potableCount = historyData.filter(row => row.prediction === "Potable").length;
        const nonPotableCount = historyData.length - potableCount;

        if (dashRatioChartInstance) {
            dashRatioChartInstance.destroy();
        }

        dashRatioChartInstance = new Chart(ratioCanvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Potable', 'Not Potable'],
                datasets: [{
                    data: [potableCount, nonPotableCount],
                    backgroundColor: ['rgba(16, 185, 129, 0.6)', 'rgba(244, 63, 94, 0.6)'],
                    borderColor: [isDark ? '#0b0f19' : '#ffffff'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textHex, font: { size: 10 } }
                    }
                }
            }
        });
    }

    // 2. Analytics Safety Score Trend Chart (past 10 runs)
    const trendCanvas = document.getElementById('analyticsTrendChart');
    if (trendCanvas && historyData.length > 0) {
        const recentSubset = [...historyData].reverse().slice(-10);
        const labels = recentSubset.map((_, idx) => `Run #${idx + 1}`);
        const scores = recentSubset.map(row => row.water_safety_score);

        if (analyticsTrendChartInstance) {
            analyticsTrendChartInstance.destroy();
        }

        analyticsTrendChartInstance = new Chart(trendCanvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Safety Score %',
                    data: scores,
                    borderColor: 'var(--primary)',
                    backgroundColor: 'rgba(14, 165, 233, 0.05)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 4,
                    pointBackgroundColor: 'var(--primary)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: { color: gridHex },
                        ticks: { color: textHex }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        grid: { color: gridHex },
                        ticks: { color: textHex }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // 3. Analytics Parameter Violations Count Bar Chart
    const barCanvas = document.getElementById('analyticsBarChart');
    if (barCanvas && historyData.length > 0) {
        // Count failure counts across parameters
        let counts = { pH: 0, Solids: 0, Chloramines: 0, Sulfate: 0, Turbidity: 0 };
        
        historyData.forEach(row => {
            if (row.ph < 6.5 || row.ph > 8.5) counts.pH++;
            if (row.solids > 1000) counts.Solids++;
            if (row.chloramines > 4.0) counts.Chloramines++;
            if (row.sulfate > 250) counts.Sulfate++;
            if (row.turbidity > 5.0) counts.Turbidity++;
        });

        if (analyticsBarChartInstance) {
            analyticsBarChartInstance.destroy();
        }

        analyticsBarChartInstance = new Chart(barCanvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: Object.keys(counts),
                datasets: [{
                    label: 'Guideline Violations',
                    data: Object.values(counts),
                    backgroundColor: 'rgba(244, 63, 94, 0.55)',
                    borderColor: 'var(--rose)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: textHex }
                    },
                    y: {
                        grid: { color: gridHex },
                        ticks: { color: textHex, stepSize: 1 }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
}

/**
 * Lazy loads multi-model evaluation charts on the performance page
 */
async function loadPerformanceTelemetry() {
    try {
        const response = await fetch('/api/performance-data');
        if (!response.ok) return;
        const data = await response.json();

        // Render comparative cards
        const xgb = data.metrics["XGBoost"];
        if (xgb) {
            document.getElementById('card-acc').textContent = `${(xgb.accuracy * 100).toFixed(1)}%`;
            document.getElementById('card-f1').textContent = `${(xgb.f1 * 100).toFixed(1)}%`;
            document.getElementById('card-auc').textContent = `${(xgb.auc * 100).toFixed(1)}%`;
        }

        // Populate Table
        const tbody = document.getElementById('metrics-table-body');
        if (tbody) {
            tbody.innerHTML = Object.keys(data.metrics).map(name => {
                const isXG = name === "XGBoost";
                const rowClass = isXG ? 'class="selected-model-row"' : '';
                const tag = isXG ? '<span class="badge-selected">Selected</span>' : '<span style="color:var(--text-muted)">Alternative</span>';
                const stats = data.metrics[name];
                return `
                    <tr ${rowClass}>
                        <td style="font-weight:700; color: ${isXG ? 'var(--text-bright)' : 'var(--text-secondary)'}">${name}</td>
                        <td>${(stats.accuracy * 100).toFixed(1)}%</td>
                        <td>${(stats.precision * 100).toFixed(1)}%</td>
                        <td>${(stats.recall * 100).toFixed(1)}%</td>
                        <td>${(stats.f1 * 100).toFixed(1)}%</td>
                        <td>${(stats.auc * 100).toFixed(1)}%</td>
                        <td>${tag}</td>
                    </tr>
                `;
            }).join('');
        }

        // Populate Confusion Matrix values
        const matrix = data.xgboost_confusion_matrix;
        if (matrix) {
            document.getElementById('matrix-tn').textContent = matrix.tn;
            document.getElementById('matrix-fp').textContent = matrix.fp;
            document.getElementById('matrix-fn').textContent = matrix.fn;
            document.getElementById('matrix-tp').textContent = matrix.tp;
        }

        // Render Charts
        const isDark = !document.body.classList.contains('light-theme');
        const textHex = isDark ? '#94a3b8' : '#475569';
        const gridHex = isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(15, 23, 42, 0.05)';

        // 1. ROC Curve
        const rocCanvas = document.getElementById('rocChart');
        if (rocCanvas) {
            const colors = {
                "Logistic Regression": "rgba(244, 63, 94, 0.75)",
                "Decision Tree": "rgba(245, 158, 11, 0.75)",
                "Random Forest": "rgba(16, 185, 129, 0.75)",
                "SVM": "rgba(168, 85, 247, 0.75)",
                "XGBoost": "rgba(14, 165, 233, 1)"
            };

            const datasets = Object.keys(data.roc_curves).map(name => {
                const isXG = name === "XGBoost";
                return {
                    label: name,
                    data: data.roc_curves[name],
                    borderColor: colors[name] || '#ffffff',
                    borderWidth: isXG ? 3 : 1.5,
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.1
                };
            });

            datasets.push({
                label: "Random Guess",
                data: [{x:0, y:0}, {x:1, y:1}],
                borderColor: "rgba(255, 255, 255, 0.15)",
                borderWidth: 1,
                borderDash: [5, 5],
                fill: false,
                pointRadius: 0
            });

            if (rocChartInstance) rocChartInstance.destroy();
            rocChartInstance = new Chart(rocCanvas.getContext('2d'), {
                type: 'line',
                data: { datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'linear',
                            position: 'bottom',
                            grid: { color: gridHex },
                            ticks: { color: textHex },
                            title: { display: true, text: 'False Positive Rate (FPR)', color: textHex, font: { size: 9 } }
                        },
                        y: {
                            type: 'linear',
                            grid: { color: gridHex },
                            ticks: { color: textHex },
                            title: { display: true, text: 'True Positive Rate (TPR)', color: textHex, font: { size: 9 } }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: textHex, font: { size: 9 } } }
                    }
                }
            });
        }

        // 2. Feature Importances
        const impCanvas = document.getElementById('importanceChart');
        if (impCanvas) {
            const sorted = data.xgboost_feature_importances.sort((a,b) => b.importance - a.importance);
            
            if (importanceChartInstance) importanceChartInstance.destroy();
            importanceChartInstance = new Chart(impCanvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: sorted.map(item => item.feature),
                    datasets: [{
                        data: sorted.map(item => item.importance * 100),
                        backgroundColor: 'rgba(14, 165, 233, 0.45)',
                        borderColor: 'var(--primary)',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            grid: { color: gridHex },
                            ticks: { color: textHex },
                            title: { display: true, text: 'Importance Weight %', color: textHex, font: { size: 9 } }
                        },
                        y: {
                            grid: { display: false },
                            ticks: { color: textHex }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

    } catch (e) {
        console.error("Failed to load multi-model comparison graphics:", e);
    }
}

/**
 * Ingestion and History Controllers
 */
function initHistoryControls() {
    const searchInput = document.getElementById('history-search');
    const refreshBtn = document.getElementById('btn-refresh-history');
    const downloadBtn = document.getElementById('btn-download-csv');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const q = e.target.value.toLowerCase();
            const filtered = historyData.filter(row => {
                return (
                    row.prediction.toLowerCase().includes(q) ||
                    (row.user_location && row.user_location.toLowerCase().includes(q)) ||
                    row.water_safety_score.toString().includes(q) ||
                    row.ph.toString().includes(q) ||
                    row.solids.toString().includes(q) ||
                    row.sulfate.toString().includes(q)
                );
            });
            populateHistoryTable(filtered);
        });
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            const icon = refreshBtn.querySelector('i');
            if (icon) icon.classList.add('spin-animation');
            
            refreshHistoryLogs().then(() => {
                setTimeout(() => {
                    if (icon) icon.classList.remove('spin-animation');
                }, 600);
            });
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            exportCSV();
        });
    }
}

function exportCSV() {
    if (historyData.length === 0) {
        alert("No logs available to export.");
        return;
    }

    const headers = ["ID", "Timestamp", "Location", "pH", "TDS (ppm)", "Chloramines (ppm)", "Sulfate (mg/L)", "Turbidity (NTU)", "Score %", "Prediction"];
    const csvRows = [headers.join(",")];

    historyData.forEach(row => {
        const rowVals = [
            row.id,
            `"${row.timestamp}"`,
            `"${row.user_location || 'Unknown'}"`,
            row.ph.toFixed(2),
            row.solids.toFixed(0),
            row.chloramines.toFixed(2),
            row.sulfate.toFixed(0),
            row.turbidity.toFixed(2),
            row.water_safety_score,
            row.prediction
        ];
        csvRows.push(rowVals.join(","));
    });

    const csvContent = "data:text/csv;charset=utf-8," + csvRows.join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `hydrosafe_ingestion_report_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * SVG Gauge & Local Heuristics
 */
function updateSafetyGauge(score, category) {
    const fillCircle = document.getElementById('gauge-fill-circle');
    const scoreSpan = document.getElementById('result-score');
    const categorySpan = document.getElementById('result-category');

    if (!fillCircle || !scoreSpan) return;

    const radius = 70;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;

    fillCircle.style.strokeDashoffset = offset;

    // Smooth counter
    let currentScore = 0;
    const speed = score > 0 ? Math.max(5, Math.floor(1000 / score)) : 5;
    scoreSpan.textContent = "0%";

    const interval = setInterval(() => {
        if (currentScore >= score) {
            scoreSpan.textContent = `${score}%`;
            clearInterval(interval);
        } else {
            currentScore++;
            scoreSpan.textContent = `${currentScore}%`;
        }
    }, speed);

    if (categorySpan) {
        categorySpan.innerHTML = `Index // <strong style="color:var(--text-primary)">${category}</strong>`;
    }
}

function renderSafetyBadge(isPotable, score) {
    const badge = document.getElementById('safety-badge');
    const badgeText = document.getElementById('safety-badge-text');
    if (!badge || !badgeText) return;

    const iconPlaceholder = document.getElementById('safety-icon-placeholder');

    if (isPotable) {
        badge.className = 'safety-badge badge-safe';
        badgeText.textContent = 'STANDARD SAFE';
        if (iconPlaceholder) {
            iconPlaceholder.innerHTML = '<i data-lucide="shield-check" size="13"></i>';
        }
    } else {
        badge.className = 'safety-badge badge-unsafe';
        badgeText.textContent = 'POTENTIAL RISK';
        if (iconPlaceholder) {
            iconPlaceholder.innerHTML = '<i data-lucide="alert-triangle" size="13"></i>';
        }
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

function renderDiagnostics(anomalies, recommendations) {
    const container = document.getElementById('issues-container');
    const anomaliesList = document.getElementById('issues-list');
    const recsList = document.getElementById('recs-list');

    if (!container || !anomaliesList || !recsList) return;

    if (anomalies.length > 0) {
        container.style.display = 'flex';
        anomaliesList.innerHTML = anomalies.map(text => `<li>${text}</li>`).join('');
    } else {
        container.style.display = 'none';
        anomaliesList.innerHTML = '';
    }

    if (recommendations.length > 0) {
        recsList.innerHTML = recommendations.map(text => `<li>${text}</li>`).join('');
    } else {
        recsList.innerHTML = '<li>All chemical metrics are within clean margins. Maintain regular filtration systems.</li>';
    }
}

function renderWhoTable(ph, solids, chloramines, sulfate, turbidity) {
    const tbody = document.getElementById('who-tbody');
    const container = document.getElementById('who-table-container');
    if (!tbody || !container) return;

    container.style.display = 'block';

    const standards = [
        { name: "pH Level", limit: "6.5 – 8.5", value: ph.toFixed(1), pass: (ph >= 6.5 && ph <= 8.5) },
        { name: "Dissolved Solids", limit: "< 1000 ppm", value: `${solids.toFixed(0)} ppm`, pass: (solids <= 1000) },
        { name: "Chloramines", limit: "< 4.0 ppm", value: `${chloramines.toFixed(1)} ppm`, pass: (chloramines <= 4.0) },
        { name: "Sulfate", limit: "< 250 mg/L", value: `${sulfate.toFixed(0)} mg/L`, pass: (sulfate <= 250) },
        { name: "Turbidity", limit: "< 5.0 NTU", value: `${turbidity.toFixed(1)} NTU`, pass: (turbidity <= 5.0) }
    ];

    tbody.innerHTML = standards.map(std => {
        const statusClass = std.pass ? 'who-status-pass' : 'who-status-fail';
        const statusText = std.pass ? '✓ Pass' : '✗ Fail';
        return `
            <tr>
                <td style="font-weight:600; color:var(--text-primary)">${std.name}</td>
                <td>${std.limit}</td>
                <td>${std.value}</td>
                <td class="${statusClass}">${statusText}</td>
            </tr>
        `;
    }).join('');
}

function renderShapExplanation(shapExplanation, prediction, confidence) {
    const container = document.getElementById('shap-container');
    const textEl = document.getElementById('shap-confidence-text');
    const listEl = document.getElementById('shap-factors-list');

    if (!container) return;

    if (!shapExplanation) {
        container.style.display = 'block';
        if (textEl) textEl.textContent = "Model Engine Offline: SHAP explainability is unavailable.";
        if (listEl) listEl.innerHTML = "";
        const canvas = document.getElementById('shapChart');
        if (canvas) canvas.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    const canvas = document.getElementById('shapChart');
    if (canvas) canvas.style.display = 'block';

    const confPercent = (confidence * 100).toFixed(1);
    if (textEl) {
        textEl.innerHTML = `Model is <strong>${confPercent}% confident</strong> in classifying this sample as <strong>${prediction}</strong>.`;
    }

    const contributions = shapExplanation.contributions;
    const features = Object.keys(contributions);
    const values = features.map(f => contributions[f]);

    const bgColors = values.map(val => val >= 0 ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.45)');
    const borderColors = values.map(val => val >= 0 ? 'var(--emerald)' : 'var(--rose)');

    const ctx = canvas.getContext('2d');
    if (shapChartInstance) {
        shapChartInstance.destroy();
    }

    shapChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: features,
            datasets: [{
                data: values,
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: 'rgba(255, 255, 255, 0.5)', font: { size: 9 } },
                    title: { display: true, text: '◄── Unsafe / Reduces Potability  |  Safe / Increases Potability ──►', color: 'rgba(255,255,255,0.6)', font: { size: 8 } }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: 'rgba(255, 255, 255, 0.75)', font: { size: 9, family: 'Inter' } }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });

    if (listEl && shapExplanation.top_factors) {
        const top = shapExplanation.top_factors;
        listEl.innerHTML = `
            <div style="font-weight: 700; color: var(--text-primary); margin-bottom: 0.25rem;">Key Driving Parameters:</div>
            ${top.slice(0, 2).map((factor, idx) => {
                const isPositive = factor.impact >= 0;
                const txt = isPositive ? 'positive contribution boosting potability' : 'negative impact reducing safety';
                const color = isPositive ? 'var(--emerald)' : 'var(--rose)';
                return `
                    <li style="margin-left: 0.5rem; position: relative; padding-left: 0.75rem;">
                        <span style="position: absolute; left: 0; color: ${color}; font-weight: bold;">•</span>
                        <strong>${factor.feature}</strong> acts as the ${idx === 0 ? 'highest' : 'second highest'} driver (${txt}).
                    </li>
                `;
            }).join('')}
        `;
    }
}

function renderMitigationPlanner(ph, solids, chloramines, sulfate, turbidity) {
    const idleEl = document.getElementById('mitigation-idle');
    const activeEl = document.getElementById('mitigation-active');
    const listEl = document.getElementById('mitigation-list');

    if (!idleEl || !activeEl || !listEl) return;

    let tasks = [];

    if (ph < 6.5) {
        tasks.push({
            parameter: 'pH Level (Acidic)',
            icon: 'arrow-up-circle',
            deviationClass: 'mitigation-deviation-up',
            deviationText: `Raise by +${(7.2 - ph).toFixed(1)} units`,
            details: `Water is corrosive (Current: <strong>${ph.toFixed(1)}</strong>, Target: <strong>7.2</strong>). Feed <strong>Soda Ash (Sodium Carbonate)</strong> at a continuous dosage of <strong>10–25 mg/L</strong>, or route flow through a limestone contact calcite filter. Recalibrate pH electrodes and test values every 30 minutes.`
        });
    } else if (ph > 8.5) {
        tasks.push({
            parameter: 'pH Level (Alkaline)',
            icon: 'arrow-down-circle',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Reduce by -${(ph - 7.2).toFixed(1)} units`,
            details: `High alkalinity causing mineral scale (Current: <strong>${ph.toFixed(1)}</strong>, Target: <strong>7.2</strong>). Inject diluted <strong>citric acid</strong> or run a carbon dioxide (CO2) carbonation diffuser system. Adjust dosage iteratively to maintain chemical stabilization.`
        });
    }

    if (solids > 1000) {
        tasks.push({
            parameter: 'Dissolved Solids (TDS)',
            icon: 'filter',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Reduce by -${(solids - 500).toFixed(0)} ppm`,
            details: `High mineral content (Current: <strong>${solids.toFixed(0)} ppm</strong>, Target: <strong>500 ppm</strong>). Initiate a high-pressure <strong>Reverse Osmosis (RO) filtration pass</strong> at 95–98% rejection rate. Clean pre-sediment filters to protect membranes.`
        });
    }

    if (chloramines > 4.0) {
        tasks.push({
            parameter: 'Chloramines Content',
            icon: 'shield-alert',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Reduce by -${(chloramines - 1.5).toFixed(1)} ppm`,
            details: `Excess chloramines causing eye/skin irritation (Current: <strong>${chloramines.toFixed(1)} ppm</strong>, Target: <strong>1.5 ppm</strong>). Feed effluent through high-performance <strong>Catalytic Carbon Block beds</strong>. Verify output using DPD colorimetric test kits.`
        });
    }

    if (sulfate > 250) {
        tasks.push({
            parameter: 'Sulfate Concentration',
            icon: 'droplet',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Reduce by -${(sulfate - 150).toFixed(0)} mg/L`,
            details: `Sulfate load above safe aesthetic levels (Current: <strong>${sulfate.toFixed(0)} mg/L</strong>, Target: <strong>150 mg/L</strong>). Run water through <strong>anion-exchange resin beds</strong> (regenerated with NaCl salt brine) or Reverse Osmosis filtration.`
        });
    }

    if (turbidity > 5.0) {
        tasks.push({
            parameter: 'Turbidity (Clarity)',
            icon: 'eye-off',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Clear by -${(turbidity - 0.8).toFixed(1)} NTU`,
            details: `Particulates blocking clarity and shields bacteria (Current: <strong>${turbidity.toFixed(1)} NTU</strong>, Target: <strong>&lt; 1.0 NTU</strong>). Add <strong>Aluminum Sulfate (Alum) coagulant</strong> at 15–30 mg/L to flocculate, allow 40 mins settling, then sand filter.`
        });
    }

    if (tasks.length > 0) {
        idleEl.style.display = 'none';
        activeEl.style.display = 'block';
        listEl.innerHTML = tasks.map(task => `
            <div class="mitigation-task-card">
                <div class="mitigation-task-header">
                    <span class="mitigation-param-title">
                        <i data-lucide="${task.icon}" size="14"></i>
                        <span>${task.parameter}</span>
                    </span>
                    <span class="mitigation-deviation-badge ${task.deviationClass}">
                        ${task.deviationText}
                    </span>
                </div>
                <div class="mitigation-task-details">
                    ${task.details}
                </div>
            </div>
        `).join('');
    } else {
        idleEl.style.display = 'flex';
        activeEl.style.display = 'none';
        listEl.innerHTML = '';
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

function calculateSafetyScore(ph, solids, chloramines, sulfate, turbidity) {
    let penalty = 0;
    if (ph < 6.5) penalty += (6.5 - ph) * 20;
    else if (ph > 8.5) penalty += (ph - 8.5) * 20;
    if (solids > 1000) penalty += ((solids - 1000) / 1000) * 35;
    if (chloramines > 4.0) penalty += ((chloramines - 4.0) / 4.0) * 35;
    if (sulfate > 250) penalty += ((sulfate - 250) / 250) * 35;
    if (turbidity > 5.0) penalty += ((turbidity - 5.0) / 5.0) * 35;
    return Math.max(0, Math.round(100 - penalty));
}

function getSafetyCategory(score) {
    if (score <= 20) return "Critical";
    if (score <= 40) return "Poor";
    if (score <= 60) return "Moderate";
    if (score <= 80) return "Good";
    return "Excellent";
}

/**
 * Smart City IoT Simulator Loop Binder
 */
function initIoTSimulator() {
    const btn = document.getElementById('btn-toggle-iot');
    if (btn) {
        btn.addEventListener('click', () => {
            toggleIoTSimulation();
        });
    }
}

function toggleIoTSimulation() {
    const btn = document.getElementById('btn-toggle-iot');
    const statusLbl = document.getElementById('iot-status-lbl');
    const pulse = document.getElementById('iot-pulse');

    if (!btn || !statusLbl || !pulse) return;

    if (iotInterval) {
        // Stop simulator
        clearInterval(iotInterval);
        iotInterval = null;
        btn.textContent = "Enable";
        btn.style.backgroundColor = "";
        statusLbl.textContent = "Offline";
        statusLbl.style.color = "";
        pulse.style.backgroundColor = "var(--text-muted)";
        pulse.style.boxShadow = "none";
        return;
    }

    // Start simulator
    btn.textContent = "Disable";
    btn.style.backgroundColor = "var(--rose)";
    statusLbl.textContent = "Active";
    statusLbl.style.color = "var(--primary)";
    pulse.style.backgroundColor = "var(--primary)";
    pulse.style.boxShadow = "0 0 8px var(--primary)";

    const sectors = [
        { name: "IoT Sensor - Sector A", cardId: "sector-north", valId: "val-sector-north", lblId: "lbl-sector-north", startNode: 1, endNode: 4 },
        { name: "IoT Sensor - Sector B", cardId: "sector-downtown", valId: "val-sector-downtown", lblId: "lbl-sector-downtown", startNode: 5, endNode: 8 },
        { name: "IoT Sensor - Sector C", cardId: "sector-industrial", valId: "val-sector-industrial", lblId: "lbl-sector-industrial", startNode: 9, endNode: 12 },
        { name: "IoT Sensor - Sector D", cardId: "sector-suburbs", valId: "val-sector-suburbs", lblId: "lbl-sector-suburbs", startNode: 13, endNode: 16 }
    ];

    // Tick immediately, then repeat every 4 seconds
    runSingleIoTTick(sectors);
    iotInterval = setInterval(() => {
        runSingleIoTTick(sectors);
    }, 4000);
}

async function runSingleIoTTick(sectors) {
    const sector = sectors[currentSectorIdx];
    currentSectorIdx = (currentSectorIdx + 1) % sectors.length;

    // Randomize slider values (simulating a natural fluctuating sensor input)
    const ph = parseFloat((Math.random() * (9.2 - 5.8) + 5.8).toFixed(1));
    const solids = Math.floor(Math.random() * 1500 + 100);
    const chloramines = parseFloat((Math.random() * 6.5 + 0.5).toFixed(1));
    const sulfate = Math.floor(Math.random() * 450 + 50);
    const turbidity = parseFloat((Math.random() * 8.5 + 0.5).toFixed(1));

    // Update UI Sliders visual state
    const sliders = { ph, solids, chloramines, sulfate, turbidity };
    Object.keys(sliders).forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.value = sliders[id];
            el.dispatchEvent(new Event('input'));
        }
    });

    const safetyScore = calculateSafetyScore(ph, solids, chloramines, sulfate, turbidity);
    const category = getSafetyCategory(safetyScore);

    // Call API with location override
    try {
        const formData = new FormData();
        formData.append('ph', ph);
        formData.append('solids', solids);
        formData.append('chloramines', chloramines);
        formData.append('sulfate', sulfate);
        formData.append('turbidity', turbidity);
        formData.append('location', sector.name);

        const response = await fetch('/', {
            method: 'POST',
            body: formData,
            headers: { 'Accept': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            const prediction = data.prediction || (safetyScore >= 80 ? "Potable" : "Not Potable");
            const score = data.water_safety_score || safetyScore;
            const cat = data.water_safety_category || category;

            // Update Sector Card text and colors immediately
            const card = document.getElementById(sector.cardId);
            const valEl = document.getElementById(sector.valId);
            const lblEl = document.getElementById(sector.lblId);
            const dot = card ? card.querySelector('.status-dot') : null;

            if (valEl) valEl.textContent = `${score}%`;
            if (lblEl) lblEl.textContent = `Quality: ${cat}`;

            let styleClass = 'safe';
            let dotColor = 'var(--emerald)';
            if (score <= 40) {
                styleClass = 'unsafe';
                dotColor = 'var(--rose)';
            } else if (score <= 75) {
                styleClass = 'warning';
                dotColor = 'var(--amber)';
            }

            if (card) {
                card.style.borderColor = `var(--${styleClass === 'safe' ? 'emerald' : styleClass === 'unsafe' ? 'rose' : 'amber'})`;
            }
            if (dot) {
                dot.style.backgroundColor = dotColor;
                dot.style.boxShadow = `0 0 8px ${dotColor}`;
            }

            // Paint corresponding sector heatmap nodes
            for (let n = sector.startNode; n <= sector.endNode; n++) {
                const nodeEl = document.querySelector(`.heatmap-node[data-node="${n}"]`);
                if (nodeEl) {
                    nodeEl.className = `heatmap-node ${styleClass}`;
                }
            }

            // Refresh history logs to update all other graphs/dashboards
            await refreshHistoryLogs();

            // Refresh location aggregates table
            await refreshLocationAnalyticsOnly();
        }
    } catch (err) {
        console.error("IoT Simulator Tick API Error:", err);
    }
}

/**
 * Smart City visualizers node update and location-based aggregates table
 */
async function updateSmartCityUI() {
    try {
        const response = await fetch('/api/location-analytics');
        if (!response.ok) return;
        const data = await response.json();
        
        // Populate Location Analytics Table
        const tbody = document.getElementById('location-tbody');
        if (tbody) {
            if (data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No location aggregates found.</td></tr>`;
            } else {
                tbody.innerHTML = data.map(row => {
                    return `
                        <tr>
                            <td style="font-weight: 600; color: var(--text-primary);">${row.location}</td>
                            <td>${row.total_assessments}</td>
                            <td><strong style="color: var(--primary);">${row.avg_safety_score}%</strong></td>
                            <td>${row.potability_rate}%</td>
                            <td style="color: ${row.primary_contaminant !== 'None' ? 'var(--rose)' : 'var(--text-muted)'}; font-weight: 600;">${row.primary_contaminant}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        // Sector mapping to card element IDs and node index bounds
        const sectorMapping = {
            "IoT Sensor - Sector A": { cardId: "sector-north", valId: "val-sector-north", lblId: "lbl-sector-north", startNode: 1, endNode: 4 },
            "IoT Sensor - Sector B": { cardId: "sector-downtown", valId: "val-sector-downtown", lblId: "lbl-sector-downtown", startNode: 5, endNode: 8 },
            "IoT Sensor - Sector C": { cardId: "sector-industrial", valId: "val-sector-industrial", lblId: "lbl-sector-industrial", startNode: 9, endNode: 12 },
            "IoT Sensor - Sector D": { cardId: "sector-suburbs", valId: "val-sector-suburbs", lblId: "lbl-sector-suburbs", startNode: 13, endNode: 16 }
        };

        // Reset all nodes to default grey first
        const allNodes = document.querySelectorAll('.heatmap-node');
        allNodes.forEach(node => {
            node.className = 'heatmap-node';
        });

        // Initialize/Update each sector based on latest database summaries
        Object.keys(sectorMapping).forEach(locName => {
            const config = sectorMapping[locName];
            const sectorData = data.find(d => d.location === locName);
            
            const card = document.getElementById(config.cardId);
            const valEl = document.getElementById(config.valId);
            const lblEl = document.getElementById(config.lblId);
            const dot = card ? card.querySelector('.status-dot') : null;

            if (sectorData) {
                const score = sectorData.avg_safety_score;
                const cat = getSafetyCategory(score);

                if (valEl) valEl.textContent = `${score.toFixed(0)}%`;
                if (lblEl) lblEl.textContent = `Avg Quality: ${cat}`;

                // Set styling based on compliance categories
                let styleClass = 'safe';
                let dotColor = 'var(--emerald)';
                if (score <= 40) {
                    styleClass = 'unsafe';
                    dotColor = 'var(--rose)';
                } else if (score <= 75) {
                    styleClass = 'warning';
                    dotColor = 'var(--amber)';
                }

                if (card) {
                    card.style.borderColor = `var(--${styleClass === 'safe' ? 'emerald' : styleClass === 'unsafe' ? 'rose' : 'amber'})`;
                }
                if (dot) {
                    dot.style.backgroundColor = dotColor;
                    dot.style.boxShadow = `0 0 8px ${dotColor}`;
                }

                // Paint nodes
                for (let n = config.startNode; n <= config.endNode; n++) {
                    const nodeEl = document.querySelector(`.heatmap-node[data-node="${n}"]`);
                    if (nodeEl) {
                        nodeEl.classList.add(styleClass);
                    }
                }
            } else {
                // Default placeholder state if no telemetry logs are present
                if (valEl) valEl.textContent = `--`;
                if (lblEl) lblEl.textContent = `No active telemetry`;
                if (card) card.style.borderColor = '';
                if (dot) {
                    dot.style.backgroundColor = 'var(--text-muted)';
                    dot.style.boxShadow = 'none';
                }
            }
        });

    } catch (e) {
        console.error("Error updating Smart City UI:", e);
    }
}

async function refreshLocationAnalyticsOnly() {
    try {
        const response = await fetch('/api/location-analytics');
        if (!response.ok) return;
        const data = await response.json();
        const tbody = document.getElementById('location-tbody');
        if (tbody) {
            if (data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No location records found.</td></tr>`;
            } else {
                tbody.innerHTML = data.map(row => {
                    return `
                        <tr>
                            <td style="font-weight: 600; color: var(--text-primary);">${row.location}</td>
                            <td>${row.total_assessments}</td>
                            <td><strong style="color: var(--primary);">${row.avg_safety_score}%</strong></td>
                            <td>${row.potability_rate}%</td>
                            <td style="color: ${row.primary_contaminant !== 'None' ? 'var(--rose)' : 'var(--text-muted)'}; font-weight: 600;">${row.primary_contaminant}</td>
                        </tr>
                    `;
                }).join('');
            }
        }
    } catch (e) {
        console.error("Failed to refresh location table:", e);
    }
}

function initHeatmapNodeClicks() {
    const nodes = document.querySelectorAll('.heatmap-node');
    nodes.forEach(node => {
        node.addEventListener('click', () => {
            const nodeNum = parseInt(node.getAttribute('data-node'));
            let sectorIndex = 0;
            if (nodeNum >= 1 && nodeNum <= 4) sectorIndex = 0;
            else if (nodeNum >= 5 && nodeNum <= 8) sectorIndex = 1;
            else if (nodeNum >= 9 && nodeNum <= 12) sectorIndex = 2;
            else if (nodeNum >= 13 && nodeNum <= 16) sectorIndex = 3;

            const sectors = [
                { name: "IoT Sensor - Sector A", cardId: "sector-north", valId: "val-sector-north", lblId: "lbl-sector-north", startNode: 1, endNode: 4 },
                { name: "IoT Sensor - Sector B", cardId: "sector-downtown", valId: "val-sector-downtown", lblId: "lbl-sector-downtown", startNode: 5, endNode: 8 },
                { name: "IoT Sensor - Sector C", cardId: "sector-industrial", valId: "val-sector-industrial", lblId: "lbl-sector-industrial", startNode: 9, endNode: 12 },
                { name: "IoT Sensor - Sector D", cardId: "sector-suburbs", valId: "val-sector-suburbs", lblId: "lbl-sector-suburbs", startNode: 13, endNode: 16 }
            ];

            // Set current sector index and trigger single tick manually
            currentSectorIdx = sectorIndex;
            runSingleIoTTick(sectors);
        });
    });
}