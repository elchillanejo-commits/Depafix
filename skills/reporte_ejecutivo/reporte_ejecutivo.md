# Skill: Reporte Ejecutivo de Negocio

## Objetivo
Generar informes ejecutivos en PDF con métricas clave del negocio (presupuestos, clientes, facturación, etc.) utilizando datos de la base de datos de DepaFix.

## Cuándo usar este skill
- Cuando el usuario pida "generar un informe ejecutivo" o "reporte de negocios".
- Para obtener un resumen semanal o mensual de la actividad comercial.
- Para compartir KPIs con el equipo o inversionistas.

## Flujo de trabajo
1. **Consultar la base de datos**:
   - Total de presupuestos (por estado).
   - Facturación del mes (suma de presupuestos aprobados/pagados).
   - Top 5 clientes por monto facturado.
   - Distribución de presupuestos por comuna (si existe).
   - Alertas críticas (ej: materiales con stock bajo, facturas vencidas).

2. **Generar el PDF**:
   - Usar el script `generar_reporte.py` para crear el informe.
   - El PDF se guarda en `~/tmp/reporte_ejecutivo_YYYYMMDD.pdf`.

3. **Entrega**:
   - Mostrar la ruta del PDF generado.
   - Opcional: enviar por correo (si está configurado).

## Estilo del documento
- Logo: DepaFix (si existe en `~/Proyectos/DepaFix/core/static/logo.png`).
- Colores: azul marino (#0a1e2e), grises suaves.
- Tablas con métricas y gráficos simples (barras, torta) si es posible.
- Fecha de generación y página.

## Dependencias
- Python: reportlab, psycopg2, matplotlib.
- Base de datos: PostgreSQL (depafix).

## Script asociado
- `generar_reporte.py` (debe estar en la misma carpeta).

## Notas
- Si no hay datos en algunos campos, mostrar "Sin datos".
- El informe se genera con los datos disponibles en el momento de la ejecución.
