# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
"""Emisor Blind Schnorr (secp256k1): lado servidor de la firma ciega (03-motor-blind-schnorr.md).

Condiciones de seguridad que cumple este módulo:
  S1  una sola sesión abierta a la vez (cerrojo) y caducidad por TTL;
  S4  todo cálculo con secretos (k, d, s = k + d·e) lo hace libsecp256k1 vía coincurve: aquí no hay
      enteros de Python derivados de k ni de d (solo se convierte `e`, que es público);
  S5  k sale del CSPRNG en cada sesión y se descarta al terminar o caducar.
Limitación conocida: Python no permite borrar memoria; «descartar» significa soltar la referencia.
"""
import secrets
import threading
import time

from coincurve import PrivateKey

Q = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141  # orden de secp256k1 (público)


class EmisionOcupada(Exception):
    """Ya hay una sesión abierta (S1)."""


class SesionInvalida(Exception):
    """Sesión desconocida, caducada o ya usada."""


class EntradaInvalida(Exception):
    """`e` con longitud incorrecta o fuera de (0, q)."""


def _mismo_id(a, b) -> bool:
    """Comparación en tiempo constante; un tipo o formato raro no es un error, simplemente no coincide."""
    try:
        return secrets.compare_digest(a, b)
    except TypeError:
        return False


# TODO (Fase 7 - Producción): El cerrojo threading.Lock() limita a 1 worker de Uvicorn.
# Para escalar horizontalmente, migrar el estado de sesión (sid, k, ttl) a Redis
# con TTL nativo y bloqueos distribuidos (SETNX), permitiendo múltiples workers.

class Emisor:
    def __init__(self, d: bytes, ttl: float = 10.0, reloj=time.monotonic):
        self._d = PrivateKey(d)  # ValueError si d no es un escalar válido
        self.Y = self._d.public_key.format()  # clave pública comprimida, 33 bytes
        self._ttl = ttl
        self._reloj = reloj
        self._cerrojo = threading.Lock()
        self._sesion = None  # (id, k, instante de inicio) o None

    def _caducada(self, sesion) -> bool:
        return self._reloj() - sesion[2] >= self._ttl

    def inicio(self):
        """Abre una sesión. Devuelve (id de sesión, R de 33 bytes)."""
        with self._cerrojo:
            if self._sesion is not None and not self._caducada(self._sesion):
                raise EmisionOcupada()
            k = PrivateKey()  # CSPRNG: escalar nuevo en cada sesión (S5)
            sid = secrets.token_hex(16)
            self._sesion = (sid, k, self._reloj())
            return sid, k.public_key.format()

    def fin(self, sesion: str, e: bytes) -> bytes:
        """Cierra la sesión y devuelve s = k + d·e (mod q), 32 bytes.

        Una sesión válida se destruye siempre, también cuando `e` es inválida."""
        with self._cerrojo:
            actual = self._sesion
            if actual is None:
                raise SesionInvalida()
            if self._caducada(actual):
                self._sesion = None  # caducada: se descarta k
                raise SesionInvalida()
            if not _mismo_id(actual[0], sesion):
                raise SesionInvalida()  # un id ajeno no destruye la sesión de otro
            self._sesion = None  # k se descarta pase lo que pase (S5)
            if not isinstance(e, bytes) or len(e) != 32 or not 0 < int.from_bytes(e, "big") < Q:
                raise EntradaInvalida()
            return self._d.multiply(e, update=False).add(actual[1].secret, update=False).secret
