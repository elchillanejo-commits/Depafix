# Manual de Uso Rápido

## 1. Procesar PDF de subcontratista (margen 40% explícito + Supabase)

```bash
cd /home/ibar/DepaFix_Maestro && .venv/bin/python procesar_subcontrato.py --pdf "/home/ibar/Documentos/Conocimiento/Tierra_Construccion/Cotizaciones_Reales/PPTOS/Stgo Centro/Blanco Encalada 1771 dpto 1313/Presupuesto_AMD_Mantenciones_Fullprop_Blanco_Encalada_1771_con_materiales.pdf" --proyecto "PRY-BLANCO-1313" --proveedor "AMD" --sku-prefix "AMD" --fecha-requerida "2026-11-15"
```

## 2. Verificar materiales

```bash
cd /home/ibar/DepaFix_Maestro && .venv/bin/python verificar_materiales.py --proyecto "PRY-BLANCO-1313"
```

## 3. Preguntar al CEO

```bash
cd /home/ibar/DepaFix_Maestro && .venv/bin/python mente_360.py
```
