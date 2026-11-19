# CHECKLIST MÓVIL — RUTA TERRENO STGO CENTRO

**Generado:** 2026-11-18 23:31  
**Cobertura:** 50 registros de la comuna de Santiago; 49 visitables y 1 administrativo.  
**Objetivo:** inspección técnica, validación de agua caliente, evidencias antes/después y levantamiento Ready-to-Rent.

> No registrar RUT, correo ni teléfono en este documento. La coordinación con propietarios/arrendatarios es responsabilidad del corredor.

## 1. Rutas por bloque

### Bloque 1

- [ ] **B1A** — 6 paradas / 26 unidades. [Abrir ruta en Google Maps](https://www.google.com/maps/dir/?api=1&origin=-33.458496,-70.675049&destination=-33.454911,-70.659785&travelmode=driving&waypoints=-33.458856,-70.677417|-33.453637,-70.669581|-33.454070,-70.663019|-33.453394,-70.660113)

### Bloque 2

- [ ] **B2A** — 11 paradas / 12 unidades. [Abrir ruta en Google Maps](https://www.google.com/maps/dir/?api=1&origin=-33.435469,-70.654023&destination=-33.471652,-70.649850&travelmode=driving&waypoints=-33.435938,-70.648049|-33.438218,-70.656389|-33.437608,-70.663746|-33.447673,-70.653474|-33.448557,-70.654751|-33.449653,-70.654590|-33.449516,-70.660225|-33.466552,-70.654800|-33.466983,-70.653705)
- [ ] **B2B** — 2 paradas / 2 unidades. [Abrir ruta en Google Maps](https://www.google.com/maps/dir/?api=1&origin=-33.475061,-70.648396&destination=-33.471569,-70.628334&travelmode=driving)

### Bloque 3

- [ ] **B3A** — 9 paradas / 9 unidades. [Abrir ruta en Google Maps](https://www.google.com/maps/dir/?api=1&origin=-33.450214,-70.647000&destination=-33.470273,-70.626344&travelmode=driving&waypoints=-33.449027,-70.642919|-33.448633,-70.643601|-33.444524,-70.644331|-33.444675,-70.642823|-33.448491,-70.636058|-33.456808,-70.643783|-33.468241,-70.626316)

## 2. Vacantes prioritarias Ready-to-Rent

| # | Prioridad | Dirección | m² | Dorm/Baño | Acción |
|---|---|---|---|---|---|
| 1 | A | Avenida España 397, Depto. 702 | s/d | s/d | Medir superficie; cotizar piso SPC por m² + iluminación LED + enchufes + soporte TV. |
| 2 | A | Blanco Encalada 1771, Depto. 1605 | 42 | 1/1 | Quick win: piso SPC, plafones LED, enchufes y soporte TV; validar agua caliente. |
| 3 | A | Santa Isabel 326, Depto. 210 | s/d | s/d | Medir superficie; cotizar piso SPC por m² + iluminación LED + enchufes + soporte TV. |
| 4 | A | San Ignacio 1498, Depto. 701 | s/d | s/d | Medir superficie; cotizar piso SPC por m² + iluminación LED + enchufes + soporte TV. |
| 5 | B | Carmen 110, Depto. 2215 | 30 | s/d | Quick win: piso SPC, plafones LED, enchufes y soporte TV; validar agua caliente. |
| 6 | B | Toesca 2002, Depto. 704 | 34 | s/d | Quick win: piso SPC, plafones LED, enchufes y soporte TV; validar agua caliente. |
| 7 | B | San Isidro 379, Depto. 151 | 80 | 3/2 | Remodelación estándar: piso SPC, iluminación, enchufes y soporte TV; presupuestar por partidas. |

## 3. Antes de salir

- [ ] Celular cargado + power bank + cable.
- [ ] Google Maps offline del área Santiago Centro descargado.
- [ ] Este checklist y `RUTA_TERRENO_STGO_CENTRO.xlsx` disponibles sin internet.
- [ ] Huincha láser, linterna, guantes y calzado de seguridad.
- [ ] Cámara/celular con fecha y hora activadas.
- [ ] Llaves/accesos coordinados con corredor.
- [ ] Confirmar por WhatsApp las visitas del día y el registro administrativo excluido.

## 4. Checklist por unidad

### Acceso y estado
- [ ] Confirmar dirección, torre y departamento.
- [ ] Validar estado: Al día / Vacante / Suspendida / Pago expirado.
- [ ] Registrar nombre del inspector y fecha/hora.
- [ ] Si no hay acceso: marcar `NO_ACCESO` y hora de reintento.

### Agua caliente (punto cero)
- [ ] Tipo: `TERMO_ELECTRICO` / `CALEFONT` / `CALDERA_CENTRAL`.
- [ ] Si es termo: fecha de última mantención y capacidad.
- [ ] Próxima mantención: 6 meses (estándar) o 12 meses (excepción autorizada).
- [ ] Revisar ánodo de magnesio, sarro, válvula y llave de paso.
- [ ] Si es calefont/caldera: presión, llaves de paso y ventilación.

### Evidencias
- [ ] Foto antes: tablero eléctrico.
- [ ] Foto antes: sello de tina/lavaplatos y encuentros de piso con muro.
- [ ] Foto antes: estado general de pintura y piso.
- [ ] Video corto 20-30 s recorriendo la unidad.
- [ ] Fotos después si se ejecuta algún ajuste inmediato.
- [ ] Nomenclatura: `ID_DEPTO_ANTES_01.jpg`, `ID_DEPTO_DESPUES_01.jpg`.

### Requerimientos mayoristas
- [ ] Plafones LED (cantidad y tipo: embutir/sobreponer, 18W/24W).
- [ ] Enchufes y placas (cantidad, Bticino/Legrand).
- [ ] Soporte TV universal (32"-65").
- [ ] m² de piso SPC (medir; si no hay dato, estimar y marcar).
- [ ] Silicona neutra antihongo y flexibles de agua/gas.

### Evaluación Ready-to-Rent
- [ ] Alfombra/flotante agotado o levantado.
- [ ] Pisos que requieren conversión a SPC.
- [ ] Iluminación deficiente o luminarias antiguas.
- [ ] Enchufes insuficientes o sin puesta a tierra.
- [ ] Pintura, sellos y humedad.

## 5. Cierre post-visita

- [ ] Insertar/actualizar inspección en `inspecciones_terreno`.
- [ ] Adjuntar rutas de fotos/videos antes y después.
- [ ] Crear `presupuestos_obra` en estado `BORRADOR` si hay remodelación.
- [ ] Registrar contacto del corredor en `log_comunicaciones_corredor`.
- [ ] WhatsApp: `PENDIENTE` / `ENVIADO` / `RESPONDIDO` / `SIN_RESPUESTA`.
- [ ] Llamada: `AGENDADO` / `RECHAZADO` / `CERRADO`.
- [ ] Definir próximo seguimiento y responsable.

## 6. Base de datos y regeneración

- SQLite: `/home/ibar/DepaFix_Maestro/datos/terreno_stgo_centro.db`
- Tablas: `inspecciones_terreno`, `presupuestos_obra`, `log_comunicaciones_corredor`.
- El pipeline deja 49 inspecciones `PENDIENTE` y 1 registro `NO_APLICA`.

```bash
cd /home/ibar/DepaFix_Maestro
python3 -m operacion_terreno \
  --xlsx /home/ibar/Descargas/propiedades_11_2026.xlsx \
  --plan PLAN_RUTA_Y_PRESUPUESTOS_STGO.md \
  --outdir .
```

## 7. Notas

- Antigüedad: estimación referencial; cobertura de catastro: 49/50 (98%).
- Google Maps: segmentos de hasta 11 paradas (máximo 9 waypoints); no se repiten paradas entre segmentos.
- El registro administrativo ID 64395 no se visita.
- El departamento 1605 de Blanco Encalada 1771 tiene dos registros; confirmar si son dos unidades.
