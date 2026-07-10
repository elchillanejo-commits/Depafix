from abc import ABC, abstractmethod
from .entities import Obra
from .value_objects import MetrosCuadrados, DuracionEstimada

class PredictionEnginePort(ABC):
    @abstractmethod
    def predecir(self, metros: MetrosCuadrados, obra: Obra) -> DuracionEstimada:
        ...

class ObraRepositoryPort(ABC):
    @abstractmethod
    def guardar(self, obra: Obra) -> None: ...
    @abstractmethod
    def buscar_por_id(self, id_obra: str) -> Obra | None: ...
