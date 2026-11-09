/* ================================================================
   monthly.js — SolarLog Premium Dashboard
   Area/Bar/Line chart toggle · Gradient fills · Rich table
   ================================================================ */

'use strict';

let dailyChart = null;
let currentChartType = 'area';
let lastDailyData = null;

// ── Helpers ──────────────────────────────────────────────
function show(id) { document.getElementById(id)?.classList.remove('sl-hidden'); }
function hide(id) { document.getElementById(id)?.classList.add('sl-hidden'); }

function fmt(n, decimals = 2) {
  if (n == null || n === '') return '—';
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtShortDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}

// ── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const monthInput = document.getElementById('monthSelector');
  const today = new Date();
  monthInput.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;

  document.getElementById('loadBtn').addEventListener('click', loadMonthlyData);
  monthInput.addEventListener('keyup', e => { if (e.key === 'Enter') loadMonthlyData(); });

  // Chart toggle
  document.querySelectorAll('.chart-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.chart-toggle__btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentChartType = btn.dataset.type;
      if (lastDailyData) buildChart(lastDailyData, currentChartType);
    });
  });

  document.getElementById('sourceSelector').addEventListener('change', syncBadges);

  loadMonthlyData();
});

// ── Badge sync ────────────────────────────────────────────
function syncBadges() {
  const source = document.getElementById('sourceSelector').value;
  const label = source ? source.toUpperCase() : 'ALL';

  ['tableSourceBadge', 'headerSource'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = label;
    el.className = source === 'memo' ? 'sl-badge sl-badge--gray' : 'sl-badge sl-badge--green';
  });

  const srcEl = document.getElementById('summarySource');
  if (srcEl) srcEl.textContent = label;
}

// ── Load ──────────────────────────────────────────────────
function loadMonthlyData() {
  const month = document.getElementById('monthSelector').value;
  const source = document.getElementById('sourceSelector').value;
  if (!month) return;

  hide('results'); show('loading'); hide('errorMessage');

  // Update header month badge
  const headerMonth = document.getElementById('headerMonth');
  if (headerMonth) headerMonth.textContent = month;

  let url = `/api/analysis/by-month/${month}`;
  if (source) url += `?source=${source}`;

  fetch(url)
    .then(r => r.ok ? r.json() : r.json().then(e => { throw new Error(e.detail || e.message || 'Load failed'); }))
    .then(data => {
      hide('loading');

      if (data.status === 'no_data') throw new Error(data.message);

      const [year, monthNum] = month.split('-');
      const monthName = new Date(year, parseInt(monthNum) - 1, 1)
        .toLocaleString('default', { month: 'long' });

      populateKPIs(data, monthName, year);
      const dailyData = buildDailyData(data);
      populateTable(dailyData);
      lastDailyData = dailyData;
      buildChart(dailyData, currentChartType);
      syncBadges();

      // Update chart subtitle
      const chartLabel = document.getElementById('chartMonthLabel');
      if (chartLabel) chartLabel.textContent = `${monthName} ${year} · Energy (MWh) & revenue (EUR) per day`;

      show('results');
    })
    .catch(err => {
      hide('loading');
      const errEl = document.getElementById('errorMessage');
      errEl.innerHTML = `<span>⚠️</span> ${err.message}`;
      show('errorMessage');
    });
}

// ── KPI ───────────────────────────────────────────────────
function populateKPIs(data, monthName, year) {
  const s = data.month_summary || {};

  document.getElementById('summaryMonth').textContent = `${monthName} ${year}`;
  document.getElementById('summaryEnergy').textContent = fmt(s.total_energy_mwh, 3);
  document.getElementById('summaryValue').textContent = fmt(s.total_value);
  document.getElementById('summaryPrice').textContent = fmt(s.avg_working_hour_price);
  document.getElementById('summaryDays').textContent = s.days_with_data ?? '—';
  document.getElementById('summaryHours').textContent = s.total_working_hours ?? '—';

  // Daily avg
  const dailyAvgEl = document.getElementById('summaryDailyAvg');
  if (dailyAvgEl && s.days_with_data && s.total_value) {
    dailyAvgEl.textContent = fmt(s.total_value / s.days_with_data);
  }
}

// ── Build daily array ─────────────────────────────────────
function buildDailyData(data) {
  return Object.entries(data)
    .filter(([k]) => k !== 'month_summary')
    .map(([date, info]) => ({
      date,
      value: parseFloat(info.total_value) || 0,
      energy: parseFloat(info.total_energy_mwh) || 0,
      price: parseFloat(info.avg_working_hour_price) || 0,
      hours: info.working_hours || 0,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

// ── Table ─────────────────────────────────────────────────
function populateTable(dailyData) {
  const tbody = document.getElementById('dataTable');
  tbody.innerHTML = '';

  const maxEnergy = Math.max(...dailyData.map(d => d.energy), 1);

  dailyData.forEach(day => {
    const pct = Math.round((day.energy / maxEnergy) * 100);
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', () => {
      window.location.href = `/ui/daily?date=${day.date}`;
    });

    tr.innerHTML = `
      <td><span class="td-mono">${fmtShortDate(day.date)}</span></td>
      <td><span class="td-energy">${fmt(day.energy, 3)}</span> <span style="font-size:11px;color:var(--text-faint)">MWh</span></td>
      <td>
        <div class="td-bar-wrap">
          <div class="td-bar"><div class="td-bar__fill" style="width:${pct}%"></div></div>
          <span style="font-size:11px;color:var(--text-muted);min-width:28px;text-align:right">${pct}%</span>
        </div>
      </td>
      <td>${fmt(day.price)} <span style="font-size:11px;color:var(--text-faint)">EUR/MWh</span></td>
      <td><span class="td-value">${fmt(day.value)}</span> <span style="font-size:11px;color:var(--text-faint)">EUR</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ── Chart ─────────────────────────────────────────────────
function buildChart(dailyData, type = 'area') {
  const ctx = document.getElementById('dailyChart');
  const labels = dailyData.map(d => new Date(d.date + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }));
  const values = dailyData.map(d => d.value);
  const energy = dailyData.map(d => d.energy);

  if (dailyChart) { dailyChart.destroy(); dailyChart = null; }

  const isFilled = type !== 'line';
  const chartType = type === 'area' ? 'line' : type;

  const gradValue = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
  gradValue.addColorStop(0, 'rgba(24,226,153,0.30)');
  gradValue.addColorStop(1, 'rgba(24,226,153,0.00)');

  const gradEnergy = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
  gradEnergy.addColorStop(0, 'rgba(99,102,241,0.18)');
  gradEnergy.addColorStop(1, 'rgba(99,102,241,0.00)');

  const TICK = { color: '#4d5870', font: { family: 'JetBrains Mono, monospace', size: 10 }, padding: 8 };
  const GRID = { color: 'rgba(255,255,255,0.055)', drawTicks: false };

  dailyChart = new Chart(ctx, {
    type: chartType,
    data: {
      labels,
      datasets: [
        {
          label: 'Revenue (EUR)',
          data: values,
          borderColor: '#18E299',
          backgroundColor: isFilled ? gradValue : 'rgba(24,226,153,0.65)',
          pointBackgroundColor: '#18E299',
          pointBorderColor: 'transparent',
          fill: isFilled,
          yAxisID: 'y',
          order: 1,
          tension: 0.4,
          pointRadius: type === 'line' ? 4 : 2,
          pointHoverRadius: 6,
          borderWidth: 2,
          borderRadius: type === 'bar' ? 5 : 0,
        },
        {
          label: 'Energy (MWh)',
          data: energy,
          type: 'line',
          borderColor: '#818cf8',
          backgroundColor: 'transparent',
          pointBackgroundColor: '#818cf8',
          pointBorderColor: 'transparent',
          fill: false,
          yAxisID: 'y1',
          order: 0,
          tension: 0.4,
          pointRadius: 3,
          pointHoverRadius: 6,
          borderWidth: 2,
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
            label: item => {
              const unit = item.datasetIndex === 0 ? ' EUR' : ' MWh';
              return `  ${item.dataset.label}: ${fmt(item.raw)}${unit}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: GRID,
          border: { display: false },
          ticks: { ...TICK, maxTicksLimit: 16 }
        },
        y: {
          position: 'left',
          beginAtZero: true,
          grid: GRID,
          border: { display: false },
          title: { display: true, text: 'EUR', color: '#4d5870', font: { size: 10, family: 'JetBrains Mono, monospace' } },
          ticks: TICK,
        },
        y1: {
          position: 'right',
          beginAtZero: true,
          grid: { drawOnChartArea: false, drawTicks: false },
          border: { display: false },
          title: { display: true, text: 'MWh', color: '#4d5870', font: { size: 10, family: 'JetBrains Mono, monospace' } },
          ticks: TICK,
        }
      },
      animation: { duration: 550, easing: 'easeOutCubic' }
    }
  });
}