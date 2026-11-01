# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Registro de la urna por API: checkpoints durante la votación, inclusión, observador y verificador."""
import importlib.util
import json
from pathlib import Path

import pytest

import registro
from helpers_api import clave_Y, crear_conv, emitir_token, votar

RAIZ = Path(__file__).parent.parent


def _script(nombre):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _votar_todos(api, cid, n, opciones=("a_favor", "en_contra", "abstencion")):
    """Emite y vota con n votantes; devuelve la lista de (r', s', opción)."""
    tokens = []
    for i in range(n):
        op = opciones[i % len(opciones)]
        R, s = emitir_token(api, cid, f"p{i}", op)
        assert votar(api, cid, op, R, s).status_code == 200
        tokens.append((R, s, op))
    return tokens


def _registro(api, cid):
    return api.client.get(f"/convocatorias/{cid}/registro").json()


def _cerrar(api, cid):
    assert api.client.patch(f"/convocatorias/{cid}/estado", headers=api.admin, json={"estado": "cerrada"}).status_code == 200


@pytest.fixture
def cada_dos(monkeypatch):
    monkeypatch.setenv("PANRAP_CHECKPOINT_CADA", "2")


def test_checkpoints_automaticos_por_lotes_y_al_cerrar(api, cada_dos):
    cid = crear_conv(api, [f"p{i}" for i in range(5)])
    assert _registro(api, cid)["checkpoints"] == []
    _votar_todos(api, cid, 5)
    reg = _registro(api, cid)
    assert [(c["seq"], c["n"]) for c in reg["checkpoints"]] == [(1, 2), (2, 4)]    # el 5.º aún sin sellar
    _cerrar(api, cid)
    reg = _registro(api, cid)
    assert [(c["seq"], c["n"]) for c in reg["checkpoints"]] == [(1, 2), (2, 4), (3, 5)]
    pub = bytes.fromhex(reg["log_pub_hex"])
    assert registro.verificar_cadena(cid, pub, reg["checkpoints"]) == []


def test_el_registro_no_revela_votos_ni_opciones_durante_la_votacion(api, cada_dos):
    cid = crear_conv(api, ["p0", "p1", "p2"])
    tokens = _votar_todos(api, cid, 2)
    texto = api.client.get(f"/convocatorias/{cid}/registro").text
    for R, s, op in tokens:
        assert R.hex() not in texto and s.hex() not in texto
    assert "a_favor" not in texto and "en_contra" not in texto
    assert api.client.get(f"/convocatorias/{cid}/urna").status_code == 400            # la urna sigue sin publicarse


def test_clave_del_registro_distinta_de_la_de_firma(api):
    cid = crear_conv(api, ["a"], estado="programada")
    d = api.client.get(f"/convocatorias/{cid}").json()
    assert len(d["log_pub_hex"]) == 66 and d["log_pub_hex"] != d["emisor_pub_hex"]
    assert _registro(api, cid)["log_pub_hex"] == d["log_pub_hex"]


def test_urna_completa_verifica_registro_y_detecta_manipulaciones(api, cada_dos):
    cid = crear_conv(api, [f"p{i}" for i in range(5)])
    _votar_todos(api, cid, 5)
    _cerrar(api, cid)
    Y, ver = clave_Y(api, cid), _script("verificador_independiente")
    urna = api.client.get(f"/convocatorias/{cid}/urna").json()
    assert all(v["lote"] in (1, 2, 3) for v in urna["votos"])
    assert ver.verificar_urna(urna, Y, cid)["problemas_registro"] == []
    # votos de un mismo lote salen ordenados por r' (no por llegada)
    for lote in (1, 2, 3):
        rs = [v["r_prima"] for v in urna["votos"] if v["lote"] == lote]
        assert rs == sorted(rs)
    retirado = json.loads(json.dumps(urna)); retirado["votos"].pop(0)
    assert ver.verificar_urna(retirado, Y, cid)["problemas_registro"]
    alterado = json.loads(json.dumps(urna)); alterado["votos"][0]["opcion"] = "abstencion"
    assert ver.verificar_urna(alterado, Y, cid)["problemas_registro"] or ver.verificar_urna(alterado, Y, cid)["invalidos"]
    sin_registro = {k: v for k, v in urna.items() if k != "registro"}
    assert ver.verificar_urna(sin_registro, Y, cid)["problemas_registro"]
    otra_clave = bytes.fromhex(api.client.get(f"/convocatorias/{crear_conv(api, ['z'], estado='programada')}").json()["log_pub_hex"])
    assert ver.verificar_urna(urna, Y, cid, log_pub=otra_clave)["problemas_registro"]   # clave del registro fijada por el verificador


def test_cerrar_sin_votos_deja_un_checkpoint_vacio_valido(api):
    cid = crear_conv(api, ["a"])
    _cerrar(api, cid)
    reg = _registro(api, cid)
    assert [(c["seq"], c["n"]) for c in reg["checkpoints"]] == [(1, 0)]
    urna = api.client.get(f"/convocatorias/{cid}/urna").json()
    assert _script("verificador_independiente").verificar_urna(urna, clave_Y(api, cid), cid)["problemas_registro"] == []


def test_sellar_manual_solo_admin_e_idempotente(api):
    cid = crear_conv(api, ["p0", "p1"])
    _votar_todos(api, cid, 2)                                    # cada 20: nada sellado aún
    assert _registro(api, cid)["checkpoints"] == []
    assert api.client.post(f"/convocatorias/{cid}/registro/sellar").status_code == 403
    r = api.client.post(f"/convocatorias/{cid}/registro/sellar", headers=api.admin).json()
    assert r["sellado"] and r["checkpoint"]["n"] == 2
    again = api.client.post(f"/convocatorias/{cid}/registro/sellar", headers=api.admin).json()
    assert again == {"sellado": False, "checkpoint": None}
    assert api.client.post("/convocatorias/no-existe/registro/sellar", headers=api.admin).status_code == 404


def test_prueba_de_inclusion_de_cada_voto(api, cada_dos):
    cid = crear_conv(api, [f"p{i}" for i in range(5)])
    tokens = _votar_todos(api, cid, 5)
    pub_sin_sellar = tokens[4][0].hex()
    assert api.client.get(f"/convocatorias/{cid}/registro/inclusion", params={"r_prima": pub_sin_sellar}).status_code == 404
    _cerrar(api, cid)
    for R, s, op in tokens:
        d = api.client.get(f"/convocatorias/{cid}/registro/inclusion", params={"r_prima": R.hex()}).json()
        hoja = registro.hash_hoja(registro.hoja_voto(R, s, op)) if hasattr(registro, "hoja_voto") else \
            registro.hojas_de_votos([(R, s, op)])[0]
        assert registro.verificar_camino(hoja, d["indice"], d["n"], [bytes.fromhex(h) for h in d["camino"]],
                                         bytes.fromhex(d["checkpoint"]["root"]))
    assert api.client.get(f"/convocatorias/{cid}/registro/inclusion", params={"r_prima": "02" + "ab" * 32}).status_code == 404
    assert api.client.get(f"/convocatorias/{cid}/registro/inclusion", params={"r_prima": "zz"}).status_code == 400
    assert api.client.get(f"/convocatorias/{cid}/registro/inclusion", params={"r_prima": "00"}).status_code == 400


def test_observador_archiva_detecta_equivocacion_y_clave_distinta(api, cada_dos, tmp_path):
    obs = _script("observador")
    cid = crear_conv(api, [f"p{i}" for i in range(5)])
    _votar_todos(api, cid, 2)
    servido = _registro(api, cid)
    codigo, cab, nuevos, msgs = obs.observar(cid, servido, None, [], None)
    assert codigo == 0 and [c["seq"] for c in nuevos] == [1] and cab["log_pub_hex"] == servido["log_pub_hex"]
    # sigue sin cambios: nada nuevo
    assert obs.observar(cid, servido, cab, nuevos, None)[2] == []
    # el servidor «reescribe» el checkpoint 1 con otra raíz (aunque la firme): equivocación
    falso = json.loads(json.dumps(servido)); falso["checkpoints"][0]["root"] = "11" * 32
    d_log = __import__("claves").derivar_clave_registro(__import__("main")._MASTER, cid)
    falso["checkpoints"][0]["firma"] = registro.firmar_checkpoint(d_log, cid, falso["checkpoints"][0])
    codigo, _, _, msgs = obs.observar(cid, falso, cab, nuevos, None)
    assert codigo == 20 and "EQUIVOCACIÓN" in msgs[0]
    # historia más corta que la archivada: retroceso
    assert obs.observar(cid, {**servido, "checkpoints": []}, cab, nuevos, None)[0] == 20
    # firma inválida
    mal = json.loads(json.dumps(servido)); mal["checkpoints"][0]["n"] = 7
    assert obs.observar(cid, mal, cab, [], None)[0] == 22
    # clave del registro distinta de la fijada por el observador
    assert obs.observar(cid, servido, None, [], "02" + "cd" * 32)[0] == 22


def test_observador_y_verificador_por_linea_de_comandos(api, cada_dos, tmp_path, monkeypatch, capsys):
    obs, ver = _script("observador"), _script("verificador_independiente")
    base = "http://servidor"
    ruta = lambda url: url.replace(base, "")
    for mod in (obs, ver):
        monkeypatch.setattr(mod, "_obtener", lambda url: api.client.get(ruta(url)).json())
    cid = crear_conv(api, [f"p{i}" for i in range(5)])
    archivo = tmp_path / "obs.jsonl"
    _votar_todos(api, cid, 4)
    assert obs.main([cid, "--api", base, "--archivo", str(archivo), "--una-vez"]) == 0
    assert obs.main([cid, "--api", base, "--archivo", str(archivo), "--una-vez"]) == 0
    lineas = [json.loads(l) for l in archivo.read_text().splitlines()]
    assert lineas[0]["tipo"] == "cabecera" and [l["seq"] for l in lineas[1:]] == [1, 2]
    _cerrar(api, cid)
    assert obs.main([cid, "--api", base, "--archivo", str(archivo), "--una-vez"]) == 0       # n=4 ya sellado: sin cambios
    Y = clave_Y(api, cid).hex()
    pub = api.client.get(f"/convocatorias/{cid}").json()["log_pub_hex"]
    assert ver.main([cid, "--api", base, "--Y", Y, "--log-pub", pub, "--archivo", str(archivo)]) == 0
    assert "0 inválidos" in capsys.readouterr().out
    # el archivo del observador contradice lo que sirve ahora el servidor: la verificación falla
    lineas[1]["root"] = "22" * 32
    archivo.write_text("\n".join(json.dumps(l) for l in lineas) + "\n")
    assert ver.main([cid, "--api", base, "--Y", Y, "--log-pub", pub, "--archivo", str(archivo)]) == 10
    assert "EQUIVOCACIÓN" in capsys.readouterr().err
    assert ver.main([cid, "--api", base, "--Y", "zz"]) == 5
