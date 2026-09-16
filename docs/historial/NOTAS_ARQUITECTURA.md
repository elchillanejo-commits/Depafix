
## Tablas con nombre engañoso (riesgo para agentes)

| Tabla actual | Función real | Acción recomendada |
|---|---|---|
| obras.obras | Inventario de materiales (material/cantidad/unidad) | Renombrar a obras.materiales_inventario |
| obras.presupuestos | Registro operativo de una obra (no financiero puro) | Documentar bien en modelos.py |
| siegfried.casos_auditoria_siegfried | Log de iteraciones de auditoría real | Nombre OK, solo documentar |

## Convención para tablas nuevas
[schema]_[entidad]_[rol] — ejemplo: obras_proyectos_maestra, legal_causas_bitacora
