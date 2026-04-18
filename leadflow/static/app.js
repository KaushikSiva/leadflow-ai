// ── State ──────────────────────────────────────────────────────────────────
const state = {
  prompts: Array.isArray(window.__INITIAL_PROMPTS__) ? window.__INITIAL_PROMPTS__ : [],
  selectedPromptId: document.body.dataset.selectedPromptId || '',
  prompt: null,
  prospects: [],
  selectedProspectId: null,
  pollHandle: null,
  lastSig: '',
};

// ── Refs ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const E = {
  promptInput:    $('prompt-input'),
  limitInput:     $('limit-input'),
  queueBtn:       $('queue-btn'),
  composerStatus: $('composer-status'),
  promptList:     $('prompt-list'),
  ledgerTitle:    $('ledger-title'),
  retryBtn:       $('retry-btn'),
  briefStrip:     $('brief-strip'),
  promptError:    $('prompt-error'),
  prospectTable:  $('prospect-table'),
  leadsCount:     $('leads-count'),
  leadsEmpty:     $('leads-empty'),
  inspHead:       $('insp-head'),
  inspAv:         $('insp-av'),
  inspName:       $('insp-name'),
  inspRole:       $('insp-role'),
  inspBar:        $('insp-bar'),
  inspScore:      $('insp-score'),
  dCompany:       $('d-company'),
  dLocation:      $('d-location'),
  dDecision:      $('d-decision'),
  dPhone:         $('d-phone'),
  dReason:        $('d-reason'),
  phoneList:      $('phone-list'),
  dProfile:       $('d-profile'),
  callBtn:        $('call-btn'),
  callStatus:     $('call-status'),
};

// ── Helpers ────────────────────────────────────────────────────────────────
const esc = v => String(v ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const trim = (v, n) => { const s = String(v ?? ''); return s.length > n ? s.slice(0, n) + '…' : s; };

function initials(name) {
  const p = String(name || '?').trim().split(/\s+/);
  return p.length >= 2 ? (p[0][0] + p[p.length-1][0]).toUpperCase() : (p[0][0] || '?').toUpperCase();
}

const AV_COLORS = [
  ['#00e5ff','#0097a7'], ['#00e676','#00897b'], ['#ffd740','#f9a825'],
  ['#ff6e40','#e64a19'], ['#e040fb','#7b1fa2'], ['#40c4ff','#0277bd'],
];
function avColor(name) {
  let h = 0; for (const c of String(name || '')) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
  return AV_COLORS[h % AV_COLORS.length];
}

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) } });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

function setStatus(msg, isErr = false) {
  E.composerStatus.textContent = msg || '';
  E.composerStatus.className = 'composer-status' + (isErr ? ' err' : '');
}

function sig(p) {
  if (!p) return '';
  return [p.status, p.discovered_count, p.scored_count, p.enriched_count, p.error_text || '', p.updated_at || ''].join('|');
}

function isActive(p) {
  return Boolean(p && ['queued','planning','discovering','scoring','enriching'].includes(p.status));
}

// ── Pipeline ───────────────────────────────────────────────────────────────
const STAGES = ['planning','discovering','scoring','enriching','ready'];

function renderPipeline(p) {
  const status = p?.status || '';
  const counts = {
    planning:    '✓',
    discovering: p ? String(p.discovered_count) : '—',
    scoring:     p ? String(p.scored_count) : '—',
    enriching:   p ? String(p.enriched_count) : '—',
    ready:       (status === 'ready' || status === 'partial') ? String(p.enriched_count) : '—',
  };
  const order = STAGES.indexOf(status);
  for (const key of STAGES) {
    const el = $(`stage-${key}`);
    const cnt = $(`pc-${key}`);
    if (!el) continue;
    const idx = STAGES.indexOf(key);
    el.className = 'pipe-stage' + (
      status === 'ready' || status === 'partial' ? ' done' :
      status === 'failed' ? (idx < order ? ' done' : '') :
      idx < order ? ' done' : idx === order ? ' active' : ''
    );
    if (cnt) cnt.textContent = p ? counts[key] : '—';
  }
}

// ── Prompt list ────────────────────────────────────────────────────────────
function dotCls(s) {
  if (['queued','planning','discovering','scoring','enriching'].includes(s)) return 'live';
  if (s === 'ready' || s === 'partial') return 'ok';
  if (s === 'failed') return 'fail';
  return '';
}

function renderPromptList() {
  E.promptList.innerHTML = state.prompts.map(p => `
    <a class="promptlink${p.id === state.selectedPromptId ? ' active' : ''}" href="/prompts/${p.id}" data-id="${esc(p.id)}">
      <div class="pl-status">
        <span class="pl-dot ${dotCls(p.status)}"></span>
        <span class="pl-status-text">${esc(p.status)}</span>
      </div>
      <div class="pl-snippet">${esc(trim(p.raw_prompt, 88))}</div>
      <div class="pl-meta">${p.discovered_count} found · ${p.enriched_count} enriched</div>
    </a>
  `).join('');
}

// ── Brief strip ────────────────────────────────────────────────────────────
function renderBrief(brief = {}) {
  const fields = [
    ['Roles',    (brief.target_roles || []).join(', ') || '—'],
    ['Industry', (brief.industries || []).join(', ') || '—'],
    ['Geo',      (brief.geographies || []).join(', ') || '—'],
    ['Seniority',(brief.seniority_hints || []).join(', ') || '—'],
    ['Exclude',  (brief.exclusions || []).join(', ') || 'None'],
    ['Angle',    brief.outreach_angle || '—'],
  ];
  E.briefStrip.innerHTML = fields.map(([k, v]) => `
    <div class="brief-cell">
      <div class="brief-key">${esc(k)}</div>
      <div class="brief-val" title="${esc(v)}">${esc(v)}</div>
    </div>
  `).join('');
}

// ── Score bar color ────────────────────────────────────────────────────────
function scoreColor(n) {
  return n >= 70 ? 'var(--green)' : n >= 40 ? 'var(--yellow)' : 'var(--red)';
}

// ── Decision badge ─────────────────────────────────────────────────────────
function badge(d) {
  const map = { target: 'b-target', review: 'b-review', reject: 'b-reject' };
  return `<span class="badge ${map[d] || 'b-pending'}">${esc(d || 'pending')}</span>`;
}

// ── Prospects table ────────────────────────────────────────────────────────
function renderProspects() {
  const items = state.prospects;
  E.leadsCount.textContent = `${items.length} lead${items.length !== 1 ? 's' : ''}`;
  if (!items.length) {
    E.prospectTable.innerHTML = '';
    E.leadsEmpty.style.display = '';
    return;
  }
  E.leadsEmpty.style.display = 'none';

  E.prospectTable.innerHTML = items.map((item, i) => {
    const sel = item.prompt_prospect_id === state.selectedProspectId ? ' sel' : '';
    const score = Number(item.confidence_score || 0);
    const [c1, c2] = avColor(item.full_name);
    const enrichCls = item.enrichment_status === 'complete' ? 'ok' : item.enrichment_status === 'failed' ? 'fail' : '';
    return `<tr class="${sel}" data-id="${esc(item.prompt_prospect_id)}" style="--i:${i}">
      <td><div class="lc">
        <div class="lc-av" style="background:linear-gradient(135deg,${c1},${c2})">${initials(item.full_name)}</div>
        <div>
          <div class="lc-name">${esc(item.full_name || 'Unnamed')}</div>
          <div class="lc-role">${esc(trim((item.job_title || '') + (item.company_name ? ' · ' + item.company_name : ''), 48))}</div>
        </div>
      </div></td>
      <td><div class="sc">
        <div class="sc-bar"><div class="sc-fill" style="width:${score}%;background:${scoreColor(score)}"></div></div>
        <span class="sc-num">${score}</span>
      </div></td>
      <td>${badge(item.ai_decision)}</td>
      <td><span class="enrich ${enrichCls}">${esc(item.enrichment_status || '—')}</span></td>
      <td><span class="phone-val">${esc(item.best_phone_e164 || '—')}</span></td>
      <td><a class="link-open" href="${esc(item.profile_url || '#')}" target="_blank" rel="noreferrer" onclick="event.stopPropagation()">↗</a></td>
    </tr>`;
  }).join('');

  E.prospectTable.querySelectorAll('tr').forEach(row => {
    row.addEventListener('click', () => {
      state.selectedProspectId = row.dataset.id;
      renderProspects();
      renderInspector();
    });
  });
}

// ── Inspector ──────────────────────────────────────────────────────────────
function renderInspector() {
  const item = state.prospects.find(p => p.prompt_prospect_id === state.selectedProspectId);
  if (!item) {
    E.inspAv.textContent = '?';
    E.inspAv.style.background = 'var(--bg2)';
    E.inspName.textContent = 'NO LEAD SELECTED';
    E.inspRole.textContent = '';
    E.inspBar.style.width = '0%';
    E.inspScore.textContent = '—';
    E.dCompany.textContent = '—'; E.dLocation.textContent = '—';
    E.dDecision.innerHTML = '—'; E.dPhone.textContent = '—';
    E.dReason.textContent = 'Select a prospect to see scoring rationale.';
    E.phoneList.innerHTML = '';
    E.dProfile.href = '#';
    E.callBtn.disabled = true;
    E.callStatus.textContent = '';
    return;
  }

  E.inspHead.classList.remove('flash');
  void E.inspHead.offsetWidth;
  E.inspHead.classList.add('flash');

  const [c1, c2] = avColor(item.full_name);
  E.inspAv.textContent = initials(item.full_name);
  E.inspAv.style.background = `linear-gradient(135deg,${c1},${c2})`;
  E.inspName.textContent = (item.full_name || 'Unnamed').toUpperCase();
  E.inspRole.textContent = [item.job_title, item.company_name].filter(Boolean).join(' at ');

  const score = Number(item.confidence_score || 0);
  E.inspBar.style.width = `${score}%`;
  E.inspBar.style.background = scoreColor(score);
  E.inspScore.textContent = `${score}/100`;
  E.inspScore.style.color = scoreColor(score);

  E.dCompany.textContent = item.company_name || '—';
  E.dLocation.textContent = item.location || '—';
  E.dDecision.innerHTML = badge(item.ai_decision);
  E.dPhone.textContent = item.best_phone_e164 || '—';
  E.dReason.textContent = item.score_reason || 'No rationale available.';

  const phones = item.phones_json || [];
  E.phoneList.innerHTML = phones.length
    ? phones.map(p => `<li>📞 ${esc(String(p))}</li>`).join('')
    : `<li style="color:var(--dim);border:none;background:none;padding:0">No enriched phones</li>`;

  E.dProfile.href = item.profile_url || '#';
  E.callBtn.disabled = false;
}

// ── Full render ────────────────────────────────────────────────────────────
function renderAll() {
  renderPromptList();
  E.ledgerTitle.textContent = state.prompt ? trim(state.prompt.raw_prompt, 80).toUpperCase() : 'SELECT A RUN';
  renderPipeline(state.prompt);
  renderBrief(state.prompt?.canonical_brief_json || {});
  E.promptError.textContent = state.prompt?.error_text || '';
  renderProspects();
  renderInspector();
}

// ── Data ───────────────────────────────────────────────────────────────────
async function loadPrompts() {
  const data = await api('/api/prompts');
  state.prompts = data.items || [];
}

async function loadSelected() {
  if (!state.selectedPromptId) {
    if (state.prompts[0]) {
      state.selectedPromptId = state.prompts[0].id;
      history.replaceState({}, '', `/prompts/${state.selectedPromptId}`);
    } else {
      state.prompt = null; state.prospects = [];
      renderAll(); return;
    }
  }
  state.prompt = await api(`/api/prompts/${state.selectedPromptId}`);
  const s = sig(state.prompt);
  if (s !== state.lastSig || !state.prospects.length) {
    const data = await api(`/api/prompts/${state.selectedPromptId}/prospects`);
    state.prospects = data.items || [];
    if (!state.prospects.find(p => p.prompt_prospect_id === state.selectedProspectId))
      state.selectedProspectId = state.prospects[0]?.prompt_prospect_id || null;
  }
  state.lastSig = s;
  renderAll();
}

// ── Polling ────────────────────────────────────────────────────────────────
function stopPoll() { if (state.pollHandle) { clearInterval(state.pollHandle); state.pollHandle = null; } }

function startPoll() {
  stopPoll();
  if (!isActive(state.prompt)) return;
  state.pollHandle = setInterval(async () => {
    try {
      const prev = state.lastSig, prevStatus = state.prompt?.status;
      state.prompt = await api(`/api/prompts/${state.selectedPromptId}`);
      const s = sig(state.prompt);
      if (s !== prev) {
        if (state.prompt.status !== prevStatus || state.prompt.discovered_count !== state.prospects.length) {
          const data = await api(`/api/prompts/${state.selectedPromptId}/prospects`);
          state.prospects = data.items || [];
          if (!state.prospects.find(p => p.prompt_prospect_id === state.selectedProspectId))
            state.selectedProspectId = state.prospects[0]?.prompt_prospect_id || null;
        }
        if (state.prompt.status !== prevStatus) await loadPrompts();
        state.lastSig = s;
        renderAll();
      }
      if (!isActive(state.prompt)) stopPoll();
    } catch (err) { E.promptError.textContent = err.message; }
  }, 4000);
}

// ── Events ─────────────────────────────────────────────────────────────────
E.queueBtn.addEventListener('click', async () => {
  const prompt = E.promptInput.value.trim();
  const limit = Number(E.limitInput.value || 5);
  if (!prompt) { setStatus('Enter a search brief first.', true); return; }
  setStatus('Queueing…');
  E.queueBtn.disabled = true;
  try {
    const data = await api('/api/prompts', { method: 'POST', body: JSON.stringify({ prompt, requested_limit: limit }) });
    state.selectedPromptId = data.id;
    history.pushState({}, '', `/prompts/${data.id}`);
    E.promptInput.value = '';
    setStatus('Queued ✓');
    await loadPrompts(); await loadSelected(); startPoll();
  } catch (err) { setStatus(err.message, true); }
  finally { E.queueBtn.disabled = false; }
});

E.retryBtn.addEventListener('click', async () => {
  if (!state.selectedPromptId) return;
  E.promptError.textContent = '';
  try {
    await api(`/api/prompts/${state.selectedPromptId}/retry`, { method: 'POST' });
    await loadPrompts(); await loadSelected(); startPoll();
  } catch (err) { E.promptError.textContent = err.message; }
});

E.callBtn.addEventListener('click', async () => {
  if (!state.selectedProspectId) return;
  E.callStatus.textContent = 'Connecting…';
  E.callStatus.className = 'call-status';
  E.callBtn.disabled = true;
  try {
    const r = await api(`/api/prompt-prospects/${state.selectedProspectId}/call`, { method: 'POST' });
    E.callStatus.textContent = `✓ ${r.voicecall_call_id}`;
    await loadSelected();
  } catch (err) {
    E.callStatus.textContent = err.message;
    E.callStatus.className = 'call-status err';
  } finally { E.callBtn.disabled = false; }
});

E.promptList.addEventListener('click', e => {
  const a = e.target.closest('a[data-id]');
  if (!a) return;
  e.preventDefault();
  state.selectedPromptId = a.dataset.id;
  state.lastSig = '';
  history.pushState({}, '', `/prompts/${state.selectedPromptId}`);
  loadSelected().then(startPoll).catch(err => { E.promptError.textContent = err.message; });
});

window.addEventListener('popstate', () => {
  const parts = window.location.pathname.split('/');
  state.selectedPromptId = parts[1] === 'prompts' ? parts[2] : '';
  state.lastSig = '';
  loadSelected().then(startPoll).catch(err => { E.promptError.textContent = err.message; });
});

// ── Boot ───────────────────────────────────────────────────────────────────
(async () => {
  try {
    renderPromptList();
    await loadPrompts();
    await loadSelected();
    startPoll();
  } catch (err) { setStatus(err.message, true); }
})();
