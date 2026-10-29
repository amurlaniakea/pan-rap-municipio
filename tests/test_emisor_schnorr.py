# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Fase 2: contrato del Emisor Blind Schnorr (03-motor-blind-schnorr.md: AC-S2, AC-S3, AC-S4).

Estado: implementado en `emisor_schnorr.py` (Fase 3); estos tests ya son normales.

Contrato de emisor_schnorr.py (decisiones del Plan):
    class EmisionOcupada(Exception)    # ya hay una sesión abierta
    class SesionInvalida(Exception)    # sesión desconocida, caducada o ya usada
    class EntradaInvalida(Exception)   # e fuera de rango o con longitud incorrecta
    class Emisor:
        def __init__(self, d: bytes, ttl: float = 10.0, reloj=time.monotonic): ...
        Y: bytes                                       # clave pública comprimida, 33 bytes
        def inicio(self) -> tuple[str, bytes]: ...     # (sesion, R de 33 bytes)
        def fin(self, sesion: str, e: bytes) -> bytes: ...   # s de 32 bytes
    Una sola sesión abierta a la vez (S1). Una `e` inválida DESTRUYE la sesión y libera el cerrojo.
"""
import secrets
import threading

import pytest

Q = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
E_VALIDO = (1).to_bytes(32, "big")

class Reloj:
    """Reloj falso para probar la caducidad sin esperar."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _emisor(reloj=None):
    import emisor_schnorr as m  # importación diferida: sin módulo, falla solo este test

    return m, m.Emisor(secrets.token_bytes(32), ttl=10.0, reloj=reloj or Reloj())


# ---------------------------------------------------------------- AC-S2: una sola sesión abierta
def test_s2_segunda_sesion_con_otra_abierta_se_rechaza():
    m, em = _emisor()
    em.inicio()
    with pytest.raises(m.EmisionOcupada):
        em.inicio()


def test_s2_la_sesion_caduca_a_los_10_s():
    reloj = Reloj()
    m, em = _emisor(reloj)
    em.inicio()
    reloj.t = 9.9
    with pytest.raises(m.EmisionOcupada):
        em.inicio()
    reloj.t = 10.1
    em.inicio()  # caducada: ya se puede abrir otra


def test_s2_fin_libera_el_cerrojo():
    m, em = _emisor()
    sesion, _ = em.inicio()
    em.fin(sesion, E_VALIDO)
    em.inicio()


def test_s2_50_hilos_solo_una_sesion_abierta():
    m, em = _emisor()
    barrera = threading.Barrier(50)
    abiertas, ocupadas = [], []

    def worker():
        barrera.wait()
        try:
            abiertas.append(em.inicio())
        except m.EmisionOcupada:
            ocupadas.append(1)

    hilos = [threading.Thread(target=worker) for _ in range(50)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(abiertas) == 1
    assert len(ocupadas) == 49


# ---------------------------------------------------------------- AC-S3: k efímero y único
def test_s3_cada_sesion_usa_un_R_distinto():
    m, em = _emisor()
    rs = set()
    for _ in range(200):
        sesion, R = em.inicio()
        rs.add(R)
        em.fin(sesion, E_VALIDO)
    assert len(rs) == 200


def test_s3_R_e_Y_miden_33_bytes():
    m, em = _emisor()
    _, R = em.inicio()
    assert len(R) == 33
    assert len(em.Y) == 33


def test_s3_una_sesion_no_se_puede_finalizar_dos_veces():
    m, em = _emisor()
    sesion, _ = em.inicio()
    em.fin(sesion, E_VALIDO)
    with pytest.raises(m.SesionInvalida):
        em.fin(sesion, E_VALIDO)


def test_s3_una_sesion_caducada_no_se_puede_finalizar():
    reloj = Reloj()
    m, em = _emisor(reloj)
    sesion, _ = em.inicio()
    reloj.t = 10.1
    with pytest.raises(m.SesionInvalida):
        em.fin(sesion, E_VALIDO)


# ---------------------------------------------------------------- AC-S4: entradas inválidas
E_INVALIDOS = [
    b"",
    b"\x01" * 31,
    b"\x01" * 33,
    (0).to_bytes(32, "big"),
    Q.to_bytes(32, "big"),
    (Q + 1).to_bytes(32, "big"),
    b"\xff" * 32,
]


@pytest.mark.parametrize("e", E_INVALIDOS)
def test_s4_entrada_invalida_cancela_la_sesion(e):
    m, em = _emisor()
    sesion, _ = em.inicio()
    with pytest.raises(m.EntradaInvalida):
        em.fin(sesion, e)
    with pytest.raises(m.SesionInvalida):  # la sesión murió: no se puede reutilizar
        em.fin(sesion, E_VALIDO)
    em.inicio()  # y el cerrojo quedó libre


def test_s4_sesion_desconocida():
    m, em = _emisor()
    with pytest.raises(m.SesionInvalida):
        em.fin("no-existe", E_VALIDO)


def test_s4_fin_devuelve_s_de_32_bytes():
    m, em = _emisor()
    sesion, _ = em.inicio()
    s = em.fin(sesion, E_VALIDO)
    assert isinstance(s, bytes)
    assert len(s) == 32


@pytest.mark.parametrize("sesion", [None, b"abc", "ñandú", 12345, ""])
def test_s4_sesion_con_tipo_o_formato_raro_es_invalida(sesion):
    m, em = _emisor()
    em.inicio()
    with pytest.raises(m.SesionInvalida):
        em.fin(sesion, E_VALIDO)
    with pytest.raises(m.EmisionOcupada):  # un id raro no destruye la sesión legítima
        em.inicio()
