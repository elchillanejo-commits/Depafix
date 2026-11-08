# Router de Intenciones (Mente 360) - Regla de Enrutamiento

## 1. Misión del Router
Capturar el input en lenguaje natural del usuario, "oler" la naturaleza del problema y delegar exclusivamente al Profesor correspondiente (`Tierra`, `Metal`, `Agua`, `Aire`, `Fuego`, `OS10`, `Ciber`, o `SENCE`).

## 2. Matriz de Activación para el Elemento TIERRA
El Router debe derivar la consulta al **Profesor de Tierra** si el texto contiene términos relacionados con:
- **Acciones:** cotizar, instalar, construir, remodelar, calcular, presupuestar, cubicación, cubicaciones.
- **Materiales o Partidas:** cerámica, tabiquería, pintura, materiales, m², artefactos, luces, instalaciones.
- **Ubicaciones (Memoria PPTOS):** Ñuñoa, Macul, Santiago, o referencias directas a obras y carpetas de presupuestos históricos.

## 3. Protocolo de Bloqueo / Excepción
Si la consulta es ambigua (ej. *"¿Cómo hacemos esto?"* sin contexto), el Router no debe adivinar ni gastar tokens pasando la pregunta a ciegas; debe solicitar aclaración inmediata al usuario sobre el área operativa (Construcción, Legal, Marketing, etc.).
