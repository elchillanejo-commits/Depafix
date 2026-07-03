# DEMO GESTALT — 20 minutos
URL: https://compressed-roulette-courtesy-lewis.trycloudflare.com
## Min 00-02: Apertura
Frase: "Este sistema controla toda la operación de Depafix en tiempo real..."
Mostrar /nav — explicar 4 agentes: Aquiles (presupuestos), Siegfried (licitaciones), Sancho (SII), Hermes (mercado)
## Min 02-07: Mercado Inmobiliario
Ir a /static/hermes.html
Filtrar: Providencia, precio_max 900000 → mostrar resultados reales
Frase: "447 propiedades monitoreadas automáticamente cada 6 horas..."
Mostrar cambios de precio detectados
## Min 07-12: Calculadora de Presupuesto
Ir a /static/medicion.html
Ingresar: cliente=Gestalt, living 25m2 + cocina 8m2 + baño 5m2, Providencia
Mostrar $1.367.584 cliente | desglose interno oculto
Clic "Ver presupuesto cliente" → presupuesto_cliente.html imprimible
Frase: "En 30 segundos el propietario recibe su cotización lista para firmar..."
## Min 12-15: Licitaciones
Mostrar alertas Siegfried: 4 licitaciones ALTO detectadas automáticamente
Frase: "El sistema detecta oportunidades en ChileCompra antes que la competencia..."
## Min 15-18: Gantt y progreso
Ir a /static/gantt.html → 80% completado en 2 semanas
## Min 18-20: Roadmap y preguntas
RESPUESTAS PREPARADAS:
1. ¿Cuánto cuesta? → VPS €4.5/mes + dominio $12/año = ~$7 USD/mes
2. ¿Si el laptop se apaga? → En producción corre en VPS 24/7
3. ¿Es seguro? → JWT auth, HTTPS, rate limiting, backups 3am
4. ¿Cuándo en nuestro dominio? → Esta semana con gestalt.cl
5. ¿Se conecta con nuestro sistema? → API REST, cualquier sistema puede integrarse
