# TDD: reglas de votación

def test_double_vote_is_impossible():
    """UNIQUE(propuesta_id, usuario_id) bloquea duplicados."""
    assert False

def test_invalid_ecc_signature_is_rejected():
    """firma_ec no válida -> voto rechazado."""
    assert False

def test_cross_postal_aval_required():
    """Propuesta requiere al menos 1 comentario de CP distinto al creador."""
    assert False
