# 🎓 MISIÓN QUIRÚRGICA: CIERRE DE BUG-032 (ELEMENTO SENCE / OTEC)
**Rol:** CEO Informático & CTO Integral de DepaFix 3.0 (bajo directrices de `CEO_INFORMATICO_MAESTRO.md`)
**Alcance del Elemento:** SENCE = OTEC = Capacitaciones (gestión de alumnos, educación, cursos presenciales y online sincrónicos/asincrónicos, códigos SENCE y franquicia tributaria).

## 🎯 Objetivo
Resolver de forma definitiva `BUG-032` en el CLI / módulo del motor SENCE / OTEC sin afectar los demás elementos ni romper la API en producción.

## 📋 Pasos de Ejecución
1. **Diagnóstico:** Leer la entrada exacta de `BUG-032` en `BUGS.md` e inspeccionar el script o módulo del motor SENCE / OTEC correspondiente.
2. **Corrección Quirúrgica:**
   - Corregir el fallo del CLI / cálculo asegurando precisión financiera con `Decimal` + `ROUND_HALF_UP` para valor hora SENCE, franquicia tributaria (100%, 50%, 15% según tramo), monto imputable y copago, soportando modalidades presenciales y online.
   - Garantizar cero valores hardcodeados indebidos y manejo limpio de argumentos/errores (`exit 1` controlado ante entradas inválidas).
3. **Validación:**
   - Ejecutar `python3 -m compileall` sobre el módulo modificado.
   - Correr pruebas reales por CLI con casos válidos (ej. cursos online y presenciales de 20h y 30h) y casos borde/inválidos.
4. **Documentación:**
   - Marcar `BUG-032` como **Resuelto** en `BUGS.md` detallando causa raíz, solución y evidencia de prueba.
   - No ejecutar `git push` (dejar listo en working tree para revisión y commit).
