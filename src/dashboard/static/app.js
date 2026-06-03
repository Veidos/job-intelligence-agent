/* ── Globals ── */
let OFFERS = [];
let ALL_OFFERS = [];
let APP_DATA = [];
let sortCol = 'match_score';
let sortAsc = false;
const charts = {};

const $ = id => document.getElementById(id);

/* ── Nav ── */
document.querySelectorAll('.nav-link').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    el.classList.add('active');
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    $(`section-${el.dataset.section}`).classList.add('active');
    if (el.dataset.section === 'aplicaciones') loadApplications();
    if (el.dataset.section === 'empresas') loadCompanies();
    if (el.dataset.section === 'monitor') {
      loadStats(); renderCharts(); loadRuns();
      fetch('/api/applications').then(r => r.json()).then(apps => renderAppFunnel(apps));
    }
  });
});

/* ── Helpers ── */
function cls(score) {
  if (score == null) return '';
  return score >= 55 ? 'high' : score >= 35 ? 'mid' : 'low';
}

function pct(v) {
  return v != null ? (v * 100).toFixed(0) : '\u2014';
}

function _parseDate(d) {
  if (!d) return null;
  const s = d.replace(' ', 'T');
  return new Date(s.endsWith('Z') ? s : s + 'Z');
}

const MONTHS = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];

function dateFmt(d) {
  const dt = _parseDate(d);
  if (!dt) return '';
  return `${dt.getDate()} ${MONTHS[dt.getMonth()]}`;
}

function fullDate(d) {
  const dt = _parseDate(d);
  if (!dt) return '';
  return `${dt.getDate()} ${MONTHS[dt.getMonth()]} ${dt.getFullYear()}`;
}

function workModeLabel(w) {
  const map = {'Solo teletrabajo':'Remoto','Híbrido':'Híbrido','Presencial':'Presencial'};
  return map[w] || w || '\u2014';
}

function tag(text, clsName) {
  if (!text) return '';
  return `<span class="tag tag-${clsName}">${text}</span>`;
}

function recTag(r) {
  const map = { 'Aplicar': 'green', 'Con expectativas bajas': 'yellow', 'No aplicar': 'red', 'Prioritario': 'blue' };
  return tag(r, map[r] || 'gray');
}

function signalTag(s) {
  const map = { yes: 'green', maybe: 'yellow', no: 'red' };
  return s ? tag(s, map[s] || 'gray') : '';
}

function relTag(r) {
  const map = { core: 'green', adjacent: 'blue', stretch: 'yellow', temporal: 'gray' };
  return r ? tag(r, map[r] || 'gray') : '';
}

function blockTag(b) {
  if (!b || b === 'null') return tag('Sin bloqueo', 'green');
  return tag(b, 'red');
}

function workModeValue(w) {
  if (!w) return 'unknown';
  if (w === 'Solo teletrabajo') return 'Remoto';
  return w;
}

/* ── Offers table ── */
function loadOffers(filters) {
  let url = '/api/offers';
  const params = new URLSearchParams();
  if (filters) {
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
  }
  const qs = params.toString();
  if (qs) url += '?' + qs;
  return fetch(url).then(r => r.json()).then(data => {
    OFFERS = data;
    const isFullLoad = !filters || Object.keys(filters).length === 0;
    if (isFullLoad) { ALL_OFFERS = data; renderWeeklySparkline(ALL_OFFERS); }
    recalcOffers();
  });
}

function recalcOffers() {
  const filtered = getFilteredData();
  renderTable(filtered);
  $('offerCount').textContent = `${filtered.length} de ${OFFERS.length}`;
}

function getFilteredData() {
  const minScore = parseInt($('filterScore').value) || 0;
  const fRec = $('filterRec').value;
  const fRel = $('filterRel').value;
  const showBlocked = $('filterBlocked').checked;
  const search = ($('filterSearch').value || '').toLowerCase();

  const wmRemote = $('filterRemote').checked;
  const wmHybrid = $('filterHybrid').checked;
  const wmOnsite = $('filterOnsite').checked;
  const allowedModes = [];
  if (wmRemote) allowedModes.push('Solo teletrabajo');
  if (wmHybrid) allowedModes.push('Híbrido');
  if (wmOnsite) allowedModes.push('Presencial');

  let filtered = OFFERS.filter(d => {
    if ((d.match_score || 0) < minScore) return false;
    if (fRec && d.recommendation !== fRec) return false;
    if (fRel && d.relevance_flag !== fRel) return false;
    if (!showBlocked && d.apply_block && d.apply_block !== 'null') return false;
    if (allowedModes.length && !allowedModes.includes(d.work_mode)) return false;
    if (search && !(d.title.toLowerCase().includes(search) || d.company_name.toLowerCase().includes(search))) return false;
    return true;
  });

  filtered.sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (sortCol === 'title' || sortCol === 'company_name' || sortCol === 'work_mode' || sortCol === 'salary_display') {
      va = (va || '').toLowerCase();
      vb = (vb || '').toLowerCase();
      return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    if (sortCol === 'recommendation') {
      const order = { 'No aplicar': 0, 'Con expectativas bajas': 1, 'Aplicar': 2, 'Prioritario': 3 };
      va = order[va] || 0;
      vb = order[vb] || 0;
      return sortAsc ? va - vb : vb - va;
    }
    if (sortCol === 'llm_apply_signal') {
      const order = { no: 0, maybe: 1, yes: 2 };
      va = order[va] || 0;
      vb = order[vb] || 0;
      return sortAsc ? va - vb : vb - va;
    }
    if (sortCol === 'published_at') {
      va = _parseDate(va)?.getTime() ?? 0;
      vb = _parseDate(vb)?.getTime() ?? 0;
      return sortAsc ? va - vb : vb - va;
    }
    if (sortCol === 'apply_block') {
      va = (va == null || va === 'null' || va === 'None') ? 0 : 1;
      vb = (vb == null || vb === 'null' || vb === 'None') ? 0 : 1;
      return sortAsc ? va - vb : vb - va;
    }
    va = va == null ? -1 : va;
    vb = vb == null ? -1 : vb;
    return sortAsc ? va - vb : vb - va;
  });

  return filtered;
}

function sortTable(col) {
  if (sortCol === col) sortAsc = !sortAsc;
  else { sortCol = col; sortAsc = col === 'match_score'; } // default desc for score
  document.querySelectorAll('th.sortable').forEach(th => {
    th.classList.toggle('sorted', th.dataset.col === col);
    const arrow = th.querySelector('.arrow');
    if (arrow) arrow.textContent = th.dataset.col === col ? (sortAsc ? '\u25B2' : '\u25BC') : '';
  });
  recalcOffers();
}

function renderTable(data) {
  const tbody = $('offersTbody');
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">No se encontraron ofertas con los filtros actuales</td></tr>';
    return;
  }
  tbody.innerHTML = data.map(d => {
    const s = d.match_score || 0;
    return `<tr onclick="openModal(${d.id})">
      <td class="num"><span class="cell-score ${cls(s)}">${s}</span></td>
      <td>${d.title || ''}</td>
      <td>${d.company_name || ''}</td>
      <td>${workModeLabel(d.work_mode)}</td>
      <td class="num nowrap">${dateFmt(d.published_at)}</td>
      <td class="num nowrap">${d.salary_display || '\u2014'}</td>
      <td>${recTag(d.recommendation)}</td>
      <td>${signalTag(d.llm_apply_signal)}</td>
      <td>${blockTag(d.apply_block)}</td>
    </tr>`;
  }).join('');
}

/* ── Sort click ── */
document.querySelectorAll('#section-ofertas th.sortable').forEach(th => {
  th.addEventListener('click', () => sortTable(th.dataset.col));
});

/* ── Filter events ── */
['filterScore', 'filterRec', 'filterRel', 'filterBlocked', 'filterSearch',
 'filterRemote', 'filterHybrid', 'filterOnsite'].forEach(id => {
  const el = $(id);
  if (!el) return;
  el.addEventListener('input', recalcOffers);
  el.addEventListener('change', recalcOffers);
});

/* ── Modal ── */
function openModal(id) {
  let d = OFFERS.find(x => x.id === id);
  if (!d) {
    const app = APP_DATA.find(x => x.offer_id === id);
    d = { id, title: app ? app.offer_title : '', company_name: app ? app.company_name : '' };
  }

  const backdrop = $('backdrop');
  const modal = $('modal');

  backdrop.classList.add('open');
  modal.classList.add('open');

  $('modalTitle').innerHTML = `
    <div class="modal-title-text">${d.title}</div>
    <div class="modal-title-company">${d.company_name}</div>
  `;
    $('modalBody').innerHTML = '<div style="text-align:center;padding:20px;color:var(--text2)">Cargando...</div>';
  // Footer con botón inmediato — no depende del fetch
  $('modalFooter').innerHTML = `
    <button class="btn-primary" id="btnSaveApp" data-offer-id="${id}">
      \uD83D\uDCBE A\u00f1adir a aplicaciones
    </button>`;

  fetch(`/api/offers/${id}`).then(r => r.json()).then(data => {
    const o = data.offer;
    const app = data.application;
    // If d is a fallback (from APP_DATA, no salary_display), merge raw SQL row
    // and parse JSON string fields that come as strings from /api/offers/<id>
    if (!d.salary_display && o) {
      Object.assign(d, o);
      ['strengths','hr_concerns','red_flags','interview_prep'].forEach(f => {
        if (typeof d[f] === 'string') {
          try { d[f] = JSON.parse(d[f]); } catch (_) { d[f] = []; }
        }
      });
    }
    const fb = data.feedback || [];
    let sd = {};
    try {
      const parsed = JSON.parse(o.scoring_detail || '{}');
      sd = (parsed && typeof parsed === 'object') ? parsed : {};
    } catch (_) { sd = {}; }
    const rawSkills = sd.skill_detail || {};
    const skillCats = Array.isArray(rawSkills)
      ? [{label: 'Skills', items: rawSkills}]
      : Object.entries(rawSkills).map(([cat, items]) => ({
          label: cat === 'core' ? 'Core' : cat === 'secondary' ? 'Secundarias' : cat,
          items: items || []
        }));
    const totalSkills = skillCats.reduce((sum, c) => sum + c.items.length, 0);

    $('modalBody').innerHTML = `
      <div class="modal-info-grid">
        <div class="modal-info-item">
          <span class="label">Salario</span>
          <span class="value">${d.salary_display || '\u2014'}</span>
        </div>
        <div class="modal-info-item">
          <span class="label">Ubicaci\u00f3n</span>
          <span class="value">${d.city || '\u2014'}</span>
        </div>
        <div class="modal-info-item">
          <span class="label">Modalidad</span>
          <span class="value">${workModeLabel(d.work_mode)}</span>
        </div>
        <div class="modal-info-item">
          <span class="label">Publicado</span>
          <span class="value">${fullDate(d.published_at)}</span>
        </div>
        <div class="modal-info-item">
          <span class="label">Empresa</span>
          <span class="value">${d.company_name}${o.company_sector ? ' \u00b7 ' + o.company_sector : ''}</span>
        </div>
        <div class="modal-info-item">
          <span class="label">Rol</span>
          <span class="value">${d.role_normalized || '\u2014'}</span>
        </div>
      </div>

      <div class="modal-section">
        <div class="verdict-row">
          <div class="verdict-item">
            <span class="label">Recomendaci\u00f3n</span>
            ${recTag(d.recommendation)}
          </div>
          <div class="verdict-item">
            <span class="label">Se\u00f1al</span>
            ${signalTag(d.llm_apply_signal)}
          </div>
          <div class="verdict-item">
            <span class="label">Bloqueo</span>
            ${blockTag(d.apply_block)}
          </div>
          <div class="verdict-item">
            <span class="label">Score</span>
            <span class="cell-score ${cls(d.match_score)}">${d.match_score}</span>
          </div>
        </div>
      </div>

      ${o.url ? `
        <div class="modal-section">
          <a href="${o.url}" target="_blank" rel="noopener" class="btn-external">Ver en InfoJobs \u2192</a>
        </div>
      ` : ''}

      ${o.description_clean ? `
        <details class="modal-section">
          <summary>Descripci\u00f3n de la oferta</summary>
          <p class="description-text">${o.description_clean.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>
        </details>
      ` : ''}

      ${d.gemma_verdict ? `
        <div class="modal-section">
          <h4>Veredicto</h4>
          <p>${d.gemma_verdict}</p>
        </div>
      ` : ''}

      ${d.strengths && d.strengths.length ? `
        <div class="modal-section">
          <h4>Fortalezas</h4>
          <ul>${d.strengths.map(s => `<li>${s}</li>`).join('')}</ul>
        </div>
      ` : ''}

      ${d.hr_concerns && d.hr_concerns.length ? `
        <div class="modal-section">
          <h4>Puntos de atenci\u00f3n</h4>
          <ul>${d.hr_concerns.map(s => `<li>${s}</li>`).join('')}</ul>
        </div>
      ` : ''}

      ${d.interview_prep && d.interview_prep.length ? `
        <div class="modal-section">
          <h4>Preparaci\u00f3n entrevista</h4>
          <ul>${d.interview_prep.map(s => `<li>${s}</li>`).join('')}</ul>
        </div>
      ` : ''}

      <details class="modal-section">
        <summary>Desglose de puntuaci\u00f3n</summary>
        <div class="scoring-grid">
          <div class="scoring-item"><span>M_core</span><span>${pct(d.M_core)}</span></div>
          <div class="scoring-item"><span>M_sec</span><span>${pct(d.M_sec)}</span></div>
          <div class="scoring-item"><span>F_exp</span><span>${pct(d.F_exp)}</span></div>
          <div class="scoring-item"><span>F_fit</span><span>${pct(d.F_fit)}</span></div>
        </div>
      </details>

      <details class="modal-section">
        <summary>Skills (${totalSkills})</summary>
        ${totalSkills ? `
          <table class="skills-table">
            <thead><tr>
              <th>Skill</th><th>Req.</th><th>Cand.</th><th>Match</th><th>L</th>
            </tr></thead>
            <tbody>
              ${skillCats.map(cat => `
                <tr class="skill-cat"><td colspan="5">${cat.label}</td></tr>
                ${cat.items.map(s => `
                  <tr>
                    <td>${s.skill || s.name || ''}</td>
                    <td>${s.level_required || '\u2014'}</td>
                    <td>${s.candidate_level || '\u2014'}</td>
                    <td>${s.present ? '\u2705' : '\u274C'}</td>
                    <td>${s.L != null ? s.L.toFixed(2) : '\u2014'}</td>
                  </tr>
                `).join('')}
              `).join('')}
            </tbody>
          </table>
        ` : '<p class="empty-small">Sin datos de skills</p>'}
      </details>

      <div class="modal-section">
        <h4>Feedback</h4>
        <div class="feedback-form">
          <textarea id="feedbackText" placeholder="Escribe tu opini\u00f3n sobre esta oferta..."></textarea>
          <button onclick="saveFeedback(${id})">Enviar</button>
        </div>
        ${fb.length ? `
          <div class="feedback-list">
            ${fb.map(f => `
              <div class="feedback-item">
                <span class="date">${fullDate(f.created_at)}</span>${f.raw_text}
              </div>
            `).join('')}
          </div>
        ` : '<p class="empty-small">Sin feedback</p>'}
      </div>
    `;

    // Actualizar estado del botón si ya está guardada
    if (app) {
      const btn = $('btnSaveApp');
      if (btn) {
        btn.outerHTML = `
          <span class="footer-status">\u2713 En aplicaciones</span>
          <button class="btn-ghost" onclick="goToApplications()">Ver en Aplicaciones \u2192</button>`;
      }
    }
  }).catch(() => {
    $('modalBody').innerHTML = '<p style="text-align:center;padding:20px;color:var(--red)">Error al cargar detalle</p>';
    // El botón sigue visible — el usuario puede intentar guardar igual
  });
}

function closeModal() {
  $('backdrop').classList.remove('open');
  $('modal').classList.remove('open');
}

function saveApplication(offerId) {
  const btn = $('btnSaveApp');
  if (btn) {
    btn.textContent = 'Guardando...';
    btn.disabled = true;
  }
  fetch('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ offer_id: offerId, status: 'applied' }),
  }).then(r => {
    if (!r.ok) throw new Error('Error del servidor');
    return r.json();
  }).then(() => {
    $('modalFooter').innerHTML = `
      <span class="footer-status">\u2713 En aplicaciones</span>
      <button class="btn-ghost" onclick="goToApplications()">Ver en Aplicaciones \u2192</button>
    `;
    loadStats();
  }).catch(err => {
    console.error('Error al guardar aplicaci\u00f3n:', err);
    if (btn) {
      btn.textContent = '\uD83D\uDCBE A\u00f1adir a aplicaciones';
      btn.disabled = false;
    }
  });
}

function saveFeedback(offerId) {
  const text = $('feedbackText').value.trim();
  if (!text) return;
  fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ offer_id: offerId, raw_text: text }),
  }).then(r => r.json()).then(() => {
    $('feedbackText').value = '';
    loadStats();
  });
}

function goToApplications() {
  closeModal();
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelector('[data-section="aplicaciones"]').classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  $('section-aplicaciones').classList.add('active');
  loadApplications();
}

/* ── Applications ── */
function loadApplications() {
  fetch('/api/applications').then(r => r.json()).then(data => {
    APP_DATA = data;
    $('appCount').textContent = data.length;
    const container = $('appList');
    if (!data.length) {
      container.innerHTML = '<div class="empty">A\u00fan no has guardado ninguna aplicaci\u00f3n. Explora ofertas y usa "A\u00f1adir a aplicaciones" desde el detalle.</div>';
      return;
    }
    container.innerHTML = data.map(a => renderAppCard(a)).join('');
  });
}

function renderAppCard(a) {
  const statuses = ['applied', 'interviewing', 'offer', 'rejected', 'archived'];
  const statusLabels = { applied: 'Applied', interviewing: 'Interviewing', offer: 'Offer', rejected: 'Rejected', archived: 'Archived' };
  const statusOptions = statuses.map(s =>
    `<option value="${s}" ${a.status === s ? 'selected' : ''}>${statusLabels[s]}</option>`
  ).join('');

  return `
    <div class="app-card" data-app-id="${a.id}">
      <div class="app-card-header" onclick="toggleAppDetails(${a.id})">
        <select id="appStatus${a.id}" onclick="event.stopPropagation()" onchange="updateAppStatus(${a.id}, this.value)">
          ${statusOptions}
        </select>
        <div class="app-card-info">
          <strong>${a.offer_title || 'Oferta'}</strong>
          <small>${a.company_name || ''}</small>
        </div>
        ${a.match_score != null ? `<span class="cell-score ${cls(a.match_score)}">${a.match_score}</span>` : ''}
        <span class="app-card-date">${fullDate(a.applied_at)}</span>
      </div>
      <div class="app-card-details" id="appDetails${a.id}">
        <textarea placeholder="Notas sobre el proceso (entrevistas, seguimiento...)" id="appNotes${a.id}">${a.notes || ''}</textarea>
        <div class="detail-row">
          <input type="text" placeholder="Contacto — Ej: Maria G. — RRHH" id="appContact${a.id}" value="${a.contact_name || ''}">
          <input type="date" id="appNextAction${a.id}" value="${a.next_action_date || ''}" title="Pr\u00f3ximo follow-up o fecha de entrevista">
          <button class="btn-ghost" onclick="openModal(${a.offer_id});event.stopPropagation()" title="Ver detalle de la oferta">Ver oferta</button>
          <button class="btn-primary" onclick="saveAppDetails(${a.id}, this);event.stopPropagation()" style="white-space:nowrap">Guardar</button>
          <button class="btn-delete" onclick="deleteApplication(${a.id});event.stopPropagation()">Eliminar</button>
        </div>
      </div>
    </div>
  `;
}

function toggleAppDetails(id) {
  const el = $(`appDetails${id}`);
  if (el) el.classList.toggle('open');
}

function updateAppStatus(id, status) {
  const a = APP_DATA.find(x => x.id === id);
  if (!a) return;
  fetch('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ offer_id: a.offer_id, status }),
  }).then(() => loadStats());
}

function saveAppDetails(id, btn) {
  const a = APP_DATA.find(x => x.id === id);
  if (!a || !btn) return;

  btn.textContent = 'Guardando...';
  btn.disabled = true;

  const statusEl = $(`appStatus${id}`);
  const status = statusEl ? statusEl.value : a.status;
  const notes = $(`appNotes${id}`).value;
  const contact = $(`appContact${id}`).value;
  const nextAction = $(`appNextAction${id}`).value;

  fetch('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ offer_id: a.offer_id, status, notes, contact_name: contact, next_action_date: nextAction }),
  }).then(r => {
    if (!r.ok) throw new Error('Error del servidor');
    return r.json();
  }).then(() => {
    btn.textContent = '\u2713 Guardado';
    btn.style.color = 'var(--green)';
    setTimeout(() => {
      btn.textContent = 'Guardar';
      btn.style.color = '';
      btn.disabled = false;
    }, 2000);
    loadStats();
  }).catch(err => {
    console.error('Error al guardar detalles:', err);
    btn.textContent = 'Error';
    btn.style.color = 'var(--red)';
    setTimeout(() => {
      btn.textContent = 'Guardar';
      btn.style.color = '';
      btn.disabled = false;
    }, 2000);
  });
}

function deleteApplication(id) {
  const a = APP_DATA.find(x => x.id === id);
  if (!a) return;
  if (!confirm('\u00bfEliminar este seguimiento? La oferta no se perder\u00e1.')) return;
  fetch(`/api/applications/${id}`, { method: 'DELETE' }).then(() => {
    loadApplications();
    loadStats();
  });
}

/* ── Companies ── */
function loadCompanies() {
  fetch('/api/companies').then(r => r.json()).then(data => {
    const tbody = $('companiesTbody');
    tbody.innerHTML = data.map(c => {
      const gf = JSON.parse(c.green_flags || '[]');
      const rf = JSON.parse(c.red_flags || '[]');
      const avg = c.avg_score;
      const gfHtml = gf.slice(0, 2).map(g => tag(g, 'green')).join(' ') + (gf.length > 2 ? ` +${gf.length - 2}` : '');
      const rfHtml = rf.slice(0, 2).map(r => tag(r, 'red')).join(' ') + (rf.length > 2 ? ` +${rf.length - 2}` : '');
      return `<tr onclick="filterByCompany(${c.id})">
        <td><strong>${c.name}</strong></td>
        <td>${c.sector || '\u2014'}</td>
        <td>${c.size_range || '\u2014'}</td>
        <td class="num">${c.offer_count}</td>
        <td class="num">${avg != null ? avg : '\u2014'}</td>
        <td>${gfHtml} ${rfHtml}</td>
      </tr>`;
    }).join('');
    renderCompanyCharts(data);
  });
}

function renderCompanyCharts(data) {
  const top5 = [...data].sort((a, b) => (b.offer_count || 0) - (a.offer_count || 0)).slice(0, 5);
  const sectors = {};
  data.forEach(c => {
    const s = c.sector || 'Otros';
    sectors[s] = (sectors[s] || 0) + 1;
  });

  destroyChart('chartEmpTop5');
  charts.chartEmpTop5 = new Chart($('chartEmpTop5'), {
    type: 'bar',
    data: {
      labels: top5.map(c => c.name),
      datasets: [{
        label: 'Ofertas',
        data: top5.map(c => c.offer_count || 0),
        backgroundColor: '#6366f1',
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: { left: 10, right: 20, top: 5, bottom: 5 },
      },
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Top 5 empresas por ofertas', color: '#e4e4e7' },
      },
      scales: {
        x: { ticks: { color: '#8a8a95' }, beginAtZero: true },
        y: { ticks: { color: '#8a8a95', font: { size: 11 } } },
      },
    },
  });

  destroyChart('chartEmpSector');
  charts.chartEmpSector = new Chart($('chartEmpSector'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(sectors),
      datasets: [{
        data: Object.values(sectors),
        backgroundColor: ['#6366f1', '#22c55e', '#eab308', '#ef4444', '#3b82f6', '#a855f7', '#ec4899', '#14b8a6'],
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'right', labels: { color: '#e4e4e7', font: { size: 11 } } },
        title: { display: true, text: 'Empresas por sector', color: '#e4e4e7' },
      },
    },
  });
}

function filterByCompany(companyId) {
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelector('[data-section="ofertas"]').classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  $('section-ofertas').classList.add('active');
  fetch(`/api/offers?company_id=${companyId}`).then(r => r.json()).then(data => {
    OFFERS = data;
    recalcOffers();
  });
}

/* ── Stats (Monitor) ── */
function loadStats() {
  return fetch('/api/stats').then(r => r.json()).then(s => {
    $('kpiGrid').innerHTML = `
      <div class="kpi-card"><div class="value blue">${s.total_offers}</div><div class="label">Ofertas</div></div>
      <div class="kpi-card"><div class="value green">${s.evaluated}</div><div class="label">Evaluadas</div></div>
      <div class="kpi-card"><div class="value ${s.pending_eval > 0 ? 'yellow' : 'green'}">${s.pending_eval}</div><div class="label">Pendientes</div></div>
      <div class="kpi-card"><div class="value blue">${s.companies}</div><div class="label">Empresas</div></div>
      <div class="kpi-card"><div class="value ${s.applications > 0 ? 'green' : ''}">${s.applications}</div><div class="label">Aplicaciones</div></div>
      <div class="kpi-card"><div class="value blue">${s.feedbacks}</div><div class="label">Feedbacks</div></div>
      <div class="kpi-card"><div class="value ${s.avg_score >= 40 ? 'green' : s.avg_score >= 30 ? 'yellow' : 'red'}">${s.avg_score || 0}</div><div class="label">Score medio</div></div>
      <div class="kpi-card"><div class="value ${s.max_score >= 55 ? 'green' : 'yellow'}">${s.max_score || 0}</div><div class="label">Score m\u00e1x</div></div>
    `;
  });
}

/* ── Runs ── */
function loadRuns() {
  fetch('/api/runs').then(r => r.json()).then(data => {
    const tbody = $('runsTbody');
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">Sin ejecuciones registradas</td></tr>';
      return;
    }
    tbody.innerHTML = data.map(r => `
      <tr>
        <td><span style="color:var(--text2);font-size:12px">${r.ran_at || ''}</span></td>
        <td class="num">${r.offers_fetched ?? '\u2014'}</td>
        <td class="num">${r.new_offers ?? '\u2014'}</td>
        <td class="num">${r.evaluated ?? '\u2014'}</td>
        <td>${r.errors ? tag(r.errors, 'red') : '\u2014'}</td>
        <td class="num">${r.duration_ms ? (r.duration_ms / 1000).toFixed(1) + 's' : '\u2014'}</td>
        <td>${r.status === 'ok' ? tag('ok', 'green') : tag(r.status, 'red')}</td>
      </tr>
    `).join('');
  });
}

/* ── Charts ── */
function renderCharts() {
  if (!ALL_OFFERS.length) return;
  const data = ALL_OFFERS;

  // Doughnut: recommendation distribution
  const recCounts = { 'Aplicar': 0, 'Con expectativas bajas': 0, 'No aplicar': 0 };
  data.forEach(d => { if (recCounts[d.recommendation] != null) recCounts[d.recommendation]++; });
  destroyChart('chartRecDist');
  charts.chartRecDist = new Chart($('chartRecDist'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(recCounts),
      datasets: [{ data: Object.values(recCounts), backgroundColor: ['#22c55e', '#eab308', '#ef4444'] }],
    },
    options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { color: '#e4e4e7' } } } },
  });

  // Histogram: score distribution
  const bins = [0, 10, 20, 30, 35, 40, 45, 50, 55, 60, 70, 80];
  const hist = bins.map(() => 0);
  data.forEach(d => {
    const s = d.match_score || 0;
    for (let i = bins.length - 1; i >= 0; i--) {
      if (s >= bins[i]) { hist[i]++; break; }
    }
  });
  const histLabels = bins.map((b, i) => i < bins.length - 1 ? `${b}\u2013${bins[i + 1]}` : `${b}+`);
  destroyChart('chartScoreDist');
  charts.chartScoreDist = new Chart($('chartScoreDist'), {
    type: 'bar',
    data: { labels: histLabels, datasets: [{ label: 'Ofertas', data: hist, backgroundColor: '#6366f1' }] },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, title: { display: true, text: 'Distribuci\u00f3n de Scores', color: '#e4e4e7' } },
      scales: { x: { ticks: { color: '#8a8a95' } }, y: { ticks: { color: '#8a8a95' }, beginAtZero: true } },
    },
  });

  // Recommendation by relevance
  const recByRel = {};
  data.forEach(d => {
    const rel = d.relevance_flag || 'other';
    const rec = d.recommendation || 'No aplicar';
    if (!recByRel[rel]) recByRel[rel] = { 'Aplicar': 0, 'Con expectativas bajas': 0, 'No aplicar': 0 };
    if (recByRel[rel][rec] != null) recByRel[rel][rec]++;
  });
  const relLabels = Object.keys(recByRel);
  const rLabels = ['Aplicar', 'Con expectativas bajas', 'No aplicar'];
  destroyChart('chartRecByRel');
  charts.chartRecByRel = new Chart($('chartRecByRel'), {
    type: 'bar',
    data: {
      labels: relLabels,
      datasets: rLabels.map((r, i) => ({
        label: r,
        data: relLabels.map(l => recByRel[l][r] || 0),
        backgroundColor: ['#22c55e', '#eab308', '#ef4444'][i],
      })),
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: 'Recomendaci\u00f3n \u00d7 Relevance', color: '#e4e4e7' } },
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { color: '#8a8a95' } } },
    },
  });

  // Signal by recommendation
  const sigByRec = {};
  data.forEach(d => {
    const rec = d.recommendation || 'No aplicar';
    const sig = d.llm_apply_signal || 'no';
    if (!sigByRec[rec]) sigByRec[rec] = { yes: 0, maybe: 0, no: 0 };
    if (sigByRec[rec][sig] != null) sigByRec[rec][sig]++;
  });
  destroyChart('chartSignalByRec');
  charts.chartSignalByRec = new Chart($('chartSignalByRec'), {
    type: 'bar',
    data: {
      labels: Object.keys(sigByRec),
      datasets: [
        { label: 'Yes', data: Object.values(sigByRec).map(v => v.yes || 0), backgroundColor: '#22c55e' },
        { label: 'Maybe', data: Object.values(sigByRec).map(v => v.maybe || 0), backgroundColor: '#eab308' },
        { label: 'No', data: Object.values(sigByRec).map(v => v.no || 0), backgroundColor: '#ef4444' },
      ],
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: 'Se\u00f1al \u00d7 Recomendaci\u00f3n', color: '#e4e4e7' } },
      scales: { x: {}, y: { beginAtZero: true, ticks: { color: '#8a8a95' } } },
    },
  });

  // Nuevos charts T-5h
  renderSkillsCharts(data);
  renderSalaryDist(data);
  renderWeeklyActivity(data);
  renderWeeklySparkline(data);
  renderModelAccuracy(data);

  // Score trend
  const sorted = [...data].filter(d => d.evaluated_at).sort((a, b) => (_parseDate(a.evaluated_at)?.getTime() ?? 0) - (_parseDate(b.evaluated_at)?.getTime() ?? 0));
  const trendLabels = sorted.map(d => dateFmt(d.evaluated_at));
  const trendData = sorted.map(d => d.match_score || 0);
  destroyChart('chartScoreTrend');
  charts.chartScoreTrend = new Chart($('chartScoreTrend'), {
    type: 'line',
    data: {
      labels: trendLabels,
      datasets: [{
        label: 'Score', data: trendData, borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,.1)', fill: true, tension: .3, pointRadius: 3,
      }],
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: 'Score por fecha de evaluaci\u00f3n', color: '#e4e4e7' } },
      scales: { x: { ticks: { color: '#8a8a95', maxRotation: 45 } }, y: { ticks: { color: '#8a8a95' }, beginAtZero: true } },
    },
  });
}

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

/* ── Delegated save button ── */
document.getElementById('modalFooter').addEventListener('click', e => {
  const btn = e.target.closest('#btnSaveApp');
  if (btn) {
    const offerId = parseInt(btn.dataset.offerId);
    if (!isNaN(offerId)) saveApplication(offerId);
  }
});

/* ── Skills helpers ── */
function computeSkillsData(offers) {
  const demand = {}, gap = {};
  offers.forEach(o => {
    const sd = o.skill_detail || {};
    const cats = Array.isArray(sd) ? sd : Object.values(sd).flat();
    cats.forEach(s => {
      if (!s) return;
      const name = s.skill || s.name;
      if (!name) return;
      demand[name] = (demand[name] || 0) + 1;
      if (!s.present) gap[name] = (gap[name] || 0) + 1;
    });
  });
  const sort = obj => Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, 12);
  return { demand: sort(demand), gap: sort(gap) };
}

function renderSkillsCharts(offers) {
  const { demand, gap } = computeSkillsData(offers);

  destroyChart('chartSkillsDemand');
  if (demand.length) {
    charts.chartSkillsDemand = new Chart($('chartSkillsDemand'), {
      type: 'bar',
      data: {
        labels: demand.map(x => x[0]),
        datasets: [{ label: 'Frecuencia', data: demand.map(x => x[1]), backgroundColor: '#6366f1' }],
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        layout: { padding: { right: 16 } },
        plugins: {
          legend: { display: false },
          title: { display: true, text: 'Skills m\u00e1s demandados en ofertas evaluadas', color: '#e4e4e7' },
        },
        scales: { x: { ticks: { color: '#8a8a95' }, beginAtZero: true }, y: { ticks: { color: '#8a8a95', font: { size: 11 } } } },
      },
    });
  }

  destroyChart('chartSkillsGap');
  if (gap.length) {
    charts.chartSkillsGap = new Chart($('chartSkillsGap'), {
      type: 'bar',
      data: {
        labels: gap.map(x => x[0]),
        datasets: [{ label: 'Ausente en', data: gap.map(x => x[1]), backgroundColor: '#ef4444' }],
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        layout: { padding: { right: 16 } },
        plugins: {
          legend: { display: false },
          title: { display: true, text: 'Skills requeridos que no tienes (en ofertas evaluadas)', color: '#e4e4e7' },
        },
        scales: { x: { ticks: { color: '#8a8a95' }, beginAtZero: true }, y: { ticks: { color: '#8a8a95', font: { size: 11 } } } },
      },
    });
  }
}

/* ── Salary distribution ── */
function renderSalaryDist(offers) {
  const bins = [0, 15000, 25000, 35000, 45000, 60000];
  const labels = ['<15k', '15\u201325k', '25\u201335k', '35\u201345k', '45\u201360k', '60k+'];
  const counts = new Array(labels.length).fill(0);
  offers.forEach(o => {
    const v = o.salary_min != null ? o.salary_min : o.salary_max;
    if (v == null) return;
    let i = bins.findIndex((b, idx) => idx === bins.length - 1 || v < bins[idx + 1]);
    if (i === -1) i = labels.length - 1;
    counts[i]++;
  });

  destroyChart('chartSalaryDist');
  charts.chartSalaryDist = new Chart($('chartSalaryDist'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Ofertas', data: counts, backgroundColor: '#22c55e' }] },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Distribuci\u00f3n salarial (salary_min)', color: '#e4e4e7' },
      },
      scales: { x: { ticks: { color: '#8a8a95' } }, y: { ticks: { color: '#8a8a95' }, beginAtZero: true } },
    },
  });
}

/* ── Weekly helper ── */
function getISOWeek(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 3 - (d.getDay() + 6) % 7);
  const week1 = new Date(d.getFullYear(), 0, 4);
  return `${d.getFullYear()}-W${String(1 + Math.round(((d - week1) / 86400000 - 3 + (week1.getDay() + 6) % 7) / 7)).padStart(2, '0')}`;
}

function renderWeeklyActivity(offers) {
  const weeks = {};
  offers.forEach(o => {
    const dt = _parseDate(o.published_at);
    if (!dt) return;
    const w = getISOWeek(dt);
    weeks[w] = (weeks[w] || 0) + 1;
  });
  const sorted = Object.entries(weeks).sort((a, b) => a[0].localeCompare(b[0]));

  destroyChart('chartWeeklyActivity');
  if (!sorted.length) return;
  charts.chartWeeklyActivity = new Chart($('chartWeeklyActivity'), {
    type: 'bar',
    data: {
      labels: sorted.map(x => x[0]),
      datasets: [{ label: 'Ofertas publicadas', data: sorted.map(x => x[1]), backgroundColor: '#3b82f6' }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Ofertas publicadas por semana', color: '#e4e4e7' },
      },
      scales: { x: { ticks: { color: '#8a8a95', maxRotation: 45 } }, y: { ticks: { color: '#8a8a95' }, beginAtZero: true } },
    },
  });
}

/* ── Sparkline en header de Ofertas ── */
function renderWeeklySparkline(offers) {
  const weeks = {};
  offers.forEach(o => {
    const dt = _parseDate(o.published_at);
    if (!dt) return;
    const w = getISOWeek(dt);
    weeks[w] = (weeks[w] || 0) + 1;
  });
  const sorted = Object.entries(weeks).sort((a, b) => a[0].localeCompare(b[0])).slice(-8);
  const canvas = $('chartWeeklySparkline');
  if (!canvas || !sorted.length) return;

  destroyChart('chartWeeklySparkline');
  charts.chartWeeklySparkline = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: sorted.map(x => x[0].replace(/^\d{4}-W/, '')),
      datasets: [{ data: sorted.map(x => x[1]), backgroundColor: 'rgba(99,102,241,0.5)', borderRadius: 2 }],
    },
    options: {
      responsive: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
      animation: false,
    },
  });
}

/* ── App funnel ── */
function renderAppFunnel(apps) {
  const STATUS_LABELS = { applied: 'Applied', interviewing: 'Interviewing', offer: 'Offer', rejected: 'Rejected', archived: 'Archived' };
  const counts = {};
  apps.forEach(a => { counts[a.status] = (counts[a.status] || 0) + 1; });
  const order = ['applied', 'interviewing', 'offer', 'rejected', 'archived'];
  const labels = order.filter(s => counts[s]).map(s => STATUS_LABELS[s]);
  const data = order.filter(s => counts[s]).map(s => counts[s]);
  const colors = { applied: '#6366f1', interviewing: '#3b82f6', offer: '#22c55e', rejected: '#ef4444', archived: '#8a8a95' };
  const bgColors = order.filter(s => counts[s]).map(s => colors[s] || '#8a8a95');

  destroyChart('chartAppFunnel');
  if (!data.length) return;
  charts.chartAppFunnel = new Chart($('chartAppFunnel'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Aplicaciones', data, backgroundColor: bgColors }] },
    options: {
      indexAxis: 'y', responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Estado de aplicaciones', color: '#e4e4e7' },
      },
      scales: { x: { ticks: { color: '#8a8a95' }, beginAtZero: true }, y: { ticks: { color: '#8a8a95' } } },
    },
  });
}

/* ── Model accuracy grouped bar ── */
function renderModelAccuracy(offers) {
  const recs = ['Aplicar', 'Con expectativas bajas', 'No aplicar'];
  const signals = ['yes', 'maybe', 'no'];
  const matrix = {};
  recs.forEach(r => { matrix[r] = { yes: 0, maybe: 0, no: 0 }; });
  offers.forEach(o => {
    const r = o.recommendation;
    const s = o.llm_apply_signal || 'no';
    if (matrix[r] && signals.includes(s)) matrix[r][s]++;
  });

  destroyChart('chartModelAccuracy');
  charts.chartModelAccuracy = new Chart($('chartModelAccuracy'), {
    type: 'bar',
    data: {
      labels: recs,
      datasets: [
        { label: 'Signal: yes',   data: recs.map(r => matrix[r].yes),   backgroundColor: '#22c55e' },
        { label: 'Signal: maybe', data: recs.map(r => matrix[r].maybe), backgroundColor: '#eab308' },
        { label: 'Signal: no',    data: recs.map(r => matrix[r].no),    backgroundColor: '#ef4444' },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        title: { display: true, text: 'Recomendaci\u00f3n \u00d7 Se\u00f1al LLM (coherencia modelo)', color: '#e4e4e7' },
        legend: { labels: { color: '#e4e4e7' } },
      },
      scales: { x: { ticks: { color: '#8a8a95' } }, y: { beginAtZero: true, ticks: { color: '#8a8a95' } } },
    },
  });
}

/* ── Init ── */
Promise.all([loadStats(), loadOffers()]).then(() => {
  renderCharts();
});
