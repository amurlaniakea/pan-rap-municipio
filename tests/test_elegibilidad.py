# SPDX-License-Identifier: AGPL-3.0-or-later
# Tests para Fase 3 — Elegibilidad Modular (§6 01-spec-v0.md)
import pytest
import hmac, hashlib
from elegibilidad import Padron

def test_c1_persona_ref_distinta_por_convocatoria():
    p = Padron(b"secreto_convocatoria", censo={"dni_123"})
    ref1 = p.registrar("conv_1", {"identificador": "dni_123"})
    ref2 = p.registrar("conv_2", {"identificador": "dni_123"})
    assert ref1 != ref2

def test_c3_sin_credenciales_401():
    p = Padron(b"secreto_convocatoria")
    assert p.autenticar("conv_1", "") is None

def test_ac_02_persona_no_elegible_403():
    # Si el identificador no está en el registro, autenticar debe fallar
    p = Padron(b"secreto_convocatoria")
    assert p.autenticar("conv_1", "dni_inexistente") is None
