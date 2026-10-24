# TDD: restricciones de capacidad (deben fallar sin implementación)
# Perfil hipotético: 26k

import pytest

PROFILE_MAX_ACCOUNTS = 26000
PROFILE_MAX_QUEUE = 500

def test_cannot_register_beyond_profile_limit():
    """Si se alcanza el límite del perfil, registro rechaza nuevas altas."""
    assert False  # pendiente: implementar límite real

def test_vote_rejected_when_queue_full():
    """Cola llena -> 503 con Retry-After."""
    assert False

def test_verified_user_always_can_vote():
    """Nunca suspender recepción de votos de usuarios ya verificados."""
    assert False
