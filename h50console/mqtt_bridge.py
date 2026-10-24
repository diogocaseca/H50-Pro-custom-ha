"""Ponte MQTT do app do Home Assistant: publica cada robô do H50 Console como dispositivo do HA (MQTT discovery).

Só conversa com a API HTTP do painel em 127.0.0.1 (token de H50_API_TOKEN), como o servidor MCP do projeto: o painel
continua sendo o único que fala com o robô (rede local), então valem a fila de prioridade, os bloqueios de segurança e o
registro de comandos dele. Nada aqui toca no robô nem na nuvem Xiaomi.

    painel  --(SSE /api/r/<id>/stream + GET /state)-->  ponte  --(MQTT)-->  Home Assistant
    painel  <--(POST/PUT na API)--  ponte  <--(MQTT, tópicos cmd/)--  Home Assistant

As funções de mapeamento (estado, discovery, comandos) são puras e testadas sem broker nem painel; o cliente MQTT
(paho-mqtt) só existe na imagem do app.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("h50console.mqtt")

BASE = "h50console"                          # raiz dos tópicos de estado e comando
BRIDGE_STATUS = f"{BASE}/bridge/status"      # online/offline da ponte (LWT)
ORIGIN = {"name": "H50 Console (app do Home Assistant)", "url": "https://github.com/diogocaseca/H50-Pro-custom-ha"}

# 2/2 (status do robô) -> estado do vacuum no HA
HA_STATE = {
    **dict.fromkeys((4, 10, 16, 17, 18), "cleaning"),
    **dict.fromkeys((6, 19, 20, 21, 24), "returning"),
    5: "paused",
    **dict.fromkeys((2, 3, 7, 9, 12, 14, 22, 23), "docked"),
    15: "error",
    **dict.fromkeys((1, 8, 11, 13), "idle"),
}
PAUSED = 5
# 2/2 -> "Limpeza em andamento": liga no início e só desliga no fim, mesmo com idas à base no meio da limpeza
SESSION_ON = {4, 16, 17, 5, 3, 19, 20}      # limpando, pausado, carregando/voltando para retomar, voltando no meio
SESSION_KEEP = {7, 12, 13}                  # lavando o mop, base trabalhando, trocando de tarefa: antes, no meio ou depois

# Enums usados nas entidades (mesmos textos do painel: catalog.ENUM_PT; um teste confere que não divergiram)
FAN_SPEED = {1: "Silencioso", 2: "Padrão", 3: "Intenso", 4: "Turbo"}                                       # 2/9
CLEAN_MODE = {1: "Aspirando", 3: "Aspirando e esfregando", 4: "Aspirar antes de esfregar", 2: "Esfregando"}  # 2/4
WATER_LEVEL = {0: "Desligada", 1: "Nível 1", 2: "Nível 2", 3: "Nível 3"}                                    # 2/10
CLEAN_ROUTE = {1: "Rápido", 2: "Padrão", 3: "Profunda"}                                                    # 2/74
CLEAN_TIMES = {1: "Uma vez", 2: "Duas vezes"}       # 2/8: o painel e o app Xiaomi Home só oferecem 1 ou 2 passadas
SELECTS = {"suction": ("2/9", "Potência de sucção", FAN_SPEED, "mdi:fan"),
           "clean_mode": ("2/4", "Modo de limpeza", CLEAN_MODE, "mdi:broom"),
           "water_level": ("2/10", "Nível de água do mop", WATER_LEVEL, "mdi:water"),
           "clean_route": ("2/74", "Caminho", CLEAN_ROUTE, "mdi:map-marker-path"),
           "clean_times": ("2/8", "Tempos de limpeza", CLEAN_TIMES, "mdi:repeat")}
CONSUMABLES = {  # item -> (prop de %, nome)
    "main_brush": ("12/1", "Escova principal"), "side_brush": ("13/1", "Escova lateral"), "filter": ("14/1", "Filtro"),
    "mop": ("9/1", "Mop"), "dust_bag": ("19/1", "Saco de pó"),
}
# componentes que já foram anunciados e saíram: vão só com a plataforma, que é como o HA remove a entidade de um
# dispositivo (discovery por dispositivo). Ficam aqui para quem atualiza de uma versão antiga.
REMOVED = {"consumable_detergent": "sensor"}      # o H50 Pro não tem reservatório de detergente (0.3.4)
# botões da base (ações simples do painel que não tiram o robô da base)
BUTTONS = {"dust": ("Esvaziar o pó", "mdi:delete-empty"), "wash-mop": ("Lavar o mop", "mdi:water-sync"),
           "dry": ("Secar o mop", "mdi:fan"), "stop-wash": ("Parar a lavagem", "mdi:water-off"),
           "stop-dry": ("Parar a secagem", "mdi:fan-off"), "self-clean-base": ("Autolimpeza da base", "mdi:shimmer")}
# vacuum.send_command: comandos simples aceitos (ações do painel)
SEND_ACTIONS = {"start", "stop", "home", "pause", "resume", "sweep", "mop", "sweep-mop", "sweep-then-mop", "spot",
                "locate", "charge", *BUTTONS}
VACUUM_COMMANDS = {"stop": "stop", "pause": "pause", "return_to_base": "home", "locate": "locate", "clean_spot": "spot"}


class CommandError(ValueError):
    """Comando do HA que não dá para traduzir (vai para o log, não derruba a ponte)."""


# -- mapeamento puro ---------------------------------------------------------------------------------------------
def ha_state(status) -> str:
    return HA_STATE.get(status, "idle" if status is not None else "error")


def cleaning_session(status, previous: bool | None, progress=None) -> bool:
    """Limpeza em andamento? Nos status ambíguos vale o valor anterior; sem anterior (ponte reiniciou), o progresso
    da limpeza (2/89 = -1 quando não há limpeza). Status desconhecido (robô fora do ar) também mantém o anterior."""
    if status in SESSION_ON:
        return True
    if status in SESSION_KEEP or status is None:
        if previous is not None:
            return previous
        return status is not None and isinstance(_num(progress), (int, float)) and progress >= 0
    return False


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def vacuum_payload(state: dict, rooms: list[dict]) -> dict:
    v = state.get("values") or {}
    out = {"state": ha_state(state.get("status")), "segments": {str(r["id"]): r["name"] for r in rooms}}
    if v.get("2/9") in FAN_SPEED:
        out["fan_speed"] = FAN_SPEED[v["2/9"]]
    return out


def attrs_payload(state: dict, cleaning: bool = False) -> dict:
    """Valores das demais entidades (sensores, seletores): um JSON só, lido por value_template."""
    v = state.get("values") or {}
    progress = _num(v.get("2/89"))
    area = _num(v.get("2/6"))
    fault = v.get("2/3")
    return {
        "status": state.get("status_label"),
        "battery": _num(state.get("battery")),
        "charging": v.get("3/2") == 1,
        "cleaning": cleaning,
        "progress": progress if progress is None or progress >= 0 else None,      # -1 = sem limpeza
        "area": None if area is None else round(area / 100, 2),                   # 2/6 vem em 0,01 m²
        "duration": _num(v.get("2/7")),
        "drying_progress": _num(v.get("2/88")),                                   # secagem dos mops (base)
        "drying_left": _num(v.get("2/90")),                                       # minutos restantes da secagem
        "fault": None if fault is None else ("Nenhuma" if fault == 0 else str(fault)),
        "dirty_tank_full": bool(v.get("2/97")),
        "clean_tank_empty": bool(v.get("2/98")),
        "suction": FAN_SPEED.get(v.get("2/9")),
        "clean_mode": CLEAN_MODE.get(v.get("2/4")),
        "water_level": WATER_LEVEL.get(v.get("2/10")),
        "clean_route": CLEAN_ROUTE.get(v.get("2/74")),
        "clean_times": CLEAN_TIMES.get(v.get("2/8")),
        "consumables": {item: _num(v.get(p)) for item, (p, _) in CONSUMABLES.items()},
    }


def topics(rid: str) -> dict:
    t = f"{BASE}/{rid}"
    return {"availability": f"{t}/availability", "vacuum": f"{t}/vacuum", "attrs": f"{t}/attrs", "cmd": f"{t}/cmd"}


def device_key(robot: dict) -> str:
    """Identificador estável do dispositivo no HA: o DID do robô (não muda ao renomear); sem DID, o id do painel."""
    return f"h50console_{robot.get('did') or robot['id']}"


def discovery(robot: dict, version: str = "") -> tuple[str, dict]:
    """(object_id, payload) da descoberta por dispositivo (homeassistant/device/<object_id>/config)."""
    rid, key = robot["id"], device_key(robot)
    t = topics(rid)
    avail = [{"t": BRIDGE_STATUS}, {"t": t["availability"]}]
    common = {"avty": avail, "avty_mode": "all"}
    attr = lambda name: f"{{{{ value_json.{name} }}}}"     # noqa: E731

    cmps: dict[str, dict] = {
        "vacuum": {"p": "vacuum", "name": None, "uniq_id": f"{key}_vacuum", **common,
                   "stat_t": t["vacuum"], "cmd_t": f"{t['cmd']}/vacuum", "send_cmd_t": f"{t['cmd']}/send",
                   "set_fan_spd_t": f"{t['cmd']}/fan_speed", "fan_spd_lst": list(FAN_SPEED.values()),
                   "clean_segments_command_topic": f"{t['cmd']}/segments",
                   "sup_feat": ["start", "stop", "pause", "return_home", "status", "locate", "clean_spot",
                                "fan_speed", "send_command"]},
        "battery": {"p": "sensor", "name": "Bateria", "uniq_id": f"{key}_battery", **common, "stat_t": t["attrs"],
                    "val_tpl": attr("battery"), "dev_cla": "battery", "unit_of_meas": "%", "stat_cla": "measurement"},
        "status": {"p": "sensor", "name": "Status", "uniq_id": f"{key}_status", **common, "stat_t": t["attrs"],
                   "val_tpl": attr("status"), "ic": "mdi:robot-vacuum"},
        "progress": {"p": "sensor", "name": "Progresso da limpeza", "uniq_id": f"{key}_progress", **common,
                     "stat_t": t["attrs"], "val_tpl": attr("progress"), "unit_of_meas": "%", "ic": "mdi:progress-clock"},
        "area": {"p": "sensor", "name": "Área limpa", "uniq_id": f"{key}_area", **common, "stat_t": t["attrs"],
                 "val_tpl": attr("area"), "unit_of_meas": "m²", "ic": "mdi:texture-box"},
        "duration": {"p": "sensor", "name": "Tempo de limpeza", "uniq_id": f"{key}_duration", **common,
                     "stat_t": t["attrs"], "val_tpl": attr("duration"), "dev_cla": "duration", "unit_of_meas": "s"},
        "drying_progress": {"p": "sensor", "name": "Progresso da secagem", "uniq_id": f"{key}_drying_progress", **common,
                            "stat_t": t["attrs"], "val_tpl": attr("drying_progress"), "unit_of_meas": "%",
                            "stat_cla": "measurement", "ic": "mdi:fan-clock"},
        "drying_left": {"p": "sensor", "name": "Secagem restante", "uniq_id": f"{key}_drying_left", **common,
                        "stat_t": t["attrs"], "val_tpl": attr("drying_left"), "dev_cla": "duration",
                        "unit_of_meas": "min", "ic": "mdi:timer-sand"},
        "fault": {"p": "sensor", "name": "Falha", "uniq_id": f"{key}_fault", **common, "stat_t": t["attrs"],
                  "val_tpl": attr("fault"), "ic": "mdi:alert-circle-outline"},
        "charging": {"p": "binary_sensor", "name": "Carregando", "uniq_id": f"{key}_charging", **common,
                     "stat_t": t["attrs"], "val_tpl": "{{ 'ON' if value_json.charging else 'OFF' }}",
                     "dev_cla": "battery_charging"},
        "cleaning": {"p": "binary_sensor", "name": "Limpeza em andamento", "uniq_id": f"{key}_cleaning", **common,
                     "stat_t": t["attrs"], "val_tpl": "{{ 'ON' if value_json.cleaning else 'OFF' }}",
                     "dev_cla": "running", "ic": "mdi:robot-vacuum-variant"},
        "dirty_tank_full": {"p": "binary_sensor", "name": "Tanque de água suja cheio", "uniq_id": f"{key}_dirty_tank",
                            **common, "stat_t": t["attrs"], "dev_cla": "problem",
                            "val_tpl": "{{ 'ON' if value_json.dirty_tank_full else 'OFF' }}"},
        "clean_tank_empty": {"p": "binary_sensor", "name": "Tanque de água limpa vazio", "uniq_id": f"{key}_clean_tank",
                             **common, "stat_t": t["attrs"], "dev_cla": "problem",
                             "val_tpl": "{{ 'ON' if value_json.clean_tank_empty else 'OFF' }}"},
        # conectividade com o robô: só depende da ponte (senão ficaria "indisponível" justamente quando importa)
        "online": {"p": "binary_sensor", "name": "Conectado pela rede local", "uniq_id": f"{key}_online",
                   "avty_t": BRIDGE_STATUS, "stat_t": t["availability"], "pl_on": "online", "pl_off": "offline",
                   "dev_cla": "connectivity", "ent_cat": "diagnostic"},
    }
    for item, (_, name) in CONSUMABLES.items():
        cmps[f"consumable_{item}"] = {
            "p": "sensor", "name": name, "uniq_id": f"{key}_consumable_{item}", **common, "stat_t": t["attrs"],
            "val_tpl": f"{{{{ value_json.consumables.{item} }}}}", "unit_of_meas": "%", "ic": "mdi:progress-wrench",
            "ent_cat": "diagnostic"}
    for cid, platform in REMOVED.items():
        cmps[cid] = {"p": platform}
    for sid, (_, name, options, icon) in SELECTS.items():
        cmps[sid] = {"p": "select", "name": name, "uniq_id": f"{key}_{sid}", **common, "stat_t": t["attrs"],
                     "val_tpl": attr(sid), "cmd_t": f"{t['cmd']}/select/{sid}", "ops": list(options.values()),
                     "ic": icon, "ent_cat": "config"}
    for action, (name, icon) in BUTTONS.items():
        cmps[f"button_{action}"] = {"p": "button", "name": name, "uniq_id": f"{key}_button_{action}", **common,
                                    "cmd_t": f"{t['cmd']}/button/{action}", "ic": icon}

    device = {"ids": [key], "name": robot.get("name") or rid, "mf": "Xiaomi", "mdl": robot.get("model") or "H50 Pro"}
    payload = {"dev": device, "o": {**ORIGIN, **({"sw": version} if version else {})}, "cmps": cmps,
               "qos": 1}
    return key, payload


def command_calls(rid: str, sub: str, payload: str, status=None) -> list[tuple[str, str, dict | None]]:
    """Comando recebido em h50console/<rid>/cmd/<sub> -> chamadas (método, caminho, corpo) à API do painel."""
    r = f"/api/r/{rid}"
    payload = payload.strip()

    def action(name: str):
        return [("POST", f"{r}/actions/{name}", None)]

    if sub == "vacuum":
        if payload == "start":
            return action("resume" if status == PAUSED else "start")
        if payload in VACUUM_COMMANDS:
            return action(VACUUM_COMMANDS[payload])
        raise CommandError(f"comando de vacuum desconhecido: {payload!r}")
    if sub == "fan_speed":
        code = _code(FAN_SPEED, payload, "potência")
        return [("PUT", f"{r}/settings/2-9", {"value": code})]
    if sub.startswith("select/"):
        sid = sub.split("/", 1)[1]
        if sid not in SELECTS:
            raise CommandError(f"seletor desconhecido: {sid}")
        key, name, options, _ = SELECTS[sid]
        return [("PUT", f"{r}/settings/{key.replace('/', '-')}", {"value": _code(options, payload, name)})]
    if sub.startswith("button/"):
        name = sub.split("/", 1)[1]
        if name not in BUTTONS:
            raise CommandError(f"botão desconhecido: {name}")
        return action(name)
    if sub == "segments":
        try:
            ids = [int(i) for i in json.loads(payload)]
        except (ValueError, TypeError) as ex:
            raise CommandError(f"lista de cômodos inválida: {payload!r}") from ex
        if not ids:
            raise CommandError("nenhum cômodo escolhido")
        return [("POST", f"{r}/clean/rooms", {"ids": ids})]
    if sub == "send":
        return _send_command(r, payload)
    raise CommandError(f"tópico de comando desconhecido: {sub}")


def _code(options: dict, label: str, what: str) -> int:
    for code, text in options.items():
        if text.casefold() == label.casefold() or str(code) == label:
            return code
    raise CommandError(f"{what} desconhecido(a): {label!r} (opções: {', '.join(options.values())})")


def _send_command(r: str, payload: str):
    """vacuum.send_command: texto puro (ação) ou JSON {"command": ..., <parâmetros>} (formato do MQTT vacuum do HA)."""
    try:
        msg = json.loads(payload)
    except ValueError:
        msg = payload
    if isinstance(msg, str):
        msg = {"command": msg}
    if not isinstance(msg, dict) or not isinstance(msg.get("command"), str):
        raise CommandError(f"send_command inválido: {payload!r}")
    cmd = msg["command"].strip()
    if cmd in SEND_ACTIONS:
        return [("POST", f"{r}/actions/{cmd}", None)]
    if cmd == "clean_rooms":
        rooms = msg.get("rooms")
        if not isinstance(rooms, list) or not rooms:
            raise CommandError('clean_rooms precisa de "rooms": [ids]')
        try:
            return [("POST", f"{r}/clean/rooms", {"ids": [int(i) for i in rooms]})]
        except (ValueError, TypeError) as ex:
            raise CommandError(f"ids de cômodos inválidos: {rooms!r}") from ex
    if cmd == "custom":
        try:
            return [("POST", f"{r}/clean/custom/{int(msg.get('id'))}", None)]
        except (ValueError, TypeError) as ex:
            raise CommandError('custom precisa de "id": <número da rotina>') from ex
    raise CommandError(f"send_command desconhecido: {cmd!r} (use clean_rooms, custom ou uma ação: "
                       f"{', '.join(sorted(SEND_ACTIONS))})")


# -- API do painel -------------------------------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class PanelApi:
    """Cliente da API do painel em 127.0.0.1, com o token de administrador local (H50_API_TOKEN)."""

    def __init__(self, port: int, token: str, timeout: float = 20.0):
        self.host, self.port, self.timeout = "127.0.0.1", port, timeout
        self.headers = {"Authorization": f"Bearer {token}", "X-H50": "1", "User-Agent": "h50console-mqtt"}

    def call(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://{self.host}:{self.port}{path}", data=data, method=method,
                                     headers={**self.headers, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as ex:
            try:
                msg = json.loads(ex.read()).get("error") or ex.reason
            except (ValueError, AttributeError):
                msg = ex.reason
            raise ApiError(ex.code, str(msg)) from None

    def events(self, path: str, stop: threading.Event):
        """Eventos SSE (nome, dados) até a conexão cair ou `stop`. O painel manda ': ping' a cada 15 s."""
        conn = http.client.HTTPConnection(self.host, self.port, timeout=45)
        try:
            conn.request("GET", path, headers=self.headers)
            resp = conn.getresponse()
            if resp.status != 200:
                raise ApiError(resp.status, resp.reason)
            event, data = None, []
            while not stop.is_set():
                line = resp.fp.readline()
                if not line:
                    return
                line = line.decode("utf-8", "replace").rstrip("\r\n")
                if not line:
                    if event:
                        try:
                            yield event, json.loads("\n".join(data)) if data else None
                        except ValueError:
                            yield event, None
                    event, data = None, []
                elif line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data.append(line[5:].strip())
        finally:
            conn.close()


# -- ponte -------------------------------------------------------------------------------------------------------
class Bridge:
    """Sincroniza os robôs do painel com o MQTT. `publish(topic, payload, retain)` é injetado (paho ou falso nos testes)."""

    REFRESH_EVERY = 60.0      # estado completo, mesmo sem eventos
    RESYNC_EVERY = 300.0      # lista de robôs e cômodos
    DEBOUNCE = 0.5

    def __init__(self, api, publish, prefix: str = "homeassistant", state_file: Path | None = None, version: str = ""):
        self.api, self.publish, self.prefix, self.version = api, publish, prefix.strip("/"), version
        self.state_file = state_file
        self.robots: dict[str, dict] = {}          # id -> resumo da API (/api/robots)
        self.rooms: dict[str, list[dict]] = {}
        self.status: dict[str, object] = {}        # último 2/2 de cada robô (para "start" virar "resume")
        self.cleaning: dict[str, bool] = {}        # "Limpeza em andamento" de cada robô
        self.dirty: set[str] = set()
        self.sent: dict[str, str] = {}             # tópico -> último payload (só publica o que mudou)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.streams: dict[str, threading.Event] = {}
        self._last_refresh = self._last_resync = 0.0
        self.connected = False

    # -- publicação
    def _pub(self, topic: str, payload, retain: bool = True, force: bool = False) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self.lock:
            if not force and self.sent.get(topic) == text:
                return
            self.sent[topic] = text
        self.publish(topic, text, retain)

    def discovery_topic(self, object_id: str) -> str:
        return f"{self.prefix}/device/{object_id}/config"

    def _published_keys(self) -> dict[str, str]:
        """Robôs anunciados antes (sobrevive a reinícios: um robô removido com a ponte parada sai do HA depois)."""
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8")) if self.state_file else {}
        except (OSError, ValueError):
            return {}

    def _save_keys(self, keys: dict[str, str]) -> None:
        if self.state_file:
            try:
                self.state_file.write_text(json.dumps(keys), encoding="utf-8")
            except OSError as ex:
                log.warning("não consegui gravar %s: %s", self.state_file, ex)

    # -- ciclo
    def on_connect(self) -> None:
        """Conectou (ou reconectou) ao broker: anuncia tudo de novo."""
        self.connected = True
        with self.lock:
            self.sent.clear()
        self._pub(BRIDGE_STATUS, "online")
        self.sync_robots()

    def on_ha_online(self) -> None:
        """O HA reiniciou (homeassistant/status = online): reenvia descoberta e estados."""
        with self.lock:
            self.sent = {k: v for k, v in self.sent.items() if not k.startswith(self.prefix + "/")}
            self.dirty.update(self.robots)
        self.sync_robots()

    def sync_robots(self) -> None:
        robots = {r["id"]: r for r in self.api.call("GET", "/api/robots")}
        old = self._published_keys()
        keys = {rid: device_key(r) for rid, r in robots.items()}
        for rid, key in old.items():
            if rid not in robots or keys.get(rid) != key:          # removido (ou trocou de DID): sai do HA
                log.info("removendo do HA o robô %s", rid)
                self._pub(self.discovery_topic(key), "", force=True)
                if rid not in robots:
                    for name in ("availability", "vacuum", "attrs"):
                        self._pub(topics(rid)[name], "", force=True)
        with self.lock:
            self.robots = robots
            self.dirty.update(robots)
        for rid, robot in robots.items():
            object_id, payload = discovery(robot, self.version)
            self._pub(self.discovery_topic(object_id), payload)
            self._load_rooms(rid)
        self._save_keys(keys)
        self._last_resync = time.monotonic()
        self._sync_streams()

    def _load_rooms(self, rid: str) -> None:
        try:
            self.rooms[rid] = [{"id": r["id"], "name": r["name"]} for r in self.api.call("GET", f"/api/r/{rid}/rooms")]
        except (ApiError, OSError, KeyError, TypeError) as ex:
            log.debug("cômodos de %s indisponíveis: %s", rid, ex)
            self.rooms.setdefault(rid, [])

    def refresh(self, rid: str) -> None:
        try:
            state = self.api.call("GET", f"/api/r/{rid}/state")
        except (ApiError, OSError) as ex:
            log.debug("estado de %s indisponível: %s", rid, ex)
            self._pub(topics(rid)["availability"], "offline")
            return
        online = bool((state.get("health") or {}).get("online")) and state.get("status") is not None
        self.status[rid] = state.get("status")
        cleaning = cleaning_session(state.get("status") if online else None, self.cleaning.get(rid),
                                    (state.get("values") or {}).get("2/89"))
        if cleaning != self.cleaning.get(rid, False):
            log.info("robô %s: limpeza %s", rid, "começou" if cleaning else "terminou")
        self.cleaning[rid] = cleaning
        t = topics(rid)
        self._pub(t["vacuum"], vacuum_payload(state, self.rooms.get(rid, [])))
        self._pub(t["attrs"], attrs_payload(state, cleaning))
        self._pub(t["availability"], "online" if online else "offline")

    def handle(self, topic: str, payload: str) -> None:
        """Mensagem MQTT recebida (comando do HA ou birth message do HA)."""
        if topic == f"{self.prefix}/status":
            if payload.strip() == "online":
                log.info("Home Assistant voltou: reenviando a descoberta")
                self.on_ha_online()
            return
        parts = topic.split("/", 3)                    # h50console/<rid>/cmd/<sub>
        if len(parts) < 4 or parts[0] != BASE or parts[2] != "cmd":
            return
        rid, sub = parts[1], parts[3]
        if rid not in self.robots:
            log.warning("comando para robô desconhecido: %s", rid)
            return
        try:
            calls = command_calls(rid, sub, payload, self.status.get(rid))
        except CommandError as ex:
            log.warning("comando ignorado (%s): %s", topic, ex)
            return
        for method, path, body in calls:
            log.info("comando do HA: %s %s %s", method, path, json.dumps(body, ensure_ascii=False) if body else "")
            try:
                self.api.call(method, path, body)
            except (ApiError, OSError) as ex:
                log.warning("o painel recusou %s %s: %s", method, path, ex)
                break
        with self.lock:
            self.dirty.add(rid)

    # -- SSE: um fluxo por robô (estado ao vivo) e o da conta (robôs adicionados/removidos)
    def _sync_streams(self) -> None:
        wanted = {f"/api/r/{rid}/stream": rid for rid in self.robots} | {"/api/stream": None}
        for path, ev in list(self.streams.items()):
            if path not in wanted:
                ev.set()
                del self.streams[path]
        for path, rid in wanted.items():
            if path not in self.streams:
                ev = threading.Event()
                self.streams[path] = ev
                threading.Thread(target=self._stream_loop, args=(path, rid, ev), daemon=True,
                                 name=f"sse{path}").start()

    def _stream_loop(self, path: str, rid: str | None, stop: threading.Event) -> None:
        delay = 1.0
        while not (stop.is_set() or self.stop.is_set()):
            try:
                for event, _ in self.api.events(path, stop):
                    delay = 1.0
                    if rid is None:
                        if event == "robots":
                            self._want_resync = True
                    elif event in ("state", "online", "offline", "command", "cleaning", "fault"):
                        with self.lock:
                            self.dirty.add(rid)
                    elif event in ("map", "mapdata"):
                        self._load_rooms(rid)
                        with self.lock:
                            self.dirty.add(rid)
            except (ApiError, OSError) as ex:
                log.debug("fluxo %s caiu: %s", path, ex)
            stop.wait(delay)
            delay = min(delay * 2, 30.0)

    _want_resync = False

    def tick(self) -> None:
        """Um passo do laço principal (separado para os testes)."""
        now = time.monotonic()
        if self._want_resync or now - self._last_resync > self.RESYNC_EVERY:
            self._want_resync = False
            self.sync_robots()
        if now - self._last_refresh > self.REFRESH_EVERY:
            self._last_refresh = now
            with self.lock:
                self.dirty.update(self.robots)
        with self.lock:
            todo, self.dirty = self.dirty & set(self.robots), set()
        for rid in todo:
            self.refresh(rid)

    def run(self) -> None:
        while not self.stop.is_set():
            if self.connected:
                try:
                    self.tick()
                except (ApiError, OSError) as ex:
                    log.warning("painel indisponível: %s", ex)
                    self.stop.wait(5)
                except Exception:  # noqa: BLE001  (a ponte nunca derruba o app)
                    log.exception("erro inesperado na ponte MQTT")
                    self.stop.wait(5)
            self.stop.wait(self.DEBOUNCE)


# -- broker (Supervisor ou opções do app) e cliente MQTT --------------------------------------------------------------
LOCAL_BROKER = "127.0.0.1"     # o app Mosquitto publica a 1883 no host; com host_network o app enxerga por aqui


def supervisor_mqtt() -> dict | None:
    """Dados do broker MQTT do HA (app Mosquitto), pela API do Supervisor (config.yaml: services mqtt:want)."""
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        return None
    req = urllib.request.Request("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read()).get("data") or {}
    except (urllib.error.URLError, OSError, ValueError) as ex:
        log.debug("Supervisor sem serviço MQTT: %s", ex)
        return None
    return data if data.get("host") else None


def resolvable(host: str) -> bool:
    import socket
    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


def choose_broker(manual: dict, service: dict | None, can_resolve=resolvable) -> dict:
    """Broker a usar. `manual` = opções do app (mqtt_host, mqtt_port, mqtt_user, mqtt_password; vazio = automático);
    `service` = o que o Supervisor informa sobre o app Mosquitto (ou None).

    Usuário e senha das opções têm prioridade sobre os do Supervisor. O host do Supervisor é o nome do container do
    Mosquitto (core-mosquitto), que um app com rede do host não resolve: nesse caso vale 127.0.0.1."""
    service = service or {}
    b = {"host": manual.get("host") or service.get("host") or "", "port": int(manual.get("port") or 1883),
         "username": service.get("username") or "", "password": service.get("password") or "",
         "ssl": bool(service.get("ssl")) and not manual.get("host"),
         "source": "opções do app" if manual.get("username") else ("Supervisor" if service else "nenhuma")}
    if manual.get("username"):
        b["username"], b["password"] = manual["username"], manual.get("password") or ""
    if not manual.get("host") and (not b["host"] or not can_resolve(b["host"])):
        b["host"], b["ssl"] = LOCAL_BROKER, False
    return b


def wait_panel(api: PanelApi, stop: threading.Event, timeout: float = 120.0) -> bool:
    end = time.monotonic() + timeout
    while not stop.is_set() and time.monotonic() < end:
        try:
            api.call("GET", "/api/robots")
            return True
        except (ApiError, OSError):
            stop.wait(1)
    return False


def run_bridge(port: int, token: str, prefix: str, data_dir: Path, stop: threading.Event, version: str = "",
               manual: dict | None = None) -> None:
    """Liga a ponte e fica nela até `stop`. Falhas de broker ou painel só geram log e novas tentativas."""
    import paho.mqtt.client as mqtt

    manual = manual or {}
    api = PanelApi(port, token)
    if not wait_panel(api, stop):
        log.error("ponte MQTT: o painel não respondeu em 127.0.0.1:%s; ponte desligada", port)
        return
    service = None
    for _ in range(1 if manual.get("username") else 3):        # o Mosquitto pode ainda estar subindo
        service = supervisor_mqtt()
        if service or stop.wait(10):
            break
    if stop.is_set():
        return
    broker = choose_broker(manual, service)
    log.info("ponte MQTT: broker %s:%s, usuário %s (credenciais: %s)", broker["host"], broker["port"],
             repr(broker["username"]) if broker["username"] else "nenhum", broker["source"])
    if not broker["username"]:
        log.warning("ponte MQTT: sem usuário do broker. O app Mosquitto recusa conexões anônimas: preencha mqtt_user e "
                    "mqtt_password (um usuário do HA ou um login do Mosquitto)")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"h50console-{os.getpid()}")
    if broker["username"]:
        client.username_pw_set(broker["username"], broker["password"] or None)
    if broker["ssl"]:
        client.tls_set()
    client.will_set(BRIDGE_STATUS, "offline", qos=1, retain=True)
    client.reconnect_delay_set(1, 60)

    def publish(topic, payload, retain):
        client.publish(topic, payload, qos=1, retain=retain)

    bridge = Bridge(api, publish, prefix, data_dir / "mqtt-robots.json", version)
    bridge.stop = stop

    def on_connect(c, _userdata, _flags, reason, _props=None):
        if reason.is_failure:
            failures["n"] += 1
            if failures["n"] in (1, 5) or failures["n"] % 30 == 0:     # sem inundar o log
                text = str(reason).lower()
                hint = " (confira mqtt_user e mqtt_password)" if "authori" in text or "password" in text else ""
                log.warning("ponte MQTT: broker recusou a conexão: %s%s (tentativa %d)", reason, hint, failures["n"])
            return
        failures["n"] = 0
        log.info("ponte MQTT conectada a %s:%s (descoberta em %s/device/...)", broker["host"], broker.get("port"), prefix)
        c.subscribe([(f"{BASE}/+/cmd/#", 1), (f"{bridge.prefix}/status", 1)])
        try:
            bridge.on_connect()
        except (ApiError, OSError) as ex:
            log.warning("ponte MQTT: painel indisponível ao anunciar: %s", ex)

    failures = {"n": 0}

    def on_connect_fail(_c, _userdata):
        failures["n"] += 1
        if failures["n"] in (1, 5) or failures["n"] % 30 == 0:     # sem inundar o log
            log.warning("ponte MQTT: não consegui conectar a %s:%s (tentativa %d); confira host e porta do broker",
                        broker["host"], broker["port"], failures["n"])

    def on_disconnect(_c, _userdata, _flags, reason, _props=None):
        was_connected, bridge.connected = bridge.connected, False
        if was_connected and not stop.is_set():
            log.warning("ponte MQTT desconectada (%s); reconectando…", reason)

    def on_message(_c, _userdata, msg):
        threading.Thread(target=bridge.handle, args=(msg.topic, msg.payload.decode("utf-8", "replace")),
                         daemon=True).start()       # comandos podem demorar (fila do robô); não segura o paho

    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message
    client.on_connect_fail = on_connect_fail
    client.connect_async(broker["host"], broker["port"], keepalive=60)
    client.loop_start()
    try:
        bridge.run()
    finally:
        try:
            client.publish(BRIDGE_STATUS, "offline", qos=1, retain=True).wait_for_publish(2)
        except Exception:  # noqa: BLE001
            pass
        client.disconnect()
        client.loop_stop()
