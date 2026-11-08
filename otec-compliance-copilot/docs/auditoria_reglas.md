# Auditoría de reglas SENCE — otec-compliance-copilot

## Estado actual del agente (vigente)

| Agente | Regla | Valor | Fuente citada | ¿Verificable? | Tag |
|--------|-------|-------|---------------|---------------|-----|
| plazo-checker | Preliquidación de acción de capacitación | 60 días corridos desde fecha de término | No citada específicamente; el agente remite a la resolución SENCE vigente | Pendiente | [PENDIENTE-VALIDACIÓN] |
| plazo-checker | Presentación de documentos de respaldo | 90 días corridos desde fecha de término | No citada específicamente; el agente remite a la resolución SENCE vigente | Pendiente | [PENDIENTE-VALIDACIÓN] |
| plazo-checker | Emisión de Declaración Jurada OTEC | Antes del vencimiento de liquidación (60 días) | No citada específicamente; el agente remite a la resolución SENCE vigente | Pendiente | [PENDIENTE-VALIDACIÓN] |
| plazo-checker | Declaración Jurada de participantes | Habilitada post-emisión de DJ OTEC | No citada específicamente; el agente remite a la resolución SENCE vigente | Pendiente | [PENDIENTE-VALIDACIÓN] |
| plazo-checker | Subsanación de observaciones en supervisión | 2 a 5 días hábiles según complejidad | No citada específicamente; el agente remite a la resolución SENCE vigente | Pendiente | [PENDIENTE-VALIDACIÓN] |
| participant-auditor | Validación de formato de RUT | RUT chileno con formato válido (ej: 11.222.333-4) | Ley N°19.518 y DS N°98 (referencia general del agente) | Pendiente | [PENDIENTE-VALIDACIÓN] |
| participant-auditor | Consistencia de asistencia libro vs. plataforma | Comparar libro de clases contra plataforma y flaggear inconsistencias | Circular N°9 y Circular N°4 (referencia general del agente) | Pendiente | [PENDIENTE-VALIDACIÓN] |
| participant-auditor | Sesión de conectividad no registrada en e-learning | Detectar sesiones de e-learning sin registro de conectividad en la plataforma | Circular N°9 y Circular N°4 (referencia general del agente) | Pendiente | [PENDIENTE-VALIDACIÓN] |

## Reglas históricas (eliminadas en ciclo 2)

| Agente | Regla (histórica) | Motivo de eliminación |
|--------|-------------------|-----------------------|
| plazo-checker | Comunicación de cursos — empresa (comunicación directa) | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | Comunicación de cursos — OTIC | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | Conteo de plazo comunicación | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | Actualización de costos — máximo por año | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | Actualización de costos — máximo por día | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | Actualización de costos — ajuste | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | Facilitadores — inscripción REUF | Referencia a REUF/LCE sin cita normativa verificable |
| plazo-checker | Facilitadores — formulario de comunicación | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker / participant-auditor | Facilitadores — acreditación externa (OS10, Directemar, MTT) | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | LCE — registro de asistencia | Referencia a REUF/LCE sin cita normativa verificable |
| plazo-checker | LCE — versión de escritorio | Referencia a REUF/LCE sin cita normativa verificable |
| plazo-checker | LCE — certificados de asistencia | Referencia a REUF/LCE sin cita normativa verificable |
| plazo-checker | Inscripción cursos — valores | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| plazo-checker | Inscripción cursos — toma de razón | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Datos del participante | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Confidencialidad de datos | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Asistencia mínima | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Registro de asistencia | Referencia a REUF/LCE sin cita normativa verificable |
| participant-auditor | Modalidades de curso | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Facilitador — REUF | Referencia a REUF/LCE sin cita normativa verificable |
| participant-auditor | Facilitador — acreditación para el curso | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Certificados | Referencia a REUF/LCE sin cita normativa verificable |
| participant-auditor | Contenido de certificado | Referencia a REUF/LCE sin cita normativa verificable |
| participant-auditor | Certificación sin asistencia mínima | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Cupos inscritos | No respaldada por fuente oficial; reemplazada por regla del supervisor |
| participant-auditor | Clasificación participantes | No respaldada por fuente oficial; reemplazada por regla del supervisor |

## Checklist para revisor legal

- [ ] Regla: Preliquidación de acción de capacitación — Confirmar contra: Resolución Exenta SENCE vigente sobre preliquidación de acciones de capacitación — Firmado por: ______
- [ ] Regla: Presentación de documentos de respaldo — Confirmar contra: Resolución Exenta SENCE vigente sobre rendición de documentos de respaldo — Firmado por: ______
- [ ] Regla: Emisión de Declaración Jurada OTEC — Confirmar contra: Resolución Exenta SENCE vigente sobre Declaración Jurada OTEC — Firmado por: ______
- [ ] Regla: Declaración Jurada de participantes — Confirmar contra: Resolución Exenta SENCE vigente sobre Declaración Jurada de participantes — Firmado por: ______
- [ ] Regla: Subsanación de observaciones en supervisión — Confirmar contra: Resolución Exenta SENCE vigente sobre supervisión y subsanación de observaciones — Firmado por: ______
- [ ] Regla: Validación de formato de RUT — Confirmar contra: Manual de Procedimientos SENCE / Ley N°19.518 y DS N°98 — Firmado por: ______
- [ ] Regla: Consistencia de asistencia libro vs. plataforma — Confirmar contra: Circular N°9 y Circular N°4 (Libro de Clases Electrónico) — Firmado por: ______
- [ ] Regla: Sesión de conectividad no registrada en e-learning — Confirmar contra: Circular N°9 y Circular N°4 (Libro de Clases Electrónico) — Firmado por: ______
