# web_display.py
# Live HTML dashboard + JSON API for the Circle of Life simulation

import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from ipc import DisplayCommand


def run_web_display(shared_state, env_to_display, display_to_env, log_to_display, host="127.0.0.1", port=8000):
    """
    Live HTML dashboard + JSON API.
      - GET  /           -> HTML page
      - GET  /api/state  -> latest snapshot as JSON
      - POST /api/cmd    -> send command to env via display_to_env queue
    """
    latest = {"ok": False, "reason": "no snapshot yet"}

    def snapshot_loop():
        nonlocal latest
        while shared_state.get("running", False):
            try:
                while True:
                    s = env_to_display.get_nowait()
                    prey_min, prey_avg, prey_max = getattr(s, "prey_energy_stats", (0, 0, 0))
                    pred_min, pred_avg, pred_max = getattr(s, "predator_energy_stats", (0, 0, 0))
                    latest = {
                        "ok": True,
                        "tick": s.tick,
                        "predators": s.predators,
                        "preys": s.preys,
                        "grass": s.grass,
                        "drought": s.drought,
                        "prey_energy": {"min": float(prey_min), "avg": float(prey_avg), "max": float(prey_max)},
                        "pred_energy": {"min": float(pred_min), "avg": float(pred_avg), "max": float(pred_max)},
                    }
            except Exception:
                pass
            time.sleep(0.05)

    threading.Thread(target=snapshot_loop, daemon=True).start()

    logs = []  
    def log_loop():
        nonlocal logs
        while shared_state.get("running", False):
            try:
                while True:
                    line = log_to_display.get_nowait()
                    logs.insert(0, line)
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
  <title>Circle of Life - Live</title>
  <style>
    :root{
      --bg1:#071a12;
      --bg2:#0b2a1d;
      --card: rgba(255,255,255,.08);
      --cardBorder: rgba(255,255,255,.14);
      --text:#ecfdf5;
      --muted: rgba(236,253,245,.72);
      --accent:#34d399;
      --warn:#f59e0b;
      --danger:#ef4444;
      --shadow: 0 12px 40px rgba(0,0,0,.35);
    }

    body{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin:0;
      color: var(--text);
      min-height:100vh;
      background:
        radial-gradient(1200px 700px at 20% 10%, rgba(52,211,153,.16), transparent 55%),
        radial-gradient(1000px 600px at 90% 30%, rgba(34,197,94,.14), transparent 60%),
        linear-gradient(160deg, var(--bg1), var(--bg2));
    }

    .wrap{
      max-width: 1100px;
      margin: 0 auto;
      padding: 22px;
    }

    h1{
      margin: 8px 0 14px;
      font-size: 26px;
      letter-spacing: .2px;
    }

    h2{
      margin: 18px 0 10px;
      font-size: 16px;
      color: var(--muted);
      font-weight: 650;
      letter-spacing: .2px;
      text-transform: uppercase;
    }

    .row{
      display:flex;
      gap:14px;
      flex-wrap:wrap;
      align-items:stretch;
    }

    .card{
      background: var(--card);
      border: 1px solid var(--cardBorder);
      border-radius: 16px;
      padding: 14px 14px 12px;
      min-width: 250px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }

    .big{
      font-size: 20px;
      font-weight: 780;
      display:flex;
      align-items:center;
      gap:8px;
    }

    .muted{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.3;
    }

    .badge{
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,.16);
      background: rgba(255,255,255,.06);
      font-size: 12px;
      color: var(--muted);
      vertical-align: middle;
    }

    .badge.ok{
      border-color: rgba(52,211,153,.35);
      background: rgba(52,211,153,.10);
      color: #bbf7d0;
    }

    .badge.warn{
      border-color: rgba(245,158,11,.45);
      background: rgba(245,158,11,.12);
      color: #fde68a;
    }

    .controls{
      display:flex;
      gap:10px;
      flex-wrap:wrap;
      align-items:center;
      padding: 10px 0 4px;
    }

    button, input{
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,.18);
      background: rgba(255,255,255,.06);
      color: var(--text);
      outline: none;
    }

    input{
      width: 120px;
    }

    button{
      cursor:pointer;
      transition: transform .06s ease, background .15s ease, border-color .15s ease;
      font-weight: 650;
    }

    button:hover{
      background: rgba(255,255,255,.10);
      border-color: rgba(255,255,255,.26);
    }

    button:active{
      transform: translateY(1px);
    }

    .btn-primary{
      border-color: rgba(52,211,153,.35);
      background: rgba(52,211,153,.12);
    }

    .btn-warn{
      border-color: rgba(245,158,11,.45);
      background: rgba(245,158,11,.14);
    }

    .btn-danger{
      border-color: rgba(239,68,68,.55);
      background: rgba(239,68,68,.16);
    }

    #log{
      white-space: pre-wrap;
      background: rgba(0,0,0,.25);
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 16px;
      padding: 12px;
      max-height: 220px;
      overflow: auto;
      color: var(--muted);
      box-shadow: var(--shadow);
    }

    .footerNote{
      margin-top: 10px;
      color: rgba(236,253,245,.55);
      font-size: 12px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Circle of Life (Live)</h1>
    <h2>H = 30, R = 60</h2>
    <div class="row">
      <div class="card">
        <div class="big">Tick: <span id="tick">-</span></div>
        <div class="muted">État: <span id="mode" class="badge">-</span></div>
      </div>

      <div class="card">
        <div class="big">🌿 Herbe: <span id="grass">-</span></div>
        <div class="muted">Ressource globale de l'écosystème.</div>
      </div>

      <div class="card">
        <div class="big">🐇 Proies: <span id="preys">-</span></div>
        <div class="muted">Énergie (min/avg/max): <span id="preyE">-</span></div>
      </div>

      <div class="card">
        <div class="big">🦁 Prédateurs: <span id="preds">-</span></div>
        <div class="muted">Énergie (min/avg/max): <span id="predE">-</span></div>
      </div>
    </div>

    <h2>Contrôles</h2>
    <div class="controls">
      <button class="btn-warn" onclick="sendCmd('drought_on')">🌵 Sécheresse ON</button>
      <button class="btn-primary" onclick="sendCmd('drought_off')">🌱 Normal</button>

      <span class="muted" style="margin-left:6px;">Herbe:</span>
      <input id="grassInput" type="number" value="100" min="0" />
      <button class="btn-primary" onclick="setGrass()">Appliquer</button>

      <span class="muted" style="margin-left:6px;">Ajouter X proies:</span>
      <input id="preyAddInput" type="number" value="1" min="1" />
      <button class="btn-primary" onclick="addPreys()">Ajouter</button>

      <span class="muted" style="margin-left:6px;">Ajouter X prédateurs:</span>
      <input id="predAddInput" type="number" value="1" min="1" />
      <button class="btn-primary" onclick="addPreds()">Ajouter</button>

      <button class="btn-danger" onclick="sendCmd('reset')">Reset (état initial)</button>
      <button class="btn-danger" onclick="sendCmd('stop')">Stop</button>
    </div>

    <h2>Journal</h2>
    <div id="log"></div>
    <div class="footerNote">Actualisation automatique toutes les 200 ms.</div>
  </div>

<script>
  const logEl = document.getElementById('log');

  function log(msg){
    const t = new Date().toLocaleTimeString();
    logEl.textContent = `[${t}] ${msg}\\n` + logEl.textContent;
  }

  async function sendCmd(cmd, args){
    try{
      const res = await fetch('/api/cmd', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({cmd, args: args || {}})
      });
      const data = await res.json();
      if(data.ok) log(`Commande envoyée: ${cmd}`);
      else log(`Erreur cmd: ${data.error || 'unknown'}`);
    }catch(e){
      log(`Erreur réseau: ${e}`);
    }
  }

  function setGrass(){
    const v = parseInt(document.getElementById('grassInput').value, 10);
    if(Number.isFinite(v) && v >= 0) sendCmd('set_grass', {value:v});
    else log('Valeur herbe invalide');
  }

  function addPreys(){
    const v = parseInt(document.getElementById('preyAddInput').value, 10);
    if(Number.isFinite(v) && v > 0) sendCmd('add_prey', {value:v});
    else log('Valeur X proies invalide');
  }

  function addPreds(){
    const v = parseInt(document.getElementById('predAddInput').value, 10);
    if(Number.isFinite(v) && v > 0) sendCmd('add_predator', {value:v});
    else log('Valeur X prédateurs invalide');
  }

  async function refresh(){
  try{
    const res = await fetch('/api/state', {cache:'no-store'});
    const s = await res.json();
    if(!s.ok){
      const modeEl = document.getElementById('mode');
      modeEl.textContent = 'en attente…';
      modeEl.className = 'badge';
      return;
    }

    document.getElementById('tick').textContent = s.tick;
    document.getElementById('grass').textContent = s.grass;
    document.getElementById('preys').textContent = s.preys;
    document.getElementById('preds').textContent = s.predators;

    const modeEl = document.getElementById('mode');
    modeEl.textContent = s.drought ? 'SÉCHERESSE' : 'Normal';
    modeEl.className = s.drought ? 'badge warn' : 'badge ok';

    const pe = s.prey_energy;
    const pr = s.pred_energy;
    document.getElementById('preyE').textContent = `${pe.min.toFixed(0)} / ${pe.avg.toFixed(1)} / ${pe.max.toFixed(0)}`;
    document.getElementById('predE').textContent = `${pr.min.toFixed(0)} / ${pr.avg.toFixed(1)} / ${pr.max.toFixed(0)}`;

    if (Array.isArray(s.logs)) {
      logEl.textContent = s.logs.join("\n");
    }
  }catch(e){
    log(`Erreur refresh: ${e}`);
  }

  setInterval(refresh, 200);
  refresh();
</script>
</body>
</html>
"""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, content_type="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return  # silence

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index.html"):
                self._send(200, INDEX_HTML, content_type="text/html")
                return
            if self.path.startswith("/api/state"):
                payload = dict(latest)
                payload["logs"] = logs
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
    print(f"WEB: http://{host}:{port} (Ctrl+C pour arrêter)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.server_close()
        except Exception:
            pass
