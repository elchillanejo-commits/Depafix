# Arquitectura DepaFix

## Diagrama (Mermaid)

```mermaid
flowchart LR
    subgraph fuentes[Fuentes de datos]
        WEB[Sitios web / portales]
        TR[Transcripciones y documentos]
    end

    subgraph ingesta[Ingesta y scraping]
        SCR[Scraper automático\n(07_IKKI_MARKETING / jobs programados)]
        ING[Pipeline de ingesta\n(normalización, chunking)]
    end

    subgraph conocimiento[Knowledge Core / RAG]
        EMB[Embeddings + índice]
        VDB[(Almacén vectorial / chunks)]
        RET[Recuperación semántica]
    end

    subgraph servicios[Servicios de aplicación]
        API[API DepaFix\n(FastAPI / endpoints)]
        COT[Motor de cotización y lógica de negocio]
        COACH[Coaches / agentes especializados]
    end

    subgraph usuarios[Consumo]
        UI[Dashboard / Streamlit / clientes]
        EXT[Integraciones externas]
    end

    WEB --> SCR
    TR --> ING
    SCR --> ING
    ING --> EMB
    EMB --> VDB
    VDB --> RET

    UI --> API
    EXT --> API
    API --> COT
    API --> RET
    RET --> COACH
    COT --> COACH
    COACH --> API
    API --> UI
```

## Cómo interactúan el scraper, el RAG y la API

El **scraper** automatiza la recolección de información desde fuentes externas (sitios web, listados y contenidos relevantes) y la entrega al pipeline de ingesta. Allí los datos se limpian, se estructuran y se fragmentan en unidades manejables (chunks) con metadatos, de modo que el conocimiento operativo de DepaFix se actualiza de forma periódica sin depender de carga manual. Esta capa es la puerta de entrada del sistema: transforma señales dispersas del mercado o de la operación en material utilizable por el resto de la plataforma.

El **RAG (Retrieval-Augmented Generation)** toma esos chunks, genera representaciones vectoriales (embeddings) y permite recuperar, ante una consulta, los fragmentos más pertinentes del Knowledge Core. La **API** actúa como orquestador entre usuarios/integraciones y las capacidades internas: recibe solicitudes, invoca recuperación semántica cuando hace falta contexto, combina resultados con reglas de negocio (por ejemplo, cotización, validaciones o cláusulas) y delega en coaches/agentes especializados para producir respuestas trazables y fundamentadas en la base de conocimiento. En conjunto, el flujo es: *scraper → ingesta → Knowledge Core (RAG) → API/coaches → respuesta al cliente o al dashboard*.
