"""Logging profesional con rotación de archivos y notificaciones."""
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from config import LOGS_DIR, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL

LOG_FILE = LOGS_DIR / "bot.log"
ERROR_LOG_FILE = LOGS_DIR / "bot_error.log"


class TelegramHandler(logging.Handler):
    """Envía mensajes de ERROR+ a Telegram."""
    def __init__(self, token: str, chat_id: str, level=logging.ERROR):
        super().__init__(level)
        self.token = token
        self.chat_id = chat_id

    def emit(self, record):
        import requests
        msg = self.format(record)
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"[TelegramHandler] Fallo envío: {e}", file=sys.stderr)


class DiscordHandler(logging.Handler):
    """Envía mensajes de ERROR+ a Discord."""
    def __init__(self, webhook_url: str, level=logging.ERROR):
        super().__init__(level)
        self.webhook_url = webhook_url

    def emit(self, record):
        import requests
        msg = self.format(record)
        try:
            requests.post(self.webhook_url, json={"content": f"```\n{msg}\n```"}, timeout=5)
        except Exception:
            pass


def setup_logging(level=logging.INFO):
    """Configura logging con rotación y notificaciones."""
    formatter = logging.Formatter(
        "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Archivo general — rotación diaria, 30 días
    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Archivo solo errores — rotación por tamaño
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    # Consola
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    console.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = []
    root.addHandler(file_handler)
    root.addHandler(error_handler)
    root.addHandler(console)

    # Notificaciones externas
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        tg = TelegramHandler(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        tg.setFormatter(logging.Formatter("🚨 <b>ALERTA CRÍTICA</b>\n\n%(message)s"))
        tg.setLevel(logging.ERROR)
        root.addHandler(tg)

    if DISCORD_WEBHOOK_URL:
        dc = DiscordHandler(DISCORD_WEBHOOK_URL)
        dc.setLevel(logging.ERROR)
        root.addHandler(dc)

    logging.info("Logging inicializado correctamente.")
