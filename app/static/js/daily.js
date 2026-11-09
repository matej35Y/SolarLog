/* ================================================================
   daily.js — SolarLog Premium Dashboard
   Area/Bar/Line chart toggle · Gradient fills · Rich table
   ================================================================ */

'use strict';

let hourlyChart = null;
let currentChartType = 'area';
let lastHourlyData = null;

// ── Helpers ──────────────────────────────────────────────
function show(id) { document.getElementById(id)?.classList.remove('sl-hidden'); }
function hide(id) { document.getElementById(id)?.classList.add('sl-hidden'); }

function fmt(n, decimals = 2) {
  if (n == null || n === '') return '—';
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtDate(dateStr) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
  });
}

// ── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const dateInput = document.getElementById('dateSelector');
  const params = new URLSearchParams(window.location.search);

  dateInput.value = params.get('date') || new Date().toISOString().split('T')[0];

  document.getElementById('loadBtn').addEventListener('click', loadDailyData);
  dateInput.addEventListener('keyup', e => { if (e.key === 'Enter') loadDailyData(); });

  // Chart type toggle
  document.querySelectorAll('.chart-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.chart-toggle__btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentChartType = btn.dataset.type;
      if (lastHourlyData) buildChart(lastHourlyData, currentChartType);
    });
  });

  // Source selector → update badge
  document.getElementById('sourceSelector').addEventListener('change', syncBadges);

  loadDailyData();
});

// ── Badge sync ────────────────────────────────────────────
function syncBadges() {
  const source = document.getElementById('sourceSelector').value;
  const label = source ? source.toUpperCase() : 'ALL';

  ['tableBadge', 'headerSource'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = label;
    el.className = source === 'memo' ? 'sl-badge sl-badge--gray' : 'sl-badge sl-badge--green';
  });
}

// ── Load ──────────────────────────────────────────────────
function loadDailyData() {
  const date = document.getElementById('dateSelector').value;
  const source = document.getElementById('sourceSelector').value;
  if (!date) return;

  hide('results'); show('loading'); hide('errorMessage');

  // Update header date badge
  const headerDate = document.getElementById('headerDate');
  if (headerDate) headerDate.textContent = date;

  let url = `/api/analysis/by-date/${date}`;
  if (source) url += `?source=${source}`;

  fetch(url)
    .then(r => r.ok ? r.json() : r.json().then(e => { throw new Error(e.detail || 'Load failed'); }))
    .then(data => {
      hide('loading');

      if (data.message && (!data.hourly_data || data.hourly_data.length === 0)) {
        const errEl = document.getElementById('errorMessage');
        errEl.textContent = data.message || 'No data for this date.';
        show('errorMessage');
        return;
      }

      populateKPIs(data, date);
      populateTable(data.hourly_data || []);
      lastHourlyData = data.hourly_data || [];
      buildChart(lastHourlyData, currentChartType);
      syncBadges();
      show('results');
    })
    .catch(err => {
      hide('loading');
      const errEl = document.getElementById('errorMessage');
      errEl.innerHTML = `<span>⚠️</span> ${err.message}`;
      show('errorMessage');
    });
}

// ── KPI Population ────────────────────────────────────────
function populateKPIs(data, date) {
  const s = data.summary || {};

  document.getElementById('summaryDate').textContent = fmtDate(date);
  document.getElementById('summaryEnergy').textContent = fmt(s.total_energy_kwh, 3);
  document.getElementById('summaryValue').textContent = fmt(s.total_value);
  document.getElementById('summaryPrice').textContent = fmt(s.arithmetic_avg_price_per_mwh);

  // Active hours sub-label
  const hoursEl = document.getElementById('kpiEnergyHours');
  if (hoursEl && s.working_hours_count != null) {
    hoursEl.textContent = `${s.working_hours_count} active hours`;
  }

  // No-production warning
  const warn = document.getElementById('noProductionWarning');
  if (warn) {
    s.working_hours_count === 0
      ? warn.classList.remove('sl-hidden')
      : warn.classList.add('sl-hidden');
  }

  // Active hours label in table header
  const ahLabel = document.getElementById('activeHoursLabel');
  if (ahLabel) ahLabel.textContent = `${s.working_hours_count || 0} hours`;
}

// ── Table ─────────────────────────────────────────────────
function populateTable(hourlyData) {
  const tbody = document.getElementById('dataTable');
  tbody.innerHTML = '';

  // Find max energy for mini-bar scaling
  const maxEnergy = Math.max(...hourlyData.map(h => parseFloat(h.energy_kwh) || 0), 1);

  hourlyData.forEach(hour => {
    const energy = parseFloat(hour.energy_kwh) || 0;
    const pct = Math.round((energy / maxEnergy) * 100);

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="td-mono">${hour.hour}</span></td>
      <td><span class="td-energy">${fmt(hour.energy_kwh, 3)}</span> <span style="font-size:11px;color:var(--text-faint)">kWh</span></td>
      <td>
        <div class="td-bar-wrap">
          <div class="td-bar"><div class="td-bar__fill" style="width:${pct}%"></div></div>
          <span style="font-size:11px;color:var(--text-muted);min-width:28px;text-align:right">${pct}%</span>
        </div>
      </td>
      <td>${fmt(hour.price_per_mwh)} <span style="font-size:11px;color:var(--text-faint)">EUR/MWh</span></td>
      <td><span class="td-value">${fmt(hour.value)}</span> <span style="font-size:11px;color:var(--text-faint)">EUR</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ── Chart ─────────────────────────────────────────────────
function buildChart(hourlyData, type = 'area') {
  const ctx = document.getElementById('hourlyChart');
  const hours = hourlyData.map(i => i.hour);
  const energy = hourlyData.map(i => parseFloat(i.energy_kwh) || 0);
  const price = hourlyData.map(i => parseFloat(i.price_per_mwh) || 0);

  if (hourlyChart) { hourlyChart.destroy(); hourlyChart = null; }

  const isFilled = type !== 'line';
  const chartType = type === 'area' ? 'line' : type;

  // Build gradient for energy dataset
  const gradEnergy = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
  gradEnergy.addColorStop(0, 'rgba(24,226,153,0.30)');
  gradEnergy.addColorStop(1, 'rgba(24,226,153,0.00)');

  const gradPrice = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
  gradPrice.addColorStop(0, 'rgba(99,102,241,0.18)');
  gradPrice.addColorStop(1, 'rgba(99,102,241,0.00)');

  const sharedOpts = {
    tension: 0.4,
    pointRadius: type === 'line' ? 4 : 2,
    pointHoverRadius: 6,
    borderWidth: 2,
  };

  const TICK = { color: '#4d5870', font: { family: 'JetBrains Mono, monospace', size: 10 }, padding: 8 };
  const GRID = { color: 'rgba(255,255,255,0.055)', drawTicks: false };

  hourlyChart = new Chart(ctx, {
    type: chartType,
    data: {
      labels: hours,
      datasets: [
        {
          label: 'Energy (kWh)',
          data: energy,
          borderColor: '#18E299',
          backgroundColor: isFilled ? gradEnergy : 'rgba(24,226,153,0.65)',
          pointBackgroundColor: '#18E299',
          pointBorderColor: 'transparent',
          fill: isFilled,
          yAxisID: 'y',
          order: 1,
          borderRadius: type === 'bar' ? 5 : 0,
          ...sharedOpts,
        },
        {
          label: 'Price (EUR/MWh)',
          data: price,
          type: 'line',
          borderColor: '#818cf8',
          backgroundColor: isFilled ? gradPrice : 'transparent',
          pointBackgroundColor: '#818cf8',
          pointBorderColor: 'transparent',
          fill: false,
          yAxisID: 'y1',
          order: 0,
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 3,
          pointHoverRadius: 6,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          align: 'end',
          labels: {
            boxWidth: 10, boxHeight: 10,
            borderRadius: 3, useBorderRadius: true,
            padding: 16,
            font: { family: 'Inter, system-ui', size: 12, weight: '500' },
            color: '#7d8ba0',
          }
        },
        tooltip: {
          backgroundColor: '#0f0f1a',
          titleColor: '#edf0f7',
          bodyColor: '#c4cdd8',
          borderColor: 'rgba(255,255,255,0.10)',
          borderWidth: 1,
          padding: { top: 10, right: 14, bottom: 10, left: 14 },
          cornerRadius: 10,
          caretSize: 5,
          titleFont: { family: 'JetBrains Mono, monospace', size: 11, weight: '600' },
          bodyFont: { family: 'Inter, system-ui', size: 12 },
          callbacks: {
            title: items => `Hour ${items[0].label}`,
            label: item => {
              const unit = item.datasetIndex === 0 ? ' kWh' : ' EUR/MWh';
              return `  ${item.dataset.label}: ${fmt(item.raw)}${unit}`;
            }
          }
        }
      },
      scales: {
        x: { grid: GRID, border: { display: false }, ticks: TICK },
        y: {
          position: 'left',
          beginAtZero: true,
          grid: GRID,
          border: { display: false },
          title: { display: true, text: 'kWh', color: '#4d5870', font: { size: 10, family: 'JetBrains Mono, monospace' } },
          ticks: TICK,
        },
        y1: {
          position: 'right',
          beginAtZero: false,
          grid: { drawOnChartArea: false, drawTicks: false },
          border: { display: false },
          title: { display: true, text: 'EUR/MWh', color: '#4d5870', font: { size: 10, family: 'JetBrains Mono, monospace' } },
          ticks: TICK,
        }
      },
      animation: { duration: 550, easing: 'easeOutCubic' }
    }
  });
}