// Chart.js global dark defaults
Chart.defaults.color = '#8892a4';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = 'Inter, sans-serif';

function createRiskGauge(canvasId, riskScore) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    let color = '#00e676'; // success
    if (riskScore >= 30 && riskScore <= 60) color = '#ffab00'; // warning
    if (riskScore > 60) color = '#ff5252'; // danger

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Risk', 'Safe'],
            datasets: [{
                data: [riskScore, 100 - riskScore],
                backgroundColor: [color, 'rgba(255,255,255,0.05)'],
                borderWidth: 0,
                cutout: '80%'
            }]
        },
        options: {
            rotation: -90,
            circumference: 180,
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            }
        }
    });
}

function createRadarChart(canvasId, labels, data, label) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: 'rgba(79, 195, 247, 0.2)',
                borderColor: '#4fc3f7',
                pointBackgroundColor: '#4fc3f7',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#4fc3f7',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: 'rgba(255,255,255,0.1)' },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    pointLabels: { color: '#e2e8f0', font: { size: 11 } },
                    ticks: {
                        display: false,
                        min: 0,
                        max: 100
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function createLatencyChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    let gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(79, 195, 247, 0.5)');
    gradient.addColorStop(1, 'rgba(79, 195, 247, 0.0)');

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Avg Latency (ms)',
                data: data,
                borderColor: '#4fc3f7',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function createTokenUsageChart(canvasId, labels, dataMini, dataLarge) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Nemotron Mini',
                    data: dataMini,
                    backgroundColor: '#4fc3f7'
                },
                {
                    label: 'Nemotron Large',
                    data: dataLarge,
                    backgroundColor: '#7c4dff'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { stacked: false },
                y: { stacked: false, beginAtZero: true }
            }
        }
    });
}

function createComparisonChart(canvasId, baseData, simulatedData) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Health', 'Affordability', 'DTI', 'Approval Prob'],
            datasets: [
                {
                    label: 'Base',
                    data: baseData,
                    backgroundColor: 'rgba(136, 146, 164, 0.5)'
                },
                {
                    label: 'Simulated',
                    data: simulatedData,
                    backgroundColor: '#4fc3f7'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, max: 100 }
            }
        }
    });
}

function updateSliderDisplay(sliderId, displayId, suffix = '') {
    const slider = document.getElementById(sliderId);
    const display = document.getElementById(displayId);
    if(slider && display) {
        display.innerText = slider.value + suffix;
        slider.addEventListener('input', function() {
            display.innerText = this.value + suffix;
        });
    }
}

function formatCurrency(amount) {
    if (isNaN(amount)) return '₹0';
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
    }).format(amount);
}

function showToast(message, type='success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    let bgClass = 'text-bg-success';
    if (type === 'danger') bgClass = 'text-bg-danger';
    else if (type === 'warning') bgClass = 'text-bg-warning';
    
    const toastHtml = `
        <div class="toast align-items-center ${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = container.lastElementChild;
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();
    
    toastEl.addEventListener('hidden.bs.toast', () => {
        toastEl.remove();
    });
}

function initializeDashboard() {
    // Basic initialization
}
