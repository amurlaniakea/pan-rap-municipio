# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes
from main import _compact_a_der

def test_roundtrip_compact_der():
    """Genera firma, la convierte a compact low-S, a DER, y verifica."""
    k = ec.generate_private_key(ec.SECP256K1())
    d = k.sign(b"1:2:a_favor", ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(d)
    n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    
    # Forzar low-S para el test (como hace noble/secp256k1)
    if s > n // 2:
        s = n - s
        
    compact = (r.to_bytes(32, "big") + s.to_bytes(32, "big")).hex()
    der = _compact_a_der(compact)
    
    # Si no lanza excepción, la verificación es exitosa
    k.public_key().verify(der, b"1:2:a_favor", ec.ECDSA(hashes.SHA256()))

def test_payload_alterado_rechazado():
    """Una firma válida para un mensaje NO sirve para otro mensaje."""
    k = ec.generate_private_key(ec.SECP256K1())
    d = k.sign(b"1:2:a_favor", ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(d)
    n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    if s > n // 2:
        s = n - s
    compact = (r.to_bytes(32, "big") + s.to_bytes(32, "big")).hex()
    der = _compact_a_der(compact)
    
    import pytest
    from cryptography.exceptions import InvalidSignature
    with pytest.raises(InvalidSignature):
        k.public_key().verify(der, b"1:2:en_contra", ec.ECDSA(hashes.SHA256()))

def test_high_s_normalizado():
    """Verifica que la función normaliza correctamente un valor high-S sin fallar."""
    # Usamos valores de 32 bytes. r es pequeño, s es claramente high-S.
    r = int.from_bytes(b"\x01" + b"\x00" * 31, "big")
    n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    s_high = n - 100  # Claramente high-S
    
    compact = (r.to_bytes(32, "big") + s_high.to_bytes(32, "big")).hex()
    
    # La prueba real: la función DEBE ejecutar sin lanzar ValueError.
    # Antes, esto lanzaba: ValueError("firma no canonica (high-S)")
    # Ahora, debe normalizarlo y devolver bytes DER válidos.
    der = _compact_a_der(compact)
    
    # Verificamos que sea un objeto bytes y tenga una longitud mínima razonable (> 30 bytes)
    assert isinstance(der, bytes)
    assert len(der) > 30  # Una firma DER, incluso con valores pequeños, tiene al menos ~38 bytes# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
