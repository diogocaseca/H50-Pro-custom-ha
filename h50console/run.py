"""Inicialização do app do Home Assistant: lê /data/options.json e sobe o painel em modo Ingress.

Em Python (e não em shell) para repassar as senhas sem problemas de aspas ou caracteres especiais.
Com a opção `mqtt` ligada, este processo também roda a ponte MQTT (mqtt_bridge.py) e vigia o painel: se o painel
sair, o app sai junto (e o watchdog do HA reinicia); se a ponte falhar, ela só tenta de novo, sem derrubar o painel.
"""

import json
import logging
import os
import secrets
import signal
import subprocess
import sys
import threading
from pathlib import Path

sys.dont_write_bytecode = True        # nada de __pycache__ em /data (entra no backup do HA)
OPTIONS = os.environ.get("H50_OPTIONS", "/data/options.json")
PORT = 8050

# O s6-overlay da imagem base inicia o CMD com o ambiente reduzido; as variáveis do container (SUPERVISOR_TOKEN,
# H50_APP_VERSION...) ficam em arquivos, como o with-contenv faz para os scripts em shell.
_ENV_DIR = Path("/run/s6/container_environment")
if _ENV_DIR.is_dir():
    for _f in _ENV_DIR.iterdir():
        try:
            os.environ.setdefault(_f.name, _f.read_text(encoding="utf-8").split("\n", 1)[0])   # como o s6-envdir
        except (OSError, UnicodeDecodeError):
            pass

try:
    with open(OPTIONS, encoding="utf-8") as f:
        opts = json.load(f)
except (OSError, ValueError) as ex:
    sys.exit(f"não consegui ler {OPTIONS}: {ex}")

log_level = str(opts.get("log_level") or "info").upper()
env = dict(os.environ)
env.update({
    "H50_DATA_DIR": "/data",           # persistente e no backup do HA
    "H50_HOST": "0.0.0.0",
    "H50_PORT": str(PORT),
    "H50_INGRESS": "true",
    "H50_LOG_LEVEL": log_level,
    "H50_CLOUD_COUNTRY": str(opts.get("cloud_region") or "auto"),   # auto = o painel descobre o servidor
    # perfis pelo usuário do HA (panel_admin: false): admin do HA ou listado em admins = administrador; demais = others
    "H50_INGRESS_ADMINS": ",".join(str(a).strip() for a in (opts.get("admins") or []) if str(a).strip()),
    "H50_INGRESS_OTHERS": str(opts.get("others") or "operator"),
})
if not opts.get("direct_access"):
    env["H50_INGRESS_ONLY"] = "true"   # rede do host: sem isto a porta 8050 ficaria aberta na LAN
for opt, var in (("password", "H50_PASSWORD"), ("viewer_password", "H50_VIEWER_PASSWORD")):
    if opts.get(opt):
        env[var] = str(opts[opt])
    else:
        env.pop(var, None)
env.pop("H50_API_TOKEN", None)

print(f"H50 Console: Ingress ligado; acesso direto pela porta {PORT} {'LIGADO (exige senha)' if opts.get('direct_access') else 'desligado'}"
      f"; MQTT {'ligado' if opts.get('mqtt') else 'desligado'}", flush=True)
os.chdir("/data")                      # o app lê um .env opcional da pasta atual: nunca o da imagem
panel = [sys.executable, "-m", "h50console"]

if not opts.get("mqtt"):
    os.execvpe(sys.executable, panel, env)

# ---- painel + ponte MQTT ---------------------------------------------------------------------------------------------
logging.basicConfig(level=getattr(logging, log_level, logging.INFO), stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("h50console.mqtt")
env["H50_API_TOKEN"] = token = secrets.token_urlsafe(32)      # só a ponte conhece; muda a cada início, nunca vai a disco
proc = subprocess.Popen(panel, env=env)
stop = threading.Event()


def _forward(signum, _frame):
    stop.set()
    if proc.poll() is None:
        proc.send_signal(signum)


signal.signal(signal.SIGTERM, _forward)
signal.signal(signal.SIGINT, _forward)


def _bridge():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import mqtt_bridge
        mqtt_bridge.run_bridge(PORT, token, str(opts.get("mqtt_discovery_prefix") or "homeassistant"), Path("/data"),
                               stop, os.environ.get("H50_APP_VERSION", ""))
    except Exception:  # noqa: BLE001  (a ponte nunca derruba o painel)
        log.exception("a ponte MQTT parou por um erro; o painel continua funcionando")


bridge = threading.Thread(target=_bridge, name="mqtt", daemon=True)
bridge.start()
code = proc.wait()
stop.set()
bridge.join(5)                         # deixa a ponte avisar "offline" ao broker
sys.exit(code)
