const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const app = $('#app');
let appState = null;
let currentPage = 'overview';
let lastToken = '';
let tokenExpiresAt = null;
let timerHandle = null;
let toastHandle = null;
let pollHandle = null;

function toast(message) {
  const el = $('#toast'); el.textContent = message; el.classList.add('show');
  clearTimeout(toastHandle); toastHandle = setTimeout(() => el.classList.remove('show'), 3300);
}
async function api(url, options={}) {
  const res = await fetch(url, {headers:{'Content-Type':'application/json'}, ...options});
  let data = {};
  try { data = await res.json(); } catch {}
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}
function initials(name='Demo Student') { return name.split(/\s+/).map(x=>x[0]).slice(0,2).join('').toUpperCase(); }
function timeAgo(iso) {
  if (!iso) return '—';
  const mins = Math.max(0, Math.floor((Date.now()-new Date(iso).getTime())/60000));
  if (mins < 1) return 'Just now'; if (mins < 60) return `${mins} min ago`;
  const h = Math.floor(mins/60); if (h < 24) return `${h} hr${h>1?'s':''} ago`;
  return new Date(iso).toLocaleDateString(undefined,{month:'short',day:'numeric'});
}
function dateTime(iso) { return iso ? new Date(iso).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—'; }
function escapeHtml(s='') { return String(s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function setPage(name) {
  if (!$('#page-'+name)) return;
  currentPage = name;
  $$('.page').forEach(p=>p.classList.toggle('active', p.id==='page-'+name));
  $$('.nav-item').forEach(b=>b.classList.toggle('active', b.dataset.page===name));
  $('#crumb-current').textContent = ({overview:'Overview',live:'Live attendance',students:'Student roster',reports:'Reports'})[name] || 'Overview';
  $('#sidebar').classList.remove('open');
  if (name==='live') refreshState();
  if (name==='students') renderStudents();
  if (name==='reports') renderReports();
}
function renderMetrics() {
  const m = appState.metrics;
  $('#metric-students').textContent = m.studentCount;
  $('#metric-average').textContent = m.averageAttendance;
  $('#metric-sessions').textContent = m.completedSessions;
  $('#metric-checkins').textContent = m.todayCheckIns;
  $('#metric-today-sessions').textContent = `${m.todaySessions} session${m.todaySessions===1?'':'s'}`;
}
function renderLatest() {
  const list = $('#latest-checkins');
  const items = appState.recentAttendance.slice(0,5);
  if (!items.length) { list.innerHTML='<div class="blank-row">Your newest check-ins will appear here.</div>'; return; }
  list.innerHTML = items.map(x=>`<div class="activity-row"><div class="student-avatar">${escapeHtml(initials(x.name))}</div><div class="activity-copy"><strong>${escapeHtml(x.name)}</strong><span>${escapeHtml(x.rollNo)} · ${escapeHtml(x.subject)}</span></div><span class="activity-time">${escapeHtml(timeAgo(x.markedAt))}</span></div>`).join('');
}
function renderOverviewSession() {
  const s = appState.activeSession;
  $('#nav-live-dot').classList.toggle('on', !!s);
  $('#overview-empty').classList.toggle('hidden', !!s);
  $('#overview-active').classList.toggle('hidden', !s);
  const status = $('#overview-session-status');
  if (s) {
    status.innerHTML='<i style="background:#4cb579"></i> Live now'; status.style.color='#348457';
    $('#overview-course').textContent=s.subject; $('#overview-subtitle').textContent=`${s.division} · ${s.faculty}`;
    $('#overview-started').textContent=`Started ${timeAgo(s.startedAt).toLowerCase()}`;
    $('#overview-count').textContent=`${s.present}/${s.total}`;
  } else { status.innerHTML='<i></i> Not started'; status.style.color=''; }
}
function renderLive() {
  const s = appState.activeSession;
  const live = !!s;
  $('#live-status').classList.toggle('off', !live);
  $('#live-status').innerHTML = live ? '<i></i><span>SESSION LIVE</span>' : '<i></i><span>NOT LIVE</span>';
  $('#qr-title').textContent = live ? s.subject : 'Your QR will appear here';
  $('#qr-subtitle').textContent = live ? `${s.division} · ${s.faculty}` : 'Start a session to open check-in';
  $('#session-toggle').innerHTML = live ? 'End attendance session <span>×</span>' : 'Start attendance session <span>→</span>';
  $('#session-toggle').classList.toggle('end-session', live);
  $('#session-hint').textContent = live ? `Session ${s.sessionId} · QR refreshes every ${s.ttl} seconds.` : 'Demo session uses fictional students. Starting will not contact college systems.';
  $('#qr-progress-wrap').classList.toggle('hidden', !live);
  $('#qr-actions').classList.toggle('hidden', !live);
  if (!live) {
    lastToken=''; $('#qr-stage').innerHTML='<div class="qr-placeholder"><div class="qr-outline"><span>▦</span></div><strong>Ready when you are</strong><span>Launch a session to create a short-lived code.</span></div>';
    stopCountdown(); $('#live-present-count').textContent='0'; $('#attendance-total').textContent=`0 of ${appState.students.length}`;
    $('#completion-ring').textContent='0%'; $('#attendance-fill').style.width='0%'; $('#live-roster').innerHTML='<div class="blank-row">Start a session to show the roster.</div>'; return;
  }
  $('#live-present-count').textContent=s.present; $('#attendance-total').textContent=`${s.present} of ${s.total}`;
  const pct = s.total ? Math.round(s.present/s.total*100) : 0;
  $('#completion-ring').textContent=`${pct}%`; $('#attendance-fill').style.width=`${pct}%`;
  if (s.token !== lastToken) {
    lastToken = s.token; tokenExpiresAt = new Date(s.expiresAt).getTime();
    $('#qr-stage').innerHTML=`<div><img class="qr-image" alt="Rotating student attendance QR code" src="/api/qr?token=${encodeURIComponent(s.token)}&v=${Date.now()}"><div class="qr-image-label">Scan with a phone camera</div></div>`;
    startCountdown();
  }
  const presentIds = new Set(appState.presentStudentIds || []);
  // server state includes roster; derive current session attendees from its recentAttendance + counts endpoint mapping.
  const currentAttendance = appState.currentAttendance || [];
  const presentSet = new Set(currentAttendance.map(a=>a.studentId));
  const roster = appState.students.filter(st=>st.division===s.division);
  $('#live-roster').innerHTML=roster.map(st=>{
    const found=currentAttendance.find(a=>a.studentId===st.studentId);
    return `<div class="checkin-row"><div class="student-avatar">${escapeHtml(initials(st.name))}</div><div class="checkin-person"><div class="checkin-name">${escapeHtml(st.name)}</div><div class="checkin-roll">${escapeHtml(st.rollNo)}</div></div><span class="attendance-status ${found?'present':''}">${found?'✓ Present':'Waiting'}</span></div>`;
  }).join('');
}
function startCountdown() {
  stopCountdown();
  timerHandle = setInterval(()=>{
    if (!tokenExpiresAt) return;
    const ms = Math.max(0, tokenExpiresAt-Date.now());
    const secs=Math.ceil(ms/1000); $('#qr-countdown').textContent=`${secs}s`;
    $('#qr-progress').style.width=`${Math.max(0,ms/((appState?.activeSession?.ttl||25)*1000)*100)}%`;
    $('#qr-progress').style.background=secs<=5?'#dba66b':'#69b98e';
  },250);
}
function stopCountdown(){if(timerHandle){clearInterval(timerHandle);timerHandle=null;} tokenExpiresAt=null;}
function renderStudents() {
  if (!appState) return;
  const q = ($('#roster-search')?.value || '').trim().toLowerCase();
  const students = appState.students.filter(s=>`${s.name} ${s.rollNo} ${s.studentId}`.toLowerCase().includes(q));
  $('#student-table-body').innerHTML=students.map(s=>`<tr><td><div class="table-person"><div class="student-avatar">${escapeHtml(initials(s.name))}</div><strong>${escapeHtml(s.name)}</strong></div></td><td>${escapeHtml(s.rollNo)}</td><td><span class="neutral-tag">${escapeHtml(s.division)}</span></td><td>${escapeHtml(s.studentId)}</td></tr>`).join('') || '<tr><td colspan="4" style="text-align:center;padding:28px;color:#9aa69e">No matching students found.</td></tr>';
  $('#roster-result-count').textContent=`Showing ${students.length} of ${appState.students.length} demo students`;
}
function renderReports() {
  if (!appState) return;
  $('#session-table-body').innerHTML=appState.sessions.map(s=>`<tr><td><div class="table-person"><div class="course-monogram" style="width:31px;height:31px;font-size:9px">${escapeHtml(s.subject.split(/\s+/).map(w=>w[0]).slice(0,2).join('').toUpperCase())}</div><div><strong style="display:block;font-size:10px;color:#355445">${escapeHtml(s.subject)}</strong><span style="font-size:8px;color:#9ca89f">${escapeHtml(s.sessionId)}</span></div></div></td><td>${escapeHtml(dateTime(s.startedAt))}</td><td>${escapeHtml(s.division)}</td><td><strong>${s.present}</strong> <span style="color:#9ca89f;font-size:9px">/ ${appState.students.length}</span></td><td><span class="status-pill ${s.status==='live'?'live':'completed'}">${s.status==='live'?'● Live':'✓ Completed'}</span></td></tr>`).join('') || '<tr><td colspan="5" style="text-align:center;padding:25px;color:#9aa69e">No sessions recorded yet.</td></tr>';
}
async function refreshState() {
  try {
    const s=await api('/api/state');
    appState=s;
    // For a live session only, retrieve records for the active session from the current API route.
    if (s.activeSession) {
      const records=await api(`/api/session-attendance?sessionId=${encodeURIComponent(s.activeSession.sessionId)}`).catch(()=>({records:[]}));
      appState.currentAttendance=records.records||[];
    } else appState.currentAttendance=[];
    renderMetrics(); renderLatest(); renderOverviewSession(); renderLive();
    if (currentPage==='students') renderStudents(); if (currentPage==='reports') renderReports();
    populateStudentSelects();
  } catch(e) { toast(`Can't reach the local demo server: ${e.message}`); }
}
async function startSession() {
  try {
    const subject=$('#subject-select').value, division=$('#division-select').value, faculty=$('#faculty-input').value.trim()||'Demo Faculty';
    await api('/api/session/start',{method:'POST',body:JSON.stringify({subject,division,faculty})});
    await refreshState(); toast('Attendance session started. The QR is live.');
  } catch(e) { toast(e.message); await refreshState(); }
}
async function stopSession() {
  if (!confirm('End this attendance session? New check-ins will stop, and the session will be saved in reports.')) return;
  try { await api('/api/session/stop',{method:'POST',body:'{}'}); await refreshState(); toast('Session ended. Attendance is saved in reports.'); }
  catch(e){toast(e.message)}
}
function populateStudentSelects() {
  if (!appState) return;
  const opts=appState.students.map(s=>`<option value="${escapeHtml(s.studentId)}">${escapeHtml(s.rollNo)} · ${escapeHtml(s.name)}</option>`).join('');
  const select=$('#sim-student-select');
  if (select && select.dataset.loaded !== 'yes') {select.innerHTML=opts;select.dataset.loaded='yes';}
}
function openSimModal() {
  if (!appState?.activeSession) {toast('Start a session first.'); return;}
  $('#student-modal').classList.remove('hidden');
}
async function simulateCheckin() {
  const s=appState?.activeSession; if (!s) {toast('Start a session first.');return;}
  const studentId=$('#sim-student-select').value;
  try {
    await api('/api/checkin',{method:'POST',body:JSON.stringify({token:s.token,studentId})});
    $('#student-modal').classList.add('hidden'); await refreshState(); toast('Demo check-in recorded. Live count updated.');
  } catch(e) { $('#student-modal').classList.add('hidden'); toast(e.message); await refreshState(); }
}
function openStudentPortal() {
  const url = location.origin + '/student?token=' + encodeURIComponent(appState?.activeSession?.token||'');
  window.open(url,'_blank','noopener');
}
async function initStudentPage() {
  document.body.className='student-page-body';
  app.innerHTML=`<main class="student-card"><div class="student-brand"><div class="brand-mark"><span></span><span></span><span></span></div><div><div class="brand-name">campusflow<span>.</span></div><div class="brand-sub" style="color:#94a99b">SMART CAMPUS CONCEPT</div></div></div><div class="eyebrow">STUDENT CHECK-IN / DEMO</div><h1>You're in the right place.</h1><p>Confirm your demo account to record attendance for this lecture. In a real deployment, your college login would identify you automatically.</p><div class="student-session-info" id="student-session-info"><strong>Verifying QR session…</strong><span>Please wait a moment.</span></div><div id="student-expired-warning" class="student-warning hidden">This QR code may have expired. Return to the classroom display and scan the latest code.</div><label class="student-select-label" for="student-account">SELECT DEMO STUDENT ACCOUNT</label><select id="student-account" class="student-select"></select><button id="student-submit" class="primary-button full">Confirm attendance <span>→</span></button><div id="student-success" class="student-success"><strong>✓ Attendance recorded</strong><span id="student-success-copy">Your demo check-in was accepted.</span></div><div class="modal-footnote" style="margin-top:18px">Prototype only · fictional student data · not connected to SAKEC systems</div></main>`;
  try {
    const state=await api('/api/state');
    $('#student-account').innerHTML=state.students.map(s=>`<option value="${escapeHtml(s.studentId)}">${escapeHtml(s.rollNo)} · ${escapeHtml(s.name)}</option>`).join('');
    const token=new URLSearchParams(location.search).get('token')||'';
    if (!token) { $('#student-session-info').innerHTML='<strong>No QR token found</strong><span>Scan the code from the classroom attendance screen.</span>'; $('#student-expired-warning').classList.remove('hidden'); $('#student-submit').disabled=true; return; }
    const s=state.activeSession;
    if (s) $('#student-session-info').innerHTML=`<strong>${escapeHtml(s.subject)}</strong><span>${escapeHtml(s.division)} · ${escapeHtml(s.faculty)} · Short-lived QR session</span>`;
    $('#student-submit').addEventListener('click',async()=>{
      $('#student-submit').disabled=true; $('#student-submit').textContent='Recording…';
      try { const res=await api('/api/checkin',{method:'POST',body:JSON.stringify({token,studentId:$('#student-account').value})}); $('#student-success-copy').textContent=`Recorded for ${res.subject}. You can return to class.`; $('#student-success').style.display='block'; $('#student-expired-warning').classList.add('hidden'); $('#student-submit').style.display='none'; }
      catch(e){
        $('#student-expired-warning').textContent=e.message;
        $('#student-expired-warning').classList.remove('hidden');
        if (e.message.toLowerCase().includes('expired') || e.message.toLowerCase().includes('latest code')) {
          $('#student-submit').disabled=true;
          $('#student-submit').textContent='Scan latest QR';
        } else {
          $('#student-submit').disabled=false;
          $('#student-submit').textContent='Try again';
        }
      }
    });
  } catch(e) { $('#student-session-info').innerHTML='<strong>Could not connect</strong><span>Return to the demo computer and try again.</span>'; }
}
function downloadRoster() {
  const rows=[['Student ID','Roll Number','Name','Division'],...appState.students.map(s=>[s.studentId,s.rollNo,s.name,s.division])];
  const csv=rows.map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\r\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8;'}));a.download='campusflow-demo-roster.csv';a.click();URL.revokeObjectURL(a.href);toast('Roster CSV downloaded.');
}
function init() {
  if (location.pathname==='/student') { initStudentPage(); return; }
  $$('.nav-item').forEach(b=>b.addEventListener('click',()=>setPage(b.dataset.page)));
  $$('[data-goto]').forEach(b=>b.addEventListener('click',()=>setPage(b.dataset.goto)));
  $('#sidebar-launch').addEventListener('click',()=>setPage('live'));
  $('#start-from-overview').addEventListener('click',()=>{setPage('live'); if(!appState?.activeSession) startSession();});
  $('#session-toggle').addEventListener('click',()=>appState?.activeSession?stopSession():startSession());
  $('#mobile-menu').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
  $('#roster-search').addEventListener('input',renderStudents);
  $('#export-roster').addEventListener('click',downloadRoster);
  $('#refresh-reports').addEventListener('click',refreshState);
  $('#simulate-checkin').addEventListener('click',openSimModal);
  $('#close-modal').addEventListener('click',()=>$('#student-modal').classList.add('hidden'));
  $('#student-modal').addEventListener('click',e=>{if(e.target===$('#student-modal'))$('#student-modal').classList.add('hidden')});
  $('#confirm-sim-checkin').addEventListener('click',simulateCheckin);
  $('#copy-link').addEventListener('click',async()=>{
    const link=location.origin+'/student?token='+encodeURIComponent(appState?.activeSession?.token||'');
    try{await navigator.clipboard.writeText(link);toast('Student check-in link copied.')}catch{toast(link)}
  });
  refreshState();
  pollHandle=setInterval(refreshState,2500);
}
init();
