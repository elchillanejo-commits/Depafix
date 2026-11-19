# 🧠 MISIÓN: AUDITORÍA DE VERACIDAD DEL RAG Y ARQUITECTURA DE OBREROS
**Rol:** CEO Informático & CTO Integral de DepaFix 3.0 (`CEO_INFORMATICO_MAESTRO.md`)

## 🎯 Objetivos
1. **Verificar Inserción Real en Supabase:**
   - Auditar la tabla de conocimiento (`knowledge_chunks_v2` o equivalente en Supabase) y cruzarla contra las carpetas de `/home/ibar/Documentos/Conocimiento` (`01_Tierra_Construccion` a `08_Trading_Cripto`).
   - Reportar conteo exacto de registros/chunks por dominio y detectar si falta alguna carpeta por ingestar o si hay dominios cruzados.
2. **Detector de "Humo" en Transcripciones:**
   - Inspeccionar una muestra aleatoria de chunks por dominio para verificar que el contenido sea conocimiento técnico/accionable y no relleno crudo de YouTube.
3. **Prueba Real de Flujo (Profesor + Auditor):**
   - Ejecutar una consulta real vía el motor RAG (`/api/v1/rag/buscar` o script directo) para cada elemento activo y mostrar la calidad de la respuesta recuperada.
4. **Propuesta de Estándar "Obrero Skill":**
   - Definir la plantilla base (`SKILL_OBRERO_TEMPLATE.md`) para crear oficios operativos ligeros (ej. `obrero-inteligencia-almacenes`) que capturen datos en terreno y alimenten a los Profesores y al CEO Informático.

## ⚠️ Reglas
- Solo lectura y diagnóstico en Supabase (no borrar ni duplicar chunks).
- No ejecutar `git push`.
- Cerrar siempre con: `ESTÁS EN EL CHAT DEPAFIX 3.0`
