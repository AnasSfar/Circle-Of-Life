# web_display.py
# Simple local HTML dashboard + JSON API for the Circle of Life simulation (LOCAL)
#  - GET  /           -> HTML page
#  - GET  /api/state  -> latest snapshot + logs as JSON
#  - POST /api/cmd    -> send command to env via display_to_env queue

import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from ipc import DisplayCommand


def run_web_display(shared_state, env_to_display, display_to_env, log_to_display, host="127.0.0.1", port=8000):
    latest = {"ok": False, "reason": "no snapshot yet"}
    latest_lock = threading.Lock()

    def _extract_probs(obj, kind: str):
        if kind == "prey":
            if isinstance(obj, (tuple, list)) and len(obj) >= 2:
                return {"eat": float(obj[0]), "repro": float(obj[1])}
            if isinstance(obj, dict):
                return {"eat": float(obj.get("eat", 0.0)), "repro": float(obj.get("repro", 0.0))}
            return {"eat": 0.0, "repro": 0.0}
        # predator
        if isinstance(obj, (tuple, list)) and len(obj) >= 2:
            return {"hunt": float(obj[0]), "repro": float(obj[1])}
        if isinstance(obj, dict):
            return {"hunt": float(obj.get("hunt", 0.0)), "repro": float(obj.get("repro", 0.0))}
        return {"hunt": 0.0, "repro": 0.0}

    def snapshot_loop():
        nonlocal latest
        while shared_state.get("running", False):
            try:
                while True:
                    s = env_to_display.get_nowait()

                    prey_min, prey_avg, prey_max = getattr(s, "prey_energy_stats", (0.0, 0.0, 0.0))
                    pred_min, pred_avg, pred_max = getattr(s, "predator_energy_stats", (0.0, 0.0, 0.0))

                    prey_probs = _extract_probs(getattr(s, "prey_probs", None), "prey")
                    pred_probs = _extract_probs(getattr(s, "pred_probs", None), "pred")

                    payload = {
                        "ok": True,
                        "tick": int(getattr(s, "tick", 0)),
                        "predators": int(getattr(s, "predators", 0)),
                        "preys": int(getattr(s, "preys", 0)),
                        "grass": int(getattr(s, "grass", 0)),
                        "drought": bool(getattr(s, "drought", False)),
                        "prey_energy": {"min": float(prey_min), "avg": float(prey_avg), "max": float(prey_max)},
                        "pred_energy": {"min": float(pred_min), "avg": float(pred_avg), "max": float(pred_max)},
                        "prey_probs": prey_probs,
                        "pred_probs": pred_probs,
                    }

                    with latest_lock:
                        latest = payload
            except Exception:
                pass
            time.sleep(0.05)

    threading.Thread(target=snapshot_loop, daemon=True).start()

    logs = []  # newest first
    logs_lock = threading.Lock()

    def log_loop():
        nonlocal logs
        while shared_state.get("running", False):
            try:
                while True:
                    line = log_to_display.get_nowait()
                    with logs_lock:
                        logs.insert(0, str(line))
                        if len(logs) > 200:
                            logs = logs[:200]
            except Exception:
                pass
            time.sleep(0.05)

    threading.Thread(target=log_loop, daemon=True).start()

    INDEX_HTML = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Circle of Life (Local)</title>
<style>
  :root{
    --bg1:#0f2027;
    --bg2:#203a43;
    --bg3:#2c5364;
    --card: rgba(255,255,255,0.08);
    --border: rgba(255,255,255,0.18);
    --text: #f1f5f9;
    --muted: rgba(241,245,249,0.7);
  }

  body{
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
    min-height: 100vh;
    background: linear-gradient(135deg, var(--bg1), var(--bg2), var(--bg3));
    color: var(--text);
  }

  h1, h3{ margin-top: 0; }
  .small{ color: var(--muted); font-size: 12px; }

  .grid{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 15px 0;
  }

  .box{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px;
  }

  .label{
    font-size: 12px;
    color: var(--muted);
  }

  .value{
    font-size: 20px;
    font-weight: bold;
    margin-top: 4px;
  }

  .row{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    margin: 10px 0;
  }

  button, input{
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.08);
    color: var(--text);
    outline: none;
  }

  input{
    width: 120px;
  }

  button{
    cursor: pointer;
    font-weight: bold;
  }

  button:hover{
    background: rgba(255,255,255,0.18);
  }

  button.primary{
    border-color: rgba(52,211,153,0.6);
  }

  button.warn{
    border-color: rgba(245,158,11,0.7);
  }

  button.danger{
    border-color: rgba(239,68,68,0.7);
  }

  #log{
    white-space: pre-wrap;
    background: rgba(0,0,0,0.25);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px;
    max-height: 260px;
    overflow: auto;
    font-family: monospace;
    font-size: 12px;
    color: var(--muted);
  }

  @media (max-width: 900px){
    .grid{
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>

</head>
<body>
  <h1>Circle of Life (Live)</h1>
  <div class="small">Rafraichissement toutes les 200 ms.</div>

  <div class="grid">
    <div class="box">
      <div class="label">Tick</div>
      <div class="value" id="tick">-</div>
      <div class="small">Etat: <span id="mode">-</span></div>
    </div>

    <div class="box">
      <div class="label">Herbe</div>
      <div class="value" id="grass">-</div>
    </div>

    <div class="box">
      <div class="label">Proies</div>
      <div class="value" id="preys">-</div>
      <div class="small">Energie (min/avg/max): <span id="preyE">-</span></div>
      <div class="small">Manger: <span id="preyEatP">-</span>% | Repro: <span id="preyRepP">-</span>%</div>
    </div>

    <div class="box">
      <div class="label">Predateurs</div>
      <div class="value" id="preds">-</div>
      <div class="small">Energie (min/avg/max): <span id="predE">-</span></div>
      <div class="small">Chasse: <span id="predHuntP">-</span>% | Repro: <span id="predRepP">-</span>%</div>
    </div>
  </div>

  <h3>Controles</h3>
  <div class="row">
    <button class="warn" onclick="sendCmd('drought_on')">Secheresse ON</button>
    <button class="primary" onclick="sendCmd('drought_off')">Normal</button>
    <span class="small">Herbe:</span>
    <input id="grassInput" type="number" value="100" min="0" />
    <button class="primary" onclick="setGrass()">Appliquer</button>
  </div>

  <div class="row">
    <button class="primary" onclick="sendCmd('add_prey',{value:1})">+1 proie</button>
    <span class="small">Ajouter X:</span>
    <input id="preyAddInput" type="number" value="1" min="1" />
    <button class="primary" onclick="addPreys()">Ajouter</button>

    <span style="width:20px;"></span>

    <button class="primary" onclick="sendCmd('add_predator',{value:1})">+1 predateur</button>
    <span class="small">Ajouter X:</span>
    <input id="predAddInput" type="number" value="1" min="1" />
    <button class="primary" onclick="addPreds()">Ajouter</button>
  </div>

  <div class="row">
    <button class="danger" onclick="sendCmd('reset')">Reset</button>
  </div>

  <h3>Journal</h3>
  <div id="log"></div>

<script>
"use strict";

const logEl = document.getElementById('log');

function pushLocalLog(line){
  const ts = new Date().toLocaleTimeString('fr-FR', {hour12:false});
  logEl.textContent = `[${ts}] ${line}` + String.fromCharCode(10) + (logEl.textContent || '');
}

async function sendCmd(cmd, args){
  try{
    const res = await fetch('/api/cmd', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({cmd, args: args || {}})
    });
    const data = await res.json();
    if(!data.ok){
      pushLocalLog(`Erreur cmd: ${data.error || 'unknown'}`);
    }
  }catch(e){
    pushLocalLog(`Erreur reseau (cmd): ${e}`);
  }
}

function setGrass(){
  const v = parseInt(document.getElementById('grassInput').value, 10);
  if(Number.isFinite(v) && v >= 0) sendCmd('set_grass', {value:v});
}

function addPreys(){
  const v = parseInt(document.getElementById('preyAddInput').value, 10);
  if(Number.isFinite(v) && v > 0) sendCmd('add_prey', {value:v});
}

function addPreds(){
  const v = parseInt(document.getElementById('predAddInput').value, 10);
  if(Number.isFinite(v) && v > 0) sendCmd('add_predator', {value:v});
}

async function refresh(){
  try{
    const res = await fetch('/api/state', {cache:'no-store'});
    const s = await res.json();

    if(!s || !s.ok){
      document.getElementById('mode').textContent = 'en attente...';
      return;
    }

    document.getElementById('tick').textContent = s.tick;
    document.getElementById('grass').textContent = s.grass;
    document.getElementById('preys').textContent = s.preys;
    document.getElementById('preds').textContent = s.predators;

    document.getElementById('mode').textContent = s.drought ? 'SECHERESSE' : 'Normal';

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

    if (Array.isArray(s.logs)) {
      logEl.textContent = s.logs.join(String.fromCharCode(10));
    }
  }catch(e){
    pushLocalLog(`Erreur refresh: ${e}`);
  }
}

setInterval(refresh, 200);
refresh();
</script>

</body>
</html>
"""

    # Remove BOM / invisible chars that can break JS parsing (your original error)
    INDEX_HTML = (
        INDEX_HTML
        .replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
    )

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