from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from config.settings import app_settings

router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CIC-YNU-IoTMal-Sandbox</title>
<style>
:root {{
  --bg:         #0d1117;
  --surface:    #161b22;
  --border:     #30363d;
  --text:       #c9d1d9;
  --muted:      #8b949e;
  --accent:     #58a6ff;
  --success:    #3fb950;
  --warning:    #d29922;
  --danger:     #f85149;
  --purple:     #a371f7;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; font-size: 13px; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

/* ── Header ─────────────────────────────────────────── */
header {{
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 20px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}}
header h1 {{ font-size: 14px; color: var(--accent); letter-spacing: 0.5px; }}
.status-bar {{ display: flex; gap: 20px; align-items: center; }}
.stat {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }}
.stat .n {{ font-size: 15px; font-weight: bold; }}
.stat.q  .n {{ color: var(--warning); }}
.stat.p  .n {{ color: var(--purple);  }}
.stat.c  .n {{ color: var(--success); }}
.stat.f  .n {{ color: var(--danger);  }}
.stat.x  .n {{ color: var(--muted);   }}
#refresh-ts {{ font-size: 11px; color: var(--muted); }}

/* ── Layout ─────────────────────────────────────────── */
.layout {{
  display: grid;
  grid-template-columns: 260px 1fr;
  flex: 1;
  overflow: hidden;
}}

/* ── Sidebar ─────────────────────────────────────────── */
.sidebar {{
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
}}
.panel {{
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
}}
.panel h2 {{
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--muted);
  margin-bottom: 10px;
}}

/* drop zone */
.drop-zone {{
  border: 2px dashed var(--border);
  border-radius: 4px;
  padding: 18px 10px;
  text-align: center;
  color: var(--muted);
  font-size: 11px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
  margin-bottom: 8px;
  user-select: none;
}}
.drop-zone:hover, .drop-zone.over {{ border-color: var(--accent); color: var(--accent); }}
#file-input {{ display: none; }}
.sel-name {{ font-size: 11px; color: var(--text); margin-bottom: 8px; word-break: break-all; min-height: 14px; }}

/* buttons */
button {{
  display: block;
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}}
button:hover:not(:disabled) {{ background: #21262d; border-color: var(--accent); color: var(--accent); }}
button.primary {{ border-color: var(--accent); color: var(--accent); }}
button.primary:hover:not(:disabled) {{ background: rgba(88,166,255,0.1); }}
button:disabled {{ opacity: 0.35; cursor: not-allowed; }}
.feedback {{ font-size: 11px; margin-top: 6px; min-height: 14px; line-height: 1.4; }}
.ok   {{ color: var(--success); }}
.err  {{ color: var(--danger);  }}
.info {{ color: var(--muted);   }}

/* ── Main panel ──────────────────────────────────────── */
.main {{ display: flex; flex-direction: column; overflow: hidden; }}

.tabs {{
  display: flex;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  padding: 0 16px;
  flex-shrink: 0;
}}
.tab {{
  padding: 10px 14px;
  font-size: 12px;
  cursor: pointer;
  color: var(--muted);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s;
  white-space: nowrap;
}}
.tab:hover {{ color: var(--text); }}
.tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
.tab .badge {{
  display: inline-block;
  background: var(--border);
  border-radius: 8px;
  padding: 1px 6px;
  font-size: 10px;
  margin-left: 5px;
  color: var(--muted);
}}

/* table */
.table-wrap {{ flex: 1; overflow-y: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
thead th {{
  position: sticky;
  top: 0;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 8px 16px;
  text-align: left;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted);
  font-weight: normal;
}}
tbody tr {{ border-bottom: 1px solid var(--border); transition: background 0.1s; }}
tbody tr:hover {{ background: var(--surface); }}
td {{ padding: 8px 16px; font-size: 12px; vertical-align: middle; }}
.tid {{ font-size: 10px; color: var(--muted); font-family: monospace; }}
.fname {{ max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

.pill {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: bold;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}}
.pill-QUEUED     {{ background: rgba(210,153,34,0.15);  color: var(--warning); }}
.pill-PROCESSING {{ background: rgba(163,113,247,0.15); color: var(--purple);  }}
.pill-COMPLETED  {{ background: rgba(63,185,80,0.15);   color: var(--success); }}
.pill-FAILED     {{ background: rgba(248,81,73,0.15);   color: var(--danger);  }}
.pill-CANCELLED  {{ background: rgba(139,148,158,0.15); color: var(--muted);   }}

.stop-btn {{
  display: inline-block;
  width: auto;
  padding: 3px 10px;
  font-size: 11px;
  border: 1px solid var(--danger);
  color: var(--danger);
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}}
.stop-btn:hover {{ background: rgba(248,81,73,0.1); }}

.dl-btn {{
  display: inline-block;
  width: auto;
  padding: 3px 10px;
  font-size: 11px;
  border: 1px solid var(--success);
  color: var(--success);
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}}
.dl-btn:hover {{ background: rgba(63,185,80,0.1); }}

.fail-reason {{
  font-size: 11px;
  color: var(--danger);
  cursor: help;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
  vertical-align: middle;
}}

.empty {{ padding: 60px 16px; text-align: center; color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>

<header>
  <h1>CIC-YNU-IoTMal-Sandbox</h1>
  <div class="status-bar">
    <div class="stat q"><span>Queued</span><span class="n" id="s-q">—</span></div>
    <div class="stat p"><span>Processing</span><span class="n" id="s-p">—</span></div>
    <div class="stat c"><span>Completed</span><span class="n" id="s-c">—</span></div>
    <div class="stat f"><span>Failed</span><span class="n" id="s-f">—</span></div>
    <div class="stat x"><span>Cancelled</span><span class="n" id="s-x">—</span></div>
    <span id="refresh-ts">—</span>
  </div>
</header>

<div class="layout">

  <!-- ── Sidebar ── -->
  <div class="sidebar">

    <div class="panel">
      <h2>Submit Sample</h2>
      <div class="drop-zone" id="dz" onclick="document.getElementById('file-input').click()">
        <input type="file" id="file-input">
        ↑ Drop file here or click to browse
      </div>
      <div class="sel-name" id="sel-name"></div>
      <button class="primary" id="upload-btn" disabled onclick="uploadFile()">Upload</button>
      <div class="feedback" id="upload-fb"></div>
    </div>

    <div class="panel">
      <h2>Bulk Enqueue</h2>
      <p style="color:var(--muted);font-size:11px;margin-bottom:10px;line-height:1.5">
        Scan the configured malware directory and enqueue all new files.
      </p>
      <button onclick="initQueue()">Init Queue</button>
      <div class="feedback" id="init-fb"></div>
    </div>

  </div>

  <!-- ── Main ── -->
  <div class="main">

    <div class="tabs">
      <div class="tab active" data-status="" onclick="setTab(this)">All <span class="badge" id="tab-n-all">0</span></div>
      <div class="tab" data-status="QUEUED"     onclick="setTab(this)">Queued <span class="badge" id="tab-n-q">0</span></div>
      <div class="tab" data-status="PROCESSING" onclick="setTab(this)">Processing <span class="badge" id="tab-n-p">0</span></div>
      <div class="tab" data-status="COMPLETED"  onclick="setTab(this)">Completed <span class="badge" id="tab-n-c">0</span></div>
      <div class="tab" data-status="FAILED"     onclick="setTab(this)">Failed <span class="badge" id="tab-n-f">0</span></div>
      <div class="tab" data-status="CANCELLED"  onclick="setTab(this)">Cancelled <span class="badge" id="tab-n-x">0</span></div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Filename</th>
            <th>Task ID</th>
            <th>Status</th>
            <th>Worker</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
      <div class="empty" id="empty" style="display:none">No tasks.</div>
    </div>

  </div>
</div>

<script>
const API = '{api_base}';
let tasks = [];
let activeStatus = '';

// ── Drop zone ────────────────────────────────────────────
const dz = document.getElementById('dz');
const fi = document.getElementById('file-input');

dz.addEventListener('dragover',  e => {{ e.preventDefault(); dz.classList.add('over'); }});
dz.addEventListener('dragleave', () => dz.classList.remove('over'));
dz.addEventListener('drop', e => {{
  e.preventDefault(); dz.classList.remove('over');
  if (e.dataTransfer.files[0]) selectFile(e.dataTransfer.files[0]);
}});
fi.addEventListener('change', () => {{ if (fi.files[0]) selectFile(fi.files[0]); }});

function selectFile(f) {{
  dz._file = f;
  document.getElementById('sel-name').textContent = f.name;
  document.getElementById('upload-btn').disabled = false;
  fb('upload-fb', '', '');
}}

// ── Upload ───────────────────────────────────────────────
async function uploadFile() {{
  if (!dz._file) return;
  const btn = document.getElementById('upload-btn');
  btn.disabled = true;
  fb('upload-fb', 'Uploading…', 'info');
  const form = new FormData();
  form.append('file', dz._file);
  try {{
    const r = await fetch(API + '/submit-file', {{ method: 'POST', body: form }});
    const d = await r.json();
    if (r.ok) {{
      fb('upload-fb', `Queued — ${{d.task_id.slice(0,8)}}…`, 'ok');
      dz._file = null; fi.value = '';
      document.getElementById('sel-name').textContent = '';
      await refresh();
    }} else {{
      fb('upload-fb', d.detail || 'Upload failed', 'err');
      btn.disabled = false;
    }}
  }} catch(e) {{
    fb('upload-fb', 'Network error', 'err');
    btn.disabled = false;
  }}
}}

// ── Init queue ───────────────────────────────────────────
async function initQueue() {{
  fb('init-fb', 'Scanning…', 'info');
  try {{
    const r = await fetch(API + '/init-queue');
    const d = await r.json();
    if (r.ok) {{
      fb('init-fb', `${{d.added}} added · ${{d.skipped}} skipped · ${{d.total}} total`, 'ok');
      await refresh();
    }} else {{
      fb('init-fb', d.detail || 'Failed', 'err');
    }}
  }} catch(e) {{
    fb('init-fb', 'Network error', 'err');
  }}
}}

// ── Tabs ─────────────────────────────────────────────────
function setTab(el) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  activeStatus = el.dataset.status;
  renderTable();
}}

// ── Refresh ──────────────────────────────────────────────
async function refresh() {{
  await Promise.all([refreshStatus(), refreshTasks()]);
  document.getElementById('refresh-ts').textContent =
    'updated ' + new Date().toLocaleTimeString();
}}

async function refreshStatus() {{
  try {{
    const r = await fetch(API + '/status');
    if (!r.ok) return;
    const d = await r.json();
    document.getElementById('s-q').textContent = d.queued;
    document.getElementById('s-p').textContent = d.processing;
    document.getElementById('s-c').textContent = d.completed;
    document.getElementById('s-f').textContent = d.failed;
    document.getElementById('s-x').textContent = d.cancelled ?? 0;
  }} catch(e) {{}}
}}

async function refreshTasks() {{
  try {{
    const r = await fetch(API + '/tasks');
    if (!r.ok) return;
    tasks = (await r.json()).tasks;
    updateTabCounts();
    renderTable();
  }} catch(e) {{}}
}}

function updateTabCounts() {{
  const counts = {{ QUEUED: 0, PROCESSING: 0, COMPLETED: 0, FAILED: 0, CANCELLED: 0 }};
  tasks.forEach(t => {{ if (counts[t.status] !== undefined) counts[t.status]++; }});
  document.getElementById('tab-n-all').textContent = tasks.length;
  document.getElementById('tab-n-q').textContent   = counts.QUEUED;
  document.getElementById('tab-n-p').textContent   = counts.PROCESSING;
  document.getElementById('tab-n-c').textContent   = counts.COMPLETED;
  document.getElementById('tab-n-f').textContent   = counts.FAILED;
  document.getElementById('tab-n-x').textContent   = counts.CANCELLED;
}}

// ── Table render ─────────────────────────────────────────
function renderTable() {{
  const rows = activeStatus ? tasks.filter(t => t.status === activeStatus) : tasks;
  const tbody = document.getElementById('tbody');
  const empty = document.getElementById('empty');

  if (rows.length === 0) {{
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }}
  empty.style.display = 'none';

  tbody.innerHTML = rows.map(t => {{
    let action = '';
    if (t.status === 'COMPLETED') {{
      action = `<button class="dl-btn" onclick="download('${{esc(t.task_id)}}','${{esc(t.filename || t.task_id)}}')">↓ zip</button>`;
    }} else if (t.status === 'PROCESSING') {{
      action = `<button class="stop-btn" onclick="stopTask('${{esc(t.task_id)}}', this)">■ stop</button>`;
    }} else if (t.status === 'FAILED' && t.failure_reason) {{
      action = `<span class="fail-reason" title="${{esc(t.failure_reason)}}">⚠ ${{esc(t.failure_reason)}}</span>`;
    }}
    return `<tr>
      <td><span class="fname" title="${{esc(t.filename)}}">${{esc(t.filename || '—')}}</span></td>
      <td><span class="tid">${{esc(t.task_id)}}</span></td>
      <td><span class="pill pill-${{esc(t.status)}}">${{esc(t.status)}}</span></td>
      <td>${{esc(t.worker_id || '—')}}</td>
      <td>${{action}}</td>
    </tr>`;
  }}).join('');
}}

// ── Download ─────────────────────────────────────────────
function download(taskId, filename) {{
  const a = document.createElement('a');
  a.href = API + '/results/' + encodeURIComponent(taskId);
  a.download = filename.replace(/\.[^.]+$/, '') + '_result.zip';
  a.click();
}}

// ── Stop task ────────────────────────────────────────────
async function stopTask(taskId, btn) {{
  btn.disabled = true;
  btn.textContent = '…';
  try {{
    const r = await fetch(API + '/cancel/' + encodeURIComponent(taskId), {{ method: 'POST' }});
    if (r.ok) {{
      await refresh();
    }} else {{
      const d = await r.json().catch(() => ({{}}));
      alert('Stop failed: ' + (d.detail || r.status));
      btn.disabled = false;
      btn.textContent = '■ stop';
    }}
  }} catch(e) {{
    alert('Network error');
    btn.disabled = false;
    btn.textContent = '■ stop';
  }}
}}

// ── Helpers ──────────────────────────────────────────────
function fb(id, msg, cls) {{
  const el = document.getElementById(id);
  el.textContent = msg;
  el.className = 'feedback' + (cls ? ' ' + cls : '');
}}

function esc(s) {{
  return String(s ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

// ── Start ────────────────────────────────────────────────
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui():
    return _HTML.format(api_base=app_settings.app_base_url)
