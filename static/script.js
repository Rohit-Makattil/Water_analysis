/**
 * HydroSafe Dashboard - Interactive Client Controller
 */

let sessionHistory = [];

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // 2. Initialize Real-Time Live Clock
    initLiveClock();

    // 3. Connect Range Sliders to Value Badges
    initRangeSliders();

    // 4. Connect Form Submission Handler
    initFormHandler();
});

/**
 * Updates the live clock in the top bar every minute
 */
function initLiveClock() {
    const timeEl = document.getElementById('live-time');
    if (!timeEl) return;

    const formatTime = () => {
        const now = new Date();
        const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
        const month = months[now.getMonth()];
        const day = String(now.getDate()).padStart(2, '0');
        const year = now.getFullYear();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        timeEl.textContent = `${month} ${day}, ${year} // ${hours}:${minutes}`;
    };

    formatTime();
    setInterval(formatTime, 60000);
}

/**
 * Connects sliders to their visual badges for instant feedback
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
            
            // Listen to both input (live dragging) and change
            slider.addEventListener('input', updateBadge);
            updateBadge(); // Initial pre-fill
        }
    });
}

/**
 * Setup AJAX form interceptor
 */
function initFormHandler() {
    const form = document.getElementById('ingestionForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await computeWaterSafety();
    });
}

/**
 * Computes safety score based on parameters
 */
function calculateSafetyScore(ph, solids, chloramines, sulfate, turbidity) {
    let penalty = 0;

    // pH safe range: 6.5 - 8.5
    if (ph < 6.5) penalty += (6.5 - ph) * 20;
    else if (ph > 8.5) penalty += (ph - 8.5) * 20;

    // Solids (TDS) safe limit: 1000 ppm
    if (solids > 1000) penalty += ((solids - 1000) / 1000) * 35;

    // Chloramines safe limit: 4.0 ppm
    if (chloramines > 4.0) penalty += ((chloramines - 4.0) / 4.0) * 35;

    // Sulfate safe limit: 250 mg/L
    if (sulfate > 250) penalty += ((sulfate - 250) / 250) * 35;

    // Turbidity safe limit: 5.0 NTU
    if (turbidity > 5.0) penalty += ((turbidity - 5.0) / 5.0) * 35;

    return Math.max(0, Math.round(100 - penalty));
}

/**
 * Runs the safety calculation and server side prediction request
 */
async function computeWaterSafety() {
    const idlePanel = document.getElementById('assessment-idle');
    const loadingPanel = document.getElementById('assessment-loading');
    const resultsPanel = document.getElementById('assessment-results');

    if (!idlePanel || !loadingPanel || !resultsPanel) return;

    // 1. Enter snappier, professional Loading State
    idlePanel.style.display = 'none';
    resultsPanel.style.display = 'none';
    loadingPanel.style.display = 'flex';

    // 2. Gather active input parameters
    const ph = parseFloat(document.getElementById('ph').value) || 7.0;
    const solids = parseFloat(document.getElementById('solids').value) || 0.0;
    const chloramines = parseFloat(document.getElementById('chloramines').value) || 0.0;
    const sulfate = parseFloat(document.getElementById('sulfate').value) || 0.0;
    const turbidity = parseFloat(document.getElementById('turbidity').value) || 0.0;

    // 3. Compute client-side mathematical Safety Score
    const safetyScore = calculateSafetyScore(ph, solids, chloramines, sulfate, turbidity) || 0;

    // 4. Build Flask Form Request
    const formData = new FormData();
    formData.append('ph', ph);
    formData.append('solids', solids);
    formData.append('chloramines', chloramines);
    formData.append('sulfate', sulfate);
    formData.append('turbidity', turbidity);

    let isPotable = safetyScore >= 80; // Standard threshold
    let predictionResult = isPotable ? "Potable" : "Not Potable";
    let anomalyReasons = [];
    let treatmentSuggestions = [];

    try {
        // Fetch diagnosis prediction from the Flask server
        const response = await fetch('/', {
            method: 'POST',
            body: formData,
            headers: {
                'Accept': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            predictionResult = data.prediction || predictionResult;
            anomalyReasons = data.reasons || [];
            treatmentSuggestions = data.suggestions || [];
            isPotable = (predictionResult === "Potable");
        } else {
            throw new Error("HTTP failure response from model server");
        }
    } catch (err) {
        console.warn("Server model engine offline. Utilizing standard fallback heuristics:", err);
        // Clean client fallback diagnostics
        if (ph < 6.5) anomalyReasons.push(`pH level (${ph.toFixed(1)}) is acidic (safe bounds: 6.5–8.5).`);
        else if (ph > 8.5) anomalyReasons.push(`pH level (${ph.toFixed(1)}) is alkaline (safe bounds: 6.5–8.5).`);
        
        if (solids > 1000) anomalyReasons.push(`Total Dissolved Solids (${solids.toFixed(0)} ppm) exceeds the standard safe limit (1,000 ppm).`);
        if (chloramines > 4) anomalyReasons.push(`Chloramines content (${chloramines.toFixed(1)} ppm) exceeds the disinfection safety threshold (4.0 ppm).`);
        if (sulfate > 250) anomalyReasons.push(`Sulfate concentration (${sulfate.toFixed(0)} mg/L) exceeds secondary drinking water standards (250 mg/L).`);
        if (turbidity > 5) anomalyReasons.push(`Turbidity reading (${turbidity.toFixed(1)} NTU) exceeds clarity limits (< 5.0 NTU).`);

        if (anomalyReasons.length === 0) {
            treatmentSuggestions.push("Water parameters reside within clean drinking water thresholds. Normal operating parameters confirmed.");
        } else {
            // Map standard suggestions
            if (ph < 6.5) treatmentSuggestions.push("Neutralize acidity using soda ash or calcite feed injection.");
            if (ph > 8.5) treatmentSuggestions.push("Lower high alkalinity with chemical pH reducers or CO2 injection.");
            if (solids > 1000) treatmentSuggestions.push("Deploy a reverse osmosis (RO) system or demineralization unit.");
            if (chloramines > 4) treatmentSuggestions.push("Utilize catalytic granular activated carbon (GAC) block filters.");
            if (sulfate > 250) treatmentSuggestions.push("Install anion-exchange resin beds or reverse osmosis filtration.");
            if (turbidity > 5) treatmentSuggestions.push("Add a chemical flocculant (e.g. alum), let settle, then backwash filters.");
        }
    }

    // 5. Hide Loader, Render Results Instantly (removing fake scanning delays)
    loadingPanel.style.display = 'none';
    resultsPanel.style.display = 'flex';

    // 6. Animate and update Safety Score Gauge
    updateSafetyGauge(safetyScore);

    // 7. Render Safety Badge
    renderSafetyBadge(isPotable, safetyScore);

    // 8. Render anomalies and recommendations list
    renderDiagnostics(anomalyReasons, treatmentSuggestions);

    // 8b. Render the Dynamic Treatment & Mitigation Planner
    renderMitigationPlanner(ph, solids, chloramines, sulfate, turbidity);

    // 9. Update Metrics Widgets
    updateMetricsWidgets(safetyScore, predictionResult, anomalyReasons.length);

    // 10. Append and Render Historical Log
    sessionHistory.unshift({
        ph: ph.toFixed(1),
        solids: solids.toFixed(0),
        chloramines: chloramines.toFixed(1),
        sulfate: sulfate.toFixed(0),
        turbidity: turbidity.toFixed(1),
        score: safetyScore,
        potability: predictionResult
    });
    updateHistoryTable();
}

/**
 * Updates safety score gauge circle and score text
 */
function updateSafetyGauge(score) {
    const fillCircle = document.getElementById('gauge-fill-circle');
    const scoreSpan = document.getElementById('result-score');

    if (!fillCircle || !scoreSpan) return;

    // Check if score is NaN or invalid
    if (isNaN(score) || score === null || score === undefined) {
        score = 0;
    }

    // SVG Math (Circumference = 2 * PI * r, r = 70 => ~439.8)
    const radius = 70;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;

    // Apply circle dashoffset transition
    fillCircle.style.strokeDashoffset = offset;

    // Smooth counter increment animation
    let currentScore = 0;
    const incrementSpeed = score > 0 ? Math.max(5, Math.floor(1000 / score)) : 5;
    scoreSpan.textContent = "0%";

    const interval = setInterval(() => {
        if (currentScore >= score) {
            scoreSpan.textContent = `${score}%`;
            clearInterval(interval);
        } else {
            currentScore++;
            scoreSpan.textContent = `${currentScore}%`;
        }
    }, incrementSpeed);
}

/**
 * Renders the safety badge below the gauge
 */
function renderSafetyBadge(isPotable, score) {
    const badge = document.getElementById('safety-badge');
    const badgeText = document.getElementById('safety-badge-text');

    if (!badge || !badgeText) return;

    const iconPlaceholder = document.getElementById('safety-icon-placeholder');

    if (isPotable) {
        badge.className = 'safety-badge badge-safe';
        badgeText.textContent = 'STANDARD SAFE';
        if (iconPlaceholder) {
            iconPlaceholder.innerHTML = '<i data-lucide="shield-check" size="14"></i>';
        }
    } else {
        badge.className = 'safety-badge badge-unsafe';
        badgeText.textContent = 'POTENTIAL RISK';
        if (iconPlaceholder) {
            iconPlaceholder.innerHTML = '<i data-lucide="alert-triangle" size="14"></i>';
        }
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

/**
 * Renders anomalies and recommendations text
 */
function renderDiagnostics(anomalies, recommendations) {
    const anomaliesContainer = document.getElementById('issues-container');
    const anomaliesList = document.getElementById('issues-list');
    const recsList = document.getElementById('recs-list');

    if (!anomaliesContainer || !anomaliesList || !recsList) return;

    // Anomalies rendering
    if (anomalies.length > 0) {
        anomaliesContainer.style.display = 'flex';
        anomaliesList.innerHTML = anomalies.map(text => `<li>${text}</li>`).join('');
    } else {
        anomaliesContainer.style.display = 'none';
        anomaliesList.innerHTML = '';
    }

    // Treatment recommendations rendering
    if (recommendations.length > 0) {
        recsList.innerHTML = recommendations.map(text => `<li>${text}</li>`).join('');
    } else {
        recsList.innerHTML = '<li>All chemical metrics are within clean margins. Maintain regular filtration systems.</li>';
    }
}

/**
 * Updates metrics widgets at the top
 */
function updateMetricsWidgets(score, prediction, issuesCount) {
    const scoreVal = document.getElementById('card-wq-score');
    const mlVal = document.getElementById('card-ml-status');
    const issuesVal = document.getElementById('card-issues-count');

    if (scoreVal) scoreVal.textContent = `${score}%`;
    if (mlVal) {
        mlVal.textContent = prediction;
        mlVal.style.color = (prediction === "Potable") ? 'var(--emerald)' : 'var(--rose)';
    }
    if (issuesVal) issuesVal.textContent = issuesCount;
}

/**
 * Renders the session history table
 */
function updateHistoryTable() {
    const tbody = document.getElementById('history-tbody');
    const countBadge = document.getElementById('history-badge');
    const totalRunsVal = document.getElementById('card-total-runs');

    if (!tbody || !countBadge) return;

    // Update session run counters
    if (totalRunsVal) totalRunsVal.textContent = sessionHistory.length;
    countBadge.textContent = `${sessionHistory.length} Ingests`;

    if (sessionHistory.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 2rem;">No parameters ingested in this session.</td></tr>`;
        return;
    }

    tbody.innerHTML = sessionHistory.map(row => {
        const isSafe = row.potability === "Potable";
        const statusClass = isSafe ? "small-status-safe" : "small-status-unsafe";
        const scoreColor = isSafe ? "var(--emerald)" : "var(--rose)";

        return `
            <tr>
                <td>${row.ph}</td>
                <td>${row.solids} ppm</td>
                <td>${row.chloramines} ppm</td>
                <td>${row.sulfate} mg/L</td>
                <td>${row.turbidity} NTU</td>
                <td>
                    <div style="font-weight: 700; color: ${scoreColor}">
                        ${row.score}%
                    </div>
                </td>
                <td>
                    <span class="small-status-badge ${statusClass}">
                        ${row.potability}
                    </span>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Renders the Dynamic Treatment & Mitigation Planner
 */
function renderMitigationPlanner(ph, solids, chloramines, sulfate, turbidity) {
    const idleEl = document.getElementById('mitigation-idle');
    const activeEl = document.getElementById('mitigation-active');
    const listEl = document.getElementById('mitigation-list');

    if (!idleEl || !activeEl || !listEl) return;

    let tasks = [];

    // 1. pH adjustment planning
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

    // 2. TDS reduction planning
    if (solids > 1000) {
        tasks.push({
            parameter: 'Dissolved Solids (TDS)',
            icon: 'filter',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Reduce by -${(solids - 500).toFixed(0)} ppm`,
            details: `High mineral content (Current: <strong>${solids.toFixed(0)} ppm</strong>, Target: <strong>500 ppm</strong>). Initiate a high-pressure <strong>Reverse Osmosis (RO) filtration pass</strong> at 95–98% rejection rate. Clean pre-sediment filters to protect membranes.`
        });
    }

    // 3. Chloramines planning
    if (chloramines > 4.0) {
        tasks.push({
            parameter: 'Chloramines Content',
            icon: 'shield-alert',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Reduce by -${(chloramines - 1.5).toFixed(1)} ppm`,
            details: `Excess chloramines causing eye/skin irritation (Current: <strong>${chloramines.toFixed(1)} ppm</strong>, Target: <strong>1.5 ppm</strong>). Feed effluent through high-performance <strong>Catalytic Carbon Block beds</strong>. Verify output using DPD colorimetric test kits.`
        });
    }

    // 4. Sulfate planning
    if (sulfate > 250) {
        tasks.push({
            parameter: 'Sulfate Concentration',
            icon: 'droplet',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Reduce by -${(sulfate - 150).toFixed(0)} mg/L`,
            details: `Sulfate load above safe aesthetic levels (Current: <strong>${sulfate.toFixed(0)} mg/L</strong>, Target: <strong>150 mg/L</strong>). Run water through <strong>anion-exchange resin beds</strong> (regenerated with NaCl salt brine) or Reverse Osmosis filtration.`
        });
    }

    // 5. Turbidity planning
    if (turbidity > 5.0) {
        tasks.push({
            parameter: 'Turbidity (Clarity)',
            icon: 'eye-off',
            deviationClass: 'mitigation-deviation-down',
            deviationText: `Clear by -${(turbidity - 0.8).toFixed(1)} NTU`,
            details: `Particulates blocking clarity and shields bacteria (Current: <strong>${turbidity.toFixed(1)} NTU</strong>, Target: <strong>&lt; 1.0 NTU</strong>). Add <strong>Aluminum Sulfate (Alum) coagulant</strong> at 15–30 mg/L to flocculate, allow 40 mins settling, then sand filter.`
        });
    }

    // Toggle panels
    if (tasks.length > 0) {
        idleEl.style.display = 'none';
        activeEl.style.display = 'flex';
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