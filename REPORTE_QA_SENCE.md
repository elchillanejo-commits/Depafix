# Reporte QA — Módulo SENCE

Fecha: 3 de noviembre de 2026.
Supervisor: Flint — QA.
Frente: API FastAPI (`api_cotizador.py`) + Tool SENCE (`sence_tools.py`) + tabla `franquicia_empresas`.

## Resumen ejecutivo

| Criterio | Estado QA | Detalle |
|---|---|---|
| **API funciona** | ✅ | `GET /health` → **200 OK**. `POST /calcular-franquicia` → **200 OK**. |
| **Cálculo correcto** | ✅ | RUT conocido devuelve `disponible: 251500` y `fuente: "franquicia_empresas"`. RUT desconocido devuelve estimación con `es_estimacion: true`. |
| **Sin dependencias rotas** | ✅ | `sence_tools.py` responde sin LangChain; el endpoint consulta Supabase y mantiene contrato JSON. |

## Evidencia de verificación

### Salud de la API

```bash
curl -sS -m 10 -w "\nHTTP_CODE:%{http_code}\n" http://localhost:8000/health
```

```json
{"status":"ok"}
HTTP_CODE:200
```

### Caso conocido: saldo real

```bash
curl -sS -m 20 -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST http://localhost:8000/calcular-franquicia \
  -H 'Content-Type: application/json' \
  -d '{"rut_empresa":"76.123.456-7","trabajadores":[]}'
```

```json
{"success":true,"data":{"rut_empresa":"76.123.456-7","rut":"76.123.456-7","razon_social":"Zengin OTEC SpA","trabajadores":0,"masa_imponible":0,"utm_valor":67000.0,"tope_anual":301500.0,"franquicia_anual":301500.0,"usado":50000.0,"disponible":251500.0,"año":2026,"fuente":"franquicia_empresas","es_estimacion":false,"nota":"Registro oficial encontrado en franquicia_empresas."}}
HTTP_CODE:200
```

### Caso desconocido: estimación

```bash
curl -sS -m 20 -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST http://localhost:8000/calcular-franquicia \
  -H 'Content-Type: application/json' \
  -d '{"rut_empresa":"11.111.111-1","trabajadores":[{"remuneracion":1500000}]}'
```

```json
{"success":true,"data":{"rut_empresa":"11.111.111-1","rut":"11.111.111-1","razon_social":"Desconocida","trabajadores":1,"masa_imponible":1500000.0,"utm_valor":67000.0,"tope_anual":301500.0,"franquicia_anual":90000.0,"usado":0.0,"disponible":90000.0,"año":2026,"fuente":"estimacion","es_estimacion":true,"nota":"No hay registro en franquicia_empresas para este RUT; se entrega una estimación con 6% de la masa imponible y tope anual de 4,5 UTM por empresa."}}
HTTP_CODE:200
```

## Validaciones

- ✅ API responde con JSON válido.
- ✅ RUT conocido lee `franquicia_empresas` y devuelve `disponible: 251500`.
- ✅ RUT desconocido devuelve `es_estimacion: true`.
- ✅ HTTP 200 en todos los casos verificados.

## Conclusión

**CIERRE DEL MÓDULO SENCE: APROBADO.**

Firma:

**Flint — Supervisor QA**  
**3 de noviembre de 2026**
