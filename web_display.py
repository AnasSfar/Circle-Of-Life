# web_display.py
# Display process:
#  - communicates with env ONLY through message queues (display_to_env, env_to_display, log_to_display)
#  - does NOT access shared_env (spec: shared memory for predator/prey only)

import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from ipc import DisplayCommand


def run_web_display(env_to_display, display_to_env, log_to_display, host="127.0.0.1", port=8000):
    latest = {"ok": False, "reason": "no snapshot yet"}
    latest_lock = threading.Lock()

    logs = []  # newest first
    logs_lock = threading.Lock()

    def snapshot_loop():
        nonlocal latest
        while True:
            try:
                s = env_to_display.get()
                payload = {
                    "ok": True,
                    "tick": int(getattr(s, "tick", 0)),
                    "predators": int(getattr(s, "predators", 0)),
                    "preys": int(getattr(s, "preys", 0)),
                    "grass": int(getattr(s, "grass", 0)),
                    "drought": bool(getattr(s, "drought", False)),
                    "prey_energy": {
                        "min": float(getattr(s, "prey_energy_stats", (0, 0, 0))[0]),
                        "avg": float(getattr(s, "prey_energy_stats", (0, 0, 0))[1]),
                        "max": float(getattr(s, "prey_energy_stats", (0, 0, 0))[2]),
                    },
                    "pred_energy": {
                        "min": float(getattr(s, "predator_energy_stats", (0, 0, 0))[0]),
                        "avg": float(getattr(s, "predator_energy_stats", (0, 0, 0))[1]),
                        "max": float(getattr(s, "predator_energy_stats", (0, 0, 0))[2]),
                    },
                    "prey_probs": {"eat": float(getattr(s, "prey_probs", (0, 0))[0]), "repro": float(getattr(s, "prey_probs", (0, 0))[1])},
                    "pred_probs": {"hunt": float(getattr(s, "pred_probs", (0, 0))[0]), "repro": float(getattr(s, "pred_probs", (0, 0))[1])},
                }
                with latest_lock:
                    latest = payload
            except Exception:
                pass

    def log_loop():
        nonlocal logs
        while True:
            try:
                line = log_to_display.get()
                with logs_lock:
                    logs.insert(0, str(line))
                    if len(logs) > 200:
                        logs = logs[:200]
            except Exception:
                pass

    threading.Thread(target=snapshot_loop, daemon=True).start()
    threading.Thread(target=log_loop, daemon=True).start()

    INDEX_HTML = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Circle of Life</title>
<style>
:root{
  --bg1:#06140e;
  --bg2:#0b2a1d;
  --bg3:#14532d;
  --card: rgba(255,255,255,0.08);
  --border: rgba(255,255,255,0.18);
  --text: #ecfdf5;
  --muted: rgba(236,253,245,0.7);
}
body{
  font-family: Arial, sans-serif;
  margin:0;
  padding: 18px;
  min-height:100vh;
  background: linear-gradient(135deg, var(--bg1), var(--bg2), var(--bg3));
  color: var(--text);
}
h1{margin:0 0 8px;}
.small{color:var(--muted); font-size:12px;}
.grid{display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:14px 0;}
.box{background:var(--card); border:1px solid var(--border); border-radius:10px; padding:12px;}
.label{font-size:12px; color:var(--muted);}
.value{font-size:20px; font-weight:bold; margin-top:4px;}
.row{display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin:10px 0;}
button,input{padding:8px 10px; border-radius:8px; border:1px solid var(--border); background:rgba(255,255,255,0.08); color:var(--text);}
button{cursor:pointer; font-weight:bold;}
button:hover{background:rgba(255,255,255,0.18);}
button.primary{border-color: rgba(52,211,153,0.6);}
button.warn{border-color: rgba(245,158,11,0.7);}
button.danger{border-color: rgba(239,68,68,0.7);}
#log{
  white-space:pre-wrap;
  background:rgba(0,0,0,0.25);
  border:1px solid var(--border);
  border-radius:10px;
  padding:10px;
  max-height:260px;
  overflow:auto;
  font-family: monospace;
  font-size:12px;
  color: var(--muted);
}
@media(max-width:900px){ .grid{grid-template-columns:repeat(2,1fr);} }
</style>
</head>
<body>
  <h1>Circle of Life (Live)</h1>
  <div class="small">Refresh 200 ms. Display talks to env via queue only.</div>

  <div class="grid">
    <div class="box">
      <div class="label">Tick</div>
      <div class="value" id="tick">-</div>
      <div class="small">Mode: <span id="mode">-</span></div>
    </div>
    <div class="box">
      <div class="label">Grass</div>
      <div class="value" id="grass">-</div>
    </div>
    <div class="box">
      <div class="label">Preys</div>
      <div class="value" id="preys">-</div>
      <div class="small">Energy (min/avg/max): <span id="preyE">-</span></div>
      <div class="small">Eat: <span id="preyEatP">-</span>% | Repro: <span id="preyRepP">-</span>%</div>
    </div>
    <div class="box">
      <div class="label">Predators</div>
      <div class="value" id="preds">-</div>
      <div class="small">Energy (min/avg/max): <span id="predE">-</span></div>
      <div class="small">Hunt: <span id="predHuntP">-</span>% | Repro: <span id="predRepP">-</span>%</div>
    </div>
  </div>

  <h3>Controls</h3>
  <div class="row">
  <button class="btn-warn" onclick="sendCmd('trigger_drought')">🌵 Sécheresse (signal)</button>
    <button class="primary" onclick="sendCmd('add_prey',{value:1})">+1 prey</button>
    <button class="primary" onclick="sendCmd('add_predator',{value:1})">+1 predator</button>
    <button class="danger" onclick="sendCmd('reset')">Reset</button>
  </div>

  <h3>Logs</h3>
  <div id="log"></div>

<script>
"use strict";

const logEl = document.getElementById('log');

async function sendCmd(cmd, args){
  try{
    const res = await fetch('/api/cmd', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({cmd: cmd, args: args || {}})
    });
    await res.json();
  }catch(e){}
}

async function refresh(){
  try{
    const res = await fetch('/api/state', {cache:'no-store'});
    const s = await res.json();

    if(!s || !s.ok){
      document.getElementById('mode').textContent = 'waiting...';
      return;
    }
    document.getElementById('tick').textContent = s.tick;
    document.getElementById('grass').textContent = s.grass;
    document.getElementById('preys').textContent = s.preys;
    document.getElementById('preds').textContent = s.predators;

    document.getElementById('mode').textContent = s.drought ? 'DROUGHT' : 'NORMAL';

    const pe = s.prey_energy || {min:0, avg:0, max:0};
    const pr = s.pred_energy || {min:0, avg:0, max:0};

    document.getElementById('preyE').textContent =
      `${Number(pe.min).toFixed(0)} / ${Number(pe.avg).toFixed(1)} / ${Number(pe.max).toFixed(0)}`;
    document.getElementById('predE').textContent =
      `${Number(pr.min).toFixed(0)} / ${Number(pr.avg).toFixed(1)} / ${Number(pr.max).toFixed(0)}`;

    const pp = s.prey_probs || {eat:0, repro:0};
    const dp = s.pred_probs || {hunt:0, repro:0};

    document.getElementById('preyEatP').textContent = Math.round(Number(pp.eat) * 100);
    document.getElementById('preyRepP').textContent = Math.round(Number(pp.repro) * 100);
    document.getElementById('predHuntP').textContent = Math.round(Number(dp.hunt) * 100);
    document.getElementById('predRepP').textContent = Math.round(Number(dp.repro) * 100);

    if (Array.isArray(s.logs)) logEl.textContent = s.logs.join("\\n");
  }catch(e){}
}

setInterval(refresh, 200);
refresh();
</script>
</body>
</html>
"""

    INDEX_HTML = INDEX_HTML.replace("\ufeff", "")

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, content_type="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            else:
                body = json.dumps({"ok": False, "error": "invalid response"}).encode("utf-8")

            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index.html"):
                self._send(200, INDEX_HTML, content_type="text/html")
                return

            if self.path.startswith("/api/state"):
                with latest_lock:
                    payload = dict(latest)
                with logs_lock:
                    payload["logs"] = list(logs)
                self._send(200, payload)
                return

            self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if self.path != "/api/cmd":
                self._send(404, {"ok": False, "error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                raw = raw.lstrip("\ufeff")
                data = json.loads(raw)

                cmd = data.get("cmd")
                args = data.get("args", {}) or {}
                if not isinstance(cmd, str):
                    self._send(400, {"ok": False, "error": "cmd must be a string"})
                    return
                if not isinstance(args, dict):
                    self._send(400, {"ok": False, "error": "args must be an object"})
                    return

                display_to_env.put(DisplayCommand(cmd=cmd, args=args))
                self._send(200, {"ok": True})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

    server = HTTPServer((host, port), Handler)
    print(f"WEB: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.server_close()
        except Exception:
            pass
