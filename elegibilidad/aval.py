"""Modo aval: K personas registradas avalan a una nueva persona."""
from .base import ProveedorElegibilidad
import hmac, hashlib

class Aval(ProveedorElegibilidad):
    def __init__(self, secreto_convocatoria: bytes, k: int = 3, tope_avales: int = 5):
        self.secreto = secreto_convocatoria
        self.k = k
        self.tope_avales = tope_avales
        self.avales = {}

    def dar_aval(self, avalador_ref: str, avalado_ident: str, convocatoria_id: str) -> bool:
        # NOTA: avales es un dict en memoria. Se pierde al reiniciar el servidor.
        # Para producción, persistir en base de datos.
        if avalador_ref not in self.avales:
            self.avales[avalador_ref] = []
        if len(self.avales[avalador_ref]) >= self.tope_avales:
            return False
        self.avales[avalador_ref].append(avalado_ident)
        return True

    def tiene_suficientes_avales(self, identificador: str) -> bool:
        count = 0
        for avalador_ref, avalados in self.avales.items():
            if identificador in avalados:
                count += 1
        return count >= self.k

    def registrar(self, convocatoria_id: str, datos: dict) -> str | None:
        identificador = datos.get("identificador", datos.get("dni", datos.get("id")))
        if not self.tiene_suficientes_avales(identificador):
            return None
        mensaje = f"{convocatoria_id}:{identificador}".encode()
        persona_ref = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        return persona_ref

    def autenticar(self, convocatoria_id: str, credencial: str) -> str | None:
        mensaje = f"{convocatoria_id}:{credencial}".encode()
        persona_ref_esperada = hmac.new(self.secreto, mensaje, hashlib.sha256).hexdigest()
        # Verificar si está avalado: buscar la referencia del avalado en los avales registrados
        for avalador_ref, avalados in self.avales.items():
            if credencial in avalados:
                return persona_ref_esperada
        return None
