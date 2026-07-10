# Skill: Generación de Presupuestos en PDF

## Objetivo
Generar presupuestos profesionales en formato PDF a partir de datos proporcionados por el usuario.

## Cuándo usar este skill
- Cuando el usuario pida "generar un presupuesto para [servicio]".
- Cuando el usuario solicite "cotización para [cliente]" o "presupuesto en PDF".

## Flujo de trabajo
1. **Recopilar información**:
   - Cliente (nombre, dirección)
   - Lista de trabajos (descripción, cantidad, precio unitario)
   - Mano de obra
   - Materiales (opcional)
   - Condiciones de pago

2. **Generar PDF**:
   - Ejecutar el script `generar_presupuesto.py` con los datos.

3. **Entrega**:
   - Informar al usuario la ubicación del PDF generado (`~/tmp/`).

## Estilo del documento
- Montos con formato chileno: $XXX.XXX (puntos de miles).
- Colores: azul marino (#0a1e2e), grises suaves.
