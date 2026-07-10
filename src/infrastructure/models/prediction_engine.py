import random
from src.domain.ports import PredictionEnginePort
from src.domain.entities import Obra
from src.domain.value_objects import MetrosCuadrados, DuracionEstimada, Confianza

class SimplePredictionEngine(PredictionEnginePort):
    """Motor de predicción basado en reglas (ejemplo)."""
    def predecir(self, metros: MetrosCuadrados, obra: Obra) -> DuracionEstimada:
        base = 30
        factor = 1.2 if "pintura" in obra.nombre.lower() else 1.0
        dias = int(metros.valor * 0.5 * factor) + random.randint(-5, 5)
        conf = random.uniform(0.7, 1.0)
        return DuracionEstimada(dias=max(1, dias), confianza=Confianza(valor=conf))
