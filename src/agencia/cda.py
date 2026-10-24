"""
cda.py — Playbooks de marketing CDA (Contexto, Diagnóstico, Acción).

Cada embudo tiene su propia narrativa, plan de 30 días, creatividades y
restricciones de cumplimiento. El motor solo consume estas piezas.
"""
from __future__ import annotations

from src.agencia.benchmarks import BenchmarkEmbudo
from src.agencia.esquemas import AccionCDA, CDA, Creatividad, Embudo, PlanItem


def construir_cda(embudo: Embudo, benchmark: BenchmarkEmbudo) -> CDA:
    if embudo == "B2C":
        return CDA(
            contexto=(
                "Gestalt Medical compite en el mercado chileno de diagnóstico genético "
                "y optimización clínica. El paciente B2C investiga en Instagram, "
                "Facebook y Google antes de cotizar; suele llegar con incertidumbre, "
                "síntomas o antecedentes familiares."
            ),
            diagnostico=(
                "La demanda existe, pero el paciente no distingue entre un test genético, "
                "un examen de laboratorio y una consulta de especialidad. Las fricciones "
                "principales son el precio, la cobertura, el proceso y el siguiente paso. "
                "Se requiere educación, prueba social y un CTA de baja fricción."
            ),
            accion=AccionCDA(
                oferta=(
                    "Evaluación genética inicial con orientación médica y una ruta clara "
                    "de próximos pasos."
                ),
                canales=[benchmark.canal_principal, *benchmark.canales_secundarios],
                mensajes=[
                    "¿Antecedentes familiares? Conoce tu ruta genética.",
                    "De la duda al siguiente paso: evaluación con especialistas.",
                    "Agenda una orientación genética y resuelve tus dudas.",
                ],
                landing=(
                    "Landing B2C con formulario corto, WhatsApp, explicación del proceso, "
                    "requisitos, precios referenciales y preguntas frecuentes."
                ),
                cta="Agenda tu evaluación genética",
                seguimiento=[
                    "Contacto humano dentro de 24 horas.",
                    "Recordatorio a las 48 horas si no hay respuesta.",
                    "Contenido educativo y prueba social.",
                    "Derivación a evaluación médica cuando corresponda.",
                ],
                kpis=benchmark.kpis_objetivo,
            ),
        )

    return CDA(
        contexto=(
            "Clínicas, laboratorios y centros médicos buscan mejorar tiempos de "
            "diagnóstico, trazabilidad y gestión asistencial. El decisor B2B es racional, "
            "con ciclo de venta largo y varios stakeholders involucrados."
        ),
        diagnostico=(
            "El dolor no es 'falta de marketing': es lista de espera, procesos manuales, "
            "baja visibilidad del pipeline clínico y dificultad para demostrar resultados. "
            "Se requiere una propuesta de piloto medible, no un anuncio genérico."
        ),
        accion=AccionCDA(
            oferta=(
                "Piloto de optimización clínica y genómica con métricas de tiempos, "
                "trazabilidad y experiencia del paciente."
            ),
            canales=[benchmark.canal_principal, *benchmark.canales_secundarios],
            mensajes=[
                "Reduce tiempos de respuesta clínica con un piloto medible.",
                "Trazabilidad genómica para tu clínica, de punta a punta.",
                "Agenda una demo de 30 minutos con el equipo clínico.",
            ],
            landing=(
                "Landing B2B con caso de negocio, agenda de demo, PDF descargable y "
                "formulario de calificación (cargo, tamaño de clínica, necesidad)."
            ),
            cta="Solicita una demo",
            seguimiento=[
                "Calificación del lead (cargo, institución, necesidad, timing).",
                "Demo de 30 minutos con especialista clínico-comercial.",
                "Piloto acotado de 30 días con métricas de éxito.",
                "Business case y propuesta de escalamiento.",
            ],
            kpis=benchmark.kpis_objetivo,
        ),
    )


def plan_30_dias(embudo: Embudo) -> list[PlanItem]:
    if embudo == "B2C":
        return [
            PlanItem(
                semana="Semana 1",
                accion="Tracking, píxel, WhatsApp y landing B2C; lanzamiento de lead ads.",
                kpi="CPL y tasa de contacto < 24 h.",
            ),
            PlanItem(
                semana="Semana 2",
                accion="Test A/B de creatividades educativas y testimoniales.",
                kpi="CTR y costo por lead calificado.",
            ),
            PlanItem(
                semana="Semana 3",
                accion="Retargeting de visitantes y lookalike de pacientes.",
                kpi="Tasa de agenda y recuperación de abandonos.",
            ),
            PlanItem(
                semana="Semana 4",
                accion="Escalar conjuntos ganadores y podar anuncios con CPL alto.",
                kpi="Leads por debajo del CPL objetivo.",
            ),
        ]

    return [
        PlanItem(
            semana="Semana 1",
            accion="Landing B2B, demo agendable y campaña de búsqueda por intención.",
            kpi="Demos agendadas y tasa de calificación.",
        ),
        PlanItem(
            semana="Semana 2",
            accion="LinkedIn ABM sobre cargos decisores y retargeting de visitantes.",
            kpi="Cobertura de cuentas objetivo y CTR B2B.",
        ),
        PlanItem(
            semana="Semana 3",
            accion="Caso de negocio, webinar y secuencia de seguimiento por email.",
            kpi="Reuniones de descubrimiento y pipeline generado.",
        ),
        PlanItem(
            semana="Semana 4",
            accion="Revisión de pipeline, ajuste de oferta y propuesta de piloto.",
            kpi="Pilotos cerrados y costo por oportunidad.",
        ),
    ]


def creatividades(embudo: Embudo) -> list[Creatividad]:
    if embudo == "B2C":
        return [
            Creatividad(
                formato="Video testimonial",
                titulo="Una duda que se resuelve con acompañamiento",
                cuerpo=(
                    "Conoce cómo es la evaluación genética paso a paso, con un equipo "
                    "que te orienta antes, durante y después."
                ),
                cta="Agenda tu orientación",
            ),
            Creatividad(
                formato="Carrusel educativo",
                titulo="¿Test genético, examen o consulta?",
                cuerpo=(
                    "Te explicamos las diferencias y cuál es el siguiente paso según tu caso."
                ),
                cta="Conoce tu ruta",
            ),
            Creatividad(
                formato="Reel corto",
                titulo="Antecedentes familiares: qué preguntar",
                cuerpo=(
                    "Tres preguntas para llevar a tu evaluación y aprovechar mejor la consulta."
                ),
                cta="Reserva tu evaluación",
            ),
        ]

    return [
        Creatividad(
            formato="Documento LinkedIn",
            titulo="Piloto de 30 días para optimizar la gestión clínica",
            cuerpo=(
                "Un caso de negocio con métricas de tiempos, trazabilidad y experiencia "
                "del paciente, sin prometer resultados antes de medir."
            ),
            cta="Descarga el caso",
        ),
        Creatividad(
            formato="Video demo",
            titulo="De la lista de espera al seguimiento trazable",
            cuerpo=(
                "Así funciona el piloto de optimización clínica en una clínica de tamaño medio."
            ),
            cta="Agenda una demo",
        ),
        Creatividad(
            formato="Carrusel B2B",
            titulo="Tres cuellos de botella que frenan tu clínica",
            cuerpo=(
                "Derivaciones, procesos manuales y falta de visibilidad del pipeline."
            ),
            cta="Hablemos de tu caso",
        ),
    ]


def reglas_cumplimiento(embudo: Embudo) -> list[str]:
    comunes = [
        "No prometer diagnósticos, curas ni resultados clínicos en los anuncios.",
        "Derivar siempre a una evaluación médica profesional.",
        "Tratar datos de salud como datos sensibles (Ley 19.628 y Ley 21.719).",
        "No usar imágenes de pacientes sin autorización escrita.",
        "Revisar las piezas con el responsable médico antes de publicar.",
    ]
    if embudo == "B2C":
        return [
            *comunes,
            "Consentimiento explícito y separado para marketing y para datos clínicos.",
        ]
    return [
        *comunes,
        "No publicar métricas de clínicas ni datos de pacientes sin acuerdo de confidencialidad.",
        "Evitar claims de reducción de costos o tiempos sin evidencia del piloto.",
    ]
