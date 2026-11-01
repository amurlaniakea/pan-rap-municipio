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


def test_hash_publicado_coincide_con_el_bundle():
    import hashlib
    linea = (RAIZ / "frontend" / "SHA256SUMS").read_text().split()
    assert linea[1] == "ui/voto.bundle.js"
    assert hashlib.sha256((RAIZ / "frontend" / "ui" / "voto.bundle.js").read_bytes()).hexdigest() == linea[0]
