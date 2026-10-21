  /* Veylith frontend: static-first, API-connected, no build step required. */
(() => {
  'use strict';

  const API_ROOT = window.CHRONICLE_API_BASE || '/api/chronicle';
  const AUTH_ROOT = API_ROOT.replace(/\/api\/chronicle\/?$/, '/api');
  const state = {
    view: 'overview',
    scenario: 'revoked',
    scenarioId: 'SCN-042',
    scenarioCatalog: [],
    tracePaused: false,
    activityRange: '24h',
    loaded: {},
  };

  const mocks = {
    recent: [
      ['dec_9f34a2', 'svc/deploy-bot', 'REJECT', '12s'],
      ['dec_9f349d', 'user/mara.k', 'ALLOW', '38s'],
      ['dec_9f3401', 'svc/rotation', 'ALLOW', '1m'],
      ['dec_9f33ab', 'svc/rollback', 'REJECT', '2m'],
    ],
    events: [
      { kind: 'CALLER', label: 'Approval presented', detail: 'approval.status = ACTIVE · version 41', time: 't+000ms', cls: '' },
      { kind: 'AUTHORITY', label: 'Policy checked', detail: 'scope deploy/prod · subject svc/deploy-bot', time: 't+042ms', cls: 'authority' },
      { kind: 'VERIFY', label: 'Claim accepted', detail: 'signature valid · freshness window 500ms', time: 't+061ms', cls: 'verify' },
      { kind: 'AUTHORITY', label: 'Approval revoked', detail: 'version 41 → 42 · reason: incident response', time: 't+118ms', cls: 'authority' },
      { kind: 'VERIFY', label: 'Commit boundary opened', detail: 'boundary proof requested from transaction', time: 't+164ms', cls: 'verify' },
      { kind: 'RESULT', label: 'Decision rejected', detail: 'stale authorization at protected commit', time: 't+428ms', cls: 'result' },
    ],
    assertions: [
      ['approval.signature', 'signed proof is authentic'],
      ['approval.subject', 'subject matches requested principal'],
      ['approval.scope', 'scope includes deploy/prod'],
      ['approval.expiry', 'approval is inside expiry window'],
      ['approval.status', 'status is current at commit boundary'],
      ['approval.version', 'authority version is monotonic'],
      ['commit.boundary_proof', 'commit is causally bound to claim'],
      ['decision.explainable', 'decision has complete rationale'],
    ],
    scenarios: {
      revoked: { id: 'SCN-042', name: 'Revoked approval race', description: 'A valid approval is revoked after the caller checks it but before the protected operation commits. The verifier must reject the stale authorization and preserve a complete causal trail.', events: [ ['CALLER', 'Present approval', 'approval.status = ACTIVE', 't+000ms', ''], ['AUTHORITY', 'Check policy', 'scope deploy/prod · subject deploy-bot', 't+042ms', 'authority'], ['VERIFY', 'Accept claim', 'signature valid · freshness 500ms', 't+061ms', 'verifier'], ['AUTHORITY', 'Revoke approval', 'version 41 → 42 · incident response', 't+118ms', 'authority'], ['VERIFY', 'Open commit boundary', 'boundary proof requested', 't+164ms', 'verifier'], ['COMMIT', 'Reject operation', 'stale authorization detected', 't+428ms', 'commit'] ] },
      clock: { id: 'SCN-017', name: 'Clock skew window', description: 'A verifier receives a claim from a worker whose wall clock is 86ms ahead. Logical time must remain authoritative at the acceptance boundary.', events: [ ['CALLER', 'Present timestamp', 'iat=12:42:09.880Z', 't+000ms', ''], ['AUTHORITY', 'Read clock source', 'worker skew +86ms', 't+018ms', 'authority'], ['VERIFY', 'Normalize logical time', 'chronicle time wins', 't+067ms', 'verifier'], ['COMMIT', 'Accept operation', 'claim inside logical window', 't+122ms', 'commit'] ] },
      replay: { id: 'SCN-031', name: 'Nonce replay attempt', description: 'A previously accepted signed claim is replayed after the gateway has advanced its nonce window.', events: [ ['CALLER', 'Present claim', 'nonce=77b2 · signature valid', 't+000ms', ''], ['VERIFY', 'Check nonce', 'nonce already observed', 't+033ms', 'verifier'], ['COMMIT', 'Reject operation', 'replay detected', 't+087ms', 'commit'] ] },
      delegation: { id: 'SCN-028', name: 'Delegation chain break', description: 'A delegated service presents a valid leaf credential after its parent grant has been withdrawn.', events: [ ['CALLER', 'Present delegated grant', 'leaf=svc/release-bot', 't+000ms', ''], ['AUTHORITY', 'Resolve parent grant', 'parent grant revoked', 't+053ms', 'authority'], ['VERIFY', 'Break delegation chain', 'ancestor not active', 't+091ms', 'verifier'], ['COMMIT', 'Reject operation', 'delegation invalid', 't+143ms', 'commit'] ] },
      custom: { id: 'SCN-NEW', name: 'Custom sequence', description: 'Start from an empty event sequence and add facts to explore a new temporal authorization boundary.', events: [] },
    },
  };

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);

  function toast(message, type = 'success', detail = '') {
    const region = qs('#toast-region');
    const node = document.createElement('div');
    node.className = `toast ${type}`;
    node.innerHTML = `<b>${esc(message)}</b>${detail ? `<small>${esc(detail)}</small>` : ''}`;
    region.append(node);
    window.setTimeout(() => node.remove(), 4300);
  }

  async function fetchJson(path, options = {}, fallback = null) {
    try {
      const response = await fetch(`${API_ROOT}${path}`, { headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) }, ...options });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      if (fallback !== null) return { ...fallback, __mock: true };
      throw error;
    }
  }

  function setView(view) {
    if (!qs(`[data-view-panel="${view}"]`)) return;
    state.view = view;
    qsa('.view').forEach((panel) => panel.classList.toggle('active', panel.dataset.viewPanel === view));
    qsa('.nav-item[data-view]').forEach((item) => item.classList.toggle('active', item.dataset.view === view));
    const heading = qs(`[data-view-panel="${view}"] h1`);
    qs('#breadcrumb').textContent = (heading?.textContent || view).toUpperCase();
    qs('#sidebar').classList.remove('open');
    if (!state.loaded[view]) loadViewData(view);
  }

  async function loadViewData(view) {
    state.loaded[view] = true;
    const routes = { overview: '/overview', runs: '/agent-runs', scenario: '/scenarios', trace: '/traces/trace-7f3a', timeline: '/timeline/trace-7f3a', comparison: '/comparisons/trace-7f3a', repair: '/repairs', evidence: '/evidence/exports', integrations: '/integrations' };
    const fallback = view === 'scenario' ? { scenarios: Object.values(mocks.scenarios) } : {};
    const data = await fetchJson(routes[view], {}, fallback);
    if (data.__mock) toast('Showing local fixture data', 'error', 'The API is unavailable; actions remain previewable in this static console.');
    if (view === 'overview') { if (data.recent) renderRecent(data.recent); if (data.metrics) renderOverviewMetrics(data.metrics); }
    if (view === 'runs') renderAgentRuns(data.runs);
    if (view === 'trace') { renderTrace(data.events || mocks.events); renderTraceSummary(data.verification, data.baseline); }
    if (view === 'timeline') renderTimeline(data.events || mocks.events);
    if (view === 'scenario') { state.scenarioCatalog = Array.isArray(data.scenarios) ? data.scenarios : []; renderScenarioCatalog(state.scenarioCatalog); }
    if (view === 'comparison') renderComparison(data);
    if (view === 'repair') renderRepairFindings(data.findings);
    if (view === 'integrations') renderIntegrationStatus(data);
  }

  function renderOverviewMetrics(metrics = {}) {
    const values = {
      '#metric-runs': metrics.workflow_runs,
      '#metric-violations': metrics.invariant_violations,
      '#metric-rejected': metrics.rejected_unsafe_transitions,
      '#metric-legitimate': metrics.successful_legitimate_workflows,
    };
    Object.entries(values).forEach(([selector, value]) => { const node = qs(selector); if (node && value !== undefined) node.textContent = String(value); });
  }

  function renderIntegrationStatus(data = {}) {
    const summary = qs('.integration-summary');
    const grid = qs('.integration-grid');
    const simulated = (data.integrations || []).filter((item) => item.kind === 'simulated');
    const optional = (data.optional || []).filter((item) => item.kind === 'real');
    if (summary) summary.innerHTML = `<div><span class="summary-icon lime">✓</span><span><b>${simulated.length} active</b><small>simulated sources</small></span></div><div><span class="summary-icon cyan">◎</span><span><b>local</b><small>execution placement</small></span></div><div><span class="summary-icon violet">${optional.length}</span><span><b>optional</b><small>real integrations</small></span></div><div><span class="summary-icon amber">!</span><span><b>no devices</b><small>physical actions disabled</small></span></div>`;
    if (grid) grid.innerHTML = `<article class="panel integration-detail"><div class="integration-title"><span class="integration-logo cyan large">◎</span><div><h2>Deterministic event simulator</h2><span class="status-badge live">ACTIVE</span></div></div><div class="integration-url mono">in-process / chronicle_guard.scenarios</div><p class="panel-copy">The demo uses typed synthetic events and never connects to a physical Ring device.</p><button class="button ghost full" data-action="test-integration">Run source health check</button></article><article class="panel integration-detail"><div class="integration-title"><span class="integration-logo muted large">R</span><div><h2>Ring official API</h2><span class="status-badge warning">UNCONFIGURED</span></div></div><div class="integration-url mono">optional / credentials not present</div><p class="panel-copy">No Ring adapter is claimed. Configure only after official access, scopes, and hackathon eligibility are independently verified.</p><button class="button ghost full" data-action="add-integration">Review blocker</button></article>`;
  }

  function renderRepairFindings(findings = []) {
    const root = qs('.finding-list');
    if (!root || !Array.isArray(findings) || !findings.length) return;
    const header = root.querySelector('.panel-heading')?.outerHTML || '';
    root.innerHTML = `${header}${findings.map((finding, index) => `<button class="finding${index === 0 ? ' selected' : ''}" data-finding-id="${esc(finding.finding_id)}"><span class="severity ${finding.code === 'revoked_approval_race' ? 'high' : 'medium'}">${finding.code === 'revoked_approval_race' ? 'H' : 'M'}</span><span><b>${esc(finding.code.replaceAll('_', ' '))}</b><small>${esc(finding.scenario_id)} · ${esc(finding.status || 'PENDING')}</small></span><span class="finding-chevron">›</span></button>`).join('')}`;
  }

  function renderRecent(rows = mocks.recent) {
    qs('#recent-decisions').innerHTML = rows.map((row) => `<tr><td>${esc(row[0])}</td><td>${esc(row[1])}</td><td><span class="result ${row[2] === 'ALLOW' ? 'allow' : 'reject'}">${esc(row[2])}</span></td><td>${esc(row[3])}</td></tr>`).join('');
  }

  function renderAgentRuns(runs = []) {
    const root = qs('#agent-runs-table');
    if (!root) return;
    if (!Array.isArray(runs) || !runs.length) { root.innerHTML = '<tr><td colspan="5">No agent runs returned by the API.</td></tr>'; return; }
    root.innerHTML = runs.map((run) => `<tr><td class="mono">${esc(run.run_id || run.id || '—')}</td><td>${esc(run.name || run.scenario_id || '—')}</td><td><span class="result ${run.outcome === 'ALLOW' ? 'allow' : 'reject'}">${esc(run.outcome || 'UNKNOWN')}</span></td><td>${esc((run.violation_codes || []).join(', ') || 'none')}</td><td class="mono">${esc(String(run.evidence_hash || '').slice(0, 12) || '—')}</td></tr>`).join('');
  }

  function renderBars(range = '24h') {
    const values = range === '7d' ? [48, 51, 57, 52, 64, 68, 75, 73, 78, 85, 81, 92] : range === '30d' ? [42, 48, 46, 59, 54, 62, 69, 65, 77, 74, 85, 91] : [28, 38, 34, 47, 45, 65, 58, 78, 72, 89, 84, 96];
    qs('#activity-chart').innerHTML = values.map((height, index) => `<i class="bar" style="--h:${height}%;--r:${index % 4 === 0 ? '7%' : '3%'}"></i>`).join('');
  }

  function scenarioKindClass(kind) { return kind.toLowerCase() === 'authority' ? 'authority' : kind.toLowerCase() === 'verify' ? 'verifier' : kind.toLowerCase() === 'commit' ? 'commit' : ''; }

  function renderScenario(scenario = mocks.scenarios[state.scenario]) {
    scenario = { ...scenario, events: Array.isArray(scenario?.events) ? scenario.events : [] };
    qs('#scenario-id').textContent = scenario.id;
    qs('#scenario-name').textContent = scenario.name;
    qs('#scenario-description').textContent = scenario.description;
    qs('#event-stack').innerHTML = scenario.events.length ? scenario.events.map((event, index) => `<div class="event-row"><span class="event-index">${String(index + 1).padStart(2, '0')}</span><span class="event-kind ${scenarioKindClass(event[0])}">${esc(event[0])}</span><span class="event-desc"><b>${esc(event[1])}</b><small>${esc(event[2])}</small></span><span class="event-time">${esc(event[3])}</span><button class="remove-event" type="button" data-action="remove-event" aria-label="Remove event">×</button></div>`).join('') : '<div class="empty-state">No events yet. Add a fact to begin a custom sequence.</div>';
  }

  function renderScenarioCatalog(scenarios) {
    if (!Array.isArray(scenarios) || !scenarios.length) return;
    const root = qs('.scenario-items');
    if (!root) return;
    root.innerHTML = scenarios.map((scenario, index) => {
      const id = scenario.id || `SCN-${index}`;
      const selected = id === state.scenarioId ? ' selected' : '';
      const severity = id === 'SCN-042' ? 'danger' : scenario.name?.includes('happy') ? 'cyan' : 'amber';
      return `<button class="scenario-item${selected}" data-scenario-id="${esc(id)}"><span class="scenario-icon ${severity}">${id === 'SCN-042' ? '!' : '◈'}</span><span><b>${esc(scenario.name || id)}</b><small>${esc(scenario.description || 'Deterministic replay scenario')}</small></span><span class="scenario-state">${esc(scenario.status || 'READY')}</span></button>`;
    }).join('');
  }

  function renderTrace(events = mocks.events) {
    qs('#trace-stream').innerHTML = events.map((event) => `<div class="trace-line"><span class="time">${esc(event.time)}</span><span class="kind ${esc(event.cls || '')}">${esc(event.kind)}</span><p><strong>${esc(event.label)}</strong><br/><span>${esc(event.detail)}</span></p><span class="trace-check">✓</span></div>`).join('');
    qs('#assertion-list').innerHTML = mocks.assertions.map(([name, detail]) => `<div class="assertion"><i>✓</i><span><b>${esc(name)}</b><small>${esc(detail)}</small></span></div>`).join('');
  }

  function renderTraceSummary(verification = {}, baseline = {}) {
    const summary = qs('.trace-summary');
    if (!summary) return;
    const outcome = verification.valid ? 'ALLOWED' : 'REJECTED';
    const violations = Array.isArray(verification.violations) ? verification.violations.length : 0;
    summary.innerHTML = `<div><span>OUTCOME</span><b class="${verification.valid ? 'lime-text' : 'danger-text'}">${outcome}</b></div><div><span>EVENTS</span><b class="mono">${(verification.checked_event_ids || []).length}</b></div><div><span>VIOLATIONS</span><b>${violations}</b></div><div><span>BASELINE</span><b class="${baseline.allowed ? 'danger-text' : 'lime-text'}">${baseline.allowed ? 'ALLOW' : 'REJECT'}</b></div>`;
  }

  function renderComparison(data = {}) {
    const root = qs('.comparison-summary');
    if (!root || !data.baseline || !data.verifier) return;
    const baseline = data.baseline;
    const verifier = data.verifier;
    const primary = verifier.violations?.[0];
    root.innerHTML = `<div class="compare-score baseline"><span class="eyebrow">LEGACY BASELINE</span><strong>${baseline.allowed ? 'ALLOW' : 'REJECT'}</strong><small>${esc((baseline.reasons || []).join(', ') || 'presence checks passed')}</small></div><div class="compare-arrow">→<small>${baseline.allowed === verifier.valid ? 'aligned' : 'diverged'}</small></div><div class="compare-score verifier"><span class="eyebrow">CHRONICLE VERIFIER</span><strong>${verifier.valid ? 'ALLOW' : 'REJECT'}</strong><small>${esc(primary?.code || 'all invariants valid')}</small></div><div class="compare-reason"><span class="eyebrow">PRIMARY FINDING</span><b>${esc(primary?.code || 'no divergence')}</b><p>${esc(primary?.message || 'The bounded trace passed temporal checks.')}</p></div>`;
  }

  async function downloadEvidence() {
    try {
      const data = await fetchJson('/evidence/exports');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'veylith-evidence.json';
      link.click();
      URL.revokeObjectURL(url);
      toast('Evidence downloaded', 'success', 'Export generated by the FastAPI evidence endpoint.');
    } catch (error) {
      toast('Evidence export failed', 'error', error instanceof Error ? error.message : 'The API did not return an export.');
    }
  }

  function openReviewerModal() {
    openModal('Reviewer authorization required', 'Repair decisions are server-side and require a reviewer session. Enter the configured demo reviewer credentials for this local deployment.', '<label class="field"><span>EMAIL</span><input id="reviewer-email" type="email" autocomplete="username" placeholder="reviewer@example.com" /></label><label class="field"><span>PASSWORD</span><input id="reviewer-password" type="password" autocomplete="current-password" placeholder="Configured demo password" /></label><div class="modal-actions"><button class="button secondary" data-action="close-modal">Cancel</button><button class="button primary" data-action="submit-repair-review">Authorize and approve</button></div>');
  }

  async function submitRepairReview() {
    const email = qs('#reviewer-email')?.value || '';
    const password = qs('#reviewer-password')?.value || '';
    const finding = (await fetchJson('/repairs', {}, { findings: [] })).findings?.[0];
    if (!finding) { toast('No pending finding', 'error'); return; }
    try {
      const loginResponse = await fetch(`${AUTH_ROOT}/auth/login`, { method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      const login = await loginResponse.json();
      if (!loginResponse.ok) throw new Error(login.detail || `Login failed (${loginResponse.status})`);
      const decision = await fetchJson(`/repairs/${encodeURIComponent(finding.finding_id)}/decision`, { method: 'POST', headers: { Authorization: `Bearer ${login.access_token}` }, body: JSON.stringify({ decision: 'approve' }) });
      closeModal();
      toast('Repair decision recorded', 'success', `${decision.status} by ${decision.decided_by}`);
      state.loaded.repair = false;
    } catch (error) {
      toast('Repair decision failed', 'error', error instanceof Error ? error.message : 'Reviewer authorization failed.');
    }
  }

  function renderTimeline(events = mocks.events) {
    const lanes = [{ label: 'CALLER', color: 'var(--cyan)' }, { label: 'AUTHORITY', color: 'var(--violet)' }, { label: 'VERIFIER', color: 'var(--amber)' }, { label: 'COMMIT', color: 'var(--lime)' }];
    const points = [18, 29, 39, 52, 66, 86];
    qs('#timeline-canvas').innerHTML = lanes.map((lane, laneIndex) => `<div class="lane" style="top:${laneIndex * 74}px"><span class="lane-label">${lane.label}</span><div class="lane-track">${events.filter((event) => event.kind === lane.label || (lane.label === 'COMMIT' && event.kind === 'RESULT')).map((event, index) => { const point = points[Math.min(index + laneIndex, points.length - 1)]; return `<button class="event-mark ${event.label === 'Approval revoked' ? 'active' : ''}" style="left:${point}%;--mark:${lane.color};--span:${Math.max(24, 72 - index * 10)}px" title="${esc(event.label)}"><span>${esc(event.time)}</span></button>`; }).join('')}</div></div>`).join('');
  }

  async function runScenario() {
    const scenario = state.scenarioCatalog.find((item) => item.id === state.scenarioId) || mocks.scenarios[state.scenario];
    if (!scenario) { toast('Select a scenario first', 'error'); return; }
    setView('trace');
    qs('#trace-stream').classList.add('loading');
    toast(`Executing ${scenario.name}`, 'success', 'Streaming verifier events…');
    const result = await fetchJson(`/scenarios/${encodeURIComponent(scenario.id)}/run`, { method: 'POST', body: JSON.stringify({ scenario_id: scenario.id }) }, { events: mocks.events, outcome: 'REJECTED' });
    renderTrace(result.events || mocks.events);
    renderTraceSummary(result.verification, result.baseline);
    renderComparison({ baseline: result.baseline, verifier: result.verification });
    qs('#trace-stream').classList.remove('loading');
    if (result.__mock) toast('Replay completed in fixture mode', 'error', 'Connect the planned scenario endpoint to run against the live verifier.');
    else toast('Replay completed', 'success', `Outcome: ${result.outcome || 'REJECTED'}`);
  }

  function openModal(title, body, actions = '') {
    qs('#modal-content').innerHTML = `<div class="eyebrow cyan">VEY LITH</div><h2 id="modal-title">${esc(title)}</h2><p>${body}</p>${actions ? `<div class="modal-actions">${actions}</div>` : ''}`;
    qs('#modal').hidden = false;
  }

  function closeModal() { qs('#modal').hidden = true; }

  function handleAction(action, target) {
    if (action === 'toggle-sidebar') qs('#sidebar').classList.toggle('open');
    if (action === 'refresh') { state.loaded = {}; loadViewData(state.view); toast('Data refreshed', 'success'); }
    if (action === 'run-race') { state.scenario = 'revoked'; state.scenarioId = 'SCN-042'; renderScenario(); setView('scenario'); toast('Flagship race loaded', 'success', 'Press Execute sequence when ready.'); }
    if (action === 'run-scenario') runScenario();
    if (action === 'pause-trace') { state.tracePaused = !state.tracePaused; target.textContent = state.tracePaused ? '▶ Resume stream' : 'Ⅱ Pause stream'; toast(state.tracePaused ? 'Trace stream paused' : 'Trace stream resumed'); }
    if (action === 'clear-trace') { qs('#trace-stream').innerHTML = ''; toast('Trace cleared'); }
    if (action === 'download-trace' || action === 'export-quick' || action === 'export-comparison' || action === 'generate-export') downloadEvidence();
    if (action === 'new-export') qs('.field input')?.focus();
    if (action === 'add-event') { mocks.scenarios[state.scenario].events.push(['CALLER', 'New event', 'Describe the event fact', 't+000ms', '']); renderScenario(); toast('Event added', 'success', 'Edit the backend payload when connected.'); }
    if (action === 'remove-event') { target.closest('.event-row')?.remove(); toast('Event removed'); }
    if (action === 'copy-code') { navigator.clipboard?.writeText('allow { approval.status == "ACTIVE"; approval.version == commit.approval_version; commit.boundary_proof != null }'); toast('Policy snippet copied'); }
    if (action === 'approve-repair') openReviewerModal();
    if (action === 'submit-repair-review') submitRepairReview();
    if (action === 'create-repair') openModal('Create repair', 'Select a finding from the queue to generate a bounded remediation patch.', '<button class="button secondary" data-action="close-modal">Cancel</button><button class="button primary" data-action="approve-repair">Create draft</button>');
    if (action === 'add-integration') openModal('Connect an integration', 'The backend can expose a connection flow here. Planned adapters: GitHub Enterprise, Vault Transit, Kafka Events, and signed webhook sources.', '<button class="button secondary" data-action="close-modal">Cancel</button><button class="button primary" data-action="close-modal">Continue</button>');
    if (action === 'test-integration' || action === 'refresh-integrations') { state.loaded.integrations = false; loadViewData('integrations'); toast('Integration status refreshed', 'success', 'Simulator and Ring configuration state re-read from the API.'); }
    if (action === 'notifications') loadNotifications();
    if (action === 'workspace' || action === 'profile') openModal(action === 'workspace' ? 'Workspace' : 'Operator profile', action === 'workspace' ? 'northstar-labs / production / us-east-1' : 'Mara K. · security engineer', '<button class="button primary" data-action="close-modal">Close</button>');
    if (action === 'zoom-in' || action === 'zoom-out') toast(action === 'zoom-in' ? 'Timeline zoomed in' : 'Timeline zoomed out');
    if (action === 'close-modal') closeModal();
  }

  async function loadNotifications() {
    try {
      const data = await fetchJson('/notifications');
      const items = data.notifications || [];
      const body = items.length ? items.slice(0, 8).map((item) => `<div class="assertion"><i>!</i><span><b>${esc(item.title || 'Veylith alert')}</b><small>${esc(item.message || '')}</small></span></div>`).join('') : '<p>No verifier notifications returned by the API.</p>';
      openModal('Notifications', body, '<button class="button primary" data-action="close-modal">Done</button>');
    } catch (error) {
      toast('Notifications unavailable', 'error', error instanceof Error ? error.message : 'The API did not return notifications.');
    }
  }

  document.addEventListener('click', (event) => {
    const viewButton = event.target.closest('[data-view]');
    if (viewButton) { setView(viewButton.dataset.view); return; }
    const actionButton = event.target.closest('[data-action]');
    if (actionButton) { handleAction(actionButton.dataset.action, actionButton); return; }
    const scenarioButton = event.target.closest('[data-scenario-id]');
    if (scenarioButton) { state.scenarioId = scenarioButton.dataset.scenarioId; const match = Object.entries(mocks.scenarios).find(([, item]) => item.id === state.scenarioId); if (match) state.scenario = match[0]; qsa('.scenario-item').forEach((item) => item.classList.toggle('selected', item === scenarioButton)); const selected = state.scenarioCatalog.find((item) => item.id === state.scenarioId) || mocks.scenarios[state.scenario]; renderScenario(selected ? { id: selected.id, name: selected.name, description: selected.description, events: mocks.scenarios[state.scenario]?.events || [] } : undefined); return; }
    const findingButton = event.target.closest('[data-finding-id]');
    if (findingButton) { qsa('.finding').forEach((item) => item.classList.toggle('selected', item === findingButton)); toast('Finding selected', 'success', findingButton.dataset.findingId); return; }
    const rangeButton = event.target.closest('[data-range]');
    if (rangeButton) { state.activityRange = rangeButton.dataset.range; qsa('[data-range]').forEach((button) => button.classList.toggle('selected', button === rangeButton)); renderBars(state.activityRange); }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeModal();
    if (event.key === '/' && document.activeElement.tagName !== 'INPUT') { event.preventDefault(); setView('scenario'); qs('#scenario-search')?.focus(); }
    if (event.key.toLowerCase() === 'o' && event.altKey) setView('overview');
  });

  loadViewData('overview');
  renderRecent();
  renderBars();
  renderScenario();
  renderTrace();
  renderTimeline();
})();
