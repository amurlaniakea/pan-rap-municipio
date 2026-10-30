"""Modo padron: persona_ref = HMAC-SHA256(secreto_convocatoria, identificador)."""
import hmac, hashlib
from .base import ProveedorElegibilidad

class Padron(ProveedorElegibilidad):
    def __init__(self, secreto_convocatoria: bytes):
        self.secreto = secreto_convocatoria

    def registrar(self, convocatoria_id: str, datos: dict) -> str:
        identificador = datos.get("identificador", datos.get("dni", datos.get("id")))
        mensaje = f"{convocatoria_id}:{identificador}".encode()
        persona_ref = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        return persona_ref

    def autenticar(self, convocatoria_id: str, credencial: str) -> str | None:
        if not credencial:
            return None
        mensaje = f"{convocatoria_id}:{credencial}".encode()
        persona_ref_esperada = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        return persona_ref_esperada
