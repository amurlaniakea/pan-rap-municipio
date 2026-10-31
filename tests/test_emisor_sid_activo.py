# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
from coincurve import PrivateKey

from emisor_schnorr import Emisor


def test_sid_activo_sigue_la_vida_de_la_sesion():
    t = [0.0]
    em = Emisor(PrivateKey().secret, ttl=10.0, reloj=lambda: t[0])
    assert em.sid_activo() is None
    sid, _ = em.inicio()
    assert em.sid_activo() == sid
    t[0] = 9.9
    assert em.sid_activo() == sid
    t[0] = 10.0          # caducada
    assert em.sid_activo() is None
    sid2, _ = em.inicio()
    assert sid2 != sid and em.sid_activo() == sid2
    em.fin(sid2, (1).to_bytes(32, "big"))
    assert em.sid_activo() is None
