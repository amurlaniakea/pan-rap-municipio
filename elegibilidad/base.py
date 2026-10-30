"""Protocolo ProveedorElegibilidad."""
from abc import ABC, abstractmethod

class ProveedorElegibilidad(ABC):
    @abstractmethod
    def registrar(self, convocatoria_id: str, datos: dict) -> str:
        ...

    @abstractmethod
    def autenticar(self, convocatoria_id: str, credencial: str) -> str | None:
        ...
