/* ── Globals ── */
let OFFERS = [];
let ALL_OFFERS = [];
let APP_DATA = [];
let sortCol = 'match_score';
let sortAsc = false;
let FILTER_COMPANY = null;
let compSortCol = 'offer_count';
let compSortAsc = false;
const charts = {};

const $ = id => document.getElementById(id);

/* ── Nav ── */
function switchTab(name) {
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelector(`[data-section="${name}"]`).classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  $(`section-${name}`).classList.add('active');
}

document.querySelectorAll('.nav-link').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    switchTab(el.dataset.section);
    if (el.dataset.section === 'aplicaciones') loadApplications();
    if (el.dataset.section === 'empresas') loadCompanies();
    if (el.dataset.section === 'pipeline') { loadPipelineRuns(); loadRuns(); }
    if (el.dataset.section === 'monitor') {
      loadStats(); renderCharts();
      fetch('/api/applications').then(r => r.json()).then(apps => {
        renderAppFunnel(apps);
        renderAppFollowUp(apps);
      });
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

const WORK_MODE_CANONICAL = {
  'Solo teletrabajo': 'Remoto',
  'Teletrabajo':      'Remoto',
  'Híbrido':          'Híbrido',
  'Presencial':       'Presencial',
};

function workModeLabel(w) {
  return WORK_MODE_CANONICAL[w] || w || '\u2014';
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
  return WORK_MODE_CANONICAL[w] || '';
}

/* ── Age & follow-up helpers ── */
function daysSince(dateStr) {
  const dt = _parseDate(dateStr);
  if (!dt) return null;
  return Math.floor((Date.now() - dt.getTime()) / 86400000);
}

function getOfferAgeBadge(days) {
  if (days == null) return '';
  if (days <= 7) return `<span class="age-dot dot-green" title="Publicado hace ${days}d"></span>`;
  if (days <= 14) return `<span class="age-dot dot-yellow" title="Publicado hace ${days}d"></span>`;
  if (days <= 21) return `<span class="age-dot dot-orange" title="Publicado hace ${days}d"></span>`;
  if (days <= 30) return `<span class="age-dot dot-red" title="Publicado hace ${days}d"></span>`;
  return `<span class="age-dot dot-gray" title="Publicado hace ${days}d"></span>`;
}

function getFollowUpStatus(days) {
  if (days == null) return null;
  if (days <= 7) return { label: 'Esperando', cls: 'fu-waiting' };
  if (days <= 14) return { label: 'Follow-up', cls: 'fu-soon' };
  if (days <= 21) return { label: 'Insistir', cls: 'fu-urgent' };
  return { label: 'Descartar', cls: 'fu-discard' };
}

function isExpired(publishedAt) {
  const d = daysSince(publishedAt);
  return d != null && d > 30;
}

function renderFollowUpBadge(a) {
  const days = daysSince(a.applied_at);
  const fu = getFollowUpStatus(days);
  if (!fu) return '';
  let html = `<span class="fu-badge ${fu.cls}">${fu.label}</span>`;
  if (a.next_action_date && daysSince(a.next_action_date) > 0) {
    html += `<span class="fu-badge fu-overdue">\uD83D\uDD14 Acci\u00f3n vencida</span>`;
  }
  return html;
}

/* ── Offers table ── */
function loadOffers(filters) {
  let url = '/api/offers';
  const params = new URLSearchParams();
  if (filters) {
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
  }
  if (FILTER_COMPANY && !params.has('company_id')) {
    params.set('company_id', FILTER_COMPANY.id);
  }
  const qs = params.toString();
  if (qs) url += '?' + qs;
  const isFullLoad = !filters || Object.keys(filters || {}).length === 0;
  return fetch(url).then(r => r.json()).then(data => {
    OFFERS = data;
    if (isFullLoad) { ALL_OFFERS = data; }
    recalcOffers();
    if (isFullLoad) {
      try { renderWeeklySparkline(ALL_OFFERS); } catch (e) { console.warn('Sparkline no disponible:', e); }
    }
  }).catch(err => {
    console.error('Error cargando ofertas:', err);
    const tbody = $('offersTbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="empty" style="color:var(--red)">Error al cargar datos</td></tr>';
  });
}

function recalcOffers() {
  const filtered = getFilteredData();
  renderTable(filtered);
  $('offerCount').textContent = `${filtered.length} de ${OFFERS.length}`;
  const info = $('filterCompanyInfo');
  if (FILTER_COMPANY) {
    info.style.display = '';
    info.innerHTML = `Filtrando por: <strong>${FILTER_COMPANY.name}</strong> <button class="btn-ghost" onclick="clearCompanyFilter()" style="min-height:auto;min-width:auto;padding:2px 6px;font-size:13px;">✕</button>`;
  } else {
    info.style.display = 'none';
  }
}

function getFilteredData() {
  const minScore = parseInt($('filterScore').value) || 0;
  const fRec = $('filterRec').value;
  const fRel = $('filterRel').value;
  const showBlocked = !$('filterBlocked').checked;
  const hideApplied = $('filterHideApplied').checked;
  const hideExpired = $('filterHideExpired').checked;
  const appliedIds = new Set(APP_DATA.map(a => a.offer_id));
  const search = ($('filterSearch').value || '').toLowerCase();

  const wmRemote = $('filterRemote').checked;
  const wmHybrid = $('filterHybrid').checked;
  const wmOnsite = $('filterOnsite').checked;
  const allowedModes = [];
  if (wmRemote) allowedModes.push('Remoto');
  if (wmHybrid) allowedModes.push('Híbrido');
  if (wmOnsite) allowedModes.push('Presencial');

  let filtered = OFFERS.filter(d => {
    if ((d.match_score || 0) < minScore) return false;
    if (fRec && d.recommendation !== fRec) return false;
    if (fRel && d.relevance_flag !== fRel) return false;
    if (!showBlocked && d.apply_block && d.apply_block !== 'null') return false;
    if (hideApplied && appliedIds.has(d.id)) return false;
    if (hideExpired && isExpired(d.published_at)) return false;
    if (allowedModes.length && d.work_mode && !allowedModes.includes(workModeValue(d.work_mode))) return false;
    if (search && !(d.title.toLowerCase().includes(search) || d.company_name.toLowerCase().includes(search))) return false;
    return true;
  });

  filtered.sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (sortCol === 'title' || sortCol === 'company_name' || sortCol === 'city' || sortCol === 'work_mode' || sortCol === 'salary_display') {
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
    tbody.innerHTML = '<tr><td colspan="10" class="empty">No se encontraron ofertas con los filtros actuales</td></tr>';
    return;
  }
  tbody.innerHTML = data.map(d => {
    const s = d.match_score || 0;
    return `<tr onclick="openModal(${d.id})">
      <td class="num"><span class="cell-score ${cls(s)}">${s}</span></td>
      <td>${d.title || ''}</td>
      <td>${d.company_name || ''}</td>
      <td>${d.city || '\u2014'}</td>
      <td>${workModeLabel(d.work_mode)}</td>
      <td class="num nowrap">${getOfferAgeBadge(daysSince(d.published_at))}${dateFmt(d.published_at)}</td>
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
document.querySelectorAll('#section-empresas th.sortable').forEach(th => {
  th.addEventListener('click', () => sortCompanies(th.dataset.col));
});

function sortCompanies(col) {
  if (compSortCol === col) compSortAsc = !compSortAsc;
  else { compSortCol = col; compSortAsc = col === 'avg_score'; }
  document.querySelectorAll('#section-empresas th.sortable').forEach(th => {
    th.classList.toggle('sorted', th.dataset.col === col);
    const arrow = th.querySelector('.arrow');
    if (arrow) arrow.textContent = th.dataset.col === col ? (compSortAsc ? '\u25B2' : '\u25BC') : '';
  });
  loadCompanies();
}

/* ── Filter events ── */
['filterScore', 'filterRec', 'filterRel', 'filterBlocked', 'filterSearch',
 'filterRemote', 'filterHybrid', 'filterOnsite', 'filterHideApplied', 'filterHideExpired'].forEach(id => {
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
    APP_DATA.push({ offer_id: offerId, status: 'applied' });
    recalcOffers();
    loadStats();
    recalcOffers();
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
    recalcOffers();
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
        ${renderFollowUpBadge(a)}
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
    recalcOffers();
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
    recalcOffers();
  });
}

/* ── Companies ── */
function loadCompanies() {
  fetch('/api/companies').then(r => r.json()).then(data => {
    data.sort((a, b) => {
      let va = a[compSortCol], vb = b[compSortCol];
      if (typeof va === 'string') va = (va || '').toLowerCase();
      if (typeof vb === 'string') vb = (vb || '').toLowerCase();
      if (va == null) va = -1;
      if (vb == null) vb = -1;
      return compSortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });
    const tbody = $('companiesTbody');
    tbody.innerHTML = data.map(c => {
      const escName = c.name.replace(/'/g, "\\'");
      const gf = JSON.parse(c.green_flags || '[]');
      const rf = JSON.parse(c.red_flags || '[]');
      const avg = c.avg_score;
      const gfHtml = gf.slice(0, 2).map(g => tag(g, 'green')).join(' ') + (gf.length > 2 ? ` +${gf.length - 2}` : '');
      const rfHtml = rf.slice(0, 2).map(r => tag(r, 'red')).join(' ') + (rf.length > 2 ? ` +${rf.length - 2}` : '');
      return `<tr onclick="filterByCompany(${c.id},'${escName}')">
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
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const total = ctx.dataset.data.reduce(function(a, b) { return a + b; }, 0);
              const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : '0.0';
              return ctx.label + ': ' + ctx.parsed + ' (' + pct + '%)';
            },
          },
        },
      },
    },
  });

  const top5Score = [...data].sort((a, b) => (b.avg_score || 0) - (a.avg_score || 0)).slice(0, 5);
  destroyChart('chartEmpTop5Score');
  charts.chartEmpTop5Score = new Chart($('chartEmpTop5Score'), {
    type: 'bar',
    data: {
      labels: top5Score.map(c => c.name),
      datasets: [{
        label: 'Score',
        data: top5Score.map(c => c.avg_score || 0),
        backgroundColor: '#22c55e',
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
        title: { display: true, text: 'Top 5 empresas por score', color: '#e4e4e7' },
      },
      scales: {
        x: { ticks: { color: '#8a8a95' }, beginAtZero: true, max: 100 },
        y: { ticks: { color: '#8a8a95', font: { size: 11 } } },
      },
    },
  });
}

function filterByCompany(id, name) {
  FILTER_COMPANY = { id, name };
  switchTab('ofertas');
  loadOffers();
}

function clearCompanyFilter() {
  FILTER_COMPANY = null;
  loadOffers();
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

/* ── Pipeline execution ── */
let _pipelinePolling = false;
let _pipelineLogOffset = 0;
let _pipelineRunId = null;

function launchPipeline() {
  const btn = $('btnRunPipeline');
  btn.disabled = true;
  btn.style.display = 'none';
  $('btnStopPipeline').style.display = 'inline-block';
  $('btnStopPipeline').disabled = false;
  $('pipelineStatus').textContent = 'Iniciando...';
  $('pipelineLogPanel').style.display = 'block';
  $('pipelineLog').textContent = '';

  fetch('/api/pipeline/run', { method: 'POST' })
    .then(function (r) {
      if (r.status === 409) {
        return r.json().then(function (d) {
          btn.disabled = false;
          btn.textContent = '\u25b6 Lanzar Pipeline';
          $('pipelineStatus').textContent = '\u26a0\ufe0f ' + (d.error || 'Ya en ejecuci\u00f3n');
          return null;
        });
      }
      return r.json();
    })
    .then(function (data) {
      if (!data) return;
      _pipelineRunId = data.run_id;
      _pipelineLogOffset = 0;
      _pipelinePolling = true;
      pollPipelineLog();
    })
    .catch(function () {
      btn.disabled = false;
      btn.textContent = '\u25b6 Lanzar Pipeline';
      $('pipelineStatus').textContent = '\u274c Error al lanzar';
    });
}

function stopPipelinePolling() {
  _pipelinePolling = false;
  $('btnRunPipeline').style.display = 'inline-block';
  $('btnRunPipeline').disabled = false;
  $('btnStopPipeline').style.display = 'none';
  $('pipelineStatus').textContent = '\u2705 Completado';
  loadRuns();
  loadPipelineRuns();
  loadOffers();
}

function stopPipeline() {
  $('btnStopPipeline').disabled = true;
  $('pipelineStatus').textContent = '\u23f3 Deteniendo...';
  fetch('/api/pipeline/stop', { method: 'POST' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.status === 'stopped' || data.status === 'already_finished') {
        _pipelinePolling = true;
        pollPipelineLog();
      }
    })
    .catch(function () {
      $('pipelineStatus').textContent = '\u274c Error al detener';
      $('btnStopPipeline').disabled = false;
    });
}

function checkPipelineStatus() {
  fetch('/api/pipeline/status')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.running) return;
      _pipelineRunId = data.run_id;
      _pipelineLogOffset = data.offset;
      _pipelinePolling = true;
      $('btnRunPipeline').style.display = 'none';
      $('btnStopPipeline').style.display = 'inline-block';
      $('btnStopPipeline').disabled = false;
      $('pipelineLogPanel').style.display = 'block';
      $('pipelineLogPanel').open = true;
      $('pipelineStatus').textContent = '\ud83d\udd04 Reconectado...';
      pollPipelineLog();
    });
}

function pollPipelineLog() {
  if (!_pipelinePolling) return;
  var url = '/api/pipeline/log?offset=' + _pipelineLogOffset;
  if (_pipelineRunId) url += '&run_id=' + _pipelineRunId;

  fetch(url)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.lines && data.lines.length) {
        var el = $('pipelineLog');
        el.textContent += data.lines.join('');
        el.scrollTop = el.scrollHeight;
      }
      _pipelineLogOffset = data.offset;
      if (data.finished) {
        stopPipelinePolling();
      } else {
        $('pipelineStatus').textContent = '\u23f3 Ejecutando...';
        setTimeout(pollPipelineLog, 2000);
      }
    })
    .catch(function () {
      $('pipelineStatus').textContent = '\u274c Error en polling';
      _pipelinePolling = false;
      $('btnRunPipeline').disabled = false;
      $('btnRunPipeline').textContent = '\u25b6 Lanzar Pipeline';
    });
}

/* ── Charts ── */
function renderCharts() {
  if (!ALL_OFFERS.length) return;

  if (typeof Chart === 'undefined') {
    console.warn('Chart.js no disponible — gráficas omitidas');
    document.querySelectorAll('.monitor-section-title').forEach(function (el) {
      var note = document.createElement('p');
      note.style.cssText = 'color:var(--text2);font-size:13px;padding:8px';
      note.textContent = '📊 Gráficas no disponibles (Chart.js no cargó)';
      el.insertAdjacentElement('afterend', note);
    });
    return;
  }

  const data = ALL_OFFERS;

  // Bar: recommendation distribution
  const recCounts = { 'Aplicar': 0, 'Con expectativas bajas': 0, 'No aplicar': 0 };
  data.forEach(d => { if (recCounts[d.recommendation] != null) recCounts[d.recommendation]++; });
  destroyChart('chartRecDist');
  charts.chartRecDist = new Chart($('chartRecDist'), {
    type: 'bar',
    data: {
      labels: Object.keys(recCounts),
      datasets: [{ label: 'Ofertas', data: Object.values(recCounts), backgroundColor: ['#22c55e', '#eab308', '#ef4444'] }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, title: { display: true, text: 'Distribuci\u00f3n por recomendaci\u00f3n', color: '#e4e4e7' } },
      scales: { x: { ticks: { color: '#8a8a95' } }, y: { beginAtZero: true, ticks: { color: '#8a8a95' } } },
    },
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
      plugins: {
        legend: { position: 'top', labels: { color: '#e4e4e7', font: { size: 11 } } },
        title: { display: true, text: 'Recomendaci\u00f3n \u00d7 Relevance', color: '#e4e4e7' },
      },
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { color: '#8a8a95' } } },
    },
  });

  // Nuevos charts T-5h
  renderSkillsCore(data);
  renderSkillsSecondary(data);
  renderSkillsGap(data);
  renderSalaryDist(data);
  renderWeeklyActivity(data);
  renderWeeklySparkline(data);
  renderModelAccuracy(data);
  renderCityModeChart(data);
  renderWorkModeChart(data);

  // Score trend: agregado por d\u00eda
  const byDay = {};
  data.filter(d => d.published_at).forEach(d => {
    const day = d.published_at.slice(0, 10);
    if (!byDay[day]) byDay[day] = [];
    byDay[day].push(d.match_score || 0);
  });
  const days = Object.keys(byDay).sort();
  const trendLabels = days;
  const trendData = days.map(d => {
    const scores = byDay[d];
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  });
  destroyChart('chartScoreTrend');
  charts.chartScoreTrend = new Chart($('chartScoreTrend'), {
    type: 'line',
    data: {
      labels: trendLabels,
      datasets: [{
        label: 'Score promedio', data: trendData, borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,.1)', fill: false, tension: .3, pointRadius: 4,
        pointBackgroundColor: '#6366f1',
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Score promedio por fecha de publicaci\u00f3n', color: '#e4e4e7' },
      },
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
  const core = {}, secondary = {}, gap = {};
  offers.forEach(o => {
    const sd = o.skill_detail || {};
    if (sd.core) {
      sd.core.forEach(s => {
        if (!s) return;
        const name = s.skill || s.name;
        if (!name) return;
        core[name] = (core[name] || 0) + 1;
        if (!s.present) gap[name] = (gap[name] || 0) + 1;
      });
    }
    if (sd.secondary) {
      sd.secondary.forEach(s => {
        if (!s) return;
        const name = s.skill || s.name;
        if (!name) return;
        secondary[name] = (secondary[name] || 0) + 1;
      });
    }
  });
  const sort = obj => Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, 10);
  return { core: sort(core), secondary: sort(secondary), gap: sort(gap) };
}

function renderSkillsCore(offers) {
  const { core } = computeSkillsData(offers);
  destroyChart('chartSkillsCore');
  if (!core.length) return;
  charts.chartSkillsCore = new Chart($('chartSkillsCore'), {
    type: 'bar',
    data: {
      labels: core.map(x => x[0]),
      datasets: [{ label: 'Frecuencia', data: core.map(x => x[1]), backgroundColor: '#6366f1' }],
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 16 } },
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Skills core m\u00e1s demandados', color: '#e4e4e7' },
      },
      scales: { x: { ticks: { color: '#8a8a95' }, beginAtZero: true }, y: { ticks: { color: '#8a8a95', font: { size: 11 } } } },
    },
  });
}

function renderSkillsSecondary(offers) {
  const { secondary } = computeSkillsData(offers);
  destroyChart('chartSkillsSecondary');
  if (!secondary.length) {
    $('chartSkillsSecondary').innerHTML = '<div class="empty-state-skills" style="display:flex;align-items:center;justify-content:center;gap:8px;padding:32px;color:#a1a1aa;font-size:14px;">— Sin datos de skills secundarios en las ofertas analizadas</div>';
    return;
  }
  charts.chartSkillsSecondary = new Chart($('chartSkillsSecondary'), {
    type: 'bar',
    data: {
      labels: secondary.map(x => x[0]),
      datasets: [{ label: 'Frecuencia', data: secondary.map(x => x[1]), backgroundColor: '#a855f7' }],
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 16 } },
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Skills secundarios / soft m\u00e1s frecuentes', color: '#e4e4e7' },
      },
      scales: { x: { ticks: { color: '#8a8a95' }, beginAtZero: true }, y: { ticks: { color: '#8a8a95', font: { size: 11 } } } },
    },
  });
}

function renderSkillsGap(offers) {
  const { gap } = computeSkillsData(offers);
  destroyChart('chartSkillsGap');
  if (!gap.length) {
    $('chartSkillsGap').innerHTML = '<div class="empty-state-skills" style="display:flex;align-items:center;justify-content:center;gap:8px;padding:32px;color:#a1a1aa;font-size:14px;">✓ Tus skills cubren todas las skills core de las ofertas analizadas</div>';
    return;
  }
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
        title: { display: true, text: 'Skills core que te faltan (gap accionable)', color: '#e4e4e7' },
      },
      scales: { x: { ticks: { color: '#8a8a95' }, beginAtZero: true }, y: { ticks: { color: '#8a8a95', font: { size: 11 } } } },
    },
  });
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
  if (typeof Chart === 'undefined') return;
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
      plugins: { legend: { display: false }, tooltip: { enabled: true, callbacks: { title: () => 'Ofertas publicadas' } } },
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

/* ── App follow-up table (Monitor) ── */
function renderAppFollowUp(apps) {
  const container = $('appFollowUpTable');
  const kpis = $('appFollowUpKpis');
  if (!container || !kpis) return;

  if (!apps.length) {
    kpis.innerHTML = '';
    container.innerHTML = '<div class="empty">Sin aplicaciones registradas</div>';
    return;
  }

  const fuSoon = apps.filter(a => { const d = daysSince(a.applied_at); return d != null && d > 7 && d <= 14; }).length;
  const fuUrgent = apps.filter(a => { const d = daysSince(a.applied_at); return d != null && d > 14; }).length;
  const overdue = apps.filter(a => a.next_action_date && daysSince(a.next_action_date) > 0).length;

  kpis.innerHTML = `
    <div class="kpi-mini-card"><span class="kpi-val">${apps.length}</span> Total</div>
    <div class="kpi-mini-card"><span class="kpi-val yellow">${fuSoon}</span> Follow-up</div>
    <div class="kpi-mini-card"><span class="kpi-val orange">${fuUrgent}</span> Urgentes</div>
    <div class="kpi-mini-card"><span class="kpi-val red">${overdue}</span> Vencidas</div>
  `;

  const sorted = [...apps].sort((a, b) => {
    const aDays = daysSince(a.applied_at) || 0;
    const bDays = daysSince(b.applied_at) || 0;
    const aUrgency = aDays > 14 ? 3 : aDays > 7 ? 2 : 1;
    const bUrgency = bDays > 14 ? 3 : bDays > 7 ? 2 : 1;
    if (aUrgency !== bUrgency) return bUrgency - aUrgency;
    const aOver = a.next_action_date && daysSince(a.next_action_date) > 0 ? 1 : 0;
    const bOver = b.next_action_date && daysSince(b.next_action_date) > 0 ? 1 : 0;
    if (aOver !== bOver) return bOver - aOver;
    return bDays - aDays;
  });

  const STATUS_LABELS = { applied: 'Applied', interviewing: 'Interviewing', offer: 'Offer', rejected: 'Rejected', archived: 'Archived' };
  const STATUS_COLORS = { applied: 'tag-blue', interviewing: 'tag-yellow', offer: 'tag-green', rejected: 'tag-red', archived: 'tag-gray' };

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Seguimiento</th>
          <th>Oferta</th>
          <th>Estado</th>
          <th class="num">Apl. hace</th>
          <th>Acci\u00f3n</th>
          <th>Contacto</th>
          <th class="num">Score</th>
        </tr>
      </thead>
      <tbody>
        ${sorted.map(a => {
          const days = daysSince(a.applied_at);
          const fu = getFollowUpStatus(days);
          const fuHtml = fu ? `<span class="fu-badge ${fu.cls}">${fu.label}</span>` : '\u2014';
          const statusCls = STATUS_COLORS[a.status] || 'tag-gray';
          const statusHtml = `<span class="tag ${statusCls}">${STATUS_LABELS[a.status] || a.status}</span>`;
          const daysAgo = days != null ? `${days}d` : '\u2014';

          let actionHtml = '\u2014';
          if (a.next_action_date) {
            const aDays = daysSince(a.next_action_date);
            actionHtml = `${fullDate(a.next_action_date)}${aDays != null && aDays > 0 ? ' <span class="fu-badge fu-overdue">\uD83D\uDD14 Vencida</span>' : ''}`;
          }

          const scoreHtml = a.match_score != null ? `<span class="cell-score ${cls(a.match_score)}">${a.match_score}</span>` : '\u2014';
          const contactHtml = a.contact_name || '\u2014';

          return `<tr>
            <td>${fuHtml}</td>
            <td>
              <strong>${a.offer_title || ''}</strong>
              <small>${a.company_name || ''}</small>
              <button class="btn-link-icon" onclick="openModal(${a.offer_id})" title="Ver detalle">\uD83D\uDD0D</button>
            </td>
            <td>${statusHtml}</td>
            <td class="num">${daysAgo}</td>
            <td>${actionHtml}</td>
            <td>${contactHtml}</td>
            <td class="num">${scoreHtml}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
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

/* ── City × work mode stacked chart ── */
function renderCityModeChart(offers) {
  const cityMode = {};
  offers.forEach(o => {
    const c = o.city || 'Sin ubicaci\u00f3n';
    if (!cityMode[c]) cityMode[c] = { 'Presencial': 0, 'H\u00edbrido': 0, 'Remoto': 0 };
    const m = workModeLabel(o.work_mode);
    if (cityMode[c][m] != null) cityMode[c][m]++;
  });
  const sorted = Object.entries(cityMode)
    .map(([city, modes]) => ({ city, total: Object.values(modes).reduce((a, b) => a + b, 0), modes }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10);

  destroyChart('chartCityMode');
  if (!sorted.length) return;
  charts.chartCityMode = new Chart($('chartCityMode'), {
    type: 'bar',
    data: {
      labels: sorted.map(x => x.city),
      datasets: [
        { label: 'Presencial', data: sorted.map(x => x.modes['Presencial']), backgroundColor: '#ef4444' },
        { label: 'H\u00edbrido', data: sorted.map(x => x.modes['H\u00edbrido']), backgroundColor: '#eab308' },
        { label: 'Remoto', data: sorted.map(x => x.modes['Remoto']), backgroundColor: '#22c55e' },
      ],
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 16 } },
      plugins: {
        title: { display: true, text: 'Ofertas por localidad y modalidad', color: '#e4e4e7' },
        legend: { position: 'top', labels: { color: '#e4e4e7', font: { size: 11 } } },
      },
      scales: {
        x: { stacked: true, ticks: { color: '#8a8a95' }, beginAtZero: true },
        y: { stacked: true, ticks: { color: '#8a8a95', font: { size: 11 } } },
      },
    },
  });
}

/* ── Work mode chart ── */
const WORK_MODE_LABELS = ['Presencial', 'H\u00edbrido', 'Remoto'];
const WORK_MODE_COLORS = { 'Presencial': '#ef4444', 'H\u00edbrido': '#eab308', 'Remoto': '#22c55e' };

function renderWorkModeChart(offers) {
  const freq = {};
  offers.forEach(o => {
    const label = workModeLabel(o.work_mode);
    if (WORK_MODE_COLORS[label]) freq[label] = (freq[label] || 0) + 1;
  });
  const labels = WORK_MODE_LABELS.filter(l => freq[l]);

  destroyChart('chartWorkMode');
  if (!labels.length) return;
  charts.chartWorkMode = new Chart($('chartWorkMode'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: 'Ofertas', data: labels.map(l => freq[l]), backgroundColor: labels.map(l => WORK_MODE_COLORS[l]) }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Modalidad de trabajo', color: '#e4e4e7' },
      },
      scales: { x: { ticks: { color: '#8a8a95' } }, y: { beginAtZero: true, ticks: { color: '#8a8a95' } } },
    },
  });
}

/* ── Pipeline run ── */
let _pipelineAllOffers = null;

function loadPipelineRuns() {
  fetch('/api/pipeline-runs').then(r => r.json()).then(data => {
    if (!data.length) {
      $('pipelineRunLabel').textContent = 'Sin datos';
      return;
    }
    const sel = $('pipelineRunDate');
    sel.innerHTML = data.map(d => `<option value="${d.run_date}">${d.run_date}</option>`).join('');

    function onRun(run) {
      renderPipelineRun(run, data);
      if (_pipelineAllOffers) {
        const runOffers = _pipelineAllOffers.filter(o =>
          o.evaluated_at && o.evaluated_at.startsWith(run.run_date)
        );
        renderScatterChart(runOffers);
        renderSignalRecomChart(runOffers);
      }
    }

    sel.onchange = function () {
      const run = data.find(d => d.run_date === this.value);
      if (run) onRun(run);
    };

    if (_pipelineAllOffers) {
      onRun(data[0]);
    } else {
      fetch('/api/offers').then(r => r.json()).then(offers => {
        _pipelineAllOffers = offers;
        onRun(data[0]);
      });
    }
  });
}

function renderPipelineRun(run, allRuns) {
  $('pipelineRunLabel').textContent = `Último: ${run.run_date}`;

  // ── Funnel ──
  const steps = [
    { key: 'fetched',    label: 'Fetch' },
    { key: 'classified', label: 'Clasif.' },
    { key: 'evaluated',  label: 'Eval.' },
    { key: 'score_ge_35', label: '≥35' },
    { key: 'score_ge_50', label: '≥50' },
    { key: 'sent',       label: 'Enviadas' },
  ];
  const funnelHtml = steps.map((s, i) => {
    const val = run[s.key];
    const base = run.fetched || 1;
    const pct = i === 0 ? '100%' : (base ? `${(val / base * 100).toFixed(0)}%` : '0%');
    return `
      <div class="funnel-step">
        <div class="val">${val}</div>
        <div class="pct">${pct}</div>
        <div class="label">${s.label}</div>
      </div>
      ${i < steps.length - 1 ? '<div class="funnel-arrow">→</div>' : ''}
    `;
  }).join('');
  $('pipelineFunnel').innerHTML = funnelHtml;

  // ── Component bands chart ──
  renderCompBandsChart(run);

  // ── Environment compatibility chart ──
  renderEnvCompatChart(run);

  // ── Actionable offers table ──
  renderActionableTable(run);

  // ── Summary table ──
  if (allRuns) renderPipelineRunsTable(allRuns);
}

function renderCompBandsChart(run) {
  if (typeof Chart === 'undefined') return;
  const bands = run.bands || [];
  if (!bands.length) return;
  const bandOrder = { lt_30: 0, grey: 1, gt_50: 2 };
  bands.sort((a, b) => (bandOrder[a.band] ?? 99) - (bandOrder[b.band] ?? 99));

  const labels = bands.map(b => ({ lt_30: '<30', grey: '30–49', gt_50: '50+' })[b.band] || b.band);
  const mCore    = bands.map(b => b.m_core);
  const fExp     = bands.map(b => b.f_exp);
  const loc      = bands.map(b => b.loc);
  const market   = bands.map(b => b.market);
  const counts   = bands.map(b => b.n);

  destroyChart('chartCompBands');
  charts.chartCompBands = new Chart($('chartCompBands'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Skills core', data: mCore, backgroundColor: '#6366f1' },
        { label: 'Experiencia', data: fExp,  backgroundColor: '#22c55e' },
        { label: 'Ubicación',   data: loc,   backgroundColor: '#eab308' },
        { label: 'Fit cultural',data: market,backgroundColor: '#f97316' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: `Componentes promedio por banda (n: ${counts.join(', ')})`,
          color: '#e4e4e7',
        },
        legend: { labels: { color: '#e4e4e7', font: { size: 11 } } },
      },
      scales: {
        x: { ticks: { color: '#8a8a95' } },
        y: { beginAtZero: true, max: 100, ticks: { color: '#8a8a95', callback: v => v + '%' } },
      },
    },
    plugins: [{
      id: 'barLabels',
      afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        chart.data.datasets.forEach((ds, dsIdx) => {
          const meta = chart.getDatasetMeta(dsIdx);
          meta.data.forEach((bar, idx) => {
            const v = ds.data[idx];
            if (v == null || v === 0) return;
            ctx.fillStyle = '#e4e4e7';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.fillText(v, bar.x, bar.y - 2);
          });
        });
      },
    }],
  });
}

function renderEnvCompatChart(run) {
  if (typeof Chart === 'undefined') return;
  const env = run.env_compat || {};
  const labels = Object.keys(env);
  const vals = Object.values(env);
  const total = vals.reduce((a, b) => a + b, 0);
  if (!total) return;
  const colors = { alta: '#22c55e', media: '#eab308', baja: '#ef4444' };

  destroyChart('chartEnvCompat');
  charts.chartEnvCompat = new Chart($('chartEnvCompat'), {
    type: 'bar',
    data: {
      labels: ['Ajuste del entorno'],
      datasets: labels.map(l => ({
        label: l,
        data: [env[l]],
        backgroundColor: colors[l] || '#6366f1',
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        title: { display: true, text: 'Compatibilidad con el entorno (F_fit)', color: '#e4e4e7' },
        legend: { labels: { color: '#e4e4e7', font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label(ctx) {
              const pct = ((ctx.raw / total) * 100).toFixed(0);
              return `${ctx.dataset.label}: ${ctx.raw} (${pct}%)`;
            },
          },
        },
      },
      scales: {
        x: { stacked: true, ticks: { color: '#8a8a95', callback: v => v + '' } },
        y: { stacked: true, ticks: { color: '#8a8a95' } },
      },
    },
    plugins: [{
      id: 'envPercentLabels',
      afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        const meta = chart.getDatasetMeta(0);
        if (!meta.data.length) return;
        const totalW = chart.chartArea.right - chart.chartArea.left;
        let xOff = 0;
        chart.data.datasets.forEach((ds, dsIdx) => {
          const m = chart.getDatasetMeta(dsIdx);
          const bar = m.data[0];
          if (!bar) return;
          const w = bar.width || 20;
          const pct = ((ds.data[0] / total) * 100).toFixed(0);
          if (pct < 8) return;
          ctx.fillStyle = '#fff';
          ctx.font = 'bold 11px sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(`${pct}%`, bar.x, bar.y);
          xOff += w;
        });
      },
    }],
  });
}

function renderActionableTable(run) {
  const items = run.actionable || [];
  const tbody = $('pipelineActionable');
  if (!items.length) {
    tbody.innerHTML = '<p style="color:var(--text2);padding:12px">Sin ofertas accionables en esta ejecución.</p>';
    return;
  }
  const rows = items.map(o => `
    <tr onclick="openModal(${o.id})">
      <td class="num">${o.match_score}</td>
      <td>${o.title}</td>
      <td>${o.company_name}</td>
      <td>${o.city || '\u2014'}</td>
      <td>${o.work_mode || '\u2014'}</td>
      <td>${recTag(o.recommendation)}</td>
      <td>${signalTag(o.llm_apply_signal)}</td>
    </tr>
  `).join('');
  tbody.innerHTML = `
    <table>
      <thead><tr>
        <th class="num">Score</th><th>Título</th><th>Empresa</th>
        <th>Ubicación</th><th>Modalidad</th><th>Recom.</th><th>Señal</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderScatterChart(offers) {
  if (typeof Chart === 'undefined') return;
  if (!offers.length) return;
  const colors = { yes: '#22c55e', maybe: '#eab308', no: '#ef4444' };
  const labels = { yes: 'Sí', maybe: 'Quizás', no: 'No' };
  const datasets = ['yes', 'maybe', 'no'].map(signal => ({
    label: labels[signal],
    data: offers.filter(o => o.llm_apply_signal === signal).map(o => ({
      x: (o.M_core ?? 0) * 100,
      y: (o.F_fit ?? 0) * 100,
      title: o.title,
      company: o.company_name,
      score: o.match_score,
    })),
    backgroundColor: colors[signal],
    borderColor: colors[signal],
    pointRadius: 5,
  }));
  destroyChart('chartScatterMcoreFfit');
  charts.chartScatterMcoreFfit = new Chart($('chartScatterMcoreFfit'), {
    type: 'scatter',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#e4e4e7', font: { size: 11 } },
          onClick: null,
        },
        tooltip: {
          callbacks: {
            title() { return ''; },
            label(ctx) {
              const p = ctx.raw;
              return `${p.title} — ${p.company} (Score: ${p.score})`;
            },
          },
        },
      },
      scales: {
        x: {
          min: 0, max: 100,
          title: { display: true, text: 'Skills core (%)', color: '#e4e4e7' },
          ticks: { color: '#8a8a95' },
        },
        y: {
          min: 0, max: 100,
          title: { display: true, text: 'Fit cultural (%)', color: '#e4e4e7' },
          ticks: { color: '#8a8a95' },
        },
      },
    },
    plugins: [{
      id: 'diagonalLine',
      beforeDraw(chart) {
        const ctx = chart.ctx;
        const xS = chart.scales.x;
        const yS = chart.scales.y;
        ctx.save();
        ctx.strokeStyle = 'rgba(255,255,255,0.2)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(xS.getPixelForValue(0), yS.getPixelForValue(0));
        ctx.lineTo(xS.getPixelForValue(100), yS.getPixelForValue(100));
        ctx.stroke();
        ctx.restore();
      },
    }],
  });
}

function renderSignalRecomChart(offers) {
  if (typeof Chart === 'undefined') return;
  if (!offers.length) return;
  const recOrder = ['Prioritario', 'Aplicar', 'Con expectativas bajas', 'No aplicar'];
  const signals = ['yes', 'maybe', 'no'];
  const colors = { yes: '#22c55e', maybe: '#eab308', no: '#ef4444' };
  const labels = { yes: 'Sí', maybe: 'Quizás', no: 'No' };
  const counts = {};
  offers.forEach(o => {
    const rec = o.recommendation || 'Sin recom.';
    const sig = o.llm_apply_signal || 'no';
    if (!counts[rec]) counts[rec] = { yes: 0, maybe: 0, no: 0 };
    counts[rec][sig]++;
  });
  const availRecs = recOrder.filter(r => counts[r]);
  destroyChart('chartSignalRecom');
  charts.chartSignalRecom = new Chart($('chartSignalRecom'), {
    type: 'bar',
    data: {
      labels: availRecs,
      datasets: signals.map(sig => ({
        label: labels[sig],
        data: availRecs.map(r => counts[r][sig] || 0),
        backgroundColor: colors[sig],
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#e4e4e7', font: { size: 11 } } },
      },
      scales: {
        x: { ticks: { color: '#8a8a95' } },
        y: { beginAtZero: true, ticks: { color: '#8a8a95', stepSize: 1 } },
      },
    },
  });
}

function renderPipelineRunsTable(allRuns) {
  const cols = [
    { key: 'run_date', label: 'Fecha' },
    { key: 'fetched', label: 'Captadas' },
    { key: 'classified', label: 'Clasificadas' },
    { key: 'evaluated', label: 'Evaluadas' },
    { key: 'score_ge_50', label: '≥50 pts' },
    { key: 'sent', label: 'Enviadas' },
    { key: 'avg_score', label: 'Score medio' },
  ];
  const html = `
    <table>
      <thead><tr>${cols.map(c => `<th>${c.label}</th>`).join('')}</tr></thead>
      <tbody>${allRuns.map(r => `
        <tr>${cols.map(c => `<td>${r[c.key] ?? '\u2014'}</td>`).join('')}</tr>
      `).join('')}</tbody>
    </table>
  `;
  $('pipelineRunsTable').innerHTML = html;
}

/* ── Init ── */
Promise.all([loadStats(), loadOffers()]).then(() => {
  renderCharts();
  checkPipelineStatus();
});
