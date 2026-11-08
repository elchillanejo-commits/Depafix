#!/usr/bin/env python3
"""Bot de Telegram para DepaFix.

Conecta el chat de Telegram con el Agente CEO (`agente_ceo_final.py`) y,
cuando el mensaje trata de franquicia SENCE, responde directo con
`responder_franquicia` / `calcular_saldo_franquicia` para mayor velocidad
(sin pasar por el LLM ni por el RAG).

Requisitos en `.env`:
  - TELEGRAM_BOT_TOKEN   (obligatorio, token de BotFather)
  - TELEGRAM_CHAT_ID     (opcional pero recomendado: chat permitido)
  - EMPRESA_RUT          (opcional: RUT de la empresa para el saldo)

Uso:
  .venv/bin/python telegram_bot.py
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("telegram_bot")

ALLOWED_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
LIMITE_TELEGRAM = 4000  # Telegram admite 4096; dejamos margen

_ceo = {"llm": None, "cliente": None, "modelo": None}


def autorizado(update: Update) -> bool:
    """Si TELEGRAM_CHAT_ID está definido, solo ese chat puede usar el bot."""
    if not ALLOWED_CHAT_ID:
        return True
    chat = update.effective_chat
    ok = chat is not None and str(chat.id) == ALLOWED_CHAT_ID
    if not ok:
        log.warning("Mensaje de chat no autorizado: %s", chat.id if chat else "?")
    return ok


def _ceo_lazy():
    """Carga una sola vez LLM + Supabase + embeddings (pesado, ~30s)."""
    if _ceo["llm"] is None:
        from sentence_transformers import SentenceTransformer
        from agente_ceo_final import MODELO_EMBEDDINGS, crear_llm, crear_supabase

        log.info("Cargando LLM, Supabase y modelo de embeddings...")
        _ceo["llm"] = crear_llm()
        _ceo["cliente"] = crear_supabase()
        _ceo["modelo"] = SentenceTransformer(MODELO_EMBEDDINGS)
    return _ceo["llm"], _ceo["cliente"], _ceo["modelo"]


def _es_franquicia(texto: str) -> bool:
    try:
        from agente_ceo_final import es_consulta_franquicia

        return es_consulta_franquicia(texto)
    except Exception:
        bajo = texto.lower()
        return "franquicia" in bajo or "remanente" in bajo or "saldo" in bajo


def _respuesta_franquicia(texto: str) -> str:
    from agente_ceo_final import responder_franquicia

    return responder_franquicia(texto)


def _respuesta_ceo(texto: str) -> str:
    from agente_ceo_final import ejecutar

    llm, cliente, modelo = _ceo_lazy()
    respuesta, _ = ejecutar(texto, llm, cliente, modelo)
    return respuesta or "No obtuve respuesta del CEO."


async def responder_partido(update: Update, texto: str):
    """Divide la respuesta para no superar el límite de 4096 caracteres."""
    for i in range(0, len(texto), LIMITE_TELEGRAM):
        await update.message.reply_text(texto[i : i + LIMITE_TELEGRAM])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update):
        return
    await update.message.reply_text(
        "Hola, soy el Agente CEO de DepaFix.\n\n"
        "Pregúntame lo que quieras (construcción, marketing, legal, SENCE, ciber).\n"
        "Atajos:\n"
        "  /saldo            saldo de franquicia SENCE\n"
        "  /saldo 5000000    estimación con masa imponible de $5.000.000\n\n"
        "O escribe: 'cuánta franquicia SENCE me queda'."
    )


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update):
        return
    await update.effective_chat.send_action(ChatAction.TYPING)
    masa = " ".join(context.args or []).strip()
    pregunta = (
        f"cuánta franquicia me queda con sueldos {masa}"
        if masa
        else "cuánta franquicia SENCE me queda"
    )
    try:
        texto = await asyncio.to_thread(_respuesta_franquicia, pregunta)
    except Exception as error:
        log.exception("Error en /saldo")
        texto = f"No pude calcular el saldo SENCE: {error}"
    await responder_partido(update, texto)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update):
        return
    if not update.message or not update.message.text:
        return

    texto = update.message.text.strip()
    if not texto:
        return

    log.info("Mensaje recibido (chat %s)", update.effective_chat.id)
    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        if _es_franquicia(texto):
            # Atajo determinista: no pasa por el LLM ni el RAG.
            respuesta = await asyncio.to_thread(_respuesta_franquicia, texto)
        else:
            respuesta = await asyncio.to_thread(_respuesta_ceo, texto)
    except Exception as error:
        log.exception("Error procesando mensaje")
        respuesta = f"Ocurrió un error procesando tu pregunta: {error}"

    await responder_partido(update, respuesta)


def main():
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise SystemExit(
            "Falta TELEGRAM_BOT_TOKEN en el .env. "
            "Consigue el token con @BotFather (/newbot) y pégalo ahí."
        )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("saldo", cmd_saldo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log.info("Bot iniciado (polling). Chat permitido: %s", ALLOWED_CHAT_ID or "cualquiera")
    app.run_polling()


if __name__ == "__main__":
    main()
