# Skill: Depafix DTE & Domain Normalization (@depafix-dte)

## 1. Contexto del Dominio
Depafix es un sistema de gestión de obras y holding digital que opera bajo un enfoque de **datos agnósticos** y archivos de configuración YAML. El pipeline principal sigue estrictamente este flujo:
1. **Input:** DTEs (Documentos Tributarios Electrónicos) o Planos.
2. **Proceso:** Normalización de datos, validación de esquemas y mapeo con coordenadas Leaflet.
3. **Output:** Reportes de desviación y vistas estáticas modulares.

## 2. Contrato de Datos (Esquema Base JSON/YAML)
Toda función que procese DTEs debe ajustarse a este contrato estricto para evitar discrepancias en los módulos:

```json
{
  "dte_id": "string (UUID o folio único)",
  "tipo_documento": "integer (ej. 33 Factura, 61 Nota de Crédito)",
  "emisor": {
    "rut": "string (Formato XX.XXX.XXX-X)",
    "razon_social": "string"
  },
  "receptor": {
    "rut": "string",
    "razon_social": "string"
  },
  "totales": {
    "neto": "float",
    "iva": "float",
    "total": "float"
  },
  "items": [
    {
      "codigo": "string",
      "descripcion": "string",
      "cantidad": "float",
      "precio_unitario": "float"
    }
  ]
}
