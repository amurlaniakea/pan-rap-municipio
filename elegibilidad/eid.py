from .base import ProveedorElegibilidad
class Eid(ProveedorElegibilidad):
    def registrar(self, convocatoria_id: str, datos: dict) -> str:
        return "eid_placeholder"
    def autenticar(self, convocatoria_id: str, credencial: str) -> str | None:
        return None
