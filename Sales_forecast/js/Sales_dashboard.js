/**
 * sales_dashboard.js
 * Rewritten dashboard JS to:
 * - Render only recent historical sales by default (no forecast shown until model is ready)
 * - Populate "Recent Sales" table correctly (last 14 days + trend)
 * - Only show forecast datasets/tables when API returns forecasts AND we have enough historical data
 * - Robust error handling and DOM-safety
 *
 * Place this file in: Sales_forecast/static/Sales_forecast/js/sales_dashboard.js
 * Include in template with {% load static %} and:
 *   <script src="{% static 'Sales_forecast/js/sales_dashboard.js' %}"></script>
 */

(() => {
  // ---------- Configuration ----------
  // App-scoped API endpoints under the sales_forecast app
  const API_FORECAST = '/sales_forecast/api/forecast/';
  const API_RETRAIN = '/sales_forecast/api/forecast/retrain/';
  const MIN_HISTORY_FOR_FORECAST = 30; // require at least this many historical points before showing model forecast

  // ---------- Helpers ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const qsAll = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function formatCurrency(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '₱0';
    return '₱' + Number(n).toLocaleString();
  }

  function isoDate(d) {
    if (!d) return '';
    if (typeof d === 'string') return d.slice(0, 10);
    if (d instanceof Date) return d.toISOString().slice(0, 10);
    // pandas Timestamp or dayjs -> try Date()
    try { return new Date(d).toISOString().slice(0, 10); } catch { return String(d); }
  }

  function toast(msg, type = 'success', ttl = 3000) {
    const wrap = document.getElementById('toasts') || (() => {
      const w = document.createElement('div');
      w.id = 'toasts';
      w.className = 'toast-wrap';
      w.style.position = 'fixed';
      w.style.right = '18px';
      w.style.bottom = '18px';
      w.style.zIndex = 9999;
      document.body.appendChild(w);
      return w;
    })();
    const el = document.createElement('div');
    el.className = `toast ${type === 'error' ? 'error' : 'success'}`;
    el.textContent = msg;
    el.style.padding = '10px 14px';
    el.style.borderRadius = '10px';
    el.style.color = '#fff';
    el.style.fontWeight = 600;
    el.style.background = type === 'error' ? '#ef4444' : '#10b981';
    el.style.transition = 'all 300ms ease';
    wrap.appendChild(el);
    setTimeout(() => { el.style.opacity = 0; el.style.transform = 'translateY(8px)'; }, ttl - 300);
    setTimeout(() => el.remove(), ttl);
  }

  async function apiFetch(url, opts = {}) {
    try {
      const res = await fetch(url, opts);
      const text = await res.text();
      let json = null;
      try { json = text ? JSON.parse(text) : null; } catch {}
      if (!res.ok) {
        const msg = (json && (json.details || json.error || json.message)) || `${res.status} ${res.statusText}`;
        const e = new Error(msg);
        e.status = res.status;
        e.body = json || text;
        throw e;
      }
      return json;
    } catch (err) {
      throw err;
    }
  }

  // ---------- Chart helpers ----------
  let chart = null;
  function createGradient(ctx, color) {
    const g = ctx.createLinearGradient(0, 0, 0, 350);
    g.addColorStop(0, color);
    g.addColorStop(1, 'rgba(255,255,255,0)');
    return g;
  }

  function renderChart({ labels = [], actual = [], forecast = [] }, options = { smooth: true }) {
    const canvas = $('#salesChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (chart) chart.destroy();
    const tension = options.smooth ? 0.45 : 0;

    // Build datasets: always show Actual. Only add Forecast dataset when forecast.length > 0.
    const datasets = [
      {
        label: 'Actual Sales',
        data: actual,
        borderColor: 'rgba(37,99,235,1)',
        backgroundColor: createGradient(ctx, 'rgba(37,99,235,0.28)'),
        fill: true,
        tension,
        pointRadius: 3,
        borderWidth: 2
      }
    ];

    if (Array.isArray(forecast) && forecast.length > 0) {
      // Align forecast to start after actuals: we expect labels = [...actualDates, ...forecastDates]
      const alignedForecast = Array(actual.length).fill(null).concat(forecast);
      datasets.push({
        label: 'Forecast',
        data: alignedForecast,
        borderColor: 'rgba(245,158,11,1)',
        borderDash: [6, 6],
        backgroundColor: createGradient(ctx, 'rgba(245,158,11,0.18)'),
        fill: true,
        tension,
        pointRadius: 4,
        borderWidth: 2
      });
    }

    chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        animation: { duration: 600 },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          tooltip: {
            callbacks: {
              label(ctx) {
                const v = ctx.parsed.y;
                return `${ctx.dataset.label}: ${formatCurrency(v)}`;
              }
            }
          },
          legend: { position: 'top' }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155' } },
          y: {
            beginAtZero: true,
            ticks: { callback: v => '₱' + Number(v).toLocaleString() }
          }
        }
      }
    });
  }

  // ---------- UI renderers ----------
  function renderRecentSales(historical = []) {
    const tbody = $('#recentBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!historical || historical.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" class="small muted">No recent sales</td></tr>`;
      return;
    }

    // Take last 14 days from historical (assumed chronological). If API returns newest last, we'll slice appropriately.
    const rows = historical.slice(-14);
    // Ensure chronological descending for UI (latest last or first? In template we prefer latest first)
    const rowsDesc = rows.slice().reverse();

    // Build a map of date -> actual for computing trend
    const dateToActual = {};
    historical.forEach(h => { dateToActual[isoDate(h.date)] = Number(h.actual || 0); });

    rowsDesc.forEach((r, idx) => {
      const d = isoDate(r.date);
      const actual = Number(r.actual || 0);
      // trend: difference from previous day (previous by date in historical, not by table order)
      // find prev day's date in ISO (one day before)
      let trend = 0;
      try {
        const prevDate = new Date(d);
        prevDate.setDate(prevDate.getDate() - 1);
        const prevIso = prevDate.toISOString().slice(0, 10);
        const prevVal = dateToActual[prevIso] !== undefined ? dateToActual[prevIso] : actual;
        trend = actual - prevVal;
      } catch {
        trend = 0;
      }

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="padding:6px;border-bottom:1px solid #eee">${d}</td>
        <td style="padding:6px;border-bottom:1px solid #eee">${formatCurrency(actual)}</td>
        <td style="padding:6px;border-bottom:1px solid #eee" class="small">${trend>=0?'+':''}${trend.toFixed(0)}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderForecastTable(forecast = [], historicalCount = 0) {
    const tbody = $('#forecastBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!forecast || forecast.length === 0) {
      if (historicalCount < MIN_HISTORY_FOR_FORECAST) {
        tbody.innerHTML = `<tr><td colspan="4" class="small muted">No forecast yet — waiting for more historical data (need at least ${MIN_HISTORY_FOR_FORECAST} days).</td></tr>`;
      } else {
        tbody.innerHTML = `<tr><td colspan="4" class="small muted">No forecast available.</td></tr>`;
      }
      return;
    }

    // last actual for percent-change baseline
    const lastActual = historicalCount > 0 ? Number($('#kpiToday')?.dataset.lastActual || 0) : 0;

    forecast.forEach(r => {
      const d = isoDate(r.date);
      const pred = Number(r.predicted || 0);
      const pct = lastActual ? ((pred - lastActual) / (lastActual || 1) * 100) : 0;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${d}</td>
        <td>${formatCurrency(pred)}</td>
        <td>${pct>=0?'+':''}${pct.toFixed(1)}%</td>
        <td><button class="button" data-date="${d}" data-pred="${pred}">Details</button></td>
      `;
      tbody.appendChild(tr);
    });

    // attach detail handlers
    qsAll('button[data-date]', tbody).forEach(btn => {
      btn.addEventListener('click', () => {
        toast(`Forecast for ${btn.dataset.date}: ${formatCurrency(btn.dataset.pred)}`);
      });
    });
  }

  function updateKPIs(historical = [], forecast = []) {
    const kpiTodayEl = $('#kpiToday');
    const kpiNextEl = $('#kpiNext');
    const kpiChangeEl = $('#kpiChange');

    const histVals = (historical || []).map(h => Number(h.actual || 0));
    const lastActual = histVals.length ? histVals[histVals.length - 1] : 0;
    const nextForecast = (forecast && forecast.length) ? Number(forecast[0].predicted || 0) : 0;

    const avgLast7 = histVals.slice(-7).length ? (histVals.slice(-7).reduce((a,b)=>a+b,0) / Math.min(7, histVals.length)) : 0;
    const avgNext = forecast && forecast.length ? (forecast.reduce((a,b)=>a + Number(b.predicted || 0), 0) / forecast.length) : 0;
    const pctChange = avgLast7 ? ((avgNext - avgLast7) / avgLast7) * 100 : 0;

    if (kpiTodayEl) {
      kpiTodayEl.textContent = formatCurrency(lastActual);
      // store last actual in data attribute for percent calculations in forecast table
      kpiTodayEl.dataset.lastActual = lastActual;
    }
    if (kpiNextEl) kpiNextEl.textContent = formatCurrency(nextForecast);
    if (kpiChangeEl) kpiChangeEl.textContent = (pctChange>=0?'+':'') + pctChange.toFixed(1) + '%';
  }

  // ---------- Main load function ----------
  async function loadDashboard() {
    const horizon = Number($('#horizon')?.value || 7);
    $('#horizonBadge') && ($('#horizonBadge').textContent = String(horizon));
    const statusEl = $('#status') || (() => {
      const s = document.createElement('div'); s.id = 'status'; s.style.cssText = 'text-align:center;color:#666;margin-top:6px;font-size:0.95rem;';
      document.querySelector('header')?.appendChild(s);
      return s;
    })();
    statusEl.textContent = 'Loading dashboard...';

    try {
      const url = new URL(API_FORECAST, location.origin);
      url.searchParams.set('horizon', horizon);
      url.searchParams.set('force', '1'); // Force prediction regardless of accuracy
      const productId = $('#productSelect')?.value;
      if (productId) url.searchParams.set('product_id', productId);

      console.log('Fetching forecast from:', url.toString());
      const data = await apiFetch(url.toString());
      console.log('API Response:', data);

      // Normalize historical & forecast arrays
      const historical = (data.historical || []).map(r => ({ date: isoDate(r.date), actual: Number(r.actual || 0) }));
      const forecast = (data.forecast || []).map(r => ({ date: isoDate(r.date), predicted: Number(r.predicted || 0) }));

      console.log('Historical count:', historical.length);
      console.log('Forecast count:', forecast.length);
      console.log('Forecast data:', forecast);

      // Prepare chart inputs: show forecast if we have any forecast data, regardless of historical count
      const labels = historical.map(h => isoDate(h.date));
      const actualSeries = historical.map(h => Number(h.actual || 0));
      let forecastSeries = [];
      let showForecast = forecast && forecast.length > 0;

      console.log('Show forecast:', showForecast);

      if (showForecast) {
        // forecastSeries remains forecast predicted values
        forecastSeries = forecast.map(f => Number(f.predicted || 0));
      } else {
        // Do not include forecast data
        forecastSeries = [];
      }

      // Render chart: labels should be combined historical + forecast labels if forecast is shown,
      // otherwise just historical labels.
      const finalLabels = showForecast ? labels.concat(forecast.map(f => isoDate(f.date))) : labels;
      renderChart({ labels: finalLabels, actual: actualSeries, forecast: forecastSeries }, { smooth: $('#smoothToggle')?.checked ?? true });

      // Populate recent sales table and KPI
      renderRecentSales(historical);
      updateKPIs(historical, showForecast ? forecast : []);

      // Populate forecast table (shows message if not ready)
      renderForecastTable(showForecast ? forecast : [], historical.length);

      statusEl.textContent = 'Dashboard updated • ' + (showForecast ? `${forecast.length} forecast(s)` : 'No forecast');
    } catch (err) {
      console.error('Dashboard error:', err);
      statusEl.textContent = 'Failed to load dashboard: ' + err.message;
      toast(err.message || 'Failed to load dashboard', 'error');
    }
  }

  // ---------- Retrain flow (keeps existing behavior) ----------
  async function retrain(days = 365, horizon = 7) {
    const csrftoken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    try {
      const res = await apiFetch(API_RETRAIN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
        body: JSON.stringify({ days, horizon })
      });
      toast('Retrain started (run ' + (res.run_id || 'n/a') + ')', 'success');
      // refresh after short delay
      setTimeout(loadDashboard, 4000);
    } catch (err) {
      console.error('Retrain failed', err);
      toast('Retrain failed: ' + (err.message || 'unknown'), 'error');
    }
  }

  // ---------- Event wiring ----------
  function attachHandlers() {
    $('#refreshBtn')?.addEventListener('click', (e) => { e.preventDefault(); loadDashboard(); });
    $('#export-csv')?.addEventListener('click', (e) => {
      e.preventDefault();
      if (!chart) return toast('No data to export', 'error');
      const labels = chart.data.labels;
      const a0 = chart.data.datasets[0].data;
      const a1 = (chart.data.datasets[1] || { data: [] }).data;
      let csv = 'date,actual,forecast\n';
      for (let i = 0; i < labels.length; i++) {
        csv += `${labels[i]},${a0[i] ?? ''},${a1[i] ?? ''}\n`;
      }
      const blob = new Blob([csv], { type: 'text/csv' });
      const u = URL.createObjectURL(blob);
      const at = document.createElement('a'); at.href = u; at.download = `sales_forecast_${new Date().toISOString().slice(0,10)}.csv`; document.body.appendChild(at); at.click(); at.remove(); URL.revokeObjectURL(u);
      toast('CSV exported');
    });

    $('#retrainBtn')?.addEventListener('click', () => {
      const modal = $('#modalBackdrop');
      if (modal) modal.classList.add('show');
      else if (confirm('Retrain model now?')) retrain(Number($('#retrainDays')?.value || 365), Number($('#retrainHorizon')?.value || 7));
    });

    $('#btnRetrainSidebar')?.addEventListener('click', () => {
      $('#modalBackdrop')?.classList.add('show');
    });
    $('#cancelRetrain')?.addEventListener('click', () => $('#modalBackdrop')?.classList.remove('show'));
    $('#confirmRetrain')?.addEventListener('click', async (e) => {
      e.preventDefault();
      const days = Number($('#retrainDays')?.value || 365);
      const horizon = Number($('#retrainHorizon')?.value || 7);
      await retrain(days, horizon);
      $('#modalBackdrop')?.classList.remove('show');
    });

    $('#smoothToggle')?.addEventListener('change', () => loadDashboard());

    // View mode change (daily/monthly) - currently reloads dashboard and can toggle UI in future
    $('#viewMode')?.addEventListener('change', (e) => {
      loadDashboard();
    });

    // Horizon change updates badge and reloads
    $('#horizon')?.addEventListener('change', (e) => {
      $('#horizonBadge') && ($('#horizonBadge').textContent = String(Number(e.target.value || 7)));
      loadDashboard();
    });

    // Product filter change -> reload
    $('#productSelect')?.addEventListener('change', (e) => {
      loadDashboard();
    });

    // Toggle sidebar
    $('#open-sidebar')?.addEventListener('click', ()=> {
      const sb = document.querySelector('.sidebar');
      if (!sb) return;
      sb.style.display = (sb.style.display === 'none' || getComputedStyle(sb).display === 'none') ? 'flex' : 'none';
    });

    // Show model runs / info (reads JSON embedded in template)
    $('#btnShowModelRuns')?.addEventListener('click', (e) => {
      try {
        const el = document.getElementById('sf_model_info');
        const info = el ? JSON.parse(el.textContent || el.innerText || '{}') : null;
        if (!info) return toast('No model info available', 'error');
        const name = info.name || 'Model';
        const trained = info.trained_on ? (new Date(info.trained_on)).toISOString().slice(0,10) : 'n/a';
        const metrics = info.metrics ? JSON.stringify(info.metrics) : '{}';
        toast(`${name} — Trained on: ${trained}`);
        // Optionally open a modal with details later; for now we show a toast and console for debugging
        console.info('Model info:', info);
      } catch (err) {
        console.error(err);
        toast('Failed to read model info', 'error');
      }
    });
  }

  // ---------- Init ----------
  function start() {
    attachHandlers();
    loadDashboard();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();

  // Expose for debugging
  window.SF = window.SF || {};
  window.SF.loadDashboard = loadDashboard;
  window.SF.retrain = retrain;
})();