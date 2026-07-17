# 03_LOGICA_NEGOCIO_CONTABLE: Reglas Contables

Documentación de los algoritmos y reglas de negocio aplicadas.

## 1. Reglas (corregido 2026-07-16 -- verificado contra core/auditor_ia.py)
- La clasificación contable de movimientos (core/auditor_ia.py, clase
  AuditorContable) usa la tabla 'reglas_contables' -- NO 'precios_serviu'.
  Es un subsistema separado: reglas_contables clasifica descripciones de
  movimientos de caja contra reglas por prioridad; no tiene relación con
  el pricing SERVIU/MINVU de precios_serviu (ver 02_MODELO_DATOS_SERVIU.md).
- Los cálculos de presupuestos (subsidios/materiales) sí se basan en
  'precios_serviu', pero vía core/predict_logic.py y core/trade_agent.py,
  no vía core/auditor_ia.py.
- Todo ajuste contable requiere auditoría previa (ver core/auditor_ia.py).

## 2. Auditoría
- Logs generados localmente (movimientos_pendientes.jsonl como fallback) y
  validados contra Supabase (tabla reglas_contables).
