# Plan Operativo de Inspección, Ruta y Presupuestación — Santiago Centro (50 Propiedades)

## 1. Objetivo Estratégico y Modelo de Negocio (Sociedad con Corredor — 10%)
* **Propuesta de Valor al Corredor:** Ejecución llave en mano de mantenimiento preventivo, remodelaciones rápidas ("Ready-to-Rent") y estandarización de inmuebles bajo el estándar técnico **DepaFix**.
* **Caso de Negocio Concreto (ROI):** Reemplazo de alfombras percudidas o pisos flotantes agotados por **pisos vinílicos SPC** y actualización de luminarias/enchufes. Esto incrementa el canon de arriendo mensual entre **$50.000 y $80.000 CLP**, reduce la vacancia a menos de 7 días y protege la plusvalía del activo.
* **Reparto:** Corredor aporta cartera de propietarios/arrendatarios y gestión comercial (10% del trabajo pagado); Sundara SpA / DepaFix aporta ingeniería, cuadrillas, software CMMS, compra mayorista de insumos y ejecución.

## 2. Segmentación de Ruta Geográfica (De Mayor a Menor Concentración)

### Bloque 1: Eje Poniente / Parque O'Higgins (24 Propiedades — Máxima Densidad)
* **Edificio Blanco Encalada 1771 (9 unidades):** Deptos. 509, 803, 911, 1313, 1605 (x2), 1607, 2002, 2003, 2201.
* **Edificio Blanco Encalada 1797 (1 unidad):** Depto. 203.
* **Edificio Av. Ejército Libertador 650 (10 unidades):** Deptos. 303, 304, 405, 406, 505, 506, 603, 605, 606, 803.
* **Edificio Av. Ejército 520 (2 unidades):** Deptos. 51-B, 81-B.
* **Edificio Toesca 2002 (2 unidades):** Deptos. 704 (*Vacante*), 904.
* **Edificio Av. España 397 (1 unidad):** Depto. 702 (*Vacante*).

### Bloque 2: Eje Centro Cívico, Histórico y Sur-Poniente (17 Propiedades)
* **Morandé 707:** Depto. 1405.
* **Catedral 1350:** Depto. 1504.
* **Santo Domingo 756 (2 unidades):** Deptos. 1508, 1608.
* **Santo Domingo 1890:** Depto. 405-B.
* **Lord Cochrane 184:** Depto. 312.
* **Lord Cochrane 252:** Depto. 1111.
* **Sazié 1738:** Depto. 704 (*Suspendida*).
* **San Ignacio 1498:** Depto. 701 (*Vacante*).
* **Tarapacá 1331:** Depto. 304.
* **Aldunate 1525:** Depto. 1603.
* **San Diego 2381:** Depto. 616-A (*Pago expirado*).
* **Franklin 200:** Depto. 806, Torre B.
* **Nataniel Cox:** ID 53874.

### Bloque 3: Eje Oriente / Vicuña Mackenna (9 Propiedades)
* **San Francisco 467:** Depto. 1804.
* **San Isidro 96:** Depto. 1806.
* **San Isidro 379:** Depto. 151 (*Vacante*).
* **Santa Isabel 326:** Depto. 210 (*Vacante*).
* **Santa Victoria 562:** Depto. 421.
* **Santa Rosa 991:** Depto. 2109-A.
* **Carmen 110:** Depto. 2215 (*Vacante*).
* **Vicuña Mackenna 920:** Depto. 1202.
* **Diagonal Vicuña Mackenna 2004:** Depto. 1110.

## 3. Protocolo Técnico de Inspección en Terreno (Checklist Obligatorio)
1. **Registro Audiovisual Inapelable (Antes y Después):** Fotos geolocalizadas y video corto con marca de fecha/hora enfocando: tablero eléctrico, sellos de tina/lavaplatos, encuentros de piso con muros (humedad) y estado general de pintura.
2. **Punto Cero — Validación de Agua Caliente (Sin asumir):**
   * *Termo Eléctrico Individual:* Si existe, levantar fecha de última mantención. **Regla:** Mantención preventiva cada **6 meses** (cambio ánodo de magnesio y limpieza de sarro); máximo **1 año** para propietarios reticentes (evita quema de resistencia y sobreconsumo).
   * *Calefont / Caldera Central:* Registrar estado de llaves de paso y presión.
3. **Evaluación de Pisos y Terminaciones:** Detectar alfombras antiguas o flotantes levantados para cotizar conversión a **Vinílico SPC**.
4. **Factor Común (Compras Mayoristas Bodega DepaFix):**
   * Plafones LED circulares (18W / 24W embutir y sobreponer).
   * Módulos de enchufes y placas estándar (Bticino / Legrand).
   * Soportes de TV universales (32" a 65") para estandarizar instalaciones y evitar perforaciones destructivas.
   * Silicona neutra antihongo y flexibles de agua/gas.

## 4. Argumentario Técnico de Venta (Para Propietarios)
* **Fatiga de Materiales:** Los departamentos con más de 10-15 años (ej. Morandé, Ejército, Tarapacá) presentan agotamiento en sellos hidráulicos y protecciones eléctricas. La inversión preventiva evita demandas por filtraciones a pisos inferiores y cortocircuitos, cuyo costo triplica una mantención programada.

## 5. Automatización Post-Visita (Pipeline Técnico)
* Una vez capturados los datos en terreno, los registros se inyectan a la base de datos SQLite/PostgreSQL de **DepaFix** para disparar:
  1. Presupuesto PDF automático (Partidas base + Ad-hoc).
  2. Secuencia de mensajería WhatsApp/Llamado coordinada con el corredor para aprobación del propietario.
