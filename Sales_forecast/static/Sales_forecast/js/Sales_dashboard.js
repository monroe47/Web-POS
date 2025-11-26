// Copied dashboard JS - same as Sales_forecast/js/Sales_dashboard.js
/**
 * sales_dashboard.js (static copy)
 * This is the same script as Sales_forecast/js/Sales_dashboard.js but placed
 * in the app's static directory so Django can serve it to the browser.
 */

(function () {
  // ---------- Configuration ----------
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

    const rows = historical.slice(-14);
    const rowsDesc = rows.slice().reverse();

    const dateToActual = {};
    historical.forEach(h => { dateToActual[isoDate(h.date)] = Number(h.actual || 0); });

    rowsDesc.forEach((r, idx) => {
      const d = isoDate(r.date);
      const actual = Number(r.actual || 0);
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

  function renderForecastTable(forecast = [], historicalCount = 0, restockRecs = {}) {
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

    forecast.forEach(r => {
      const d = isoDate(r.date);
      const pred = Number(r.predicted || 0);
      
      // Get restock recommendation for this date
      const rec = restockRecs[d];
      const restockText = rec 
        ? `${rec.sku ? '(' + rec.sku + ')' : ''}${rec.product_name}`
        : 'No restock needed';
      
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${d}</td>
        <td>${formatCurrency(pred)}</td>
        <td style="color:#059669;font-weight:600;font-size:0.9rem">${restockText}</td>
        <td><button class="button" data-date="${d}" data-prod="${rec ? rec.product_name : ''}" data-sku="${rec ? rec.sku : ''}">Details</button></td>
      `;
      tbody.appendChild(tr);
    });

    qsAll('button[data-date]', tbody).forEach(btn => {
      btn.addEventListener('click', () => {
        const d = btn.dataset.date;
        const prod = btn.dataset.prod;
        const sku = btn.dataset.sku;
        let msg = `Forecast for ${d}: ${formatCurrency(btn.dataset.date ? '0' : 'n/a')}`;
        if (prod) {
          msg = `Product to Restock on ${d}:\n${sku ? '(' + sku + ')' : ''}${prod}`;
        } else {
          msg = `No restock needed on ${d}`;
        }
        alert(msg);
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
      
      // ✅ NEW: Add demo parameter if in demo mode
      if (window.DEMO_MODE) {
        url.searchParams.set('demo', '1');
        console.log('📊 Requesting demo forecast data');
      }
      
      const productId = $('#productSelect')?.value;
      if (productId) url.searchParams.set('product_id', productId);

      console.log('Fetching forecast from:', url.toString());
      const data = await apiFetch(url.toString());
      console.log('API Response:', data);

      const historical = (data.historical || []).map(r => ({ date: isoDate(r.date), actual: Number(r.actual || 0) }));
      const forecast = (data.forecast || []).map(r => ({ date: isoDate(r.date), predicted: Number(r.predicted || 0) }));
      const restockRecs = data.restock_recommendations || {};

      console.log('Historical count:', historical.length);
      console.log('Forecast count:', forecast.length);
      console.log('Forecast data:', forecast);
      console.log('Restock recommendations:', restockRecs);

      const labels = historical.map(h => isoDate(h.date));
      const actualSeries = historical.map(h => Number(h.actual || 0));
      
      // Show forecast if we have any forecast data, regardless of historical count
      let forecastSeries = [];
      let showForecast = forecast && forecast.length > 0;

      console.log('Show forecast:', showForecast);

      if (showForecast) {
        forecastSeries = forecast.map(f => Number(f.predicted || 0));
      }

      const finalLabels = showForecast ? labels.concat(forecast.map(f => isoDate(f.date))) : labels;
      renderChart({ labels: finalLabels, actual: actualSeries, forecast: forecastSeries }, { smooth: $('#smoothToggle')?.checked ?? true });

      renderRecentSales(historical);
      updateKPIs(historical, showForecast ? forecast : []);

      renderForecastTable(showForecast ? forecast : [], historical.length, restockRecs);

      statusEl.textContent = 'Dashboard updated • ' + (showForecast ? `${forecast.length} forecast(s)` : 'No forecast');
    } catch (err) {
      console.error('Dashboard error:', err);
      statusEl.textContent = 'Failed to load dashboard: ' + err.message;
      toast(err.message || 'Failed to load dashboard', 'error');
    }
  }

  // ---------- Retrain flow ----------
  async function retrain(days = 365, horizon = 7) {
    const csrftoken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    try {
      const res = await apiFetch(API_RETRAIN, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
        body: JSON.stringify({ days, horizon })
      });
      toast('Retrain started (run ' + (res.run_id || 'n/a') + ')', 'success');
      setTimeout(loadDashboard, 4000);
    } catch (err) {
      console.error('Retrain failed', err);
      toast('Retrain failed: ' + (err.message || 'unknown'), 'error');
    }
  }

  // ---------- Event wiring ----------
  function attachHandlers() {
    $('#refreshBtn')?.addEventListener('click', (e) => { e.preventDefault(); loadDashboard(); });

    $('#retrainBtn')?.addEventListener('click', () => {
      const modal = $('#modalBackdrop');
      if (modal) {
        modal.classList.add('show');
      } else if (confirm('Retrain model now?')) {
        retrain(Number($('#retrainDays')?.value || 365), Number($('#retrainHorizon')?.value || 7));
      }
    });

    $('#btnRetrainSidebar')?.addEventListener('click', () => {
      const modal = $('#modalBackdrop');
      if (modal) modal.classList.add('show');
    });
    $('#cancelRetrain')?.addEventListener('click', () => {
      const modal = $('#modalBackdrop');
      if (modal) modal.classList.remove('show');
    });
    $('#confirmRetrain')?.addEventListener('click', async (e) => {
      e.preventDefault();
      const days = Number($('#retrainDays')?.value || 365);
      const horizon = Number($('#retrainHorizon')?.value || 7);
      await retrain(days, horizon);
      const modal = $('#modalBackdrop');
      if (modal) modal.classList.remove('show');
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

    // --- Recent Sales row click: fetch daily details and show modal ---
    const recentBody = $('#recentBody');
    if (recentBody) {
      recentBody.addEventListener('click', async (e) => {
        let tr = e.target.closest('tr');
        if (!tr || !tr.firstElementChild) return;
        const date = tr.firstElementChild.textContent.trim();
        if (!date) return;

        try {
          const url = `/sales_forecast/api/daily_sales_details/?date=${encodeURIComponent(date)}`;
          const data = await apiFetch(url);

          const backdrop = document.getElementById('dailySalesModal');
          if (!backdrop) return toast('Sales details modal not found', 'error');

          // Populate products table
          const productsTbody = document.getElementById('modalProductsTable');
          if (productsTbody) {
            if (!data || !Array.isArray(data.products) || data.products.length === 0) {
              productsTbody.innerHTML = '<tr><td colspan="4" style="padding:12px;text-align:center;color:#999;">No sales for this date.</td></tr>';
            } else {
              const rows = data.products.map(p => {
                const name = p.product_name || '';
                const qty = Number(p.quantity || 0);
                const unit = Number(p.unit_price || 0);
                const total = Number(p.total_amount || (qty * unit));
                return `
                  <tr>
                    <td style="padding:12px">${name}</td>
                    <td style="padding:12px;text-align:center">${qty}</td>
                    <td style="padding:12px;text-align:right">${formatCurrency(unit)}</td>
                    <td style="padding:12px;text-align:right">${formatCurrency(total)}</td>
                  </tr>`;
              }).join('');
              productsTbody.innerHTML = rows;
            }
          }

          // Update summary fields
          const totalItemsEl = document.getElementById('modalTotalItems');
          const uniqueProductsEl = document.getElementById('modalUniqueProducts');
          const grandTotalEl = document.getElementById('modalGrandTotal');
          const titleEl = document.getElementById('modalDateTitle');
          const formattedEl = document.getElementById('modalDateFormatted');

          if (totalItemsEl) totalItemsEl.textContent = String(data.total_items_sold || 0);
          if (uniqueProductsEl) uniqueProductsEl.textContent = String(data.total_products || (data.products ? data.products.length : 0));
          if (grandTotalEl) grandTotalEl.textContent = formatCurrency(Number(data.grand_total || 0));
          if (titleEl) titleEl.textContent = `Sales Details — ${date}`;
          if (formattedEl) formattedEl.textContent = data.formatted_date || '';

          // Show backdrop
          backdrop.style.display = 'flex';
        } catch (err) {
          console.error('Daily details error', err);
          toast('Failed to fetch sales details: ' + (err.message || 'unknown'), 'error');
        }
      });
    }

    // Expose close function used by template buttons
    window.closeDailySalesModal = function () {
      const backdrop = document.getElementById('dailySalesModal');
      if (backdrop) backdrop.style.display = 'none';
    };
  }

  // ---------- Init ----------
  function start() {
    attachHandlers();
    loadDashboard();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();

  window.SF = window.SF || {};
  window.SF.loadDashboard = loadDashboard;
  window.SF.retrain = retrain;
})();