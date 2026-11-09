import React, { useState, useEffect, useMemo, Component } from 'react';
import { createClient } from '@insforge/sdk';
import {
  Chart as ChartJS,
  registerables
} from 'chart.js';
import { Chart } from 'react-chartjs-2';
import { Sun, Euro, Zap, Activity, Calendar, RefreshCw, AlertCircle, TrendingUp, BarChart2 } from 'lucide-react';

ChartJS.register(...registerables);

// Fallback credentials if env is not injected
const INSFORGE_URL = import.meta.env.VITE_INSFORGE_URL || 'https://z9dt4nnj.eu-central.insforge.app';
const INSFORGE_ANON_KEY = import.meta.env.VITE_INSFORGE_ANON_KEY || 'anon_1f42d6b636d8e8c20f309877f9bda81f5bb64f2278a93a0477001524f4f9ee2e';

const insforge = createClient({
  baseUrl: INSFORGE_URL,
  anonKey: INSFORGE_ANON_KEY
});

// Helper formatting functions
function fmt(n, decimals = 2) {
  if (n == null || isNaN(n)) return '0.00';
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function fmtDate(dateStr) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-GB', {
      weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
    });
  } catch {
    return dateStr;
  }
}

function fmtShortDate(dateStr) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-GB', {
      weekday: 'short', day: 'numeric', month: 'short'
    });
  } catch {
    return dateStr;
  }
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

function formatMonthLabel(monthStr) {
  if (!monthStr) return '';
  try {
    const [year, m] = monthStr.split('-').map(Number);
    return `${MONTH_NAMES[m - 1]} ${year}`;
  } catch {
    return monthStr;
  }
}

function getMonthOptions(year) {
  const list = [];
  for (let m = 12; m >= 1; m--) {
    const mStr = String(m).padStart(2, '0');
    list.push({
      value: `${year}-${mStr}`,
      label: `${mStr} · ${MONTH_NAMES[m - 1]} ${year}`
    });
  }
  return list;
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("Dashboard error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '40px 20px', textAlign: 'center', fontFamily: 'Inter, sans-serif' }}>
          <div style={{ background: '#ffffff', maxWidth: '520px', margin: '40px auto', padding: '32px', borderRadius: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', border: '1px solid rgba(0,0,0,0.08)' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: '#fee2e2', color: '#ef4444', display: 'grid', placeItems: 'center', margin: '0 auto 16px' }}>
              <AlertCircle size={26} />
            </div>
            <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '0 0 8px', color: '#0f172a' }}>Application Error</h2>
            <p style={{ color: '#64748b', fontSize: '14px', margin: '0 0 24px' }}>{this.state.error?.message || "An unexpected error occurred."}</p>
            <button
              onClick={() => window.location.reload()}
              style={{ background: '#0aaf72', color: '#fff', border: 'none', padding: '10px 24px', borderRadius: '9999px', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}
            >
              Reload Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function Dashboard() {
  const [activeTab, setActiveTab] = useState('daily'); // 'daily' | 'monthly'
  const [selectedDate, setSelectedDate] = useState(() => {
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return local.toISOString().split('T')[0];
  });
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
    return local.toISOString().substring(0, 7);
  });
  const [selectedSource, setSelectedSource] = useState('hupx');
  const [chartType, setChartType] = useState('combo'); // 'combo' | 'bar' | 'line'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Daily data
  const [dailyData, setDailyData] = useState({ prices: [], energy: [] });
  // Monthly data
  const [monthlyData, setMonthlyData] = useState({ prices: [], energy: [] });

  const monthGroups = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const maxYear = Math.max(currentYear, 2026);
    const startYear = 2024;
    const groups = [];
    for (let y = maxYear; y >= startYear; y--) {
      groups.push({
        year: y,
        options: getMonthOptions(y)
      });
    }
    return groups;
  }, []);

  const handlePrevMonth = () => {
    if (!selectedMonth) return;
    const [y, m] = selectedMonth.split('-').map(Number);
    const prev = new Date(y, m - 2, 1);
    const prevStr = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}`;
    setSelectedMonth(prevStr);
  };

  const handleNextMonth = () => {
    if (!selectedMonth) return;
    const [y, m] = selectedMonth.split('-').map(Number);
    const next = new Date(y, m, 1);
    const nextStr = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`;
    setSelectedMonth(nextStr);
  };

  const handlePrevDay = () => {
    if (!selectedDate) return;
    const d = new Date(selectedDate + 'T12:00:00');
    d.setDate(d.getDate() - 1);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const handleNextDay = () => {
    if (!selectedDate) return;
    const d = new Date(selectedDate + 'T12:00:00');
    d.setDate(d.getDate() + 1);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  // On mount: discover the latest date in DB
  useEffect(() => {
    async function initLatest() {
      try {
        const { data: latest } = await insforge.database
          .from('energy_generation')
          .select('date')
          .order('date', { ascending: false })
          .limit(1);

        if (latest && latest.length > 0 && latest[0].date) {
          const d = latest[0].date.split('T')[0];
          setSelectedDate(d);
          setSelectedMonth(d.substring(0, 7));
        }
      } catch (err) {
        console.warn("Could not fetch latest date:", err);
      }
    }
    initLatest();
  }, []);

  // Fetch Daily
  const fetchDaily = async (dateStr, source) => {
    setLoading(true);
    setError(null);
    try {
      const pQuery = insforge.database
        .from('hourly_prices')
        .select('*')
        .eq('date', dateStr);
      if (source) pQuery.eq('source', source);

      const [priceRes, energyRes] = await Promise.all([
        pQuery,
        insforge.database.from('energy_generation').select('*').eq('date', dateStr)
      ]);

      if (priceRes.error) throw priceRes.error;
      if (energyRes.error) throw energyRes.error;

      setDailyData({
        prices: priceRes.data || [],
        energy: energyRes.data || []
      });
    } catch (err) {
      console.error("Daily fetch error:", err);
      setError("Failed to load daily data from cloud. Check connection or pick another date.");
    } finally {
      setLoading(false);
    }
  };

  // Fetch Monthly
  const fetchMonthly = async (monthStr, source) => {
    setLoading(true);
    setError(null);
    try {
      const start = `${monthStr}-01`;
      // compute last day of month
      const [year, month] = monthStr.split('-').map(Number);
      const nextMonth = new Date(year, month, 0).getDate();
      const end = `${monthStr}-${String(nextMonth).padStart(2, '0')}`;

      const pQuery = insforge.database
        .from('hourly_prices')
        .select('*')
        .gte('date', start)
        .lte('date', end)
        .limit(5000);
      if (source) pQuery.eq('source', source);

      const [priceRes, energyRes] = await Promise.all([
        pQuery,
        insforge.database.from('energy_generation').select('*').gte('date', start).lte('date', end).limit(5000)
      ]);

      if (priceRes.error) throw priceRes.error;
      if (energyRes.error) throw energyRes.error;

      setMonthlyData({
        prices: priceRes.data || [],
        energy: energyRes.data || []
      });
    } catch (err) {
      console.error("Monthly fetch error:", err);
      setError("Failed to load monthly data from cloud.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'daily' && selectedDate) {
      fetchDaily(selectedDate, selectedSource);
    } else if (activeTab === 'monthly' && selectedMonth) {
      fetchMonthly(selectedMonth, selectedSource);
    }
  }, [activeTab, selectedDate, selectedMonth, selectedSource]);

  // Auto-refresh every 5 minutes to stay in sync with background bridge
  useEffect(() => {
    const timer = setInterval(() => {
      if (activeTab === 'daily' && selectedDate) {
        fetchDaily(selectedDate, selectedSource);
      } else if (activeTab === 'monthly' && selectedMonth) {
        fetchMonthly(selectedMonth, selectedSource);
      }
    }, 5 * 60 * 1000);
    return () => clearInterval(timer);
  }, [activeTab, selectedDate, selectedMonth, selectedSource]);

  // ── Daily Calculations ────────────────────────────────────
  const dailyAnalysis = useMemo(() => {
    const hourlyMap = {};
    for (let i = 1; i <= 24; i++) {
      const hKey = `H${i}`;
      hourlyMap[hKey] = { hour: hKey, hourNum: i, energy: 0, price: 0, value: 0 };
    }

    dailyData.prices.forEach(p => {
      if (hourlyMap[p.hour]) {
        hourlyMap[p.hour].price = Number(p.price) || 0;
      }
    });

    dailyData.energy.forEach(e => {
      if (hourlyMap[e.hour]) {
        hourlyMap[e.hour].energy = Number(e.energy_kwh) || 0;
      }
    });

    const list = Object.values(hourlyMap).sort((a, b) => a.hourNum - b.hourNum);
    let totalEnergy = 0;
    let totalValue = 0;
    let activeHours = 0;
    let priceSum = 0;
    let maxEnergy = 1;

    list.forEach(item => {
      const val = (item.energy * item.price) / 1000;
      item.value = val;
      totalEnergy += item.energy;
      totalValue += val;
      if (item.energy > 0) {
        activeHours++;
        priceSum += item.price;
        if (item.energy > maxEnergy) maxEnergy = item.energy;
      }
    });

    return {
      rows: list,
      maxEnergy,
      totalEnergy,
      totalValue,
      avgPrice: activeHours > 0 ? priceSum / activeHours : 0,
      activeHours
    };
  }, [dailyData]);

  // ── Monthly Calculations (Exact Hour-by-Hour Pricing) ─────
  const monthlyAnalysis = useMemo(() => {
    // 1. Index hourly prices by date + hour
    const priceMap = {};
    monthlyData.prices.forEach(p => {
      const d = p.date.split('T')[0];
      priceMap[`${d}_${p.hour}`] = Number(p.price) || 0;
    });

    // 2. Index energy by date + hour & collect distinct dates
    const energyMap = {};
    const datesSet = new Set();
    monthlyData.energy.forEach(e => {
      const d = e.date.split('T')[0];
      datesSet.add(d);
      energyMap[`${d}_${e.hour}`] = Number(e.energy_kwh) || 0;
    });

    const dates = Array.from(datesSet).sort();
    let totalMonthKwh = 0;
    let totalMonthVal = 0;
    let totalWorkingHours = 0;
    let allWorkingPrices = [];
    let maxDayEnergy = 1;

    const days = dates.map(d => {
      let dayEnergy = 0;
      let dayVal = 0;
      let workingHours = 0;
      let workingPriceSum = 0;

      for (let h = 1; h <= 24; h++) {
        const hKey = `H${h}`;
        const energy = energyMap[`${d}_${hKey}`] || 0;
        const price = priceMap[`${d}_${hKey}`] || 0;

        if (energy > 0) {
          dayEnergy += energy;
          dayVal += (energy * price) / 1000;
          workingHours++;
          workingPriceSum += price;
          allWorkingPrices.push(price);
        }
      }

      totalMonthKwh += dayEnergy;
      totalMonthVal += dayVal;
      totalWorkingHours += workingHours;
      if (dayEnergy > maxDayEnergy) maxDayEnergy = dayEnergy;

      const avgDayPrice = workingHours > 0 ? workingPriceSum / workingHours : 0;

      return {
        date: d,
        energy: dayEnergy,
        energyMWh: dayEnergy / 1000,
        value: dayVal,
        avgPrice: avgDayPrice,
        hours: workingHours
      };
    });

    const monthAvgPrice = allWorkingPrices.length > 0
      ? allWorkingPrices.reduce((a, b) => a + b, 0) / allWorkingPrices.length
      : 0;

    const daysWithData = days.filter(d => d.energy > 0).length;
    const avgDailyRevenue = daysWithData > 0 ? totalMonthVal / daysWithData : 0;

    return {
      days,
      maxDayEnergy,
      totalKwh: totalMonthKwh,
      totalMWh: totalMonthKwh / 1000,
      totalVal: totalMonthVal,
      avgPrice: monthAvgPrice,
      workingHours: totalWorkingHours,
      daysWithData,
      avgDailyRevenue
    };
  }, [monthlyData]);

  // ── Daily Chart Configuration ─────────────────────────────
  const dailyChartData = useMemo(() => {
    const labels = dailyAnalysis.rows.map(r => r.hour);

    const datasets = [];

    if (chartType === 'combo' || chartType === 'bar') {
      datasets.push({
        type: 'bar',
        label: 'Energy (kWh)',
        data: dailyAnalysis.rows.map(r => r.energy),
        backgroundColor: 'rgba(10, 175, 114, 0.7)',
        borderColor: '#0aaf72',
        borderWidth: 1,
        borderRadius: 4,
        yAxisID: 'y',
        order: 2,
      });
    }

    if (chartType === 'combo' || chartType === 'line') {
      datasets.push({
        type: 'line',
        label: `Market Price (€/MWh)`,
        data: dailyAnalysis.rows.map(r => r.price),
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99, 102, 241, 0.1)',
        borderWidth: 2.2,
        pointBackgroundColor: '#6366f1',
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.35,
        fill: chartType === 'line',
        yAxisID: 'y1',
        order: 1,
      });
    }

    return { labels, datasets };
  }, [dailyAnalysis, chartType]);

  // ── Monthly Chart Configuration ───────────────────────────
  const monthlyChartData = useMemo(() => {
    const labels = monthlyAnalysis.days.map(d => {
      try {
        const parts = d.date.split('-');
        return `${Number(parts[2])}`; // Day number 1, 2, ...
      } catch {
        return d.date.substring(8);
      }
    });

    return {
      labels,
      datasets: [
        {
          type: 'bar',
          label: 'Daily Revenue (€)',
          data: monthlyAnalysis.days.map(d => Number(d.value.toFixed(2))),
          backgroundColor: 'rgba(10, 175, 114, 0.75)',
          borderColor: '#0aaf72',
          borderWidth: 1,
          borderRadius: 4,
          yAxisID: 'y',
          order: 2,
        },
        {
          type: 'line',
          label: 'Generation (MWh)',
          data: monthlyAnalysis.days.map(d => Number(d.energyMWh.toFixed(3))),
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.08)',
          borderWidth: 2.2,
          pointBackgroundColor: '#6366f1',
          pointRadius: 3,
          pointHoverRadius: 6,
          tension: 0.35,
          fill: false,
          yAxisID: 'y1',
          order: 1,
        }
      ]
    };
  }, [monthlyAnalysis]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        title: {
          display: true,
          text: activeTab === 'daily' ? 'Energy (kWh)' : 'Revenue (€)',
          font: { family: 'Inter', weight: 600, size: 12 },
          color: '#6b7a8d'
        },
        grid: { color: 'rgba(0, 0, 0, 0.05)' }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        title: {
          display: true,
          text: activeTab === 'daily' ? 'Price (€/MWh)' : 'Generation (MWh)',
          font: { family: 'Inter', weight: 600, size: 12 },
          color: '#6b7a8d'
        },
        grid: { drawOnChartArea: false }
      },
      x: {
        grid: { display: false },
        ticks: { font: { family: 'JetBrains Mono', size: 11 }, color: '#6b7a8d' }
      }
    },
    plugins: {
      legend: {
        position: 'top',
        labels: { font: { family: 'Inter', size: 12, weight: 500 }, usePointStyle: true, boxWidth: 8 }
      },
      tooltip: {
        backgroundColor: '#0f1623',
        padding: 12,
        titleFont: { family: 'Inter', weight: 700, size: 13 },
        bodyFont: { family: 'Inter', size: 12 },
        cornerRadius: 8
      }
    }
  };

  return (
    <div>
      {/* ── Top Navigation ──────────────────────────────────── */}
      <nav className="sl-nav">
        <div className="sl-nav__inner">
          <div className="sl-nav__brand">
            <span className="sl-nav__logo">
              <Sun size={17} color="#ffffff" strokeWidth={2.4} />
            </span>
            SolarLogZOJA ☀️
          </div>
          <span className="sl-nav__sep"></span>
          <ul className="sl-nav__links">
            <li>
              <button
                type="button"
                className={`sl-nav__link ${activeTab === 'daily' ? 'active' : ''}`}
                onClick={() => setActiveTab('daily')}
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
              >
                Daily
              </button>
            </li>
            <li>
              <button
                type="button"
                className={`sl-nav__link ${activeTab === 'monthly' ? 'active' : ''}`}
                onClick={() => setActiveTab('monthly')}
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
              >
                Monthly
              </button>
            </li>
          </ul>
          <div className="sl-nav__right">
            <span className="sl-nav__pill">Live</span>
          </div>
        </div>
      </nav>

      {/* ── Main Page ───────────────────────────────────────── */}
      <main className="sl-page">

        {/* Header */}
        <header className="sl-dash-header">
          <div className="sl-dash-header__left">
            <div className="sl-dash-header__eyebrow">
              <svg width="7" height="7" viewBox="0 0 8 8"><circle cx="4" cy="4" r="3" fill="#0aaf72"/></svg>
              Energy Intelligence
            </div>
            <h1>{activeTab === 'daily' ? 'Daily Analysis' : 'Monthly Overview'}</h1>
            <p className="sl-dash-header__sub">
              {activeTab === 'daily'
                ? 'Hourly production, spot pricing & financial valuation'
                : 'Daily totals, cumulative revenue & performance trends'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="sl-badge sl-badge--green">{selectedSource.toUpperCase()}</span>
            <span className="sl-badge sl-badge--gray" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              {activeTab === 'daily' ? fmtDate(selectedDate) : formatMonthLabel(selectedMonth)}
            </span>
          </div>
        </header>

        {/* View Switcher Tabs (Directly visible on mobile and desktop) */}
        <div className="sl-tab-bar" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'daily'}
            className={`sl-tab-btn ${activeTab === 'daily' ? 'active' : ''}`}
            onClick={() => setActiveTab('daily')}
          >
            <Sun size={15} />
            <span>Daily Breakdown</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'monthly'}
            className={`sl-tab-btn ${activeTab === 'monthly' ? 'active' : ''}`}
            onClick={() => setActiveTab('monthly')}
          >
            <Calendar size={15} />
            <span>Monthly Overview</span>
          </button>
        </div>

        {/* Controls Toolbar */}
        <div className="sl-controls" role="search">
          {activeTab === 'daily' ? (
            <div className="sl-controls__group">
              <span className="sl-controls__label">Date</span>
              <div className="sl-ctrl-picker">
                <button
                  type="button"
                  className="sl-ctrl-btn"
                  title="Previous day"
                  onClick={handlePrevDay}
                >
                  ◀
                </button>
                <input
                  type="date"
                  className="sl-input"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  style={{ fontWeight: 600 }}
                />
                <button
                  type="button"
                  className="sl-ctrl-btn"
                  title="Next day"
                  onClick={handleNextDay}
                >
                  ▶
                </button>
              </div>
            </div>
          ) : (
            <div className="sl-controls__group">
              <span className="sl-controls__label">Month</span>
              <div className="sl-ctrl-picker">
                <button
                  type="button"
                  className="sl-ctrl-btn"
                  title="Previous month"
                  onClick={handlePrevMonth}
                >
                  ◀
                </button>
                <select
                  className="sl-select"
                  value={selectedMonth}
                  onChange={(e) => setSelectedMonth(e.target.value)}
                  style={{ fontWeight: 600 }}
                >
                  {monthGroups.map(g => (
                    <optgroup key={g.year} label={String(g.year)}>
                      {g.options.map(m => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                <button
                  type="button"
                  className="sl-ctrl-btn"
                  title="Next month"
                  onClick={handleNextMonth}
                >
                  ▶
                </button>
              </div>
            </div>
          )}

          <span className="sl-controls__divider"></span>

          <div className="sl-controls__group">
            <span className="sl-controls__label">Source</span>
            <div className="sl-ctrl-picker">
              <select
                className="sl-select"
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
                style={{ fontWeight: 600 }}
              >
                <option value="hupx">HUPX (Hungary)</option>
                <option value="memo">MEMO (Macedonia)</option>
              </select>
            </div>
          </div>

          <span className="sl-controls__divider"></span>

          <button
            type="button"
            className="btn-primary btn-sm"
            onClick={() => activeTab === 'daily' ? fetchDaily(selectedDate, selectedSource) : fetchMonthly(selectedMonth, selectedSource)}
          >
            <RefreshCw size={13} strokeWidth={2.4} className={loading ? 'spin' : ''} />
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="sl-alert sl-alert--error" style={{ marginBottom: '20px' }}>
            <span>⚠️</span> {error}
          </div>
        )}

        {/* ── KPI Grid ────────────────────────────────────────── */}
        {activeTab === 'daily' ? (
          <div className="sl-kpi-grid">
            <div className="sl-kpi sl-kpi--indigo">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Total Energy</span>
                <span className="sl-kpi__icon"><Zap size={15} color="#6366f1" /></span>
              </div>
              <div className="sl-kpi__value indigo">
                {fmt(dailyAnalysis.totalEnergy, 2)} <span className="sl-kpi__unit">kWh</span>
              </div>
              <div className="sl-kpi__sub">{dailyAnalysis.activeHours} active generating hours</div>
            </div>

            <div className="sl-kpi sl-kpi--teal">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Total Revenue</span>
                <span className="sl-kpi__icon"><Euro size={15} color="#0aaf72" /></span>
              </div>
              <div className="sl-kpi__value teal">
                €{fmt(dailyAnalysis.totalValue, 2)}
              </div>
              <div className="sl-kpi__sub">Estimated spot market value</div>
            </div>

            <div className="sl-kpi sl-kpi--amber">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Avg. Price</span>
                <span className="sl-kpi__icon"><Activity size={15} color="#d97706" /></span>
              </div>
              <div className="sl-kpi__value amber">
                €{fmt(dailyAnalysis.avgPrice, 2)} <span className="sl-kpi__unit">/MWh</span>
              </div>
              <div className="sl-kpi__sub">During solar production</div>
            </div>

            <div className="sl-kpi sl-kpi--blue">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Peak Power</span>
                <span className="sl-kpi__icon"><Sun size={15} color="#2563eb" /></span>
              </div>
              <div className="sl-kpi__value blue">
                {fmt(dailyAnalysis.maxEnergy, 1)} <span className="sl-kpi__unit">kWh/h</span>
              </div>
              <div className="sl-kpi__sub">Highest hourly output</div>
            </div>
          </div>
        ) : (
          <div className="sl-kpi-grid">
            <div className="sl-kpi sl-kpi--indigo">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Monthly Energy</span>
                <span className="sl-kpi__icon"><Zap size={15} color="#6366f1" /></span>
              </div>
              <div className="sl-kpi__value indigo">
                {fmt(monthlyAnalysis.totalMWh, 2)} <span className="sl-kpi__unit">MWh</span>
              </div>
              <div className="sl-kpi__sub">{fmt(monthlyAnalysis.totalKwh, 0)} kWh · {monthlyAnalysis.workingHours} active hrs</div>
            </div>

            <div className="sl-kpi sl-kpi--teal">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Monthly Revenue</span>
                <span className="sl-kpi__icon"><Euro size={15} color="#0aaf72" /></span>
              </div>
              <div className="sl-kpi__value teal">
                €{fmt(monthlyAnalysis.totalVal, 2)}
              </div>
              <div className="sl-kpi__sub">
                {monthlyAnalysis.daysWithData > 0 ? `~€${fmt(monthlyAnalysis.avgDailyRevenue, 2)}/day avg` : 'Cumulative value'}
              </div>
            </div>

            <div className="sl-kpi sl-kpi--amber">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Avg. Spot Price</span>
                <span className="sl-kpi__icon"><Activity size={15} color="#d97706" /></span>
              </div>
              <div className="sl-kpi__value amber">
                €{fmt(monthlyAnalysis.avgPrice, 2)} <span className="sl-kpi__unit">/MWh</span>
              </div>
              <div className="sl-kpi__sub">Weighted spot avg</div>
            </div>

            <div className="sl-kpi sl-kpi--blue">
              <div className="sl-kpi__top">
                <span className="sl-kpi__label">Active Generation</span>
                <span className="sl-kpi__icon"><Sun size={15} color="#2563eb" /></span>
              </div>
              <div className="sl-kpi__value blue">
                {monthlyAnalysis.daysWithData} <span className="sl-kpi__unit">Days</span>
              </div>
              <div className="sl-kpi__sub">Days with solar generation</div>
            </div>
          </div>
        )}

        {/* ── Main Chart Card ─────────────────────────────────── */}
        <div className="sl-chart-card">
          <div className="sl-chart-card__header">
            <div>
              <div className="sl-chart-card__title">
                {activeTab === 'daily' ? 'Hourly Performance vs Spot Price' : 'Daily Output & Revenue Trends'}
              </div>
              <div className="sl-chart-card__sub">
                {activeTab === 'daily'
                  ? `Comparing energy output (kWh) with ${selectedSource.toUpperCase()} market spot prices (€/MWh)`
                  : `Monthly generation across days with revenue overlay`}
              </div>
            </div>

            {activeTab === 'daily' && (
              <div className="chart-toggle">
                <button
                  type="button"
                  className={`chart-toggle__btn ${chartType === 'combo' ? 'active' : ''}`}
                  onClick={() => setChartType('combo')}
                >
                  Combo
                </button>
                <button
                  type="button"
                  className={`chart-toggle__btn ${chartType === 'bar' ? 'active' : ''}`}
                  onClick={() => setChartType('bar')}
                >
                  Bar
                </button>
                <button
                  type="button"
                  className={`chart-toggle__btn ${chartType === 'line' ? 'active' : ''}`}
                  onClick={() => setChartType('line')}
                >
                  Line
                </button>
              </div>
            )}
          </div>

          <div className="sl-chart-wrap" style={{ height: '360px', position: 'relative' }}>
            {loading ? (
              <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#6b7a8d' }}>
                <div className="sl-spinner"></div>
              </div>
            ) : (
              <Chart
                type="bar"
                data={activeTab === 'daily' ? dailyChartData : monthlyChartData}
                options={chartOptions}
              />
            )}
          </div>
        </div>

        {/* ── Detailed Table Card ─────────────────────────────── */}
        <div className="sl-table-card">
          <div className="sl-table-card__header">
            <div>
              <div className="sl-table-card__title">
                {activeTab === 'daily' ? 'Hourly Breakdown' : 'Daily Summary Breakdown'}
              </div>
              {activeTab === 'monthly' && (
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Tap any day row to inspect hourly performance
                </div>
              )}
            </div>
            <span className="sl-badge sl-badge--gray">
              {activeTab === 'daily' ? `${dailyAnalysis.activeHours} generating hours` : `${monthlyAnalysis.daysWithData} active days`}
            </span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="sl-table">
              <thead>
                <tr>
                  <th>{activeTab === 'daily' ? 'Hour' : 'Date'}</th>
                  <th>Production</th>
                  <th>Share</th>
                  <th>{activeTab === 'daily' ? 'Market Price' : 'Avg. Working Price'}</th>
                  <th>Revenue</th>
                </tr>
              </thead>
              <tbody>
                {activeTab === 'daily' ? (
                  dailyAnalysis.rows.map(row => {
                    const pct = Math.round((row.energy / dailyAnalysis.maxEnergy) * 100);
                    return (
                      <tr key={row.hour}>
                        <td><span className="td-mono">{row.hour}</span></td>
                        <td>
                          <span className="td-energy">{fmt(row.energy, 3)}</span>{' '}
                          <span style={{ fontSize: '11px', color: 'var(--text-faint)' }}>kWh</span>
                        </td>
                        <td>
                          <div className="td-bar-wrap">
                            <div className="td-bar">
                              <div className="td-bar__fill" style={{ width: `${pct}%` }}></div>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', minWidth: '28px', textAlign: 'right' }}>
                              {pct}%
                            </span>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>€{fmt(row.price, 2)}</span>
                        </td>
                        <td>
                          <span className="td-value">€{fmt(row.value, 2)}</span>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  monthlyAnalysis.days.map(d => {
                    const pct = monthlyAnalysis.maxDayEnergy > 0 ? Math.round((d.energy / monthlyAnalysis.maxDayEnergy) * 100) : 0;
                    return (
                      <tr
                        key={d.date}
                        style={{ cursor: 'pointer' }}
                        title="Click to view daily hourly breakdown"
                        onClick={() => {
                          setSelectedDate(d.date);
                          setActiveTab('daily');
                        }}
                      >
                        <td>
                          <span className="td-mono" style={{ fontWeight: 600 }}>{fmtShortDate(d.date)}</span>
                          <span style={{ display: 'block', fontSize: '11px', color: 'var(--text-faint)' }}>{d.date}</span>
                        </td>
                        <td>
                          <span className="td-energy">{fmt(d.energyMWh, 3)}</span>{' '}
                          <span style={{ fontSize: '11px', color: 'var(--text-faint)' }}>MWh</span>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{fmt(d.energy, 0)} kWh</div>
                        </td>
                        <td>
                          <div className="td-bar-wrap">
                            <div className="td-bar">
                              <div className="td-bar__fill" style={{ width: `${pct}%` }}></div>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', minWidth: '28px', textAlign: 'right' }}>
                              {pct}%
                            </span>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>€{fmt(d.avgPrice, 2)}</span>
                          <span style={{ fontSize: '11px', color: 'var(--text-faint)' }}> /MWh</span>
                        </td>
                        <td>
                          <span className="td-value">€{fmt(d.value, 2)}</span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Dashboard />
    </ErrorBoundary>
  );
}
