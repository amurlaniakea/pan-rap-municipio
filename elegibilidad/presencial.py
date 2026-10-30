"""Modo presencial: registrador entrega código que el votante presenta."""
from .base import ProveedorElegibilidad
import secrets, hmac, hashlib

class Presencial(ProveedorElegibilidad):
    def __init__(self, secreto_convocatoria: bytes, registradores: list | None = None):
        self.secreto = secreto_convocatoria
        self.registradores = registradores or ["admin"]
        self.codigos_usados = set()

    def generar_codigo(self, registrador: str) -> str | None:
        if registrador not in self.registradores:
            return None
        return secrets.token_urlsafe(16)

    def registrar(self, convocatoria_id: str, datos: dict) -> str | None:
        codigo = datos.get("codigo")
        if not codigo or codigo in self.codigos_usados:
            return None
        # NOTA: codigos_usados es un set en memoria. Se pierde al reiniciar el servidor.
        # Para producción, persistir en base de datos.
        mensaje = f"{convocatoria_id}:{codigo}".encode()
        persona_ref = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        self.codigos_usados.add(codigo)
        return persona_ref

    def autenticar(self, convocatoria_id: str, credencial: str) -> str | None:
        mensaje = f"{convocatoria_id}:{credencial}".encode()
        persona_ref_esperada = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        return persona_ref_esperada
