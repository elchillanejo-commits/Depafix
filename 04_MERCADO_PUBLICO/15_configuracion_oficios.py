#!/usr/bin/env python3
"""
Patrones de búsqueda reutilizables por oficio.
Cada entrada define las palabras clave típicas de ese rubro para
personalizar búsquedas de licitaciones (ver 14_busqueda_cliente_rut.py).
"""

OFICIOS = {
    "remodelacion": {
        "nombre": "Mejoramiento y remodelación",
        "palabras_clave": [
            "mejoramiento", "remodelación", "reparación", "mantenimiento",
            "ampliación", "refacción", "restauración", "acondicionamiento",
        ],
    },
    "gasfiteria": {
        "nombre": "Gasfitería y redes sanitarias",
        "palabras_clave": [
            "gasfitería", "gasfiteria", "agua potable", "alcantarillado",
            "sanitario", "cañería", "cañerias",
        ],
    },
    "electricidad": {
        "nombre": "Instalaciones eléctricas",
        "palabras_clave": [
            "eléctrico", "electrico", "instalación eléctrica",
            "tablero eléctrico", "cableado", "iluminación", "iluminacion",
        ],
    },
    "pintura": {
        "nombre": "Pintura y terminaciones",
        "palabras_clave": ["pintura", "pintado", "terminaciones", "revestimiento"],
    },
    "construccion_general": {
        "nombre": "Construcción y obra gruesa",
        "palabras_clave": [
            "construcción", "construccion", "obra gruesa",
            "edificación", "edificacion",
        ],
    },
    "climatizacion": {
        "nombre": "Climatización y calefacción",
        "palabras_clave": [
            "climatización", "climatizacion", "calefacción", "calefaccion",
            "ventilación", "ventilacion", "aire acondicionado",
        ],
    },
}


def obtener_oficio(clave: str) -> dict:
    """Devuelve la configuración de un oficio o lanza ValueError si no existe."""
    if clave not in OFICIOS:
        disponibles = ", ".join(OFICIOS.keys())
        raise ValueError(f"Oficio '{clave}' no configurado. Disponibles: {disponibles}")
    return OFICIOS[clave]


if __name__ == "__main__":
    for clave, datos in OFICIOS.items():
        print(f"{clave}: {datos['nombre']} ({len(datos['palabras_clave'])} palabras clave)")
