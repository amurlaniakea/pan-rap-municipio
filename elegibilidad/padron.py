"""Modo padron: persona_ref = HMAC-SHA256(secreto_convocatoria, identificador)."""
import hmac, hashlib
from .base import ProveedorElegibilidad

class Padron(ProveedorElegibilidad):
    def __init__(self, secreto_convocatoria: bytes, censo: set | None = None):
        self.secreto = secreto_convocatoria
        self.censo = censo if censo is not None else set()

    def registrar(self, convocatoria_id: str, datos: dict) -> str:
        identificador = datos.get("identificador", datos.get("dni", datos.get("id")))
        if identificador not in self.censo:
            return None
        mensaje = f"{convocatoria_id}:{identificador}".encode()
        persona_ref = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        return persona_ref

    def autenticar(self, convocatoria_id: str, credencial: str) -> str | None:
        if not credencial:
            return None
        mensaje = f"{convocatoria_id}:{credencial}".encode()
        persona_ref_esperada = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        # Verificación contra censo: el identificador debe estar en el censo cargado
        identificador = credencial
        if identificador not in self.censo:
            return None
        return persona_ref_esperada
