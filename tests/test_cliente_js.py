# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Cliente web: interoperabilidad JS↔Python con vectores fijos y votación real contra un servidor uvicorn."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from coincurve import PrivateKey, PublicKey

import urna_schnorr as U

RAIZ = Path(__file__).parent.parent
NODE = shutil.which("node")
requiere_node = pytest.mark.skipif(
    NODE is None or not (RAIZ / "node_modules" / "@noble").exists(),
    reason="requiere node y `npm ci` (CI lo ejecuta)")
Q = U.Q


def _vector(i, conv_id, opcion):
    """Vector determinista calculado con aritmética de enteros (solo tests; el emisor real usa libsecp256k1)."""
    d, k, a, b = (int.from_bytes(__import__("hashlib").sha256(f"vec{i}-{n}".encode()).digest(), "big") % (Q - 1) + 1
                  for n in "dkab")
    sc = lambda x: x.to_bytes(32, "big")
    Y = PrivateKey(sc(d)).public_key.format()
    R = PrivateKey(sc(k)).public_key.format()
    Rp = PublicKey.combine_keys([PublicKey(R), PrivateKey(sc(a)).public_key,
                                 PublicKey(Y).multiply(sc(b), update=False)]).format()
    e = (U.desafio(Y, Rp, U.mensaje(conv_id, opcion)) + b) % Q
    s = (k + d * e) % Q
    return {"Y_hex": Y.hex(), "R_hex": R.hex(), "a_hex": sc(a).hex(), "b_hex": sc(b).hex(), "conv_id": conv_id,
            "opcion": opcion, "s_hex": sc(s).hex(), "s_ajena_hex": sc((s + 1) % Q).hex(),
            "esperado": {"R_prima_hex": Rp.hex(), "e_hex": sc(e).hex(), "s_prima_hex": sc((s + a) % Q).hex()}}


@requiere_node
def test_nucleo_js_coincide_con_python(tmp_path):
    vectores = [_vector(i, c, o) for i, (c, o) in enumerate(
        [("conv-1", "a_favor"), ("3f2c-uuid-like-id", "en_contra"), ("x", "abstencion"), ("conv_ñ", "sí")])]
    f = tmp_path / "v.json"
    f.write_text(json.dumps(vectores))
    r = subprocess.run([NODE, str(RAIZ / "frontend/test/interop.mjs"), str(f)], capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    for v, js in zip(vectores, json.loads(r.stdout)):
        esp = v["esperado"]
        assert (js["R_prima_hex"], js["e_hex"], js["s_prima_hex"]) == (esp["R_prima_hex"], esp["e_hex"], esp["s_prima_hex"])
        assert js["error_s_ajena"] == "Respuesta del emisor inválida"
        # el token calculado por JS lo acepta la urna de producción
        assert U.verificar(bytes.fromhex(v["Y_hex"]), v["conv_id"], v["opcion"],
                           bytes.fromhex(js["R_prima_hex"]), bytes.fromhex(js["s_prima_hex"]))


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http(base, metodo, ruta, cuerpo=None, token=None):
    req = urllib.request.Request(base + ruta, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 headers={"Content-Type": "application/json", **({"X-Admin-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.fixture
def servidor(tmp_path):
    token = "s" * 40
    puerto = _puerto_libre()
    env = {**os.environ, "PANRAP_DB": str(tmp_path / "e2e.db"), "PANRAP_ADMIN_TOKEN": token, "PANRAP_ALLOW_EPHEMERAL_KEY": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(puerto),
                             "--workers", "1", "--log-level", "warning"], cwd=RAIZ, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            _http(base, "GET", "/convocatorias/x")
            break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("el servidor no arrancó")
    yield base, token
    proc.terminate()
    proc.wait(timeout=10)


@requiere_node
def test_votacion_real_desde_el_cliente_js(servidor):
    base, tok = servidor
    s, d = _http(base, "POST", "/convocatorias", {"titulo": "t", "texto": "x", "opciones": ["si", "no"],
                 "emision_abre_en": "2026-11-01T00:00:00", "voto_abre_en": "2026-11-02T00:00:00",
                 "cierra_en": "2026-11-03T00:00:00"}, tok)
    assert s == 201
    cid = d["id"]
    assert _http(base, "POST", f"/convocatorias/{cid}/censo", {"identificadores": ["ana", "beto"]}, tok)[0] == 201
    for est in ("programada", "emision"):
        assert _http(base, "PATCH", f"/convocatorias/{cid}/estado", {"estado": est}, tok)[0] == 200

    def votar_js(cred, opcion):
        r = subprocess.run([NODE, str(RAIZ / "frontend/test/e2e.mjs"), base, cid, cred, opcion],
                           capture_output=True, text=True, cwd=RAIZ)
        return r.returncode, json.loads(r.stdout)

    assert votar_js("ana", "si") == (0, {"mensaje": "Voto registrado", "opcion": "si"})
    assert votar_js("beto", "no")[0] == 0
    codigo, salida = votar_js("ana", "si")                # segunda emisión de la misma persona
    assert codigo == 1 and "ya utilizada" in salida["error"]
    codigo, salida = votar_js("intruso", "si")
    assert codigo == 1 and "Credencial" in salida["error"]
    codigo, salida = votar_js("ana", "otra")              # opción inválida: ni siquiera pide emisión
    assert codigo == 1 and "Opción no válida" in salida["error"]
    assert _http(base, "PATCH", f"/convocatorias/{cid}/estado", {"estado": "cerrada"}, tok)[0] == 200
    s, esc = _http(base, "GET", f"/convocatorias/{cid}/escrutinio")
    assert esc["recuento"] == {"si": 1, "no": 1} and esc["emisiones_completadas"] == 2
    s, urna = _http(base, "GET", f"/convocatorias/{cid}/urna")
    Y = bytes.fromhex(urna["emisor_pub_hex"])
    assert all(U.verificar(Y, cid, v["opcion"], bytes.fromhex(v["r_prima"]), bytes.fromhex(v["s_prima"])) for v in urna["votos"])


def test_ui_se_sirve_con_csp_y_sin_cdn(api):
    r = api.client.get("/ui/")
    assert r.status_code == 200
    html = r.text
    assert "Content-Security-Policy" in html and "script-src 'self'" in html
    assert "http://" not in html and "https://" not in html and "onclick" not in html
    assert api.client.get("/ui/voto.bundle.js").status_code == 200
    assert api.client.get("/ui/estilos.css").status_code == 200
    assert api.client.get("/ui/../build.js").status_code in (404, 400, 307)
    assert "style=" not in html and "<script>" not in html           # compatible con la CSP estricta
    css = api.client.get("/ui/estilos.css").text
    assert "@import" not in css and "http" not in css                # sin recursos externos
    assert "prefers-color-scheme: dark" in css                       # tema claro y oscuro


def test_hash_publicado_coincide_con_el_bundle():
    import hashlib
    linea = (RAIZ / "frontend" / "SHA256SUMS").read_text().split()
    assert linea[1] == "ui/voto.bundle.js"
    assert hashlib.sha256((RAIZ / "frontend" / "ui" / "voto.bundle.js").read_bytes()).hexdigest() == linea[0]


def _crear_abierta(base, tok, titulo="Demo", creds=("ana", "beto")):
    s, d = _http(base, "POST", "/convocatorias", {"titulo": titulo, "texto": "x", "opciones": ["si", "no"],
                 "emision_abre_en": "2026-11-01T00:00:00", "voto_abre_en": "2026-11-02T00:00:00",
                 "cierra_en": "2026-11-03T00:00:00"}, tok)
    assert s == 201
    cid = d["id"]
    _http(base, "POST", f"/convocatorias/{cid}/censo", {"identificadores": list(creds)}, tok)
    for est in ("programada", "emision"):
        _http(base, "PATCH", f"/convocatorias/{cid}/estado", {"estado": est}, tok)
    return cid


def _ui_js(base, conv, cred, opcion):
    r = subprocess.run([NODE, str(RAIZ / "frontend/test/ui.mjs"), base, conv, cred, opcion],
                       capture_output=True, text=True, cwd=RAIZ, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@requiere_node
def test_interfaz_publicada_vota_con_dom_real(servidor):
    """Ejecuta el bundle publicado sobre el HTML servido, con un DOM, contra el servidor real."""
    base, tok = servidor
    cid = _crear_abierta(base, tok, "Presupuesto participativo")
    r = _ui_js(base, cid, "ana", "si")
    assert r["cargada"] and r["titulo"] == "Presupuesto participativo" and r["clave"] and r["csp"]
    assert r["opciones"] == ["si", "no"]
    assert r["estado"].startswith("✅") and "cerrar esta página" in r["estado"], r
    again = _ui_js(base, cid, "ana", "no")                        # misma credencial: la UI muestra el error
    assert again["estado"].startswith("❌") and again["clase"] == "error"
    assert "exactamente igual" in again["estado"]                   # ayuda ante credencial mal escrita
    sin_cred = _ui_js(base, cid, "", "si")
    assert "Introduce tu credencial" in sin_cred["estado"]
    s, esc = _http(base, "GET", f"/convocatorias/{cid}/escrutinio")
    assert s == 400                                               # sigue abierta
    _http(base, "PATCH", f"/convocatorias/{cid}/estado", {"estado": "cerrada"}, tok)
    assert _http(base, "GET", f"/convocatorias/{cid}/escrutinio")[1]["recuento"] == {"si": 1, "no": 0}


@requiere_node
def test_interfaz_sin_id_muestra_la_lista_y_permite_votar(servidor):
    base, tok = servidor
    r0 = _ui_js(base, "-", "x", "si")
    assert r0["lista"] == [] and not r0["cargada"]            # sin convocatorias abiertas: no hay lista ni panel
    _crear_abierta(base, tok, "Primera", creds=("carla",))
    r = _ui_js(base, "-", "carla", "no")
    assert r["lista"] == ["Primera"] and r["cargada"] and r["estado"].startswith("✅"), r


def test_raiz_redirige_a_la_ui_y_lista_convocatorias_abiertas(api):
    from helpers_api import crear_conv
    r = api.client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/ui/"
    assert api.client.get("/convocatorias").json() == []
    abierta = crear_conv(api, ["a"], estado="emision")
    crear_conv(api, ["a"], estado="programada")                   # no abierta: no aparece
    lista = api.client.get("/convocatorias").json()
    assert [c["id"] for c in lista] == [abierta] and set(lista[0]) == {"id", "titulo", "estado"}


def test_demo_local_deja_una_convocatoria_lista_para_votar(servidor):
    base, tok = servidor
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "demo_local.py"), "--api", base, "--votantes", "2"],
                       capture_output=True, text=True, env={**os.environ, "PANRAP_ADMIN_TOKEN": tok}, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    assert "votante1, votante2" in r.stdout and "/ui/?conv=" in r.stdout
    assert len(_http(base, "GET", "/convocatorias")[1]) == 1


def _ui_comprobante(base, cid, cred, opcion, guardar):
    r = subprocess.run([NODE, str(RAIZ / "frontend/test/ui_comprobante.mjs"), base, cid, cred, opcion, "1" if guardar else "0"],
                       capture_output=True, text=True, cwd=RAIZ, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _ui_verificar(base, casos, tmp_path):
    f = tmp_path / "casos.json"
    f.write_text(json.dumps(casos))
    r = subprocess.run([NODE, str(RAIZ / "frontend/test/ui_verificar.mjs"), base, str(f)],
                       capture_output=True, text=True, cwd=RAIZ, timeout=90)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@requiere_node
def test_comprobante_desactivado_por_defecto_no_genera_ningun_documento(servidor):
    base, tok = servidor
    cid = _crear_abierta(base, tok, "Sin comprobante", creds=("ana",))
    r = _ui_comprobante(base, cid, "ana", "si", guardar=False)
    assert r["guardar_por_defecto"] is False                       # la casilla viene desmarcada
    assert r["estado"].startswith("✅") and r["hecho_visible"] and not r["panel_visible"] and r["paso"] == "3"
    assert r["bloque_comprobante_visible"] is False and r["comprobante"] is None


@requiere_node
def test_comprobante_opcional_se_genera_y_se_verifica_en_el_navegador(servidor, tmp_path):
    base, tok = servidor
    cid = _crear_abierta(base, tok, "Con comprobante", creds=("ana", "beto", "carla"))
    comps = {}
    for cred, op in (("ana", "si"), ("beto", "no"), ("carla", "si")):
        r = _ui_comprobante(base, cid, cred, op, guardar=True)
        assert r["bloque_comprobante_visible"] is True
        c = r["comprobante"]
        assert set(c) == {"tipo", "version", "convocatoria_id", "opcion", "r_prima", "s_prima"}   # nada más
        assert c["convocatoria_id"] == cid and c["opcion"] == op and cred not in json.dumps(c)       # y jamás la credencial
        comps[cred] = c
    log_pub = _http(base, "GET", f"/convocatorias/{cid}")[1]["log_pub_hex"]
    otra_pub = "02" + "ab" * 32
    textos = lambda res: " | ".join(x["texto"] for x in res)
    clases = lambda res: [x["clase"] for x in res]

    # 1) antes de sellar: el voto aún no consta en ningún checkpoint (cada 20 votos por defecto)
    res = _ui_verificar(base, [{"comprobante": comps["ana"]}], tmp_path)[0]
    assert "aún no está sellado" in textos(res) and "ok final" not in clases(res) and "error final" not in clases(res)

    # 2) sellar y verificar cada voto; con la clave del registro fijada no hay aviso de «clave del servidor»
    assert _http(base, "POST", f"/convocatorias/{cid}/registro/sellar", None, tok)[0] == 200
    casos = [{"comprobante": comps[c], "logpub": log_pub} for c in ("ana", "beto", "carla")]
    for res in _ui_verificar(base, casos, tmp_path):
        assert "ok final" in clases(res), textos(res)
        assert "checkpoint nº 1 (3 votos sellados)" in textos(res) and "propio servidor" not in textos(res)
    sin_fijar = _ui_verificar(base, [{"comprobante": comps["beto"]}], tmp_path)[0]
    assert "ok final" in clases(sin_fijar) and "propio servidor" in textos(sin_fijar)               # aviso de clave no fijada

    # 3) falsificaciones: clave del registro equivocada, opción cambiada, token alterado, JSON roto, formato incorrecto
    malos = [
        {"comprobante": comps["ana"], "logpub": otra_pub},
        {"comprobante": {**comps["ana"], "opcion": "no"}},
        {"comprobante": {**comps["ana"], "s_prima": "11" * 32}},
        {"comprobante": {**comps["ana"], "convocatoria_id": "no-existe"}},
        {"comprobante": "esto no es json"},
        {"comprobante": {"tipo": "otra-cosa"}},
    ]
    for caso, res in zip(malos, _ui_verificar(base, malos, tmp_path)):
        assert "error" in " ".join(clases(res)) and "ok final" not in clases(res), (caso, textos(res))
    resultados = _ui_verificar(base, malos, tmp_path)
    for i in (1, 2):                                                   # opción cambiada y s' alterado: falla ya la firma del token
        assert resultados[i][0]["clase"] == "error" and "firma de tu token" in resultados[i][0]["texto"]
    assert resultados[0][0]["clase"] == "ok" and resultados[0][-1]["clase"].startswith("error")       # el token es bueno; falla la clave del registro


@requiere_node
def test_merkle_js_coincide_con_python_y_rechaza_pruebas_falsas(tmp_path):
    import hashlib
    import registro as R
    vectores, esperado = [], []
    for n in (1, 2, 3, 5, 8, 13):
        votos = [(bytes([2]) + hashlib.sha256(f"r{n}-{i}".encode()).digest(), hashlib.sha256(f"s{n}-{i}".encode()).digest(),
                  ("si", "no", "sí")[i % 3]) for i in range(n)]
        hojas = R.hojas_de_votos(votos)
        raiz = R.raiz(hojas)
        for i, (r, s, op) in enumerate(votos):
            ruta = [h.hex() for h in R.camino(hojas, i)]
            base = {"r": r.hex(), "s": s.hex(), "opcion": op, "n": n, "i": i, "camino": ruta, "raiz": raiz.hex()}
            vectores.append(base); esperado.append((hojas[i].hex(), True))
            vectores.append({**base, "raiz": "00" * 32}); esperado.append((hojas[i].hex(), False))              # raíz equivocada
            vectores.append({**base, "opcion": "otra"}); esperado.append((R.hash_hoja(R.hoja_voto(r, s, "otra")).hex(), False))  # hoja alterada
            if ruta:
                vectores.append({**base, "camino": ruta[:-1]}); esperado.append((hojas[i].hex(), False))          # camino truncado
                vectores.append({**base, "camino": ruta[::-1] if len(ruta) > 1 and ruta != ruta[::-1] else ruta + ["00" * 32]})
                esperado.append((hojas[i].hex(), False))                                                         # camino desordenado/ampliado
            if n > 1:
                vectores.append({**base, "i": (i + 1) % n}); esperado.append((hojas[i].hex(), n == 2 and False))  # índice equivocado
    f = tmp_path / "merkle.json"
    f.write_text(json.dumps(vectores))
    r = subprocess.run([NODE, str(RAIZ / "frontend/test/registro_vectores.mjs"), str(f)], capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    for v, (hoja_py, ok_py), js in zip(vectores, esperado, json.loads(r.stdout)):
        assert js["hoja"] == hoja_py                                   # la hoja se calcula igual en JS y en Python
        if not ok_py:
            assert js["camino_ok"] is False, v
        elif v["raiz"] != "00" * 32:
            assert js["camino_ok"] is True, v
