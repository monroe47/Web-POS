// Shared spreadsheet logic used by sheet.html and excel.html
// Exposes global functions used by templates (createGrid, recalculateAll, etc.)

const ROWS = 10;
const COLS = 5;
const COLUMN_LABELS = ['A','B','C','D','E'];
const COLOR_PALETTE = ['bg-white','bg-yellow-200','bg-green-200','bg-red-200'];

let currentFileId = null;
let currentFileName = 'Untitled';
const cells = {};
let activeCellId = 'A1';
let isEditing = false;
let fileList = []; // used by local-storage dashboard

function showMessage(text, type='info'){
  const box = document.getElementById('message-box');
  if(!box) return;
  box.textContent = text;
  box.className = '';
  box.classList.add('mt-6','p-4','border','rounded-lg');
  box.classList.add(type === 'success' ? 'bg-green-100' : type === 'error' ? 'bg-red-100' : 'bg-yellow-100');
  setTimeout(()=> box.classList.add('hidden'), 4000);
  box.classList.remove('hidden');
}

function colToLetter(i){ return COLUMN_LABELS[i] || '' }
function getCellData(id){ return cells[id] || { value:'', result:'', color:'bg-white' }; }
function getCellValue(id){ const d = getCellData(id); return (typeof d.result === 'number' && !isNaN(d.result)) ? d.result : (parseFloat(d.result) || 0); }

function updateCellDisplay(id){
  const el = document.querySelector(`.data-cell[data-cell-id="${id}"]`);
  if(!el) return;
  const data = getCellData(id);
  if(typeof data.value === 'string' && data.value.startsWith('=')){
    el.textContent = String(data.result);
    el.classList.add('text-green-600'); el.classList.remove('text-gray-800');
  } else {
    el.textContent = String(data.value || '');
    el.classList.remove('text-green-600'); el.classList.add('text-gray-800');
  }
  if(el instanceof HTMLElement){ el.style.textAlign = isNaN(parseFloat(data.result)) ? 'left' : 'right'; }
}

function resolveCellReference(match){ const id = match.toUpperCase(); return String(getCellValue(id)); }

function evaluateFormula(formula){
  if(!formula || typeof formula !== 'string') return '';
  if(!formula.startsWith('=')){
    const n = parseFloat(formula); return isNaN(n) ? formula : n;
  }
  let expr = formula.substring(1).trim();
  expr = expr.replace(/SUM\(([A-E])(\d+):([A-E])(\d+)\)/gi, (m, sc, sr, ec, er)=>{
    if(sc !== ec) return 'NaN';
    let sum = 0; const s=parseInt(sr,10), e=parseInt(er,10);
    for(let r=s;r<=e;r++) sum += Number(getCellValue(sc + r) || 0);
    return String(sum);
  });
  expr = expr.replace(/([A-E]\d+)/gi, (m)=> resolveCellReference(m));
  try{ const res = new Function('return '+expr)(); if(typeof res === 'number' && res % 1 !== 0) return parseFloat(res.toFixed(4)); return res; }catch(e){ return '#ERROR'; }
}

function recalculateAll(){
  const raw = {};
  for(const k in cells) raw[k] = cells[k].value;
  for(const k in cells) cells[k].result = 0;
  let changed=true, iter=0, max=ROWS*COLS;
  while(changed && iter++ < max){
    changed = false;
    for(const id in cells){
      const newR = evaluateFormula(raw[id]);
      if(newR !== cells[id].result){ cells[id].result = newR; changed = true; }
    }
  }
  for(const id in cells) updateCellDisplay(id);
}

function handleFormulaInput(newValue){ if(!activeCellId) return; if(!cells[activeCellId]) cells[activeCellId] = { value:'', result:'', color:'bg-white' }; cells[activeCellId].value = newValue; recalculateAll(); }

function activateCell(id){
  const oldEl = document.querySelector(`.data-cell[data-cell-id="${activeCellId}"]`);
  if(oldEl) oldEl.classList.remove('bg-blue-100','ring-2','ring-blue-500');
  activeCellId = id;
  const data = getCellData(id);
  const fin = document.getElementById('formula-input'); if(fin instanceof HTMLInputElement) fin.value = data.value || '';
  const newEl = document.querySelector(`.data-cell[data-cell-id="${id}"]`);
  if(newEl) { newEl.classList.remove(...COLOR_PALETTE); newEl.classList.add('bg-blue-100','ring-2','ring-blue-500'); }
  const cur = document.getElementById('current-cell-id'); if(cur) cur.textContent = id;
}

function cycleCellColor(id){ const el = document.querySelector(`.data-cell[data-cell-id="${id}"]`); if(!el) return; const data = getCellData(id); const idx = COLOR_PALETTE.indexOf(data.color || 'bg-white'); const next = COLOR_PALETTE[(idx+1)%COLOR_PALETTE.length]; data.color = next; cells[id] = data; el.classList.remove(...COLOR_PALETTE); if(id !== activeCellId) el.classList.add(next); }

// Inline editor overlay
function startCellEdit(id){ const cell = document.querySelector(`.data-cell[data-cell-id="${id}"]`); if(!cell) return; activateCell(id); const editor = document.getElementById('cell-editor'); if(!(editor instanceof HTMLInputElement)) return; const wrap = document.querySelector('.grid-wrapper'); const rect = cell.getBoundingClientRect(); const wrect = wrap ? wrap.getBoundingClientRect() : { left:0, top:0 }; editor.style.left = (rect.left - wrect.left) + 'px'; editor.style.top = (rect.top - wrect.top) + 'px'; editor.style.width = rect.width + 'px'; editor.style.height = rect.height + 'px'; editor.value = getCellData(id).value || ''; editor.style.display = 'block'; editor.focus(); try{ editor.select(); }catch(e){} isEditing = true; }
function finishCellEdit(save=true){ const editor = document.getElementById('cell-editor'); if(!(editor instanceof HTMLInputElement)) return; const val = editor.value; const id = activeCellId; if(save){ cells[id] = cells[id] || { value:'', result:'', color:'bg-white' }; cells[id].value = val; recalculateAll(); updateCellDisplay(id); const fin = document.getElementById('formula-input'); if(fin instanceof HTMLInputElement) fin.value = val; } editor.style.display = 'none'; isEditing = false; }
function cancelCellEdit(){ const editor = document.getElementById('cell-editor'); if(editor) editor.style.display = 'none'; isEditing = false; }

// Keyboard navigation
document.addEventListener('keydown', (e)=>{
  const editor = document.getElementById('cell-editor');
  if(editor && editor.style.display === 'block'){
    if(e.key === 'Enter'){ e.preventDefault(); finishCellEdit(true); moveActive(1,0); }
    else if(e.key === 'Tab'){ e.preventDefault(); finishCellEdit(true); moveActive(0,1); }
    else if(e.key === 'Escape'){ e.preventDefault(); cancelCellEdit(); }
    return;
  }
  if((e.ctrlKey||e.metaKey) && e.key.toLowerCase() === 'c'){ e.preventDefault(); navigator.clipboard && navigator.clipboard.writeText(getCellData(activeCellId).value || ''); showMessage('Copied','success'); }
  if((e.ctrlKey||e.metaKey) && e.key.toLowerCase() === 'v'){ e.preventDefault(); navigator.clipboard && navigator.clipboard.readText().then(t=>{ cells[activeCellId].value = t; recalculateAll(); updateCellDisplay(activeCellId); }); }
  if(!isEditing){ if(e.key === 'ArrowUp'){ e.preventDefault(); moveActive(-1,0);} else if(e.key === 'ArrowDown'){ e.preventDefault(); moveActive(1,0);} else if(e.key === 'ArrowLeft'){ e.preventDefault(); moveActive(0,-1);} else if(e.key === 'ArrowRight'){ e.preventDefault(); moveActive(0,1);} else if(e.key==='Enter' || e.key==='F2'){ e.preventDefault(); startCellEdit(activeCellId); } }
});

function moveActive(dr, dc){ const m = activeCellId.match(/^([A-Z]+)(\d+)$/); if(!m) return; const col = m[1], row = parseInt(m[2],10); const ci = COLUMN_LABELS.indexOf(col); let nci = Math.max(0, Math.min(COLS-1, ci + dc)); let nri = Math.max(1, Math.min(ROWS, row + dr)); const nid = COLUMN_LABELS[nci] + nri; activateCell(nid); }

function attachCellListeners(){ document.querySelectorAll('.data-cell').forEach(el=>{ const id = el.getAttribute('data-cell-id'); if(!id) return; el.addEventListener('click', ()=> activateCell(id)); el.addEventListener('dblclick', ()=> startCellEdit(id)); el.addEventListener('contextmenu', (e)=>{ e.preventDefault(); cycleCellColor(id); }); }); }

function createGrid(){ const grid = document.getElementById('spreadsheet-grid'); if(!grid) return; grid.innerHTML = ''; grid.insertAdjacentHTML('beforeend', `<div class="cell cell-header"></div>`); COLUMN_LABELS.forEach(l=> grid.insertAdjacentHTML('beforeend', `<div class="cell cell-header">${l}</div>`)); for(let r=1;r<=ROWS;r++){ grid.insertAdjacentHTML('beforeend', `<div class="cell cell-row-header">${r}</div>`); for(let c=0;c<COLS;c++){ const id = colToLetter(c) + r; cells[id] = cells[id] || { value:'', result:'', color:'bg-white' }; grid.insertAdjacentHTML('beforeend', `<div class="cell data-cell text-right text-gray-800 bg-white" data-cell-id="${id}"></div>`); } } attachCellListeners(); activateCell('A1'); }

function exportToCSV(){ const rows = []; rows.push([''].concat(COLUMN_LABELS).join(',')); for(let r=1;r<=ROWS;r++){ const cols=[r.toString()]; for(let c=0;c<COLS;c++){ const id = COLUMN_LABELS[c]+r; let v = (getCellData(id).value || '').toString(); v = v.replace(/"/g,'""'); if(v.includes(',')||v.includes('\n')||v.includes('"')) v = '"'+v+'"'; cols.push(v); } rows.push(cols.join(',')); } const blob = new Blob([rows.join('\n')], { type: 'text/csv' }); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${(currentFileName||'untitled')}.csv`; document.body.appendChild(a); a.click(); a.remove(); showMessage('Exported CSV','info'); }

// Local persistence helpers (used by sheet.html)
function _localLoadAll(){ try{ const s = localStorage.getItem('sheet_files'); return s ? JSON.parse(s) : {}; }catch(e){return{}} }
function _localSaveAll(m){ try{ localStorage.setItem('sheet_files', JSON.stringify(m)); }catch(e){console.warn(e);} }
function persistLocalFile(id,name,cellsObj){ const all = _localLoadAll(); all[id]={name,updated:new Date().toISOString(),cells:cellsObj}; _localSaveAll(all); }
function removeLocalFile(id){ const all = _localLoadAll(); if(all[id]){ delete all[id]; _localSaveAll(all); } }
function listLocalFiles(){ const all=_localLoadAll(); return Object.keys(all).map(id=>({ id, name: all[id].name, updated: all[id].updated })); }

function saveFile(){ let id = currentFileId; let name = currentFileName; if(!id){ const n = prompt('Enter file name:'); if(!n) return; name = n; id = Math.random().toString(36).slice(2,12); } const data={}; for(const k in cells) if(cells[k].value !== '' || cells[k].color !== 'bg-white') data[k]=cells[k]; persistLocalFile(id,name,data); currentFileId = id; currentFileName = name; fileList = listLocalFiles(); renderDashboard(); showMessage('Saved locally','success'); }

function loadSpreadsheet_local(id){ const all = _localLoadAll(); const doc = all[id]; if(!doc){ showMessage('File not found','error'); return; } for(const k in cells){ const s = doc.cells[k]; if(s){ cells[k].value = s.value || ''; cells[k].result = s.result || ''; cells[k].color = s.color || 'bg-white'; } else { cells[k].value=''; cells[k].result=''; cells[k].color='bg-white'; } } recalculateAll(); for(const k in cells){ const el = document.querySelector(`.data-cell[data-cell-id="${k}"]`); if(el instanceof HTMLElement){ el.classList.remove(...COLOR_PALETTE); el.classList.add(cells[k].color); } } currentFileId = id; currentFileName = doc.name || 'Untitled'; const disp = document.getElementById('current-file-name-display'); if(disp) disp.textContent = currentFileName; showSpreadsheet(); showMessage('Loaded local file','success'); }

function clearAllCells(){ for(let r=1;r<=ROWS;r++){ for(let c=0;c<COLS;c++){ const id = COLUMN_LABELS[c]+r; cells[id] = { value:'', result:'', color:'bg-white' }; const el = document.querySelector(`.data-cell[data-cell-id="${id}"]`); if(el instanceof HTMLElement){ el.classList.remove(...COLOR_PALETTE); el.classList.add('bg-white'); el.textContent=''; } } } recalculateAll(); const fin=document.getElementById('formula-input'); if(fin instanceof HTMLInputElement) fin.value=''; }

function deleteLocalFile(id){ const ok = confirm(`Delete "${id}"?`); if(!ok) return; removeLocalFile(id); fileList = listLocalFiles(); renderDashboard(); if(currentFileId===id){ currentFileId=null; currentFileName='Untitled'; clearAllCells(); showDashboard(); } showMessage('Deleted','success'); }

// Add view helpers used by templates
function showDashboard(){
  const sv = document.getElementById('spreadsheet-view');
  const dv = document.getElementById('dashboard-view');
  if(sv) sv.classList.add('hidden-view');
  if(dv) dv.classList.remove('hidden-view');
}
function showSpreadsheet(){
  const sv = document.getElementById('spreadsheet-view');
  const dv = document.getElementById('dashboard-view');
  if(dv) dv.classList.add('hidden-view');
  if(sv) sv.classList.remove('hidden-view');
}
function updateFileDisplay(id, name){
  currentFileId = id;
  currentFileName = name || 'Untitled';
  const el = document.getElementById('current-file-name-display'); if(el) el.textContent = currentFileName;
}
function createNewSpreadsheet(){
  currentFileId = null;
  currentFileName = 'Untitled';
  updateFileDisplay(null, 'Untitled');
  clearAllCells();
  showSpreadsheet();
  showMessage("New blank spreadsheet created. Click 'Save File' to name it.", 'info');
}

// Fix renderDashboard sort to use Date.parse for numeric subtraction
function renderDashboard(){ const list = document.getElementById('file-list'); if(!list) return; list.innerHTML=''; if(!fileList || fileList.length===0){ list.innerHTML = `<div class="p-6 text-center text-gray-500">You haven't saved any spreadsheets yet.</div>`; return; } fileList.sort((a,b)=> Date.parse(String(b.updated)) - Date.parse(String(a.updated))); fileList.forEach(f=>{ const d = document.createElement('div'); d.className='flex items-center justify-between p-4 border-b border-gray-100 hover:bg-gray-50 transition duration-100'; d.innerHTML = `<div class="flex-1 min-w-0 pr-4"><p class="text-lg font-medium text-gray-900 truncate">${f.name}</p><p class="text-sm text-gray-500">Last updated: ${new Date(f.updated).toLocaleString()}</p></div>`; const right = document.createElement('div'); right.className='flex space-x-2'; const load = document.createElement('button'); load.className='btn btn-primary text-sm'; load.textContent='Load'; load.onclick = ()=> loadSpreadsheet_local(f.id); const del = document.createElement('button'); del.className='btn btn-secondary text-sm'; del.textContent='Delete'; del.onclick = ()=> deleteLocalFile(f.id); right.appendChild(load); right.appendChild(del); d.appendChild(right); list.appendChild(d); }); }

// Expose new view helpers
window.showDashboard = showDashboard;
window.showSpreadsheet = showSpreadsheet;
window.createNewSpreadsheet = createNewSpreadsheet;
window.updateFileDisplay = updateFileDisplay;
window.renderDashboard = renderDashboard; // overwrite previous export with the fixed one

// expose some globals used by templates
window.createGrid = createGrid;
window.recalculateAll = recalculateAll;
window.handleFormulaInput = handleFormulaInput;
window.activateCell = activateCell;
window.startCellEdit = startCellEdit;
window.finishCellEdit = finishCellEdit;
window.cancelCellEdit = cancelCellEdit;
window.saveFile = saveFile;
window.exportToCSV = exportToCSV;
window.loadSpreadsheet_local = loadSpreadsheet_local;
window.clearAllCells = clearAllCells;
window.renderDashboard = renderDashboard;
window.listLocalFiles = listLocalFiles;
window.deleteLocalFile = deleteLocalFile;

console.log('spreadsheet.js loaded');
