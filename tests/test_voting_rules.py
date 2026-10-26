# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
# TDD: reglas de votación
import pytest

@pytest.mark.xfail(strict=True, reason="TDD pendiente")
def test_double_vote_is_impossible():
    """UNIQUE(propuesta_id, usuario_id) bloquea duplicados."""
    assert False

@pytest.mark.xfail(strict=True, reason="TDD pendiente")
def test_invalid_ecc_signature_is_rejected():
    """firma_ec no válida -> voto rechazado."""
    assert False

@pytest.mark.xfail(strict=True, reason="TDD pendiente")
def test_cross_postal_aval_required():
    """Propuesta requiere al menos 1 comentario de CP distinto al creador."""
    assert False
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
