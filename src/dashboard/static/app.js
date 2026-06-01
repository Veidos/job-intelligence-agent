/* ── Globals ── */
let DATA = [];
let APP_DATA = [];
let FEEDBACK_DATA = [];
let charts = {};

/* ── Nav ── */
document.querySelectorAll('.nav-link').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    el.classList.add('active');
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById('section-' + el.dataset.section).classList.add('active');
    if (el.dataset.section === 'estadisticos') renderCharts();
    if (el.dataset.section === 'aplicaciones') loadApplications();
    if (el.dataset.section === 'empresas') loadCompanies();
    if (el.dataset.section === 'runs') loadRuns();
  });
});

/* ── Helpers ── */
function cls(score) {
  if (score == null) return '';
  return score >= 55 ? 'high' : score >= 35 ? 'mid' : 'low';
}
function pct(v) { return v != null ? (v * 100).toFixed(0) : '\u2014'; }
function dateFmt(d) {
  if (!d) return '';
  const dt = new Date(d + 'Z');
  const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  return `${dt.getDate()} ${months[dt.getMonth()]} ${dt.getFullYear()}`;
}
function monthFmt(d) {
  if (!d) return '';
  const dt = new Date(d + 'Z');
  return dt.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' });
}
function workModeTag(w) {
  if (!w) return '\u2014';
  const icons = {'Solo teletrabajo':'\uD83C\uDFE0 Remoto','H\u00EDbrido':'\uD83D\uDD04 H\u00EDbrido','Presencial':'\uD83C\uDFE2 Presencial'};
  return icons[w] || w;
}
function blockTag(b) {
  if (!b || b === 'null') return '<span class="tag green">Sin bloqueo</span>';
  return `<span class="tag red">${b}</span>`;
}
function recTag(r) {
  const map = {'Aplicar':'green','Con expectativas bajas':'yellow','No aplicar':'red','Prioritario':'blue'};
  return `<span class="tag ${map[r] || 'gray'}">${r || ''}</span>`;
}
function signalTag(s) {
  const map = {yes:'green',maybe:'yellow',no:'red'};
  return s ? `<span class="tag ${map[s] || 'gray'}">${s}</span>` : '';
}
function relTag(r) {
  const map = {core:'green',adjacent:'blue',stretch:'yellow',temporal:'gray'};
  return r ? `<span class="tag ${map[r] || 'gray'}">${r}</span>` : '';
}
function appStatusTag(s) {
  const map = {applied:'blue',interviewing:'yellow',rejected:'red',offer:'green',accepted:'green',archived:'gray'};
  return `<span class="tag ${map[s] || 'gray'}">${s}</span>`;
}

/* ── Modal ── */
function openModal(id) {
  const d = DATA.find(x => x.id === id);
  if (!d) return;
  document.getElementById('modalTitle').textContent = `${d.title} @ ${d.company_name}`;
  const body = document.getElementById('modalBody');
  const pb = {M_core:d.M_core,M_sec:d.M_sec,F_exp:d.F_exp,F_fit:d.F_fit};

  // Fetch full detail with feedback + application
  fetch(`/api/offers/${id}`).then(r => r.json()).then(data => {
    const o = data.offer;
    const app = data.application;
    const fb = data.feedback || [];

    let skillsHtml = '';
    const sd = JSON.parse(o.scoring_detail || '{}');
    const sk = sd.skill_detail || [];
    if (sk.length) {
      const rows = sk.map(s => `
        <tr><td>${s.name}</td><td>${s.level_required || '\u2014'}</td>
        <td>${s.candidate_level || '\u2014'}</td>
        <td>${s.present ? '\u2705' : '\u274C'}</td>
        <td>${s.L != null ? s.L.toFixed(2) : '\u2014'}</td></tr>
      `).join('');
      skillsHtml = `<table style="width:100%;font-size:13px;border-collapse:collapse;"><thead><tr style="color:var(--text2)">
        <th style="text-align:left">Skill</th><th style="text-align:left">Req.</th><th style="text-align:left">Cand.</th><th>Match</th><th>L</th>
        </tr></thead><tbody>${rows}</tbody></table>`;
    } else {
      skillsHtml = '<p style="color:var(--text2)">Sin skills estructuradas</p>';
    }

    const feedbackHtml = fb.length
      ? fb.map(f => `<div class="feedback-item"><span class="date">${dateFmt(f.created_at)}</span> ${f.raw_text}</div>`).join('')
      : '<p style="color:var(--text2);font-size:12px;">Sin feedback</p>';

    body.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
        <div><strong>Score:</strong> <span style="color:var(--${cls(d.match_score) === 'high' ? 'green' : cls(d.match_score) === 'mid' ? 'yellow' : 'red'})">${d.match_score}</span></div>
        <div><strong>Recomendación:</strong> ${recTag(d.recommendation)}</div>
        <div><strong>M_core:</strong> ${pct(d.M_core)}</div>
        <div><strong>M_sec:</strong> ${pct(d.M_sec)}</div>
        <div><strong>F_exp:</strong> ${pct(d.F_exp)}</div>
        <div><strong>F_fit:</strong> ${pct(d.F_fit)}</div>
        <div><strong>Modalidad:</strong> ${workModeTag(d.work_mode)}</div>
        <div><strong>Ubicación:</strong> ${d.city}</div>
        <div><strong>Señal:</strong> ${signalTag(d.llm_apply_signal)}</div>
        <div><strong>Bloqueo:</strong> ${blockTag(d.apply_block)}${d.apply_block_reason ? ': ' + d.apply_block_reason : ''}</div>
      </div>
      <div class="modal-section"><h4>Skills</h4>${skillsHtml}</div>
      <div class="modal-section"><h4>Veredicto HR</h4><p>${d.gemma_verdict || 'No disponible'}</p></div>
      ${d.strengths && d.strengths.length ? '<div class="modal-section"><h4>Fortalezas</h4><ul>' + d.strengths.map(s => '<li>' + s + '</li>').join('') + '</ul></div>' : ''}
      ${d.hr_concerns && d.hr_concerns.length ? '<div class="modal-section"><h4>HR Concerns</h4><ul>' + d.hr_concerns.map(s => '<li>' + s + '</li>').join('') + '</ul></div>' : ''}
      ${d.interview_prep && d.interview_prep.length ? '<div class="modal-section"><h4>Interview Prep</h4><ul>' + d.interview_prep.map(s => '<li>' + s + '</li>').join('') + '</ul></div>' : ''}

      <div class="modal-section"><h4>Seguimiento</h4>
        <div class="app-section">
          <select id="appStatus">
            <option value="applied" ${app && app.status === 'applied' ? 'selected' : ''}>Applied</option>
            <option value="interviewing" ${app && app.status === 'interviewing' ? 'selected' : ''}>Interviewing</option>
            <option value="rejected" ${app && app.status === 'rejected' ? 'selected' : ''}>Rejected</option>
            <option value="offer" ${app && app.status === 'offer' ? 'selected' : ''}>Offer</option>
            <option value="accepted" ${app && app.status === 'accepted' ? 'selected' : ''}>Accepted</option>
            <option value="archived" ${app && app.status === 'archived' ? 'selected' : ''}>Archived</option>
          </select>
          <input type="text" id="appContact" placeholder="Contacto" value="${app ? (app.contact_name || '') : ''}">
          <input type="date" id="appNextAction" value="${app ? (app.next_action_date || '') : ''}">
          <button onclick="saveApplication(${id})">Guardar</button>
          ${app ? `<button style="background:var(--red);color:#fff;" onclick="deleteApplication(${app.id})">Eliminar</button>` : ''}
          ${app ? `<span class="app-status">${appStatusTag(app.status)}</span>` : ''}
        </div>
      </div>

      <div class="modal-section"><h4>Feedback</h4>
        <div class="feedback-form">
          <textarea id="feedbackText" placeholder="Escribe tu feedback sobre esta oferta..."></textarea>
          <button onclick="saveFeedback(${id})">Enviar</button>
        </div>
        <div class="feedback-list">${feedbackHtml}</div>
      </div>
    `;
  });

  document.getElementById('backdrop').classList.add('open');
  document.getElementById('modal').classList.add('open');
}
function closeModal() {
  document.getElementById('backdrop').classList.remove('open');
  document.getElementById('modal').classList.remove('open');
}

/* ── Feedback ── */
function saveFeedback(offerId) {
  const text = document.getElementById('feedbackText').value.trim();
  if (!text) return;
  fetch('/api/feedback', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({offer_id: offerId, raw_text: text})
  }).then(r => r.json()).then(() => {
    document.getElementById('feedbackText').value = '';
    loadStats();
  });
}

/* ── Applications ── */
function saveApplication(offerId) {
  const status = document.getElementById('appStatus').value;
  const contact_name = document.getElementById('appContact').value;
  const next_action_date = document.getElementById('appNextAction').value;
  fetch('/api/applications', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({offer_id: offerId, status, contact_name, next_action_date})
  }).then(r => r.json()).then(() => {
    loadStats();
    if (document.getElementById('section-aplicaciones').classList.contains('active')) loadApplications();
  });
}
function deleteApplication(appId) {
  fetch(`/api/applications/${appId}`, {method: 'DELETE'}).then(() => {
    loadStats();
    if (document.getElementById('section-aplicaciones').classList.contains('active')) loadApplications();
    closeModal();
  });
}

/* ── Sort ── */
let sortCol = 'match_score';
let sortAsc = false;
function sortTable(col) {
  if (sortCol === col) sortAsc = !sortAsc;
  else { sortCol = col; sortAsc = false; }
  document.querySelectorAll('th.sortable').forEach(th => {
    th.classList.toggle('sorted', th.dataset.col === col);
    const arrow = th.querySelector('.arrow');
    if (arrow) arrow.textContent = th.dataset.col === col ? (sortAsc ? '\u25B2' : '\u25BC') : '';
  });
  renderTable();
}

/* ── Load data ── */
function loadStats() {
  fetch('/api/stats').then(r => r.json()).then(s => {
    document.getElementById('kpiGrid').innerHTML = `
      <div class="kpi-card"><div class="value blue">${s.total_offers}</div><div class="label">Ofertas totales</div></div>
      <div class="kpi-card"><div class="value ${s.evaluated > 0 ? 'green' : ''}">${s.evaluated}</div><div class="label">Evaluadas</div></div>
      <div class="kpi-card"><div class="value ${s.pending_eval > 0 ? 'yellow' : 'green'}">${s.pending_eval}</div><div class="label">Pendientes eval.</div></div>
      <div class="kpi-card"><div class="value blue">${s.companies}</div><div class="label">Empresas</div></div>
      <div class="kpi-card"><div class="value ${s.applications > 0 ? 'green' : ''}">${s.applications}</div><div class="label">Aplicaciones</div></div>
      <div class="kpi-card"><div class="value blue">${s.feedbacks}</div><div class="label">Feedbacks</div></div>
      <div class="kpi-card"><div class="value ${s.avg_score >= 40 ? 'green' : s.avg_score >= 30 ? 'yellow' : 'red'}">${s.avg_score || 0}</div><div class="label">Score medio</div></div>
      <div class="kpi-card"><div class="value ${s.max_score >= 55 ? 'green' : 'yellow'}">${s.max_score || 0}</div><div class="label">Score máximo</div></div>
    `;
    document.getElementById('offerCount').textContent = `${s.evaluated} evaluadas`;
  });
}

function loadOffers(filters) {
  let url = '/api/offers';
  if (filters) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k,v]) => { if (v) params.set(k, v); });
    const qs = params.toString();
    if (qs) url += '?' + qs;
  }
  fetch(url).then(r => r.json()).then(data => {
    DATA = data;
    renderTable();
    renderCharts();
  });
}

function renderTable() {
  const filtered = getFilteredData();
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = filtered.map(d => {
    const s = d.match_score || 0;
    return `<tr data-id="${d.id}" onclick="openModal(${d.id})" style="cursor:pointer">
      <td class="num"><span class="cell-score ${cls(s)}">${s}</span></td>
      <td class="num">${pct(d.M_core)}</td>
      <td class="num">${pct(d.M_sec)}</td>
      <td class="num">${pct(d.F_exp)}</td>
      <td class="num">${pct(d.F_fit)}</td>
      <td>${d.title || ''}</td>
      <td>${d.company_name || ''}</td>
      <td>${d.role_normalized || ''}</td>
      <td>${relTag(d.relevance_flag)}</td>
      <td><span class="cell-date">${dateFmt(d.published_at)}</span></td>
      <td>${d.salary_display || '\u2014'}</td>
      <td>${d.city || ''}</td>
      <td>${workModeTag(d.work_mode)}</td>
      <td>${signalTag(d.llm_apply_signal)}</td>
      <td>${recTag(d.recommendation)}</td>
      <td>${blockTag(d.apply_block)}</td>
    </tr>`;
  }).join('');
}

function getFilteredData() {
  const minScore = parseInt(document.getElementById('filterScore').value) || 0;
  const fRec = document.getElementById('filterRec').value;
  const fSig = document.getElementById('filterSignal').value;
  const fRel = document.getElementById('filterRel').value;
  const includeBlocked = document.getElementById('filterBlocked').checked;
  const search = (document.getElementById('filterSearch').value || '').toLowerCase();

  let filtered = DATA.filter(d => {
    if ((d.match_score || 0) < minScore) return false;
    if (fRec && d.recommendation !== fRec) return false;
    if (fSig && d.llm_apply_signal !== fSig) return false;
    if (fRel && d.relevance_flag !== fRel) return false;
    if (!includeBlocked && d.apply_block && d.apply_block !== 'null') return false;
    if (search && !(d.title.toLowerCase().includes(search) || d.company_name.toLowerCase().includes(search))) return false;
    return true;
  });

  // sort
  filtered.sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (sortCol === 'title' || sortCol === 'company_name' || sortCol === 'role_normalized' || sortCol === 'location' || sortCol === 'work_mode' || sortCol === 'salary_display') {
      va = (va || '').toLowerCase();
      vb = (vb || '').toLowerCase();
      return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    if (sortCol === 'published_at') {
      va = va ? new Date(va + 'Z').getTime() : 0;
      vb = vb ? new Date(vb + 'Z').getTime() : 0;
      return sortAsc ? va - vb : vb - va;
    }
    if (sortCol === 'recommendation') {
      const order = {'No aplicar':0, 'Con expectativas bajas':1, 'Aplicar':2, 'Prioritario':3};
      va = order[va] || 0;
      vb = order[vb] || 0;
      return sortAsc ? va - vb : vb - va;
    }
    if (sortCol === 'relevance_flag') {
      const order = {'temporal':0, 'stretch':1, 'adjacent':2, 'core':3};
      va = order[va] || 0;
      vb = order[vb] || 0;
      return sortAsc ? va - vb : vb - va;
    }
    if (sortCol === 'llm_apply_signal') {
      const order = {no:0, maybe:1, yes:2};
      va = order[va] || 0;
      vb = order[vb] || 0;
      return sortAsc ? va - vb : vb - va;
    }
    va = va == null ? -1 : va;
    vb = vb == null ? -1 : vb;
    return sortAsc ? va - vb : vb - va;
  });

  return filtered;
}

// ── Filter events ──
['filterScore','filterRec','filterSignal','filterRel','filterBlocked','filterSearch'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('input', renderTable);
  el.addEventListener('change', renderTable);
});

// ── Sort click ──
document.querySelectorAll('th.sortable').forEach(th => {
  th.addEventListener('click', () => sortTable(th.dataset.col));
});

/* ── Companies ── */
function loadCompanies() {
  fetch('/api/companies').then(r => r.json()).then(data => {
    const tbody = document.getElementById('companiesTbody');
    tbody.innerHTML = data.map(c => {
      const gf = JSON.parse(c.green_flags || '[]');
      const rf = JSON.parse(c.red_flags || '[]');
      const avg = c.avg_score;
      return `<tr onclick="filterByCompany(${c.id})" style="cursor:pointer">
        <td><strong>${c.name}</strong></td>
        <td>${c.sector || '\u2014'}</td>
        <td>${c.size_range || '\u2014'}</td>
        <td class="num">${c.offer_count}</td>
        <td class="num">${avg != null ? avg : '\u2014'}</td>
        <td>${gf.slice(0,2).map(g => `<span class="tag green">${g}</span>`).join(' ')}${gf.length > 2 ? ` +${gf.length - 2}` : ''}</td>
        <td>${rf.slice(0,2).map(r => `<span class="tag red">${r}</span>`).join(' ')}${rf.length > 2 ? ` +${rf.length - 2}` : ''}</td>
      </tr>`;
    }).join('');
  });
}
function filterByCompany(companyId) {
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelector('[data-section="evaluaciones"]').classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById('section-evaluaciones').classList.add('active');
  fetch('/api/offers?company_id=' + companyId).then(r => r.json()).then(data => {
    DATA = data;
    renderTable();
  });
}

/* ── Applications Timeline ── */
function loadApplications() {
  fetch('/api/applications').then(r => r.json()).then(data => {
    APP_DATA = data;
    const timeline = document.getElementById('timeline');
    if (!data.length) {
      timeline.innerHTML = '<div class="empty">Aún no has marcado ninguna aplicación</div>';
      return;
    }
    // Group by week
    const weeks = {};
    data.forEach(a => {
      const d = new Date(a.applied_at + 'Z');
      const weekStart = new Date(d);
      weekStart.setDate(d.getDate() - d.getDay());
      const key = weekStart.toISOString().slice(0, 10);
      if (!weeks[key]) weeks[key] = [];
      weeks[key].push(a);
    });
    timeline.innerHTML = Object.entries(weeks).sort((a,b) => b[0].localeCompare(a[0])).map(([wk, apps]) => {
      const d = new Date(wk + 'T12:00:00Z');
      const label = d.toLocaleDateString('es-ES', {weekday:'long', day:'numeric', month:'long', year:'numeric'});
      const cards = apps.map(a => `
        <div class="timeline-card">
          <div class="date">${monthFmt(a.applied_at)}</div>
          <div class="info">
            <strong>${a.offer_title || 'Oferta'}</strong>
            <small>${a.company_name || ''}</small>
          </div>
          <div class="meta">
            ${appStatusTag(a.status)}
            ${a.match_score != null ? `<span class="cell-score ${cls(a.match_score)}">${a.match_score}</span>` : ''}
            ${a.next_action_date ? `<span class="tag blue">${a.next_action_date}</span>` : ''}
            ${a.contact_name ? `<span style="color:var(--text2);font-size:12px;">${a.contact_name}</span>` : ''}
          </div>
          <div class="actions">
            ${a.offer_id ? `<button onclick="openModal(${a.offer_id})" title="Ver oferta">🔍</button>` : ''}
            <button onclick="deleteApplication(${a.id})" title="Eliminar">🗑</button>
          </div>
        </div>
      `).join('');
      return `<div class="timeline-week"><h3>${label}</h3>${cards}</div>`;
    }).join('');
  });
}

/* ── Charts ── */
function renderCharts() {
  if (!DATA.length) return;

  // 1. Score distribution (histogram)
  const bins = [0,10,20,30,35,40,45,50,55,60,70,80];
  const hist = bins.map(() => 0);
  DATA.forEach(d => {
    const s = d.match_score || 0;
    for (let i = bins.length - 1; i >= 0; i--) {
      if (s >= bins[i]) { hist[i]++; break; }
    }
  });
  const histLabels = bins.map((b,i) => i < bins.length - 1 ? `${b}–${bins[i+1]}` : `${b}+`);
  destroyChart('chartScoreDist');
  charts.scoreDist = new Chart(document.getElementById('chartScoreDist'), {
    type: 'bar',
    data: { labels: histLabels, datasets: [{ label: 'Ofertas', data: hist, backgroundColor: '#6366f1' }] },
    options: { responsive: true, plugins: { legend: { display: false }, title: { display: true, text: 'Distribución de Scores', color:'#e4e4e7' } },
      scales: { x: { ticks: { color:'#8a8a95' } }, y: { ticks: { color:'#8a8a95' }, beginAtZero: true } }
    }
  });

  // 2. Recommendation by relevance
  const recByRel = {};
  DATA.forEach(d => {
    const rel = d.relevance_flag || 'other';
    const rec = d.recommendation || 'No aplicar';
    if (!recByRel[rel]) recByRel[rel] = { 'Aplicar':0, 'Con expectativas bajas':0, 'No aplicar':0 };
    if (recByRel[rel][rec] != null) recByRel[rel][rec]++;
  });
  const relLabels = Object.keys(recByRel);
  const recLabels = ['Aplicar', 'Con expectativas bajas', 'No aplicar'];
  destroyChart('chartRecByRel');
  charts.recByRel = new Chart(document.getElementById('chartRecByRel'), {
    type: 'bar',
    data: {
      labels: relLabels,
      datasets: recLabels.map((r, i) => ({
        label: r,
        data: relLabels.map(l => recByRel[l][r] || 0),
        backgroundColor: ['#22c55e','#eab308','#ef4444'][i],
      }))
    },
    options: { responsive: true, plugins: { title: { display: true, text: 'Recomendación × Relevance', color:'#e4e4e7' } },
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { color:'#8a8a95' } } }
    }
  });

  // 3. Signal by recommendation
  const sigByRec = {};
  DATA.forEach(d => {
    const rec = d.recommendation || 'No aplicar';
    const sig = d.llm_apply_signal || 'no';
    if (!sigByRec[rec]) sigByRec[rec] = { yes:0, maybe:0, no:0 };
    if (sigByRec[rec][sig] != null) sigByRec[rec][sig]++;
  });
  destroyChart('chartSignalByRec');
  charts.signalByRec = new Chart(document.getElementById('chartSignalByRec'), {
    type: 'bar',
    data: {
      labels: Object.keys(sigByRec),
      datasets: [
        { label: 'Yes', data: Object.values(sigByRec).map(v => v.yes || 0), backgroundColor: '#22c55e' },
        { label: 'Maybe', data: Object.values(sigByRec).map(v => v.maybe || 0), backgroundColor: '#eab308' },
        { label: 'No', data: Object.values(sigByRec).map(v => v.no || 0), backgroundColor: '#ef4444' },
      ]
    },
    options: { responsive: true, plugins: { title: { display: true, text: 'Señal × Recomendación', color:'#e4e4e7' } },
      scales: { x: {}, y: { beginAtZero: true, ticks: { color:'#8a8a95' } } }
    }
  });

  // 4. Score trend (by evaluated_at)
  const sorted = [...DATA].filter(d => d.evaluated_at).sort((a,b) => new Date(a.evaluated_at+'Z') - new Date(b.evaluated_at+'Z'));
  const trendLabels = sorted.map(d => dateFmt(d.evaluated_at));
  const trendData = sorted.map(d => d.match_score || 0);
  destroyChart('chartScoreTrend');
  charts.scoreTrend = new Chart(document.getElementById('chartScoreTrend'), {
    type: 'line',
    data: {
      labels: trendLabels,
      datasets: [{
        label: 'Score', data: trendData, borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,.1)', fill: true, tension: .3,
        pointRadius: 3,
      }]
    },
    options: { responsive: true, plugins: { title: { display: true, text: 'Score por fecha de evaluación', color:'#e4e4e7' } },
      scales: { x: { ticks: { color:'#8a8a95', maxRotation: 45 } }, y: { ticks: { color:'#8a8a95' }, beginAtZero: true } }
    }
  });
}

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

/* ── Pipeline Runs ── */
function loadRuns() {
  fetch('/api/runs').then(r => r.json()).then(data => {
    const tbody = document.getElementById('runsTbody');
    tbody.innerHTML = data.map(r => `
      <tr>
        <td><span class="cell-date">${r.ran_at || ''}</span></td>
        <td class="num">${r.offers_fetched ?? '\u2014'}</td>
        <td class="num">${r.new_offers ?? '\u2014'}</td>
        <td class="num">${r.evaluated ?? '\u2014'}</td>
        <td>${r.errors ? `<span class="tag red">${r.errors}</span>` : '\u2014'}</td>
        <td class="num">${r.duration_ms ? (r.duration_ms/1000).toFixed(1) + 's' : '\u2014'}</td>
        <td>${r.status === 'ok' ? '<span class="tag green">ok</span>' : `<span class="tag red">${r.status}</span>`}</td>
      </tr>
    `).join('');
    // Sort click for runs table
    document.querySelectorAll('#runsTable th.sortable').forEach(th => {
      th.addEventListener('click', () => sortRuns(th.dataset.col));
    });
  });
}
let runsSortCol = 'ran_at';
let runsSortAsc = false;
function sortRuns(col) {
  if (runsSortCol === col) runsSortAsc = !runsSortAsc;
  else { runsSortCol = col; runsSortAsc = false; }
  loadRuns();
}

/* ── Init ── */
Promise.all([
  loadStats(),
  loadOffers(),
]).then(() => {
  // Pipeline doughnut chart
  destroyChart('chartRecDist');
  const counts = {'Aplicar':0,'Con expectativas bajas':0,'No aplicar':0};
  DATA.forEach(d => { if (counts[d.recommendation] != null) counts[d.recommendation]++; });
  charts.recDist = new Chart(document.getElementById('chartRecDist'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(counts),
      datasets: [{ data: Object.values(counts), backgroundColor: ['#22c55e','#eab308','#ef4444'] }]
    },
    options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { color:'#e4e4e7' } } } }
  });
});
