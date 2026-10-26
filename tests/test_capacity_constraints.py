# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
# TDD: restricciones de capacidad (deben fallar sin implementación)
# Perfil hipotético: 26k

import pytest

PROFILE_MAX_ACCOUNTS = 26000
PROFILE_MAX_QUEUE = 500

@pytest.mark.xfail(strict=True, reason="TDD pendiente")
def test_cannot_register_beyond_profile_limit():
    """Si se alcanza el límite del perfil, registro rechaza nuevas altas."""
    assert False  # pendiente: implementar límite real

@pytest.mark.xfail(strict=True, reason="TDD pendiente")
def test_vote_rejected_when_queue_full():
    """Cola llena -> 503 con Retry-After."""
    assert False

@pytest.mark.xfail(strict=True, reason="TDD pendiente")
def test_verified_user_always_can_vote():
    """Nunca suspender recepción de votos de usuarios ya verificados."""
    assert False
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
