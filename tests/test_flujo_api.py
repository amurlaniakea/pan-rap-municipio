# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""T4-T7: padrón, clave por convocatoria, votos y emisión robusta, siempre a través de la API."""
import time
from pathlib import Path

import pytest

import main
from helpers_api import clave_Y, crear_conv, emitir_token, votar
from tests_db import conn_db, emisiones, personas_cols


# ---------- T4: padrón y privacidad del censo ----------

def test_censo_inserta_personas_y_no_guarda_identificadores(api):
    cid = crear_conv(api, ["dni_1", "dni_2"], estado="programada")
    with conn_db() as c:
        assert c.execute("SELECT COUNT(*) FROM personas").fetchone()[0] == 2
    assert "alta_por" not in personas_cols()
    assert b"dni_1" not in Path(main.DB_PATH()).read_bytes()
    again = api.client.post(f"/convocatorias/{cid}/censo", headers=api.admin, json={"identificadores": ["dni_1", "dni_3"]})
    assert again.json() == {"convocatoria_id": cid, "recibidos": 2, "cargados": 1}


def test_censo_solo_en_borrador_o_programada(api):
    cid = crear_conv(api, ["a"], estado="emision")
    r = api.client.post(f"/convocatorias/{cid}/censo", headers=api.admin, json={"identificadores": ["b"]})
    assert r.status_code == 400
    assert api.client.post("/convocatorias/no-existe/censo", headers=api.admin, json={"identificadores": ["b"]}).status_code == 404
    cid2 = crear_conv(api, [], estado="programada")
    for malo in (None, "dni", [5], [""], ["x" * 129]):
        assert api.client.post(f"/convocatorias/{cid2}/censo", headers=api.admin, json={"identificadores": malo}).status_code == 400


def test_inicio_con_credencial_en_claro_y_mensaje_unico(api):
    cid = crear_conv(api, ["dni_1"])
    assert api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "dni_1"}).status_code == 200
    desconocido = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "otro"})
    assert desconocido.status_code == 400
    assert desconocido.json()["detail"] == main.MENSAJE_GENERICO


# ---------- T5: la firma está ligada a la convocatoria ----------

def test_token_de_una_convocatoria_no_vale_en_otra(api):
    a = crear_conv(api, ["p1"])
    b = crear_conv(api, ["p1"])
    R, s = emitir_token(api, a, "p1", "a_favor", msg_conv=b)  # el votante firma un mensaje de B pidiendo token en A
    assert votar(api, b, "a_favor", R, s).status_code == 400   # Y de B ≠ Y de A
    assert votar(api, a, "a_favor", R, s).status_code == 400   # y el mensaje era de B
    R2, s2 = emitir_token(api, b, "p1", "a_favor")
    assert votar(api, a, "a_favor", R2, s2).status_code == 400
    assert votar(api, b, "a_favor", R2, s2).status_code == 200


def test_fin_con_sid_de_otra_convocatoria_403(api):
    a = crear_conv(api, ["p1"])
    b = crear_conv(api, ["p1"])
    sid = api.client.post(f"/convocatorias/{a}/emision/inicio", json={"credencial": "p1"}).json()["sid"]
    r = api.client.post(f"/convocatorias/{b}/emision/fin", json={"sesion": sid, "e": "01" * 32})
    assert r.status_code == 403


def test_clave_publicada_es_la_derivada(api):
    cid = crear_conv(api, ["p1"], estado="programada")
    assert clave_Y(api, cid) == main._emisor_de(cid).Y


# ---------- T6: /votos ----------

def test_votar_en_convocatoria_inexistente_o_cerrada(api):
    cid = crear_conv(api, ["p1", "p2"])
    R, s = emitir_token(api, cid, "p1", "a_favor")
    R2, s2 = emitir_token(api, cid, "p2", "a_favor")
    ok = votar(api, "no-existe", "a_favor", R, s)
    assert ok.status_code == 404
    for st in ("cerrada",):
        api.client.patch(f"/convocatorias/{cid}/estado", headers=api.admin, json={"estado": st})
    assert votar(api, cid, "a_favor", R, s).status_code == 400
    assert votar(api, cid, "a_favor", R2, s2).status_code == 400


@pytest.mark.parametrize("cuerpo", [
    {"opcion": "a_favor", "r_prima": "zz", "s_prima": "00" * 32},
    {"opcion": "a_favor", "r_prima": "00" * 33, "s_prima": "00" * 31},
    {"opcion": 5, "r_prima": "00" * 33, "s_prima": "00" * 32},
    {"opcion": "a_favor"}, {},
])
def test_votos_entrada_basura_400_nunca_500(api, cuerpo):
    cid = crear_conv(api, ["p1"])
    assert api.client.post(f"/convocatorias/{cid}/votos", json=cuerpo).status_code == 400


def test_opcion_ajena_y_opciones_propias(api):
    cid = crear_conv(api, ["p1", "p2"], opciones=("si", "no"))
    R, s = emitir_token(api, cid, "p1", "abstencion")  # firmada pero no es opción de esta convocatoria
    assert votar(api, cid, "abstencion", R, s).status_code == 400
    R2, s2 = emitir_token(api, cid, "p2", "si")
    assert votar(api, cid, "si", R2, s2).status_code == 200
    assert votar(api, cid, "si", R2, s2).status_code == 409  # doble gasto


def test_token_no_sirve_para_otra_opcion(api):
    cid = crear_conv(api, ["p1"])
    R, s = emitir_token(api, cid, "p1", "a_favor")
    assert votar(api, cid, "en_contra", R, s).status_code == 400


# ---------- T7: emisión robusta ----------

def test_no_se_puede_emitir_dos_veces(api):
    cid = crear_conv(api, ["p1"])
    emitir_token(api, cid, "p1", "a_favor")
    assert emisiones()[0][1] == "completada"
    r = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"})
    assert r.status_code == 400 and r.json()["detail"] == main.MENSAJE_GENERICO


def test_sesion_viva_no_se_pierde_por_otro_votante(api):
    """Regresión del intento 1: un tercero no puede borrar la fila de quien tiene la sesión abierta."""
    cid = crear_conv(api, ["p1", "p2"])
    d1 = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"}).json()
    r2 = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p2"})
    assert r2.status_code == 503
    assert len(emisiones()) == 1  # solo p1; p2 no deja rastro
    from helpers_api import blindar
    e, fin = blindar(clave_Y(api, cid), bytes.fromhex(d1["R"]), cid, "a_favor")
    f = api.client.post(f"/convocatorias/{cid}/emision/fin", json={"sesion": d1["sid"], "e": e.hex()})
    assert f.status_code == 200
    assert api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"}).status_code == 400
    # y ahora p2 puede emitir
    assert api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p2"}).status_code == 200


def _caducar(cid):
    """Adelanta 11 s el reloj del emisor de la convocatoria (TTL = 10 s); el adelanto se acumula."""
    em = main._emisor_de(cid)
    adelanto = getattr(em, "_adelanto", 0) + 11
    em._adelanto = adelanto
    em._reloj = lambda: time.monotonic() + adelanto


def test_abandono_permite_reintento_y_bloquea_al_tercero(api):
    cid = crear_conv(api, ["p1"])
    for intento in (1, 2, 3):
        r = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"})
        assert r.status_code == 200, (intento, r.text)
        assert emisiones()[0][2] == intento
        _caducar(cid)
    r = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"})
    assert r.status_code == 400
    assert emisiones()[0][1] == "bloqueada"


def test_fin_con_sid_ajeno_no_toca_la_fila(api):
    cid = crear_conv(api, ["p1"])
    api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"})
    r = api.client.post(f"/convocatorias/{cid}/emision/fin", json={"sesion": "ff" * 16, "e": "01" * 32})
    assert r.status_code == 403
    assert emisiones()[0][1] == "pendiente"


@pytest.mark.parametrize("e", ["zz", "", "00" * 32, "01"])
def test_fin_con_e_invalida_400_y_se_puede_reintentar(api, e):
    cid = crear_conv(api, ["p1"])
    sid = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"}).json()["sid"]
    r = api.client.post(f"/convocatorias/{cid}/emision/fin", json={"sesion": sid, "e": e})
    assert r.status_code == 400
    assert emisiones()[0][1] == "pendiente"           # no se liberó ninguna firma
    if e in ("00" * 32, "01"):                        # e llegó al emisor: la sesión se destruyó
        again = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"})
        assert again.status_code == 200


def test_fin_repetido_tras_completar_403(api):
    cid = crear_conv(api, ["p1"])
    d = api.client.post(f"/convocatorias/{cid}/emision/inicio", json={"credencial": "p1"}).json()
    from helpers_api import blindar
    e, _ = blindar(clave_Y(api, cid), bytes.fromhex(d["R"]), cid, "a_favor")
    body = {"sesion": d["sid"], "e": e.hex()}
    assert api.client.post(f"/convocatorias/{cid}/emision/fin", json=body).status_code == 200
    assert api.client.post(f"/convocatorias/{cid}/emision/fin", json=body).status_code == 403
