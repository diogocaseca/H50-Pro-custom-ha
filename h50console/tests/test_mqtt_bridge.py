"""Testes da ponte MQTT. Rodam no estágio `test` do Dockerfile, com o código do painel (já com os patches) em /src."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

import mqtt_bridge as mb
from h50console import catalog

ROBOT = {"id": "sala", "name": "Robô da sala", "model": "xiaomi.vacuum.ov42gl", "did": "123456"}
STATE = {"health": {"online": True}, "status": 4, "status_label": "Limpando", "battery": 87,
         "values": {"2/2": 4, "3/1": 87, "3/2": 2, "2/9": 3, "2/4": 3, "2/10": 2, "2/89": 40, "2/6": 1234, "2/7": 600,
                    "2/3": 0, "2/97": 1, "2/98": 0, "12/1": 90, "13/1": 80, "14/1": 70, "9/1": 60, "18/1": 50,
                    "19/1": None}}
ROOMS = [{"id": 3, "name": "Sala", "last_clean": None}, {"id": 5, "name": "Cozinha", "last_clean": None}]


class Mapping(unittest.TestCase):
    def test_every_panel_status_has_an_explicit_ha_state(self):
        self.assertEqual(set(mb.HA_STATE), set(catalog.STATUS))
        self.assertTrue(set(mb.HA_STATE.values()) <= {"cleaning", "docked", "paused", "idle", "returning", "error"})
        self.assertEqual(mb.ha_state(None), "error")

    def test_labels_and_props_match_the_panel_catalog(self):
        self.assertEqual(mb.FAN_SPEED, catalog.ENUM_PT["2/9"])
        self.assertEqual(mb.CLEAN_MODE, catalog.ENUM_PT["2/4"])
        self.assertEqual(mb.WATER_LEVEL, catalog.ENUM_PT["2/10"])
        for item, (prop, _) in mb.CONSUMABLES.items():
            self.assertEqual(prop, catalog.CONSUMABLE_PROPS[item][0])
        self.assertTrue(mb.SEND_ACTIONS <= set(catalog.SIMPLE_ACTIONS))
        self.assertFalse(set(mb.BUTTONS) & catalog.LEAVES_BASE)          # botões não tiram o robô da base
        for key, *_ in mb.SELECTS.values():
            self.assertIn(key, {k for k, _, _ in catalog.SETTINGS})

    def test_vacuum_and_attrs_payloads(self):
        self.assertEqual(mb.vacuum_payload(STATE, ROOMS),
                         {"state": "cleaning", "fan_speed": "Intenso", "segments": {"3": "Sala", "5": "Cozinha"}})
        a = mb.attrs_payload(STATE)
        self.assertEqual((a["battery"], a["charging"], a["progress"], a["area"], a["duration"], a["fault"]),
                         (87, False, 40, 12.34, 600, "Nenhuma"))
        self.assertEqual((a["dirty_tank_full"], a["clean_tank_empty"]), (True, False))
        self.assertEqual((a["clean_mode"], a["water_level"], a["suction"]), ("Aspirando e esfregando", "Nível 2", "Intenso"))
        self.assertEqual(a["consumables"]["main_brush"], 90)
        self.assertIsNone(a["consumables"]["dust_bag"])
        idle = mb.attrs_payload({"status": 2, "values": {"2/89": -1, "3/2": 1, "2/3": 210013}})
        self.assertEqual((idle["progress"], idle["charging"], idle["fault"], idle["battery"]), (None, True, "210013", None))
        self.assertNotIn("fan_speed", mb.vacuum_payload({"status": 2, "values": {}}, []))

    def test_discovery(self):
        object_id, p = mb.discovery(ROBOT, "0.2.0")
        self.assertEqual(object_id, "h50console_123456")
        self.assertEqual(p["dev"]["ids"], ["h50console_123456"])
        self.assertEqual((p["o"]["sw"], p["dev"]["name"]), ("0.2.0", "Robô da sala"))
        cmps = p["cmps"]
        ids = [c["uniq_id"] for c in cmps.values()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all("p" in c for c in cmps.values()))
        v = cmps["vacuum"]
        self.assertEqual((v["p"], v["stat_t"], v["cmd_t"]), ("vacuum", "h50console/sala/vacuum", "h50console/sala/cmd/vacuum"))
        self.assertEqual(v["fan_spd_lst"], ["Silencioso", "Padrão", "Intenso", "Turbo"])
        self.assertEqual(v["clean_segments_command_topic"], "h50console/sala/cmd/segments")
        self.assertEqual(v["avty_mode"], "all")
        self.assertEqual(cmps["online"]["avty_t"], mb.BRIDGE_STATUS)       # conectividade não some com o robô
        self.assertEqual(cmps["clean_mode"]["ops"][0], "Aspirando")
        s = cmps["suction"]
        self.assertEqual((s["p"], s["ent_cat"], s["cmd_t"], s["ops"]),
                         ("select", "config", "h50console/sala/cmd/select/suction", ["Silencioso", "Padrão", "Intenso", "Turbo"]))
        self.assertEqual(s["val_tpl"], "{{ value_json.suction }}")
        self.assertEqual(json.loads(json.dumps(p)), p)
        self.assertEqual(mb.discovery({"id": "x"})[0], "h50console_x")    # sem DID: id do painel


class Commands(unittest.TestCase):
    def calls(self, sub, payload, status=None):
        return mb.command_calls("sala", sub, payload, status)

    def test_vacuum_commands(self):
        a = "/api/r/sala/actions/"
        self.assertEqual(self.calls("vacuum", "start"), [("POST", a + "start", None)])
        self.assertEqual(self.calls("vacuum", "start", mb.PAUSED), [("POST", a + "resume", None)])
        for ha, panel in (("pause", "pause"), ("stop", "stop"), ("return_to_base", "home"), ("locate", "locate"),
                          ("clean_spot", "spot")):
            self.assertEqual(self.calls("vacuum", ha), [("POST", a + panel, None)])
        with self.assertRaises(mb.CommandError):
            self.calls("vacuum", "explodir")

    def test_settings_buttons_and_rooms(self):
        self.assertEqual(self.calls("fan_speed", "Turbo"), [("PUT", "/api/r/sala/settings/2-9", {"value": 4})])
        self.assertEqual(self.calls("fan_speed", "turbo")[0][2], {"value": 4})
        self.assertEqual(self.calls("select/water_level", "Nível 3"), [("PUT", "/api/r/sala/settings/2-10", {"value": 3})])
        self.assertEqual(self.calls("select/clean_mode", "Esfregando")[0][2], {"value": 2})
        self.assertEqual(self.calls("select/suction", "Turbo"), [("PUT", "/api/r/sala/settings/2-9", {"value": 4})])
        self.assertEqual(self.calls("button/dust", "PRESS"), [("POST", "/api/r/sala/actions/dust", None)])
        self.assertEqual(self.calls("segments", '["3", "5"]'), [("POST", "/api/r/sala/clean/rooms", {"ids": [3, 5]})])
        for sub, payload in (("fan_speed", "Máximo"), ("select/x", "a"), ("button/start", "PRESS"),
                             ("segments", "[]"), ("segments", "sala"), ("outra", "x")):
            with self.assertRaises(mb.CommandError, msg=(sub, payload)):
                self.calls(sub, payload)

    def test_send_command(self):
        self.assertEqual(self.calls("send", "wash-mop"), [("POST", "/api/r/sala/actions/wash-mop", None)])
        self.assertEqual(self.calls("send", '{"command": "clean_rooms", "rooms": [3, "5"]}'),
                         [("POST", "/api/r/sala/clean/rooms", {"ids": [3, 5]})])
        self.assertEqual(self.calls("send", '{"command": "custom", "id": 2}'),
                         [("POST", "/api/r/sala/clean/custom/2", None)])
        for bad in ("raw", '{"command": "clean_rooms"}', '{"command": "custom"}', "[1]", '{"command": "build-map"}'):
            with self.assertRaises(mb.CommandError, msg=bad):
                self.calls("send", bad)


class FakeApi:
    def __init__(self):
        self.robots = [dict(ROBOT)]
        self.state = json.loads(json.dumps(STATE))
        self.calls = []
        self.fail = None

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method != "GET":
            if self.fail:
                raise mb.ApiError(409, self.fail)
            return {"ok": True}
        if path == "/api/robots":
            return self.robots
        if path.endswith("/rooms"):
            return ROOMS
        if path.endswith("/state"):
            return self.state
        raise mb.ApiError(404, path)

    def events(self, path, stop):
        stop.wait(0.05)
        return iter(())


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.api, self.out = FakeApi(), []
        self.bridge = mb.Bridge(self.api, lambda t, p, r: self.out.append((t, p, r)), "homeassistant",
                                Path(self.tmp.name) / "mqtt-robots.json", "0.2.0")
        self.addCleanup(self.bridge.stop.set)

    def published(self):
        d = {}
        for t, p, _ in self.out:
            d[t] = p
        return d

    def test_connect_announces_and_publishes_state(self):
        self.bridge.on_connect()
        self.bridge.tick()
        pub = self.published()
        self.assertEqual(pub[mb.BRIDGE_STATUS], "online")
        disc = json.loads(pub["homeassistant/device/h50console_123456/config"])
        self.assertIn("vacuum", disc["cmps"])
        self.assertEqual(json.loads(pub["h50console/sala/vacuum"])["state"], "cleaning")
        self.assertEqual(json.loads(pub["h50console/sala/attrs"])["battery"], 87)
        self.assertEqual(pub["h50console/sala/availability"], "online")
        self.assertTrue(all(r for _, _, r in self.out))                  # tudo retido
        # sem mudança, nada é republicado
        n = len(self.out)
        self.bridge.dirty.add("sala")
        self.bridge.tick()
        self.assertEqual(len(self.out), n)
        # mudança de bateria: só o attrs sai de novo
        self.api.state["battery"] = 86
        self.bridge.dirty.add("sala")
        self.bridge.tick()
        self.assertEqual([t for t, _, _ in self.out[n:]], ["h50console/sala/attrs"])

    def test_offline_robot_and_removed_robot(self):
        self.bridge.on_connect()
        self.bridge.tick()
        self.api.state["health"]["online"] = False
        self.bridge.dirty.add("sala")
        self.bridge.tick()
        self.assertEqual(self.published()["h50console/sala/availability"], "offline")
        # removido no painel (mesmo com a ponte reiniciada): descoberta e estados apagados
        self.api.robots = []
        fresh = mb.Bridge(self.api, lambda t, p, r: self.out.append((t, p, r)), "homeassistant",
                          Path(self.tmp.name) / "mqtt-robots.json")
        self.addCleanup(fresh.stop.set)
        fresh.on_connect()
        pub = self.published()
        self.assertEqual(pub["homeassistant/device/h50console_123456/config"], "")
        self.assertEqual(pub["h50console/sala/attrs"], "")

    def test_commands_go_to_the_panel(self):
        self.bridge.on_connect()
        self.bridge.tick()
        self.bridge.handle("h50console/sala/cmd/vacuum", "return_to_base")
        self.assertIn(("POST", "/api/r/sala/actions/home", None), self.api.calls)
        self.api.state["status"] = mb.PAUSED
        self.bridge.dirty.add("sala")
        self.bridge.tick()
        self.bridge.handle("h50console/sala/cmd/vacuum", "start")
        self.assertEqual(self.api.calls[-1], ("POST", "/api/r/sala/actions/resume", None))
        n = len(self.api.calls)
        self.api.fail = "robô ocupado"
        with self.assertLogs("h50console.mqtt", "WARNING"):
            self.bridge.handle("h50console/sala/cmd/button/dust", "PRESS")    # recusa do painel: só log
            self.bridge.handle("h50console/outro/cmd/vacuum", "start")        # robô desconhecido
            self.bridge.handle("h50console/sala/cmd/vacuum", "voar")          # comando inválido
        self.assertEqual(len([c for c in self.api.calls[n:] if c[0] != "GET"]), 1)

    def test_home_assistant_restart_republishes_discovery(self):
        self.bridge.on_connect()
        self.bridge.tick()
        n = len(self.out)
        self.bridge.handle("homeassistant/status", "online")
        self.assertIn("homeassistant/device/h50console_123456/config", [t for t, _, _ in self.out[n:]])


class BrokerChoice(unittest.TestCase):
    SERVICE = {"host": "core-mosquitto", "port": 1883, "ssl": False, "username": "addons", "password": "s"}

    def test_supervisor_host_not_resolvable_falls_back_to_localhost(self):
        b = mb.choose_broker({"port": 1883}, self.SERVICE, can_resolve=lambda h: False)
        self.assertEqual((b["host"], b["port"], b["username"], b["password"], b["source"]),
                         ("127.0.0.1", 1883, "addons", "s", "Supervisor"))
        b = mb.choose_broker({"port": 1883}, self.SERVICE, can_resolve=lambda h: True)
        self.assertEqual(b["host"], "core-mosquitto")

    def test_options_win_over_the_supervisor(self):
        b = mb.choose_broker({"port": 1884, "username": "robo", "password": "x"}, self.SERVICE, can_resolve=lambda h: False)
        self.assertEqual((b["host"], b["port"], b["username"], b["password"], b["source"]),
                         ("127.0.0.1", 1884, "robo", "x", "opções do app"))
        b = mb.choose_broker({"host": "10.0.0.5", "port": 1883, "username": "u", "password": "p"}, None)
        self.assertEqual((b["host"], b["username"], b["ssl"]), ("10.0.0.5", "u", False))

    def test_nothing_configured(self):
        b = mb.choose_broker({}, None)
        self.assertEqual((b["host"], b["port"], b["username"], b["source"]), ("127.0.0.1", 1883, "", "nenhuma"))


class PanelIntegration(unittest.TestCase):
    """PanelApi contra o servidor real do painel, com H50_API_TOKEN (patch 0005)."""

    def test_token_and_sse(self):
        from h50console.fleet import Fleet
        from h50console.hub import Hub
        from h50console.web import make_server
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        from h50console.auth import Auth
        fleet = Fleet(tmp.name, None, start_threads=False)
        hub = Hub(fleet, None)
        token = "k" * 40
        srv = make_server(hub, "127.0.0.1", 0, auth=Auth(tmp.name, iters=1000), ingress=True, ingress_only=True,
                          api_token=token)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        port = srv.server_address[1]
        self.assertEqual(mb.PanelApi(port, token).call("GET", "/api/robots"), [])
        with self.assertRaises(mb.ApiError) as ctx:
            mb.PanelApi(port, "x" * 40).call("GET", "/api/robots")
        self.assertEqual(ctx.exception.status, 401)
        stop = threading.Event()
        got = []

        def listen():
            for event, data in mb.PanelApi(port, token).events("/api/stream", stop):
                got.append((event, data))
                stop.set()
        th = threading.Thread(target=listen, daemon=True)
        th.start()
        import time
        for _ in range(50):                       # espera o assinante entrar no barramento
            if hub.bus.subscribers:
                break
            time.sleep(0.05)
        hub.bus.publish("robots", {"added": "sala"})
        th.join(5)
        self.assertEqual(got, [("robots", {"added": "sala"})])


if __name__ == "__main__":
    unittest.main()
