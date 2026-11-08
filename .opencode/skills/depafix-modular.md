# Skill: Depafix Modular Frontend & Leaflet Integration (@depafix-modular)

## 1. Arquitectura de la Web Estática Modular
Depafix utiliza un enfoque de componentes estáticos desacoplados. 
- **Estructura de Directorios:** Los módulos deben mantenerse modulares, separando la lógica de renderizado estático de los scripts de procesamiento de datos.
- **Datos Agnósticos:** Las vistas consumen exclusivamente archivos de configuración YAML o JSON estructurados, sin hardcodear lógica de negocio en el HTML.

## 2. Integración con Leaflet (Mapas y Coordenadas)
Para la visualización de obras, terrenos o trazados inmobiliarios:
- **Carga de Coordenadas:** Toda latitud y longitud debe provenir normalizada del pipeline de datos.
- **Renderizado de Capas:** Los reportes de desviación deben inyectarse en los marcadores de Leaflet mediante objetos GeoJSON o arrays de puntos limpios.
- **Estilo:** Mantener interfaces limpias, ligeras y orientadas a la visualización rápida en terreno, compatibles con dispositivos móviles y navegadores de escritorio.

## 3. Reglas de Salida (Output)
- **HTML/JS:** Código vainilla o modular sin dependencias pesadas de frameworks de frontend innecesarios, priorizando velocidad de carga estática.
- **Reportes de Desviación:** El formato visual debe destacar claramente las alertas (costos, plazos o coordenadas fuera de rango) según los umbrales definidos en el archivo YAML de configuración del proyecto.
