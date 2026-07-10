from src.domain.ports import PredictionEnginePort, ObraRepositoryPort
from src.domain.entities import Obra

class ObraPredictionService:
    def __init__(self, engine: PredictionEnginePort, repository: ObraRepositoryPort):
        self._engine = engine
        self._repository = repository

    def predecir_y_guardar(self, obra: Obra) -> Obra:
        prediccion = self._engine.predecir(obra.metros, obra)
        obra.asignar_prediccion(prediccion)
        self._repository.guardar(obra)
        return obra
