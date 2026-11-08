# OTEC Compliance Copilot

Copiloto de cumplimiento normativo para Organismos Técnicos de Capacitación (OTEC) y empresas que usan la Franquicia Tributaria SENCE (Chile).

## Estructura del proyecto

```
otec-compliance-copilot/
├── opencode.json                 # Definición de los 3 agentes OpenCode
├── .opencode/
│   └── agents/
│       ├── compliance-supervisor.md   # Supervisor (orquestador)
│       ├── plazo-checker.md           # Auditor de plazos SENCE
│       └── participant-auditor.md     # Auditor de participantes
├── data/
│   └── cursos_activos.json     # Schema y ejemplo de entrada
└── README.md                   # Este archivo
```

## Agentes

| Agente | Responsabilidad |
|--------|-----------------|
| `compliance-supervisor` | Recibe consultas, deriva a subagentes y sintetiza respuestas |
| `plazo-checker` | Verifica plazos legales: comunicación de cursos, actualización de costos, facilitadores, LCE |
| `participant-auditor` | Audita participantes, asistencia, facilitadores y certificados |

## Cómo usar

1. Instala OpenCode y configura los agentes desde `opencode.json`.
2. Inicia una conversación con el agente `compliance-supervisor`.
3. Ejemplos de consulta:
   - "¿Tengo plazo para comunicar el curso CUR-2026-001 a SENCE?"
   - "Audita los participantes del curso CUR-2026-002 usando `data/cursos_activos.json`"
   - "¿Cuántas actualizaciones de costo le quedan al código OTEC-12345-2026 este año?"

## Entrada de datos

El sistema espera un archivo JSON tipo `data/cursos_activos.json` con los cursos activos, sus fechas, facilitadores e inscritos. El `plazo-checker` y el `participant-auditor` leen este formato para realizar sus verificaciones.

## Limitaciones legales ⚠️

1. **No es asesoría jurídica.** Este copiloto entrega información basada en normativa pública (Ley N°19.518, DS N°98, Resoluciones Exentas, Circulares SENCE). Siempre verifica con [sence.gob.cl](https://www.sence.gob.cl) o con tu asesor legal antes de actuar.
2. **Plazos y montos referenciales.** Los valores de UTM, topes de franquicia y fechas de vencimiento de versiones de software (LCE) pueden cambiar. Confirma la vigencia en las fuentes oficiales.
3. **Datos personales.** No incluyas RUTs reales, nombres completos ni datos sensibles de trabajadores en los archivos de entrada salvo que tengas autorización y cumplan con la Ley N°19.628 (protección de la vida privada).
4. **No modifica registros oficiales.** Esta herramienta solo lee y evalúa; no emite certificados, no se comunica con SENCE ni altera el Libro de Clases Electrónico.

## Estado de validación de reglas

Todas las reglas de plazos y auditoría contenidas en los archivos de agentes están marcadas con **[PENDIENTE-VALIDACIÓN]**. Esto significa que **no han sido verificadas contra la resolución SENCE vigente** y no deben considerarse definitivas.

### Reglas con estado `[PENDIENTE-VALIDACIÓN]`

**Plazo Checker (`plazo-checker.md`):**
1. Preliquidación de acción de capacitación: 60 días corridos desde fecha de término
2. Presentación de documentos de respaldo: 90 días corridos desde fecha de término
3. Emisión de Declaración Jurada OTEC: antes del vencimiento de liquidación (60 días)
4. Declaración Jurada de participantes: habilitada post-emisión de DJ OTEC
5. Subsanación de observaciones en supervisión: 2 a 5 días hábiles según complejidad

**Participant Auditor (`participant-auditor.md`):**
1. Validación de formato de RUT chileno
2. Consistencia de asistencia libro vs. plataforma
3. Flag de sesión de conectividad no registrada en e-learning

> ⚠️ **Advertencia de producción:** Este agente **no debe usarse en producción** hasta que un abogado o contador confirme cada regla contra la resolución SENCE vigente y las fuentes oficiales (sence.gob.cl). El uso de plazos incorrectos puede generar incumplimiento normativo y sanciones administrativas.

## Normativa citada

- Ley N°19.518 — Estatuto de Capacitación y Empleo
- Decreto Supremo N°98 — Reglamento General de la Ley N°19.518
- Ley N°19.628 — Protección de la vida privada
- Ley N°19.880 — Bases de procedimientos administrativos
- Resoluciones Exentas y Circulares de la Dirección Nacional de SENCE
