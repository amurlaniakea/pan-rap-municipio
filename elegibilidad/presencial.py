from .base import ProveedorElegibilidad
class Presencial(ProveedorElegibilidad):
    def registrar(self, convocatoria_id: str, datos: dict) -> str:
        return datos.get("dni", "")
    def autenticar(self, convocatoria_id: str, credencial: str) -> str | None:
        return credencial if credencial else None
