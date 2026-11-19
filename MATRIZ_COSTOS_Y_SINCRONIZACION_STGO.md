# Matriz de Costos Mayoristas, Argumentario ROI y Sincronización API — Santiago Centro

## 1. Matriz de Precios Mayoristas y Venta (Base Referencial CLP Neto)
*Valores estandarizados para compras por volumen en bodega DepaFix y cotización rápida al corredor/propietario (incluye margen operativo + 10% comisión corredor).*

| Ítem / Partida | Unidad | Costo Mayorista Est. | Precio Venta Cliente | Margen Bruto | Argumento Técnico / ROI |
|---|---|---|---|---|---|
| **Piso Vinílico SPC (4mm–5mm + manta)** | m² | $11.500 | $22.000 | ~48% | Resistente al agua, elimina alfombra percudida; sube arriendo +$50k-$80k/mes. |
| **Plafón LED Circular (18W/24W)** | Unid. | $3.200 | $9.500 | ~66% | Iluminación moderna, bajo consumo; mejora percepción visual en fotos de portal. |
| **Módulo Enchufe / Interruptor (Bticino/Legrand)** | Unid. | $2.800 | $8.500 | ~67% | Seguridad eléctrica normativa; elimina riesgo de cortocircuito y enchufes sueltos. |
| **Soporte TV Universal (32"–65") + Instalación** | Unid. | $6.500 | $18.000 | ~64% | Evita perforaciones hechizas destructivas de arrendatarios en tabiquería. |
| **Mantención Termo Eléctrico (Ánodo + Purga Sarro)** | Unid. | $12.000 | $38.000 | ~68% | Obligatorio cada 6 meses (o máx 12m); evita quema de resistencia y triplicar gasto luz. |
| **Sellado Perimetral Silicona Antihongo (Baño/Cocina)** | Gl | $4.500 | $16.000 | ~72% | Previene filtraciones a pisos inferiores y multas de administración. |

---

## 2. Casos de Negocio Listos para Cerrar con el Corredor (Vacantes Prioritarias)

### Caso A: Quick Win 1D1B (Ej. Blanco Encalada 1771, Depto. 1605 — 42 m²)
* **Alcance:** 35 m² Piso SPC + 4 Plafones LED + 6 Enchufes + 1 Soporte TV + Sellos Baño/Cocina + Revisión Termo.
* **Inversión Propietario Est.:** ~$930.000 CLP Neto.
* **Retorno:** Se arrienda en menos de 7 días y sube canon de $470.000 a ~$530.000 CLP (+$60.000/mes). Se recupera en ~15 meses y evita vacancia prolongada.

### Caso B: Remodelación Estándar 3D2B (Ej. San Isidro 379, Depto. 151 — 80 m²)
* **Alcance:** 68 m² Piso SPC + 8 Plafones LED + 12 Enchufes + 2 Soportes TV + Sellos completos.
* **Inversión Propietario Est.:** ~$1.780.000 CLP Neto.
* **Retorno:** Transforma unidad antigua en producto ejecutivo "Ready-to-Rent" sin meses muertos.

---

## 3. Especificación Técnica de Sincronización con API Railway
* **Endpoint Destino:** `POST https://depafix-presupuestos-production.up.railway.app/api/v1/cotizaciones/`
* **Base Origen:** `/home/ibar/DepaFix_Maestro/datos/terreno_stgo_centro.db` (tablas `inspecciones_terreno` y `presupuestos_obra`).
* **Estructura Obligatoria del Payload JSON (Validación Pydantic verificada):**
  ```json
  {
    "direccion": "Blanco Encalada 1771, Depto. 1605",
    "comuna": "Santiago",
    "items": [
      {
        "codigo": "SPC-001",
        "desc": "Suministro e instalación piso vinílico SPC (35 m2)",
        "cantidad": 35,
        "precio": 22000.0
      }
    ],
    "total_neto": 770000.0
  }
  ```

* **Regla de Negocio:** Al aprobarse un presupuesto en estado `BORRADOR` dentro de SQLite, el script debe calcular automáticamente el `total_neto` exacto (usando `Decimal`), generar la tabla resumen en Markdown para enviar por WhatsApp al corredor y disparar el `POST` a Railway guardando el `uuid` retornado en SQLite para trazabilidad.
