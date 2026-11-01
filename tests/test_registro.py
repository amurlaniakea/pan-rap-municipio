# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Registro verificable: árbol de Merkle (RFC 6962), checkpoints firmados y su verificación (módulo registro)."""
import hashlib
import secrets

import pytest
from coincurve import PrivateKey

import registro as R

CONV = "conv-test"


def _voto(i):
    return (bytes([2]) + hashlib.sha256(f"r{i}".encode()).digest(), hashlib.sha256(f"s{i}".encode()).digest(), "a_favor")


def test_vectores_rfc6962_vacio_y_una_hoja():
    assert R.raiz([]).hex() == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    h = R.hash_hoja(b"x")
    assert h == hashlib.sha256(b"\x00x").digest() and R.raiz([h]) == h


def test_raiz_de_dos_y_tres_hojas_a_mano():
    a, b, c = (R.hash_hoja(x) for x in (b"a", b"b", b"c"))
    n = lambda l, r: hashlib.sha256(b"\x01" + l + r).digest()
    assert R.raiz([a, b]) == n(a, b)
    assert R.raiz([a, b, c]) == n(n(a, b), c)          # RFC 6962: el árbol se parte en la mayor potencia de 2 < n


@pytest.mark.parametrize("n", list(range(1, 18)))
def test_pruebas_de_inclusion_para_todas_las_hojas(n):
    hojas = [R.hash_hoja(bytes([i])) for i in range(n)]
    r = R.raiz(hojas)
    for i in range(n):
        ruta = R.camino(hojas, i)
        assert R.verificar_camino(hojas[i], i, n, ruta, r)
        assert not R.verificar_camino(R.hash_hoja(b"otra"), i, n, ruta, r)
        assert not R.verificar_camino(hojas[i], (i + 1) % n if n > 1 else 0, n, ruta, r) or n == 1


def test_camino_manipulado_o_de_otro_tamano_no_verifica():
    hojas = [R.hash_hoja(bytes([i])) for i in range(7)]
    r = R.raiz(hojas)
    ruta = R.camino(hojas, 3)
    assert not R.verificar_camino(hojas[3], 3, 7, ruta[:-1], r)
    assert not R.verificar_camino(hojas[3], 3, 7, ruta + [bytes(32)], r)
    # el tamaño del árbol no lo autentica la prueba sino el checkpoint firmado (que incluye n): aquí solo la raíz
    assert not R.verificar_camino(hojas[3], 3, 7, ruta, R.raiz(hojas[:6]))
    assert not R.verificar_camino(hojas[3], 9, 7, ruta, r)


def _cadena(d_log, lotes):
    """lotes: lista de listas de votos. Devuelve (checkpoints, votos_con_lote)."""
    cps, votos, previos = [], [], []
    for k, lote in enumerate(lotes, 1):
        votos += [(r, s, o, k) for r, s, o in lote]
        orden = sorted(votos, key=lambda v: (v[3], v[0]))
        cp = {"seq": k, "n": len(orden),
              "root": R.raiz(R.hojas_de_votos([(r, s, o) for r, s, o, _ in orden])).hex(),
              "prev": R.GENESIS if not cps else R.hash_checkpoint(CONV, cps[-1]), "creado": f"2026-11-0{k}T10:00:00Z"}
        cp["firma"] = R.firmar_checkpoint(d_log, CONV, cp)
        cps.append(cp)
    return cps, votos


@pytest.fixture
def clave():
    d = secrets.token_bytes(32)
    return d, PrivateKey(d).public_key.format()


def test_registro_valido(clave):
    d, pub = clave
    cps, votos = _cadena(d, [[_voto(1), _voto(2)], [_voto(3)], [_voto(4), _voto(5), _voto(6)]])
    assert R.verificar_registro(CONV, pub, cps, votos) == []


def test_votos_retirados_o_alterados_o_anadidos_se_detectan(clave):
    d, pub = clave
    cps, votos = _cadena(d, [[_voto(1), _voto(2)], [_voto(3), _voto(4)]])
    assert R.verificar_registro(CONV, pub, cps, votos[:-1])                               # retirado
    r, s, o, lote = votos[0]
    assert R.verificar_registro(CONV, pub, cps, [(r, s, "en_contra", lote)] + votos[1:])  # opción cambiada
    assert R.verificar_registro(CONV, pub, cps, votos + [(*_voto(9), 2)])                 # añadido en lote sellado
    assert R.verificar_registro(CONV, pub, cps, votos + [(*_voto(9), None)])              # añadido sin sellar
    assert R.verificar_registro(CONV, pub, cps, [(r, s, o, 2)] + votos[1:])               # movido de lote


def test_firma_cadena_y_numeracion(clave):
    d, pub = clave
    cps, _ = _cadena(d, [[_voto(1)], [_voto(2)], [_voto(3)]])
    assert R.verificar_cadena(CONV, pub, cps) == []
    assert R.verificar_cadena(CONV, PrivateKey().public_key.format(), cps)                # otra clave
    assert R.verificar_cadena("otra-conv", pub, cps)                                      # otra convocatoria
    mal = [dict(c) for c in cps]; mal[1]["n"] = 99
    assert any("firma" in p for p in R.verificar_cadena(CONV, pub, mal))                  # contenido alterado
    assert R.verificar_cadena(CONV, pub, [cps[0], cps[2]])                                # falta uno
    assert R.verificar_cadena(CONV, pub, [cps[1], cps[0], cps[2]])                        # reordenados
    assert R.verificar_cadena(CONV, pub, [{"seq": 1}])                                    # formato inválido no lanza


def test_n_no_puede_decrecer_aunque_este_firmado(clave):
    d, pub = clave
    cps, _ = _cadena(d, [[_voto(1), _voto(2)], [_voto(3)]])
    cp = dict(cps[1]); cp["n"] = 1; cp["firma"] = R.firmar_checkpoint(d, CONV, cp)
    assert any("decrece" in p for p in R.verificar_cadena(CONV, pub, [cps[0], cp]))


def test_equivocacion_y_retroceso_con_archivo(clave):
    d, _ = clave
    a, _ = _cadena(d, [[_voto(1)], [_voto(2)]])
    b, _ = _cadena(d, [[_voto(7)], [_voto(2)]])                    # misma seq, otra historia, ambas firmadas
    assert R.comparar_con_archivo(a, a) == []
    assert R.comparar_con_archivo(a[:1], a) == []                  # crecer es normal
    assert any("EQUIVOCACIÓN" in p for p in R.comparar_con_archivo(a, b))
    assert any("RETROCESO" in p for p in R.comparar_con_archivo(a, a[:1]))
