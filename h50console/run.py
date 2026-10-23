"""Inicialização do app do Home Assistant: lê /data/options.json e sobe o painel em modo Ingress.

Em Python (e não em shell) para repassar as senhas sem problemas de aspas ou caracteres especiais.
"""

import json
import os
import sys

OPTIONS = os.environ.get("H50_OPTIONS", "/data/options.json")

try:
    with open(OPTIONS, encoding="utf-8") as f:
        opts = json.load(f)
except (OSError, ValueError) as ex:
    sys.exit(f"não consegui ler {OPTIONS}: {ex}")

env = dict(os.environ)
env.update({
    "H50_DATA_DIR": "/data",           # persistente e no backup do HA
    "H50_HOST": "0.0.0.0",
    "H50_PORT": "8050",
    "H50_INGRESS": "true",
    "H50_LOG_LEVEL": str(opts.get("log_level") or "info").upper(),
    "H50_CLOUD_COUNTRY": str(opts.get("cloud_region") or "auto"),   # auto = o painel descobre o servidor
})
if not opts.get("direct_access"):
    env["H50_INGRESS_ONLY"] = "true"   # rede do host: sem isto a porta 8050 ficaria aberta na LAN
for opt, var in (("password", "H50_PASSWORD"), ("viewer_password", "H50_VIEWER_PASSWORD")):
    if opts.get(opt):
        env[var] = str(opts[opt])
    else:
        env.pop(var, None)

print(f"H50 Console: Ingress ligado; acesso direto pela porta 8050 {'LIGADO (exige senha)' if opts.get('direct_access') else 'desligado'}",
      flush=True)
os.chdir("/data")                      # o app lê um .env opcional da pasta atual: nunca o da imagem
os.execvpe(sys.executable, [sys.executable, "-m", "h50console"], env)
